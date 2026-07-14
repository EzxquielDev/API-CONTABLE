"""Consultas de inventario actual contra Odoo."""

from odoo_client import get_odoo_client


def _many2one_name(value):
    """Obtiene el texto de un campo many2one que devuelve XML-RPC."""
    return value[1] if value else ""


def obtener_almacenes():
    """Almacenes disponibles para filtrar el reporte."""
    odoo = get_odoo_client()
    almacenes = odoo.search_read(
        "stock.warehouse",
        domain=[],
        fields=["name", "code"],
        order="name asc",
        limit=False,
    )
    return [
        {"id": almacen["id"], "nombre": almacen["name"], "codigo": almacen.get("code", "")}
        for almacen in almacenes
    ]


def _dominio_cuantos(almacen_id=None, producto=None):
    """Solo incluye stock físico que pertenece a ubicaciones internas."""
    domain = [["location_id.usage", "=", "internal"]]

    if almacen_id:
        odoo = get_odoo_client()
        almacen = odoo.search_read(
            "stock.warehouse",
            domain=[["id", "=", almacen_id]],
            fields=["view_location_id"],
            limit=1,
        )
        if not almacen:
            raise ValueError("El almacén indicado no existe.")
        vista_almacen = almacen[0].get("view_location_id")
        if not vista_almacen:
            raise ValueError("El almacén indicado no tiene ubicación raíz configurada.")
        domain.append(["location_id", "child_of", vista_almacen[0]])

    if producto:
        texto = producto.strip()
        if texto:
            # Incluye búsqueda por nombre y por referencia interna (SKU).
            domain.extend(["|", ["product_id.name", "ilike", texto], ["product_id.default_code", "ilike", texto]])

    return domain


def _datos_producto(producto_ids):
    if not producto_ids:
        return {}

    odoo = get_odoo_client()
    productos = odoo.search_read(
        "product.product",
        domain=[["id", "in", producto_ids]],
        fields=["display_name", "default_code", "categ_id", "uom_id", "standard_price", "list_price"],
        limit=False,
    )
    return {producto["id"]: producto for producto in productos}


def obtener_reporte_inventario(almacen_id=None, producto=None, pagina=1, por_pagina=100):
    """Existencia actual consolidada por producto.

    ``stock.quant`` es la fuente de verdad del inventario actual. Se excluyen
    ubicaciones de proveedores, clientes, tránsito e inventario virtual.
    """
    if pagina < 1 or por_pagina < 1 or por_pagina > 500:
        raise ValueError("Los parámetros de paginación son inválidos.")

    domain = _dominio_cuantos(almacen_id=almacen_id, producto=producto)
    odoo = get_odoo_client()
    grupos = odoo.read_group(
        "stock.quant",
        domain=domain,
        fields=["product_id", "quantity:sum", "reserved_quantity:sum"],
        groupby=["product_id"],
        orderby="product_id",
        offset=(pagina - 1) * por_pagina,
        limit=por_pagina,
        lazy=False,
    )

    # read_group puede devolver grupos de producto vacío en bases con datos
    # incompletos; no representan una ficha inventariable.
    grupos = [grupo for grupo in grupos if grupo.get("product_id")]
    producto_ids = [grupo["product_id"][0] for grupo in grupos]
    productos = _datos_producto(producto_ids)

    detalle = []
    for grupo in grupos:
        producto_id = grupo["product_id"][0]
        ficha = productos.get(producto_id)
        if not ficha:
            continue

        existencia = float(grupo.get("quantity", 0) or 0)
        reservado = float(grupo.get("reserved_quantity", 0) or 0)
        disponible = existencia - reservado
        costo = float(ficha.get("standard_price", 0) or 0)

        detalle.append({
            "producto_id": producto_id,
            "producto": ficha.get("display_name") or _many2one_name(grupo["product_id"]),
            "sku": ficha.get("default_code") or "",
            "categoria": _many2one_name(ficha.get("categ_id")),
            "unidad_medida": _many2one_name(ficha.get("uom_id")),
            "existencia": round(existencia, 2),
            "reservado": round(reservado, 2),
            "disponible": round(disponible, 2),
            "costo_unitario": round(costo, 2),
            "precio_venta": round(float(ficha.get("list_price", 0) or 0), 2),
            "valor_inventario": round(existencia * costo, 2),
        })

    return {
        "pagina": pagina,
        "por_pagina": por_pagina,
        "almacen_id": almacen_id,
        "producto_filtro": producto or "",
        "productos": detalle,
    }


def obtener_productos_inventario(almacen_id=None, producto=None):
    """Obtiene el detalle completo en bloques, útil para la vista y exportaciones."""
    productos = []
    pagina = 1
    while True:
        bloque = obtener_reporte_inventario(
            almacen_id=almacen_id,
            producto=producto,
            pagina=pagina,
            por_pagina=500,
        )["productos"]
        productos.extend(bloque)
        if len(bloque) < 500:
            return productos
        pagina += 1


def obtener_resumen_inventario(almacen_id=None, producto=None):
    """Totales globales del mismo universo del reporte detallado."""
    # Se obtienen todos los productos para no aplicar paginación a los totales.
    productos = obtener_productos_inventario(almacen_id=almacen_id, producto=producto)

    return {
        "almacen_id": almacen_id,
        "cantidad_productos": len(productos),
        "existencia_total": round(sum(producto["existencia"] for producto in productos), 2),
        "reservado_total": round(sum(producto["reservado"] for producto in productos), 2),
        "disponible_total": round(sum(producto["disponible"] for producto in productos), 2),
        "valor_inventario_total": round(sum(producto["valor_inventario"] for producto in productos), 2),
    }
