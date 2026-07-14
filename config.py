import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Conexión a Odoo
    ODOO_URL = os.getenv("ODOO_URL")
    ODOO_DB = os.getenv("ODOO_DB")
    ODOO_USER = os.getenv("ODOO_USER")
    ODOO_PASSWORD = os.getenv("ODOO_PASSWORD")

    # ⚠️ Solo poner en "true" si tu red/antivirus rompe la verificación SSL.
    # Ideal: resolver el certificado y dejar esto en "false".
    ODOO_SSL_UNVERIFIED = os.getenv("ODOO_SSL_UNVERIFIED", "false").lower() == "true"

    # Seguridad de TU API Flask (no confundir con las credenciales de Odoo)
    API_KEY = os.getenv("FLASK_API_KEY")
