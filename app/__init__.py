import importlib
import pkgutil
from flask import Flask
from .config import load_config

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    load_config(app)

    register_modules(app)
    return app

def register_modules(app):
    """
    Lädt automatisch alle Blueprints aus app/modules/<modulname>/routes.py.
    Erwartet: jede routes.py enthält ein Blueprint-Objekt 'bp'.
    """
    package_name = "app.modules"
    package = importlib.import_module(package_name)

    for _, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
        if not is_pkg:
            continue
        try:
            mod = importlib.import_module(f"{package_name}.{module_name}.routes")
            bp = getattr(mod, "bp", None)
            if bp is None:
                app.logger.warning(f"⚠ Modul '{module_name}' hat keinen 'bp' Blueprint – wird übersprungen")
                continue
            app.register_blueprint(bp)
            app.logger.info(f"✅ Modul geladen: {module_name} ({bp.name})")
        except ModuleNotFoundError as e:
            app.logger.warning(f"⚠ Kein routes.py in Modul '{module_name}': {e}")
        except Exception as e:
            app.logger.error(f"❌ Fehler beim Laden von Modul '{module_name}': {e}")
