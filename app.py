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
import os, time, datetime, traceback

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
MONGO_URL = os.getenv("MONGO_URL")  # Railway: set this to ${MongoDB.MONGO_URL}
if not MONGO_URL:
    raise RuntimeError("Set MONGO_URL in environment (.env or Railway env)")
mongo = MongoClient(MONGO_URL)
db = mongo.get_database("BaseDeDatosDeRufles")
  # use default DB from connection string
tareas_col = db["tareas"]

# ---------------- Selenium driver factory ----------------
def make_driver():
    """Create a headless Chrome/Chromium WebDriver using webdriver-manager.
       In Docker we install chromium-browser and use default binary.
    """
    opts = Options()
    # In Docker we will have /usr/bin/chromium-browser
    # If running locally on Windows, comment the next line and set binary_location to Brave path if needed.
    chrome_bin = os.getenv("CHROME_BINARY", "/usr/bin/chromium-browser")
    if os.path.exists(chrome_bin):
        opts.binary_location = chrome_bin

    opts.add_argument("--headless=new")  # headless
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    # optional to avoid detection
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-background-networking")

    # webdriver-manager will download matching chromedriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    return driver

# ---------------- Helper DB functions ----------------
def upsert_tarea(t):
    """Upsert tarea dict into Mongo. Use unique key (uni,materia,tarea,fecha)."""
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

# ---------------- Scraping flows (Microsoft for CATO, Google for UDA) ----------------
def login_microsoft_and_scrape(user_email, user_pass):
    """Login to Microsoft + EVEA UCACUE and scrape assignments.
       Returns list of tareas dicts.
       NOTE: selectors may need tweaks depending on EVEA HTML changes.
    """
    tareas = []
    driver = make_driver()
    wait = WebDriverWait(driver, 20)
    try:
        # go to platform page (this will redirect to MS login)
        driver.get("https://evea.ucacue.edu.ec/my/courses.php")
        # Wait and click Microsoft login button if present
        try:
            btn = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Microsoft")))
            btn.click()
        except Exception:
            # maybe direct redirect; proceed
            pass

        # Microsoft login flow
        # email
        wait.until(EC.presence_of_element_located((By.NAME, "loginfmt"))).send_keys(user_email)
        driver.find_element(By.ID, "idSIButton9").click()
        # password
        wait.until(EC.presence_of_element_located((By.NAME, "passwd"))).send_keys(user_pass)
        driver.find_element(By.ID, "idSIButton9").click()
        # handle "Stay signed in?" -> NO (idBtn_Back) or YES (idSIButton9) - we try both safely
        time.sleep(1)
        try:
            no_btn = driver.find_element(By.ID, "idBtn_Back")
            no_btn.click()
        except:
            try:
                yes_btn = driver.find_element(By.ID, "idSIButton9")
                yes_btn.click()
            except:
                pass

        # now should be logged into EVEA - wait for courses page to load
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".coursename, .coursebox")))
        time.sleep(1)

        # Scrape courses and assignment items - selectors may differ
        # Try to find assignment activities inside a course page
        course_links = driver.find_elements(By.CSS_SELECTOR, ".coursename a, .course_title a")
        links = [a.get_attribute("href") for a in course_links if a.get_attribute("href")]
        # if no links found, find course containers
        if not links:
            links = [el.get_attribute("href") for el in driver.find_elements(By.CSS_SELECTOR, ".coursebox a") if el.get_attribute("href")]

        # iterate up to a few courses
        for link in links[:10]:
            try:
                driver.get(link)
                time.sleep(1)
                # find assignment blocks - moodle uses assign, modtype-assign, activity assign
                acts = driver.find_elements(By.CSS_SELECTOR, ".activity.assign, .modtype_assign, a[title*='Tarea'], .activity.activity")
                for a in acts:
                    try:
                        title = a.text.strip()
                        # try to find due date nearby
                        try:
                            fecha = a.find_element(By.XPATH, ".//ancestor::div[contains(@class,'activity')]/div[contains(@class,'dates') or contains(@class,'activitydates')]").text
                        except:
                            # fallback: search for date text inside course page
                            fecha = ""
                        tarea = {
                            "uni": "CATO",
                            "materia": link.split("/")[-1] or "Curso",
                            "tarea": title or "Tarea",
                            # normalize fecha to ISO if possible - here we keep raw string; later you can parse
                            "fecha": fecha or datetime.date.today().isoformat(),
                            "estado": "Pendiente",
                            "scraped_at": datetime.datetime.utcnow()
                        }
                        tareas.append(tarea)
                    except Exception:
                        continue
            except Exception:
                continue

    except Exception as e:
        print("Error scraping CATO:", e)
        traceback.print_exc()
    finally:
        driver.quit()
    return tareas

def login_google_and_scrape(user_email, user_pass):
    """Login to UDA campus (Google Sign-In) and scrape assignments.
       Returns list of tareas dicts.
    """
    tareas = []
    driver = make_driver()
    wait = WebDriverWait(driver, 20)
    try:
        driver.get("https://campus-virtual.uazuay.edu.ec/v241/")
        # Click "Sign in with Google" if present - try to detect buttons
        try:
            google_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Google') or contains(., 'Sign in with Google') or contains(., 'Iniciar sesión con Google')]")))
            google_btn.click()
        except Exception:
            # maybe redirect opened, or sign-in link
            pass

        # Google login flow
        # email
        wait.until(EC.presence_of_element_located((By.ID, "identifierId"))).send_keys(user_email)
        driver.find_element(By.ID, "identifierNext").click()
        # password
        wait.until(EC.presence_of_element_located((By.NAME, "password"))).send_keys(user_pass)
        driver.find_element(By.ID, "passwordNext").click()
        time.sleep(2)

        # after login, wait for courses
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".course, .coursebox, .course-title")))
        time.sleep(1)

        # scrape courses and assignments (structure may differ)
        course_links = driver.find_elements(By.CSS_SELECTOR, ".course a, .coursename a, .course-title a")
        links = [a.get_attribute("href") for a in course_links if a.get_attribute("href")]
        for link in links[:10]:
            try:
                driver.get(link)
                time.sleep(1)
                acts = driver.find_elements(By.CSS_SELECTOR, ".activity.assign, .modtype_assign, a[title*='Tarea']")
                for a in acts:
                    try:
                        title = a.text.strip()
                        fecha = ""
                        tarea = {
                            "uni": "UDA",
                            "materia": link.split("/")[-1] or "Curso",
                            "tarea": title or "Tarea",
                            "fecha": fecha or datetime.date.today().isoformat(),
                            "estado": "Pendiente",
                            "scraped_at": datetime.datetime.utcnow()
                        }
                        tareas.append(tarea)
                    except Exception:
                        continue
            except Exception:
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
        # read creds from env
        cato_user = os.getenv("CATO_USER")
        cato_pass = os.getenv("CATO_PASS")
        uda_user = os.getenv("UDA_USER")
        uda_pass = os.getenv("UDA_PASS")
        # scrape
        cato_tareas = []
        uda_tareas = []
        if cato_user and cato_pass:
            cato_tareas = login_microsoft_and_scrape(cato_user, cato_pass)
        if uda_user and uda_pass:
            uda_tareas = login_google_and_scrape(uda_user, uda_pass)

        all_t = cato_tareas + uda_tareas
        for t in all_t:
            # ensure fecha is ISO (if not, leave as-is). You should parse it in production.
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
# run every hour
scheduler.add_job(job_scrape_and_store, "interval", hours=1, next_run_time=datetime.datetime.utcnow())
scheduler.start()

# ---------------- Flask routes ----------------
@app.route("/")
def index():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    # show small overview (latest scraped tasks)
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
    # load tasks grouped by uni
    tareas = list(tareas_col.find({}, {"_id": 0}))
    return render_template("tareas.html", user=user, tareas=tareas)

# ---------------- Cleanup on shutdown ----------------
import atexit
atexit.register(lambda: scheduler.shutdown(wait=False))

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
