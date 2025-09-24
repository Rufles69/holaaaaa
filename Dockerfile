# Imagen base de Python
FROM python:3.11-slim

# Instalar dependencias necesarias y Google Chrome estable
RUN apt-get update && apt-get install -y \
    wget gnupg unzip curl \
    && mkdir -p /etc/apt/keyrings \
    && wget -q -O- https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Crear carpeta de la app
WORKDIR /app

# Copiar requirements primero (para aprovechar cache de capas)
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Exponer el puerto Flask
EXPOSE 5000

# Comando para correr la app
CMD ["python", "app.py"]
