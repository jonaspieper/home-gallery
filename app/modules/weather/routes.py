from flask import Blueprint, render_template, jsonify

bp = Blueprint("weather", __name__, url_prefix="/weather")

@bp.route("/")
def index():
    return render_template("weather.html")

@bp.route("/api/now")
def api_now():
    # später: echte Daten (z.B. von deinem eigenen Wetterserver)
    return jsonify({"ok": True, "temp": None})