# ========================================================
# Archivo WSGI para PythonAnywhere
# Copia todo este contenido en tu archivo WSGI de PythonAnywhere
# (usualmente ubicado en /var/www/tuusuario_pythonanywhere_com_wsgi.py)
# ========================================================

import sys
import os

# 1. Reemplaza 'tuusuario' con tu nombre de usuario real en PythonAnywhere
# y asegúrate de que la ruta coincida con la carpeta de tu proyecto.
path = '/home/tuusuario/API-CONTABLE'

if path not in sys.path:
    sys.path.insert(0, path)

# 2. Configura el directorio de trabajo
os.chdir(path)

# 3. Importar la aplicación Flask.
# IMPORTANTE: En PythonAnywhere, el objeto Flask DEBE llamarse 'application'
from app import app as application
