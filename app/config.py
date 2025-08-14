import os
from dotenv import load_dotenv

def load_config(app):
    load_dotenv()
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    app.config["ADMIN_TOKEN"] = os.getenv("ADMIN_TOKEN")  # optional für Admin-APIs