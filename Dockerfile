# Imagen base
FROM python:3.11-slim

# Dependencias de Chrome
RUN apt-get update && apt-get install -y \
    wget unzip curl gnupg \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# Por defecto corre Flask
CMD ["python", "app.py"]
