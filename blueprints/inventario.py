import csv
import io
import os
from datetime import date, timedelta

from flask import Blueprint, Response, jsonify, request, send_file
from werkzeug.utils import secure_filename
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from auth import require_api_key
from services.inventario_service import (
    obtener_almacenes,
    obtener_productos_inventario,
    obtener_reporte_inventario,
    obtener_resumen_inventario,
)
from services.entradas_service import obtener_todas_entradas_inventario
from services.background_cache import get_cached_inventario_resumen, get_cached_inventario_reporte

inventario_bp = Blueprint("inventario", __name__, url_prefix="/api/inventario")

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
EXCEL_GUARDADO = os.path.join(UPLOADS_DIR, "inventario_excel.xlsx")

os.makedirs(UPLOADS_DIR, exist_ok=True)

def _filtros():
    almacen_id = request.args.get("almacen_id", type=int)
    producto = request.args.get("producto", default="", type=str)
    return almacen_id, producto

def _reporte_completo(almacen_id, producto):
    return obtener_productos_inventario(almacen_id, producto)

def _fechas_entradas():
    desde = request.args.get("desde", default=(date.today() - timedelta(days=30)).isoformat())
    hasta = request.args.get("hasta", default=date.today().isoformat())
    date.fromisoformat(desde)
    date.fromisoformat(hasta)
    if desde > hasta:
        raise ValueError("La fecha inicial no puede ser posterior a la fecha final.")
    return desde, hasta

@inventario_bp.route("/almacenes", methods=["GET"])
@require_api_key
def almacenes():
    try:
        return jsonify({"almacenes": obtener_almacenes()})
    except Exception as error:
        return jsonify({"error": str(error)}), 500

@inventario_bp.route("/reporte", methods=["GET"])
@require_api_key
def reporte():
    try:
        almacen_id, producto = _filtros()
        pagina = request.args.get("pagina", default=1, type=int)
        por_pagina = request.args.get("por_pagina", default=100, type=int)
        
        # Intentar obtener del caché en memoria (hilo en segundo plano)
        cached_data = get_cached_inventario_reporte(almacen_id, producto)
        if cached_data is not None:
            total = len(cached_data)
            inicio = (pagina - 1) * por_pagina
            fin = inicio + por_pagina
            return jsonify({
                "total": total,
                "pagina": pagina,
                "por_pagina": por_pagina,
                "paginas": (total + por_pagina - 1) // por_pagina,
                "productos": cached_data[inicio:fin]
            })
            
        # Si no hay caché o los filtros no aplican, consultar a Odoo
        return jsonify(obtener_reporte_inventario(almacen_id, producto, pagina, por_pagina))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        return jsonify({"error": str(error)}), 500

@inventario_bp.route("/resumen", methods=["GET"])
@require_api_key
def resumen():
    try:
        almacen_id, producto = _filtros()
        
        # Intentar obtener del caché en memoria
        cached_resumen = get_cached_inventario_resumen()
        if cached_resumen is not None and not almacen_id and not producto:
            return jsonify(cached_resumen)
            
        return jsonify(obtener_resumen_inventario(almacen_id, producto))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        return jsonify({"error": str(error)}), 500

@inventario_bp.route("/entradas", methods=["GET"])
@require_api_key
def entradas():
    try:
        desde, hasta = _fechas_entradas()
        return jsonify({"desde": desde, "hasta": hasta, "entradas": obtener_todas_entradas_inventario(desde, hasta)})
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        return jsonify({"error": str(error)}), 500

@inventario_bp.route("/entradas.xlsx", methods=["GET"])
@require_api_key
def entradas_xlsx():
    try:
        desde, hasta = _fechas_entradas()
        entradas = obtener_todas_entradas_inventario(desde, hasta)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        return jsonify({"error": str(error)}), 500

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Entradas"
    encabezados = ["Fecha", "Proveedor", "Factura", "Código", "Descripción", "Cantidad", "Unitario", "Total"]
    estilo_encabezado = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
    for columna, texto in enumerate(encabezados, start=1):
        celda = hoja.cell(row=1, column=columna, value=texto)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = estilo_encabezado
        celda.alignment = Alignment(horizontal="center")

    for fila, entrada in enumerate(entradas, start=2):
        valores = [
            entrada.get("fecha"), entrada.get("proveedor"), entrada.get("factura"), entrada.get("codigo"),
            entrada.get("producto"), entrada.get("cantidad"), entrada.get("costo_unitario"), entrada.get("valor_total"),
        ]
        for columna, valor in enumerate(valores, start=1):
            hoja.cell(row=fila, column=columna, value=valor)
        hoja.cell(row=fila, column=6).number_format = "#,##0.00"
        for columna in (7, 8):
            hoja.cell(row=fila, column=columna).number_format = "$#,##0.00"

    for columna, ancho in {"A": 14, "B": 22, "C": 18, "D": 18, "E": 42, "F": 14, "G": 16, "H": 16}.items():
        hoja.column_dimensions[columna].width = ancho
    hoja.freeze_panes = "A2"

    buffer = io.BytesIO()
    libro.save(buffer)
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"entradas_{desde}_a_{hasta}.xlsx",
    )

@inventario_bp.route("/reporte.csv", methods=["GET"])
@require_api_key
def reporte_csv():
    try:
        productos = _reporte_completo(*_filtros())
        salida = io.StringIO()
        columnas = ["sku", "producto", "categoria", "unidad_medida", "existencia", "reservado", "disponible", "costo_unitario", "precio_venta", "valor_inventario"]
        writer = csv.DictWriter(salida, fieldnames=columnas)
        writer.writeheader()
        writer.writerows(productos)
        return Response(salida.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=inventario.csv"})
    except Exception as error:
        return jsonify({"error": str(error)}), 500

@inventario_bp.route("/reporte.xlsx", methods=["GET"])
@require_api_key
def reporte_xlsx():
    try:
        productos = _reporte_completo(*_filtros())
    except Exception as error:
        return jsonify({"error": str(error)}), 500

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Inventario"
    encabezados = ["SKU", "Producto", "Categoría", "Unidad", "Existencia", "Reservado", "Disponible", "Costo unitario", "Precio venta", "Valor inventario"]
    estilo_encabezado = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
    for columna, texto in enumerate(encabezados, start=1):
        celda = hoja.cell(row=1, column=columna, value=texto)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = estilo_encabezado
        celda.alignment = Alignment(horizontal="center")

    for fila, producto in enumerate(productos, start=2):
        valores = [producto[campo] for campo in ["sku", "producto", "categoria", "unidad_medida", "existencia", "reservado", "disponible", "costo_unitario", "precio_venta", "valor_inventario"]]
        for columna, valor in enumerate(valores, start=1):
            hoja.cell(row=fila, column=columna, value=valor)
        for columna in (8, 9, 10):
            hoja.cell(row=fila, column=columna).number_format = "$#,##0.00"

    for columna, ancho in {"A": 18, "B": 38, "C": 25, "D": 14, "E": 13, "F": 13, "G": 13, "H": 16, "I": 16, "J": 18}.items():
        hoja.column_dimensions[columna].width = ancho
    hoja.freeze_panes = "A2"

    buffer = io.BytesIO()
    libro.save(buffer)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name="inventario.xlsx")


import glob
from datetime import datetime, timedelta

MAX_EXCEL_GUARDADOS = 15
UN_ANIO = timedelta(days=365)


def _listar_excels():
    """Retorna lista de archivos Excel guardados, ordenados del más reciente al más antiguo."""
    archivos = glob.glob(os.path.join(UPLOADS_DIR, "inventario_*.xlsx"))
    archivos.sort(reverse=True)
    return archivos


def _limpiar_excels():
    """Elimina archivos con más de 1 año o que excedan el máximo permitido."""
    archivos = _listar_excels()
    limite_fecha = datetime.now() - UN_ANIO
    for ruta in archivos:
        nombre = os.path.basename(ruta)
        # Intentar extraer fecha del nombre: inventario_YYYY-MM-DD_HHMMSS.xlsx
        try:
            parte_fecha = nombre.replace("inventario_", "").replace(".xlsx", "")
            fecha_archivo = datetime.strptime(parte_fecha, "%Y-%m-%d_%H%M%S")
            if fecha_archivo < limite_fecha:
                os.remove(ruta)
        except (ValueError, OSError):
            pass

    # Volver a listar y borrar los que excedan el máximo
    archivos = _listar_excels()
    for ruta in archivos[MAX_EXCEL_GUARDADOS:]:
        try:
            os.remove(ruta)
        except OSError:
            pass


@inventario_bp.route("/subir-excel", methods=["POST"])
@require_api_key
def subir_excel():
    """Guarda el Excel con timestamp en el historial del servidor."""
    if "file" not in request.files:
        return jsonify({"error": "No se envió ningún archivo."}), 400
    archivo = request.files["file"]
    if not archivo.filename or not archivo.filename.lower().endswith((".xlsx", ".xls")):
        return jsonify({"error": "El archivo debe ser .xlsx o .xls"}), 400
    try:
        sello = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        nombre_destino = f"inventario_{sello}.xlsx"
        ruta_destino = os.path.join(UPLOADS_DIR, nombre_destino)
        archivo.save(ruta_destino)
        _limpiar_excels()
        return jsonify({"ok": True, "nombre": nombre_destino, "mensaje": "Excel guardado en el servidor."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@inventario_bp.route("/excel-guardado", methods=["GET"])
@require_api_key
def excel_guardado():
    """Devuelve el Excel más reciente (o el especificado con ?archivo=nombre)."""
    nombre = request.args.get("archivo", "")
    if nombre:
        ruta = os.path.join(UPLOADS_DIR, os.path.basename(nombre))
    else:
        archivos = _listar_excels()
        if not archivos:
            return jsonify({"error": "No hay Excel guardado."}), 404
        ruta = archivos[0]

    if not os.path.exists(ruta):
        return jsonify({"error": "Archivo no encontrado."}), 404

    response = send_file(
        ruta,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=False,
        download_name=os.path.basename(ruta)
    )
    response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
    response.headers["Content-Disposition"] = f'inline; filename="{os.path.basename(ruta)}"'
    return response


@inventario_bp.route("/excel-historial", methods=["GET"])
@require_api_key
def excel_historial():
    """Devuelve la lista de Excels guardados en el servidor."""
    archivos = _listar_excels()
    resultado = []
    for ruta in archivos:
        nombre = os.path.basename(ruta)
        try:
            parte = nombre.replace("inventario_", "").replace(".xlsx", "")
            fecha = datetime.strptime(parte, "%Y-%m-%d_%H%M%S")
            fecha_str = fecha.strftime("%d/%m/%Y %H:%M")
        except ValueError:
            fecha_str = "—"
        resultado.append({
            "nombre": nombre,
            "fecha": fecha_str,
            "tamano_kb": round(os.path.getsize(ruta) / 1024, 1)
        })
    return jsonify({"archivos": resultado})