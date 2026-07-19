from flask import jsonify


def register_odoo_logout_routes(app):
    @app.route('/api/odoo/logout', methods=['POST'])
    def logout_odoo():
        # No guardamos credenciales en servidor.
        # El borrado real lo hace el frontend removiendo localStorage.
        return jsonify({'ok': True, 'message': 'Sesión borrada (del servidor no hay estado).'})

