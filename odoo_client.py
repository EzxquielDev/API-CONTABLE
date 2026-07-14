import ssl
import xmlrpc.client
from config import Config


class OdooClient:
    """Wrapper simple sobre la API XML-RPC de Odoo."""

    def __init__(self):
        self.url = Config.ODOO_URL
        self.db = Config.ODOO_DB
        self.username = Config.ODOO_USER
        self.password = Config.ODOO_PASSWORD

        context = ssl._create_unverified_context() if Config.ODOO_SSL_UNVERIFIED else None

        common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", context=context)
        self.uid = common.authenticate(self.db, self.username, self.password, {})

        if not self.uid:
            raise RuntimeError(
                "No se pudo autenticar con Odoo. Revisa usuario/contraseña/base de datos, "
                "o si tienes 2FA activado (en ese caso necesitas una API key de Odoo)."
            )

        self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", context=context)

    def search_read(self, model, domain=None, fields=None, **kwargs):
        domain = domain or []
        fields = fields or []
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, "search_read",
            [domain, fields], kwargs
        )

    def read_group(self, model, domain, fields, groupby, **kwargs):
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, "read_group",
            [domain, fields, groupby], kwargs
        )


def get_odoo_client():
    """Crea una nueva conexión por request. Simple y suficiente para uso de un solo admin."""
    return OdooClient()
