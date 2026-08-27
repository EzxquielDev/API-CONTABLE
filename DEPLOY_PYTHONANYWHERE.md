# Guía de Despliegue en PythonAnywhere (Plan de Pago)

Este proyecto está 100% listo para ser alojado en tu cuenta de PythonAnywhere, y como tienes el **Hacker plan ($5/mes)**, la API de OpenRouter funcionará sin ningún problema de bloqueos.

## 1. Clonar el proyecto
1. Abre una consola "Bash" en PythonAnywhere.
2. Clona tu repositorio a tu carpeta principal:
   ```bash
   git clone https://github.com/EzxquielDev/API-CONTABLE.git
   cd API-CONTABLE
   ```

## 2. Configurar el Entorno Virtual
Para no tener conflictos con PythonAnywhere, crearemos un entorno virtual propio:
```bash
# Crear entorno virtual llamado 'venv'
mkvirtualenv --python=/usr/bin/python3.10 venv

# Instalar los requerimientos
pip install -r requirements.txt
```

## 3. Configurar el archivo .env
El archivo `.env` nunca se sube a GitHub por seguridad, así que debes crearlo tú mismo:
1. En la pestaña **Files**, navega a `/home/tuusuario/API-CONTABLE/`.
2. Escribe `.env` en la caja de texto y dale a "New file".
3. Pega todo el contenido de tu `.env` (el mismo que usamos en local con tus claves de Odoo y OpenRouter) y guárdalo.

## 4. Configurar la Pestaña "Web"
1. Ve a la pestaña **Web** y haz clic en **Add a new web app**.
2. Selecciona **Manual configuration** (¡importante! NO elijas Flask).
3. Selecciona Python 3.10.
4. En la sección **Virtualenv**, pon la ruta de tu entorno virtual: `/home/tuusuario/.virtualenvs/venv`.
5. En la sección **Code**, pon la ruta de tu código fuente: `/home/tuusuario/API-CONTABLE`.

## 5. Configurar el archivo WSGI
1. En la misma pestaña **Web**, haz clic en el enlace de tu archivo WSGI (`/var/www/tuusuario_pythonanywhere_com_wsgi.py`).
2. Borra absolutamente todo el código que trae por defecto.
3. Copia el código que está dentro del archivo `pythonanywhere_wsgi.py` de tu proyecto y pégalo ahí.
4. Cambia la palabra `tuusuario` por tu nombre de usuario real en la línea `path = '/home/tuusuario/API-CONTABLE'`.
5. Haz clic en "Save".

## 6. ¡Lanzar la aplicación!
Regresa a la pestaña **Web** y presiona el gran botón verde **Reload tuusuario.pythonanywhere.com**.
¡Listo! Si vas a tu enlace, la app estará en línea, conectada a Odoo y con la IA súper rápida de OpenRouter.
