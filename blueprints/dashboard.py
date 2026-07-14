import csv
import io
from flask import Blueprint, jsonify, Response
from auth import require_api_key
from services.dashboard_service import obtener_resumen_financiero, obtener_facturas_pendientes

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@dashboard_bp.route("/resumen", methods=["GET"])
@require_api_key
def resumen():
    """Resumen financiero del mes actual. Ideal para Google Sheets (Apps Script) o Power Query."""
    try:
        data = obtener_resumen_financiero()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/facturas-pendientes", methods=["GET"])
@require_api_key
def facturas_pendientes():
    """Facturas de cliente con saldo pendiente, en JSON."""
    try:
        data = obtener_facturas_pendientes(tipo="cliente")
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/facturas-pendientes.csv", methods=["GET"])
@require_api_key
def facturas_pendientes_csv():
    """Mismo contenido que arriba, pero en CSV listo para abrir/pegar en Excel."""
    try:
        data = obtener_facturas_pendientes(tipo="cliente")

        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=facturas_pendientes.csv"},
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/gastos-pendientes", methods=["GET"])
@require_api_key
def gastos_pendientes():
    """Facturas de proveedor con saldo pendiente, en JSON."""
    try:
        data = obtener_facturas_pendientes(tipo="proveedor")
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
