from functools import wraps
from flask import request, jsonify
from config import Config


def require_api_key(f):
    """Protege un endpoint exigiendo el header X-API-Key.

    Uso en Google Sheets / Power Query: agregar el header
    X-API-Key: <tu clave> a la petición.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key")
        if not Config.API_KEY:
            return jsonify({"error": "FLASK_API_KEY no configurada en el servidor"}), 500
        if key != Config.API_KEY:
            return jsonify({"error": "API key inválida o faltante"}), 401
        return f(*args, **kwargs)
    return decorated
