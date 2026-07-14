from flask import Flask, jsonify, render_template
from blueprints.dashboard import dashboard_bp
from blueprints.ventas import ventas_bp
from blueprints.inventario import inventario_bp

# Rutas de Inventario
from Rutas.inventario import Invetario_ruta


# Ruras no puestas
from config import Config

app = Flask(__name__)
app.register_blueprint(dashboard_bp)
app.register_blueprint(ventas_bp)
app.register_blueprint(inventario_bp)



@app.route("/")
def index():
    return render_template("index.html", api_key=Config.API_KEY)


@app.route("/api")
def api_info():
    return jsonify({
        "status": "ok",
        "mensaje": "API contable de Odoo funcionando",
        "endpoints": [
            "GET /api/dashboard/resumen",
            "GET /api/dashboard/facturas-pendientes",
            "GET /api/dashboard/facturas-pendientes.csv",
            "GET /api/dashboard/gastos-pendientes",
            "GET /api/ventas/reporte?desde=YYYY-MM-DD&hasta=YYYY-MM-DD",
            "GET /api/ventas/reporte.xlsx?desde=YYYY-MM-DD&hasta=YYYY-MM-DD",
            "GET /api/inventario/resumen?almacen_id=ID",
            "GET /api/inventario/reporte?almacen_id=ID&producto=TEXTO",
            "GET /api/inventario/reporte.csv",
            "GET /api/inventario/reporte.xlsx",
        ],
    })

@app.route("/inventario")
def inventario():
    return Invetario_ruta()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
