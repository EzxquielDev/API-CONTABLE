from flask import Flask, jsonify
from blueprints.dashboard import dashboard_bp

app = Flask(__name__)
app.register_blueprint(dashboard_bp)


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
        ],
    })

@app.route("/inventario")
def inventario():
    return Invetario_ruta()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
