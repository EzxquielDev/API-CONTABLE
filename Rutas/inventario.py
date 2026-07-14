from flask import render_template, request
from config import Config
from services.inventario_service import (
    obtener_almacenes,
    obtener_productos_inventario,
    obtener_resumen_inventario,
)

def Invetario_ruta():
    almacen_id = request.args.get("almacen_id", type=int)
    producto_filtro = request.args.get("producto", default="", type=str).strip()
    contexto = {
        "title": "Inventario",
        "api_key": Config.API_KEY,
        "almacenes": [],
        "almacen_id": almacen_id,
        "producto_filtro": producto_filtro,
        "productos": [],
        "resumen": None,
        "error": None,
    }
    try:
        contexto["almacenes"] = obtener_almacenes()
        contexto["productos"] = obtener_productos_inventario(almacen_id, producto_filtro)
        contexto["resumen"] = obtener_resumen_inventario(almacen_id, producto_filtro)
    except Exception as error:
        contexto["error"] = str(error)

    return render_template("inventario.html", **contexto)
