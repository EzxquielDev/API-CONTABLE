from flask import render_template
from config import Config

def Invetario_ruta():
    """Muestra la pantalla sin bloquearla con llamadas a Odoo.

    Los datos se solicitan desde el navegador una vez que la vista ya se
    mostró. Así una conexión lenta a Odoo no demora la navegación.
    """
    return render_template("inventario.html", title="Inventario", api_key=Config.API_KEY)
