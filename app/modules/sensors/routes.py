from flask import Blueprint, render_template, jsonify

bp = Blueprint("sensors", __name__, url_prefix="/sensors")

@bp.route("/")
def index():
    return render_template("sensors.html")

@bp.route("/api/list")
def api_list():
    # später: Messwerte aus MQTT/Influx/CSV etc.
    return jsonify({"sensors": []})