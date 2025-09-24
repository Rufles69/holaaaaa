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

# Instalar dependencias de Chrome
RUN apt-get update && apt-get install -y wget gnupg unzip \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable
