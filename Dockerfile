# Imagen base de Python
FROM python:3.11-slim

# Instalar dependencias necesarias para Selenium y Chrome
RUN apt-get update && apt-get install -y \
    wget unzip curl gnupg \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Crear carpeta de la app
WORKDIR /app

# Copiar requirements primero (para aprovechar cache)
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Exponer el puerto Flask
EXPOSE 5000

# Comando para correr la app
CMD ["python", "app.py"]
