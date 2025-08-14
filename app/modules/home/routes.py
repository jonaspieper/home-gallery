from flask import Blueprint, render_template

bp = Blueprint("home", __name__, url_prefix="")

@bp.route("/")
def index():
    tiles = [
        {"title": "Galerie", "href": "/gallery", "desc": "Bilder mit Zusatzinfos"},
        {"title": "Wetter", "href": "/weather", "desc": "Lokaler Wetterdienst (später)"},
        {"title": "Sensoren", "href": "/sensors", "desc": "Smart-Home Daten (später)"},
    ]
    return render_template("home.html", tiles=tiles)