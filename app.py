from flask import Flask, jsonify, redirect, render_template, url_for

# =========================
# IMPORTACIONES DE BLUEPRINTS
# =========================
from blueprints.dashboard import dashboard_bp
from blueprints.ventas import ventas_bp
from blueprints.kardex import kardex_bp
from blueprints.inventario import inventario_bp
from blueprints.libro_diario import libro_diario_bp
from blueprints.chat import chat_bp

from config import Config
from auth import require_api_key

# =========================
# IMPORTACIONES DE AUTENTICACIÓN (Faltaban)
# =========================
from odoo_auth import register_odoo_auth_routes
from odoo_logout import register_odoo_logout_routes
from services.background_cache import start_background_cache


app = Flask(__name__)

# Iniciar caché en segundo plano (intervalo de 5 minutos)
start_background_cache(interval_minutes=5)


# =========================
# REGISTRO DE BLUEPRINTS
# =========================
app.register_blueprint(dashboard_bp)
app.register_blueprint(ventas_bp)
app.register_blueprint(kardex_bp)
app.register_blueprint(inventario_bp)
app.register_blueprint(libro_diario_bp)
app.register_blueprint(chat_bp)


# =========================
# RUTAS WEB / PÁGINAS (Frontend)
# =========================

@app.route("/")
def index():
    """Pantalla principal (Dashboard de Negocio)."""
    return render_template(
        "dashboard_grafico.html",
        title="Dashboard",
        api_key=Config.API_KEY
    )


@app.route("/ventas")
def ventas_ui():
    """Pantalla de Ventas (antes facturacion)."""
    return render_template(
        "facturacion.html",
        title="Ventas",
        api_key=Config.API_KEY
    )


@app.route("/kardex")
def kardex():
    return render_template(
        "kardex.html",
        title="Kardex",
        api_key=Config.API_KEY
    )


@app.route("/login")
def login():
    return render_template(
        "odoo_login.html",
        title="Login",
        api_key=Config.API_KEY
    )


@app.route("/entradas-productos")
def entradas_productos():
    """Pantalla para consultar las entradas de productos de Odoo."""
    return render_template(
        "api.html",
        title="Entradas",
        api_key=Config.API_KEY
    )


@app.route("/api")
def api_info():
    """Ruta anterior del panel; se conserva para enlaces existentes."""
    return redirect(url_for("entradas_productos"))


@app.route("/estado-financiero")
def estado_financiero():
    """Pantalla del frontend para el estado financiero (ventas vs. compras)."""
    return render_template(
        "estado_financiero.html",
        title="Estado Financiero",
        api_key=Config.API_KEY
    )


@app.route("/libro-diario")
def libro_diario():
    """Pantalla del frontend para el libro diario (asientos contables)."""
    return render_template(
        "libro_diario.html",
        title="Libro Diario",
        api_key=Config.API_KEY
    )


@app.route("/inventario")
def inventario():
    """Pantalla del frontend para el inventario."""
    # CORRECCIÓN: Renderizamos la plantilla HTML en lugar de llamar a una ruta eliminada.
    # Asegúrate de tener un archivo 'inventario.html' en tu carpeta de templates.
    return render_template(
        "inventario.html", 
        title="Inventario de Productos",
        api_key=Config.API_KEY
    )




# =========================
# INFORMACIÓN DE LA API (Endpoints)
# =========================

@app.route("/api/info")
@require_api_key
def api_estado():
    return jsonify({
        "status": "ok",
        "mensaje": "API contable de Odoo funcionando",
        "endpoints": [
            "GET /api/dashboard/resumen",
            "GET /api/dashboard/facturas-pendientes",
            "GET /api/dashboard/facturas-pendientes.csv",
            "GET /api/dashboard/gastos-pendientes",
            "GET /api/dashboard/estado-financiero?desde=YYYY-MM-DD&hasta=YYYY-MM-DD",
            "GET /api/dashboard/estado-financiero.xlsx?desde=YYYY-MM-DD&hasta=YYYY-MM-DD",
            "GET /api/libro-diario?desde=YYYY-MM-DD&hasta=YYYY-MM-DD",
            "GET /api/libro-diario.xlsx?desde=YYYY-MM-DD&hasta=YYYY-MM-DD",
            "GET /api/ventas/reporte?desde=YYYY-MM-DD&hasta=YYYY-MM-DD",
            "GET /api/ventas/reporte.xlsx?desde=YYYY-MM-DD&hasta=YYYY-MM-DD",
            "GET /api/kardex?desde=YYYY-MM-DD&hasta=YYYY-MM-DD&codigo=(opcional)",
            "GET /api/kardex.xlsx?desde=YYYY-MM-DD&hasta=YYYY-MM-DD&codigo=(opcional)",
            "GET /api/inventario/entradas?desde=YYYY-MM-DD&hasta=YYYY-MM-DD"
        ]
    })


# =========================
# AUTENTICACIÓN ODOO
# =========================
register_odoo_auth_routes(app)
register_odoo_logout_routes(app)


# =========================
# EJECUCIÓN LOCAL
# =========================
if __name__ == "__main__":
    app.run(debug=True, port=5000)
