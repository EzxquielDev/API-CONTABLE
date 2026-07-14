from flask import Flask, jsonify
from blueprints.dashboard import dashboard_bp

app = Flask(__name__)
app.register_blueprint(dashboard_bp)


@app.route("/")
def index():
    return jsonify({
        "status": "ok",
        "mensaje": "API contable de Odoo funcionando",
        "endpoints": [
            "GET /api/dashboard/resumen",
            "GET /api/dashboard/facturas-pendientes",
            "GET /api/dashboard/facturas-pendientes.csv",
            "GET /api/dashboard/gastos-pendientes",
        ],
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
