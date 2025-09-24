from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

def iniciar_driver():
    # Configuración de Chrome en modo headless
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Headless moderno
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    # Usar el ChromeDriver que viene en el sistema (instalado en Dockerfile)
    service = Service("/usr/bin/chromedriver")

    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def ejemplo_scraping():
    driver = iniciar_driver()

    try:
        driver.get("https://example.com")
        time.sleep(2)  # Esperar a que cargue

        print("Título de la página:", driver.title)

        # Ejemplo: obtener un elemento
        h1 = driver.find_element(By.TAG_NAME, "h1")
        print("Encabezado:", h1.text)

    finally:
        driver.quit()

if __name__ == "__main__":
    ejemplo_scraping()
