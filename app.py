
from flask import Flask, jsonify, redirect, render_template, url_for
from blueprints.dashboard import dashboard_bp
from blueprints.ventas import ventas_bp
from blueprints.kardex import kardex_bp
from blueprints.inventario import inventario_bp
# Rutas de Inventario
from Rutas.inventario import Invetario_ruta
from config import Config

app = Flask(__name__)
app.register_blueprint(dashboard_bp)
app.register_blueprint(ventas_bp)
app.register_blueprint(kardex_bp)
app.register_blueprint(inventario_bp)


@app.route("/")
def index():
    return render_template("facturacion.html", title="Reporte de Ventas", api_key=Config.API_KEY)

@app.route("/kardex")
def kardex():
    return render_template("kardex.html", title="Kardex de Productos", api_key=Config.API_KEY)


@app.route("/entradas-productos")
def entradas_productos():
    """Pantalla para consultar las entradas de productos de Odoo."""
    return render_template("api.html", title="Panel API", api_key=Config.API_KEY)


@app.route("/api")
def api_info():
    """Ruta anterior del panel; se conserva para enlaces existentes."""
    return redirect(url_for("entradas_productos"))


@app.route("/api/info")
def api_estado():
    """Información técnica de la API para clientes que consumen JSON."""
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
            "GET /api/kardex?desde=YYYY-MM-DD&hasta=YYYY-MM-DD&codigo=(opcional)",
            "GET /api/kardex.xlsx?desde=YYYY-MM-DD&hasta=YYYY-MM-DD&codigo=(opcional)",
            "GET /api/inventario/entradas?desde=YYYY-MM-DD&hasta=YYYY-MM-DD",
        ],
    })

@app.route("/inventario")
def inventario():
    return Invetario_ruta()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
