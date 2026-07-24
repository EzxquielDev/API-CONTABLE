import os
import ssl
import xmlrpc.client
from dotenv import load_dotenv

# ==========================================
# CONFIGURACIÓN DE CONEXIÓN A ODOO
# ==========================================
load_dotenv()

ODOO_URL = os.getenv("ODOO_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USER = os.getenv("ODOO_USER")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD")
ODOO_SSL_UNVERIFIED = os.getenv("ODOO_SSL_UNVERIFIED", "false").lower() == "true"

import time

_cache_inventario = {}
CACHE_TTL = 120  # 2 minutos en segundos


def _get_connection():
    """Autentica y devuelve el objeto models y el uid para hacer consultas."""
    if not all([ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD]):
        raise Exception("Faltan credenciales en el archivo .env.")
        
    ctx = None
    if ODOO_SSL_UNVERIFIED:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common', context=ctx)
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
    
    if not uid:
        raise Exception("Fallo la autenticación con Odoo. Verifica tus credenciales.")
    
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object', context=ctx)
    return models, uid


def _m2o_name(field_data, default="N/A"):
    """Extrae el nombre de un campo Many2one de Odoo (que viene como [id, 'Nombre'])."""
    if isinstance(field_data, (list, tuple)) and len(field_data) == 2:
        return field_data[1]
    return default


# ==========================================
# SERVICIOS DE INVENTARIO
# ==========================================

def obtener_almacenes():
    """Obtiene todas las ubicaciones de tipo interno (almacenes físicos)."""
    models, uid = _get_connection()
    domain = [('usage', '=', 'internal')]
    fields = ['id', 'display_name']
    
    ubicaciones = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD, 'stock.location', 'search_read',
        [domain], {'fields': fields, 'order': 'display_name ASC'}
    )
    
    return [{"id": u["id"], "nombre": u["display_name"]} for u in ubicaciones]


def _construir_dominio_productos(producto):
    """Construye el dominio base para buscar productos almacenables."""
    domain = [('type', '=', 'product')] 
    if producto:
        domain.append(('name', 'ilike', producto))
    return domain


def _mapear_producto(p):
    """Mapea el diccionario de Odoo al formato que espera la API/Excel."""
    existencia = float(p.get('qty_available', 0.0))
    disponible = float(p.get('free_qty', 0.0))
    reservado = existencia - disponible
    costo = float(p.get('standard_price', 0.0))
    
    return {
        "sku": p.get('default_code') or "Sin SKU",
        "producto": p.get('name'),
        "categoria": _m2o_name(p.get('categ_id')),
        "unidad_medida": _m2o_name(p.get('uom_id')),
        "existencia": existencia,
        "reservado": reservado if reservado > 0 else 0.0,
        "disponible": disponible,
        "costo_unitario": costo,
        "precio_venta": float(p.get('list_price', 0.0)),
        "valor_inventario": existencia * costo
    }


def obtener_productos_inventario(almacen_id=None, producto=""):
    """
    Obtiene TODOS los productos desde Odoo (o filtrados) con sus existencias.
    Implementa caché en memoria de 2 minutos (120s) por combinación de filtros.
    """
    clave_cache = f"{almacen_id}_{producto}"
    ahora = time.time()
    
    if clave_cache in _cache_inventario:
        datos, timestamp = _cache_inventario[clave_cache]
        if ahora - timestamp < CACHE_TTL:
            return datos

    models, uid = _get_connection()
    domain = _construir_dominio_productos(producto)
    context = {'location': almacen_id} if almacen_id else {}
    
    campos = ['default_code', 'name', 'categ_id', 'uom_id', 'qty_available', 'free_qty', 'standard_price', 'list_price']
    
    productos_odoo = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD, 'product.product', 'search_read',
        [domain], {'fields': campos, 'context': context}
    )
    
    resultado = [_mapear_producto(p) for p in productos_odoo]
    
    # Guardar en caché
    _cache_inventario[clave_cache] = (resultado, ahora)
    
    return resultado


def obtener_reporte_inventario(almacen_id, producto, pagina=1, por_pagina=100):
    """Obtiene los productos con paginación para la vista de la UI."""
    clave_cache = f"reporte_{almacen_id}_{producto}_{pagina}_{por_pagina}"
    ahora = time.time()
    
    if clave_cache in _cache_inventario:
        datos, timestamp = _cache_inventario[clave_cache]
        if ahora - timestamp < CACHE_TTL:
            return datos

    models, uid = _get_connection()
    domain = _construir_dominio_productos(producto)
    context = {'location': almacen_id} if almacen_id else {}
    
    total_registros = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD, 'product.product', 'search_count', [domain]
    )
    
    campos = ['default_code', 'name', 'categ_id', 'uom_id', 'qty_available', 'free_qty', 'standard_price', 'list_price']
    limit = por_pagina
    offset = (pagina - 1) * por_pagina
    
    productos_odoo = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD, 'product.product', 'search_read',
        [domain], {'fields': campos, 'context': context, 'limit': limit, 'offset': offset}
    )
    
    resultado = {
        "total": total_registros,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "paginas": (total_registros + por_pagina - 1) // por_pagina,
        "productos": [_mapear_producto(p) for p in productos_odoo]
    }
    
    _cache_inventario[clave_cache] = (resultado, ahora)
    return resultado


def obtener_resumen_inventario(almacen_id, producto):
    """Calcula los totales (SKUs, piezas y valor monetario) del inventario."""
    productos = obtener_productos_inventario(almacen_id, producto)
    
    total_skus = len(productos)
    total_piezas = sum(p['existencia'] for p in productos)
    disponible_total = sum(p['disponible'] for p in productos)
    reservado_total = sum(p['reservado'] for p in productos)
    valor_total = sum(p['valor_inventario'] for p in productos)
    
    return {
        "cantidad_productos": total_skus,
        "existencia_total": total_piezas,
        "disponible_total": disponible_total,
        "reservado_total": reservado_total,
        "valor_inventario_total": valor_total
    }


# (Las entradas de compras se movieron a services/entradas_service.py)
