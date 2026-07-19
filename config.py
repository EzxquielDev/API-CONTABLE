import json
import os
from pathlib import Path


RUTA_CONFIG_JSON = Path(__file__).with_name("config.json")
RUTA_ENV_LEGACY = Path(__file__).with_name(".env")


def _cargar_configuracion_json():
    """Carga la configuración local desde JSON, si ya fue creada."""
    if not RUTA_CONFIG_JSON.exists():
        return {}
    try:
        with RUTA_CONFIG_JSON.open(encoding="utf-8") as archivo:
            configuracion = json.load(archivo)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"El archivo {RUTA_CONFIG_JSON.name} no contiene JSON válido.") from error
    if not isinstance(configuracion, dict):
        raise RuntimeError(f"El archivo {RUTA_CONFIG_JSON.name} debe contener un objeto JSON.")
    return configuracion


CONFIGURACION_JSON = _cargar_configuracion_json()


def _cargar_env_legacy():
    """Lee el .env anterior sin depender de python-dotenv durante la migración."""
    if not RUTA_ENV_LEGACY.exists():
        return {}
    valores = {}
    for linea in RUTA_ENV_LEGACY.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        nombre, valor = linea.split("=", 1)
        valores[nombre.strip()] = valor.strip().strip('"').strip("'")
    return valores


CONFIGURACION_ENV_LEGACY = _cargar_env_legacy()


def _valor_configuracion(nombre, predeterminado=None):
    """Prioriza config.json y conserva .env como compatibilidad temporal."""
    valor = CONFIGURACION_JSON.get(nombre)
    if valor not in (None, ""):
        return valor
    return os.getenv(nombre, CONFIGURACION_ENV_LEGACY.get(nombre, predeterminado))


class Config:
    # Conexión a Odoo
    ODOO_URL = _valor_configuracion("ODOO_URL")
    ODOO_DB = _valor_configuracion("ODOO_DB")
    ODOO_USER = _valor_configuracion("ODOO_USER")
    ODOO_PASSWORD = _valor_configuracion("ODOO_PASSWORD")

    # ⚠️ Solo poner en "true" si tu red/antivirus rompe la verificación SSL.
    # Ideal: resolver el certificado y dejar esto en "false".
    ODOO_SSL_UNVERIFIED = str(_valor_configuracion("ODOO_SSL_UNVERIFIED", "false")).lower() == "true"

    # Seguridad de TU API Flask (no confundir con las credenciales de Odoo)
    API_KEY = _valor_configuracion("FLASK_API_KEY")
