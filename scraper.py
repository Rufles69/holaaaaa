import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


def iniciar_driver():
    chrome_options = Options()
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--headless")  # quítalo si quieres ver la ventana en Windows
    chrome_options.add_argument("--window-size=1920,1080")

    # Detectar si estamos en Railway (Linux) o en Windows local
    if os.name == "nt":  # Windows
        print("➡ Usando webdriver_manager en Windows...")
        service = Service(ChromeDriverManager().install())
    else:  # Linux (Railway/Docker)
        print("➡ Usando chromedriver del sistema en Linux...")
        service = Service("/usr/bin/chromedriver")

    return webdriver.Chrome(service=service, options=chrome_options)


def scrapear_y_guardar():
    driver = iniciar_driver()
    driver.get("https://www.google.com")
    print("Título de la página:", driver.title)
    driver.quit()


if __name__ == "__main__":
    scrapear_y_guardar()
