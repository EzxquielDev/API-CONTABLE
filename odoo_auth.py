from flask import jsonify, request

from config import Config
from odoo_client import create_odoo_client


STORAGE_FIELDS = {
    "user": "odoo_login_user",
    "pass": "odoo_login_password",
    "verified": "odoo_login_verified",
}


def register_odoo_auth_routes(app):
    @app.route("/api/odoo/verify", methods=["POST"])
    def verify_odoo_credentials():
        payload = request.get_json(silent=True) or {}
        username = (payload.get("odoo_user") or "").strip()
        password = payload.get("odoo_password") or ""

        if not username or not password:
            return jsonify({"error": "Faltan o están vacíos 'odoo_user' y/o 'odoo_password'."}), 400

        try:
            # Solo valida: intenta autenticar con XML-RPC de Odoo.
            client = create_odoo_client(
                url=Config.ODOO_URL,
                db=Config.ODOO_DB,
                username=username,
                password=password,
                ssl_unverified=Config.ODOO_SSL_UNVERIFIED,
            )

            # Si no lanzó excepción, OK.
            # No guardamos credenciales del usuario en servidor.
            # El frontend marca como verificado localmente.
            return jsonify({"ok": True, "message": "Credenciales válidas."})
        except Exception as e:
            return jsonify({"error": str(e)}), 401

