from flask import jsonify, request

from config import Config
from odoo_client import create_odoo_client
from auth import require_api_key


def register_odoo_auth_routes(app):

    @app.route("/api/odoo/verify", methods=["POST"])
    @require_api_key
    def verify_odoo_credentials():

        payload = request.get_json(silent=True) or {}

        username = (payload.get("odoo_user") or "").strip()
        password = payload.get("odoo_password") or ""

        if not username or not password:
            return jsonify({
                "error": "Faltan o están vacíos 'odoo_user' y/o 'odoo_password'."
            }), 400

        try:
            client = create_odoo_client(
                url=Config.ODOO_URL,
                db=Config.ODOO_DB,
                username=username,
                password=password,
                ssl_unverified=Config.ODOO_SSL_UNVERIFIED,
            )

            return jsonify({
                "ok": True,
                "message": "Credenciales válidas."
            })

        except Exception as e:
            return jsonify({
                "error": str(e)
            }), 401

    @app.route("/api/odoo/change_password", methods=["POST"])
    @require_api_key
    def change_odoo_password():
        payload = request.get_json(silent=True) or {}
        
        username = (payload.get("odoo_user") or "").strip()
        old_password = payload.get("odoo_password_old") or ""
        new_password = payload.get("odoo_password_new") or ""

        if not username or not old_password or not new_password:
            return jsonify({"error": "Faltan parámetros de autenticación."}), 400

        try:
            # Autenticar con contraseña antigua
            client = create_odoo_client(
                url=Config.ODOO_URL,
                db=Config.ODOO_DB,
                username=username,
                password=old_password,
                ssl_unverified=Config.ODOO_SSL_UNVERIFIED,
            )

            # Cambiar a nueva contraseña invocando change_password en Odoo
            # signature: change_password(self, old_passwd, new_passwd)
            client.execute_kw(
                "res.users",
                "change_password",
                [[client.uid], old_password, new_password]
            )

            return jsonify({
                "ok": True,
                "message": "Contraseña actualizada exitosamente."
            })
            
        except Exception as e:
            return jsonify({
                "error": f"Fallo al cambiar la contraseña: {str(e)}"
            }), 401
