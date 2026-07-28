import threading
import time
import logging
from datetime import datetime
from services.inventario_service import obtener_resumen_inventario, obtener_productos_inventario

logger = logging.getLogger(__name__)

CACHE = {
    'inventario_resumen': None,
    'inventario_reporte': None,
    'last_updated': None
}

def update_cache():
    logger.info("[Background Cache] Iniciando actualización de caché de Odoo en hilo secundario...")
    try:
        # Resumen de inventario
        resumen = obtener_resumen_inventario(None, "")
        CACHE['inventario_resumen'] = resumen
        
        # Reporte completo de inventario (sin filtros)
        reporte = obtener_productos_inventario(None, "")
        CACHE['inventario_reporte'] = reporte
        
        CACHE['last_updated'] = datetime.now()
        logger.info("[Background Cache] Caché actualizado exitosamente de manera asíncrona.")
    except Exception as e:
        logger.error(f"[Background Cache] Error actualizando caché: {e}")

def cache_updater_loop(interval_minutes):
    # Pausa inicial pequeña para dejar que Flask arranque sin bloqueos bruscos
    time.sleep(2)
    while True:
        update_cache()
        time.sleep(interval_minutes * 60)

def start_background_cache(interval_minutes=5):
    thread = threading.Thread(target=cache_updater_loop, args=(interval_minutes,), daemon=True)
    thread.start()
    logger.info(f"[Background Cache] Hilo de caché iniciado (frecuencia: {interval_minutes} minutos).")

def get_cached_inventario_resumen():
    return CACHE.get('inventario_resumen')

def get_cached_inventario_reporte(almacen_id, producto):
    # Si no hay caché disponible aún
    if not CACHE.get('inventario_reporte'):
        return None
        
    # Si no hay filtros, devolver todo
    if not almacen_id and not producto:
        return CACHE['inventario_reporte']
    
    # Si filtran por producto pero no por almacén, filtramos en memoria
    if producto and not almacen_id:
        prod_lower = producto.lower()
        filtrado = []
        for p in CACHE['inventario_reporte']:
            nombre = p.get('producto', '').lower()
            sku = p.get('sku', '') or ''
            if prod_lower in nombre or prod_lower in sku.lower():
                filtrado.append(p)
        return filtrado
        
    return None
