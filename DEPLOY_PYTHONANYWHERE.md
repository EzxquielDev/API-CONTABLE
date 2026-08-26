# Guía de Despliegue en PythonAnywhere

Este proyecto está listo para ser alojado en PythonAnywhere. Sigue estos pasos para subirlo y configurarlo correctamente:

## 1. Clonar o subir el proyecto
1. Abre la consola "Bash" en PythonAnywhere.
2. Clona tu repositorio o sube los archivos directamente a tu carpeta (por ejemplo, `/home/tuusuario/API-CONTABLE`).
   ```bash
   git clone https://github.com/EzxquielDev/API-CONTABLE.git
   cd API-CONTABLE
   ```

## 2. Configurar el Entorno Virtual (Recomendado)
Para evitar conflictos con otras librerías, crea un entorno virtual:
```bash
# Crear entorno virtual llamado 'venv'
mkvirtualenv --python=/usr/bin/python3.10 venv

# Instalar los requerimientos
pip install -r requirements.txt
```

## 3. Configurar el archivo .env
Como el archivo `.env` no se sube a GitHub por seguridad, tienes que crearlo manualmente en PythonAnywhere:
1. En la pestaña "Files", ve a `/home/tuusuario/API-CONTABLE/`.
2. Crea un nuevo archivo llamado `.env`.
3. Pega tus credenciales allí (igual que en tu servidor local).

## 4. Configurar la Pestaña "Web"
1. Ve a la pestaña **Web** y haz clic en **Add a new web app**.
2. Selecciona **Manual configuration** (muy importante, no elijas Flask porque generará archivos por defecto que no necesitamos).
3. Selecciona la versión de Python correspondiente (ej: Python 3.10).
4. En la sección **Virtualenv**, pon la ruta a tu entorno virtual (ej: `/home/tuusuario/.virtualenvs/venv`).
5. En la sección **Code**, pon la ruta de tu proyecto en "Source code" (ej: `/home/tuusuario/API-CONTABLE`).

## 5. Configurar el archivo WSGI
1. En la pestaña **Web**, haz clic en el enlace al archivo WSGI (usualmente `/var/www/tuusuario_pythonanywhere_com_wsgi.py`).
2. Borra todo el contenido de ese archivo.
3. Copia el contenido del archivo `pythonanywhere_wsgi.py` que está en este proyecto y pégalo ahí.
4. **IMPORTANTE:** Cambia la palabra `tuusuario` por tu nombre de usuario real en PythonAnywhere dentro de la ruta `path = '/home/tuusuario/API-CONTABLE'`.
5. Guarda el archivo.

## 6. ¡Lanzar la aplicación!
Vuelve a la pestaña **Web** y haz clic en el botón verde grande **Reload tuusuario.pythonanywhere.com**.
Tu aplicación debería estar corriendo y disponible en la URL proporcionada.

### Notas adicionales sobre PythonAnywhere
- **Hilos en segundo plano:** En `app.py` hay una función que limpia la caché en segundo plano (`start_background_cache`). En PythonAnywhere los "workers" se pueden reiniciar solos si no hay tráfico, pero no afectará el funcionamiento principal de tu app, solo ten en cuenta que el hilo podría morir y revivir junto con los workers.
- **Whitelist de conexiones:** Si estás en la cuenta gratuita de PythonAnywhere, asegúrate de que la URL de tu Odoo, OpenAI y OpenRouter estén permitidos por su proxy, o actualiza a una cuenta de pago (Hacker plan) que tiene internet sin restricciones.
