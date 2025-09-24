# app.py
from flask import Flask, redirect, url_for, session, render_template, request
from authlib.integrations.flask_client import OAuth
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
import os, time, datetime, traceback, atexit

# ---------------- CONFIG ----------------
load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

# Google OAuth
oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# Mongo
MONGO_URL = os.getenv("MONGO_URL")
if not MONGO_URL:
    raise RuntimeError("Set MONGO_URL in environment (.env or Railway env)")
mongo = MongoClient(MONGO_URL)
db = mongo.get_database("BaseDeDatosDeRufles")
tareas_col = db["tareas"]

# ---------------- Selenium driver factory ----------------
def make_driver():
    """Create a headless Chrome/Chromium WebDriver using webdriver-manager.
       En Docker se usa /usr/bin/chromium-browser si existe.
    """
    opts = Options()
    chrome_bin = os.getenv("CHROME_BINARY", "/usr/bin/chromium-browser")
    if os.path.exists(chrome_bin):
        opts.binary_location = chrome_bin

    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-background-networking")

    # Instalar/descargar el chromedriver
    driver_path = ChromeDriverManager().install()

    # A veces webdriver_manager devuelve un archivo de texto (THIRD_PARTY_NOTICES)
    if not os.path.basename(driver_path).startswith("chromedriver"):
        for root, dirs, files in os.walk(os.path.dirname(driver_path)):
            for f in files:
                if f == "chromedriver" or f.startswith("chromedriver"):
                    driver_path = os.path.join(root, f)
                    break

    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=opts)
    return driver

# ---------------- Helper DB functions ----------------
def upsert_tarea(t):
    key = {
        "uni": t["uni"],
        "materia": t["materia"],
        "tarea": t["tarea"],
        "fecha": t["fecha"]
    }
    tareas_col.update_one(key, {"$set": t}, upsert=True)

def eliminar_vencidas():
    hoy = datetime.date.today().isoformat()
    tareas_col.delete_many({"fecha": {"$lt": hoy}})

# ---------------- Scraping flows ----------------
def login_microsoft_and_scrape(user_email, user_pass):
    tareas = []
    driver = make_driver()
    wait = WebDriverWait(driver, 20)
    try:
        driver.get("https://evea.ucacue.edu.ec/my/courses.php")
        try:
            btn = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Microsoft")))
            btn.click()
        except:
            pass

        wait.until(EC.presence_of_element_located((By.NAME, "loginfmt"))).send_keys(user_email)
        driver.find_element(By.ID, "idSIButton9").click()
        wait.until(EC.presence_of_element_located((By.NAME, "passwd"))).send_keys(user_pass)
        driver.find_element(By.ID, "idSIButton9").click()

        time.sleep(1)
        try:
            driver.find_element(By.ID, "idBtn_Back").click()
        except:
            try:
                driver.find_element(By.ID, "idSIButton9").click()
            except:
                pass

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".coursename, .coursebox")))
        time.sleep(1)

        course_links = driver.find_elements(By.CSS_SELECTOR, ".coursename a, .course_title a")
        links = [a.get_attribute("href") for a in course_links if a.get_attribute("href")]
        if not links:
            links = [el.get_attribute("href") for el in driver.find_elements(By.CSS_SELECTOR, ".coursebox a") if el.get_attribute("href")]

        for link in links[:10]:
            try:
                driver.get(link)
                time.sleep(1)
                acts = driver.find_elements(By.CSS_SELECTOR, ".activity.assign, .modtype_assign, a[title*='Tarea'], .activity.activity")
                for a in acts:
                    title = a.text.strip()
                    try:
                        fecha = a.find_element(By.XPATH, ".//ancestor::div[contains(@class,'activity')]/div[contains(@class,'dates') or contains(@class,'activitydates')]").text
                    except:
                        fecha = ""
                    tarea = {
                        "uni": "CATO",
                        "materia": link.split("/")[-1] or "Curso",
                        "tarea": title or "Tarea",
                        "fecha": fecha or datetime.date.today().isoformat(),
                        "estado": "Pendiente",
                        "scraped_at": datetime.datetime.utcnow()
                    }
                    tareas.append(tarea)
            except:
                continue
    except Exception as e:
        print("Error scraping CATO:", e)
        traceback.print_exc()
    finally:
        driver.quit()
    return tareas

def login_google_and_scrape(user_email, user_pass):
    tareas = []
    driver = make_driver()
    wait = WebDriverWait(driver, 20)
    try:
        driver.get("https://campus-virtual.uazuay.edu.ec/v241/")
        try:
            google_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Google') or contains(., 'Sign in with Google') or contains(., 'Iniciar sesión con Google')]")))
            google_btn.click()
        except:
            pass

        wait.until(EC.presence_of_element_located((By.ID, "identifierId"))).send_keys(user_email)
        driver.find_element(By.ID, "identifierNext").click()
        wait.until(EC.presence_of_element_located((By.NAME, "password"))).send_keys(user_pass)
        driver.find_element(By.ID, "passwordNext").click()
        time.sleep(2)

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".course, .coursebox, .course-title")))
        time.sleep(1)

        course_links = driver.find_elements(By.CSS_SELECTOR, ".course a, .coursename a, .course-title a")
        links = [a.get_attribute("href") for a in course_links if a.get_attribute("href")]
        for link in links[:10]:
            try:
                driver.get(link)
                time.sleep(1)
                acts = driver.find_elements(By.CSS_SELECTOR, ".activity.assign, .modtype_assign, a[title*='Tarea']")
                for a in acts:
                    title = a.text.strip()
                    tarea = {
                        "uni": "UDA",
                        "materia": link.split("/")[-1] or "Curso",
                        "tarea": title or "Tarea",
                        "fecha": datetime.date.today().isoformat(),
                        "estado": "Pendiente",
                        "scraped_at": datetime.datetime.utcnow()
                    }
                    tareas.append(tarea)
            except:
                continue
    except Exception as e:
        print("Error scraping UDA:", e)
        traceback.print_exc()
    finally:
        driver.quit()
    return tareas

# ---------------- Job para scheduler ----------------
def job_scrape_and_store():
    print("Job: scraping start", datetime.datetime.utcnow())
    try:
        cato_user = os.getenv("CATO_USER")
        cato_pass = os.getenv("CATO_PASS")
        uda_user = os.getenv("UDA_USER")
        uda_pass = os.getenv("UDA_PASS")

        cato_tareas = login_microsoft_and_scrape(cato_user, cato_pass) if cato_user and cato_pass else []
        uda_tareas = login_google_and_scrape(uda_user, uda_pass) if uda_user and uda_pass else []

        all_t = cato_tareas + uda_tareas
        for t in all_t:
            if not t.get("fecha"):
                t["fecha"] = datetime.date.today().isoformat()
            upsert_tarea(t)
        eliminar_vencidas()
        print(f"Job done: inserted/updated {len(all_t)} tareas")
    except Exception as e:
        print("Job error:", e)
        traceback.print_exc()

# ---------------- Scheduler ----------------
scheduler = BackgroundScheduler()
scheduler.add_job(job_scrape_and_store, "interval", hours=1, next_run_time=datetime.datetime.utcnow())
scheduler.start()

# ---------------- Flask routes ----------------
@app.route("/")
def index():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    latest = list(tareas_col.find({}, {"_id": 0}).sort("scraped_at", -1).limit(10))
    return render_template("index.html", user=user, latest=latest)

@app.route("/login")
def login():
    redirect_uri = url_for("authorize", _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/authorize")
def authorize():
    token = google.authorize_access_token()
    user = google.get("https://openidconnect.googleapis.com/v1/userinfo").json()
    session["user"] = user
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))

@app.route("/tareas")
def ver_tareas():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    tareas = list(tareas_col.find({}, {"_id": 0}))
    return render_template("tareas.html", user=user, tareas=tareas)

# ---------------- Cleanup ----------------
atexit.register(lambda: scheduler.shutdown(wait=False))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
