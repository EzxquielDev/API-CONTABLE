# Usa una imagen oficial de Python 3.10 ligera
FROM python:3.10-slim

# Establecer variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Crear y establecer el directorio de trabajo
WORKDIR /app

# Copiar los requerimientos primero para aprovechar la caché de Docker
COPY requirements.txt .

# Instalar las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código del proyecto
COPY . .

# Exponer el puerto en el que correrá Gunicorn
EXPOSE 5000

# Comando para ejecutar la aplicación en producción con Gunicorn
# -w 4 significa que usará 4 "workers" (procesos paralelos) para manejar el tráfico
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
