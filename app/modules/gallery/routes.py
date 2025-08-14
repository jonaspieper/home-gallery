import os
import json
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, current_app, jsonify
from werkzeug.utils import secure_filename
from PIL import Image

bp = Blueprint("gallery", __name__, url_prefix="/gallery")

UPLOAD_FOLDER = "app/static/images"
THUMB_FOLDER = "app/static/thumbs"

# Maximale Abmessungen für Thumbnails & Bilder
THUMB_SIZE = (300, 300)
MAX_IMAGE_SIZE = (1920, 1080)  # z.B. Full HD für Originalbilder


@bp.route("/")
def index():
    return render_template("gallery/index.html")


@bp.route("/api/items")
def api_items():
    """Liefert die aktuelle data.json zurück"""
    data_path = os.path.join(current_app.static_folder, "data.json")
    if os.path.exists(data_path):
        with open(data_path, encoding="utf-8") as f:
            return jsonify(json.load(f))
    return jsonify([])


@bp.route("/upload", methods=["GET", "POST"])
def upload():
    """Formular und Upload-Logik für neue Bilder"""
    if request.method == "POST":
        f = request.files["photo"]
        if f:
            # 1) Eindeutigen Dateinamen erstellen
            ext = os.path.splitext(f.filename)[1].lower()
            unique_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
            filename = f"{unique_id}{ext}"

            # 2) Zielordner sicherstellen
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            os.makedirs(THUMB_FOLDER, exist_ok=True)

            # 3) Bild öffnen
            img = Image.open(f.stream)

            # 4) Originalbild ggf. verkleinern
            img.thumbnail(MAX_IMAGE_SIZE)
            img_path = os.path.join(UPLOAD_FOLDER, filename)
            img.save(img_path, optimize=True, quality=85)

            # 5) Thumbnail erstellen
            thumb = img.copy()
            thumb.thumbnail(THUMB_SIZE)
            thumb_path = os.path.join(THUMB_FOLDER, filename)
            thumb.save(thumb_path, optimize=True, quality=70)

            # 6) Metadaten eintragen
            new_item = {
                "id": unique_id,
                "title": request.form.get("title"),
                "year": int(request.form.get("year") or 0),
                "location": request.form.get("location"),
                "description": request.form.get("description"),
                "image": f"/static/images/{filename}",
                "thumb": f"/static/thumbs/{filename}",
                "tags": [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()],
                "links": [],
                "created": datetime.now().isoformat()
            }

            data_path = os.path.join(current_app.static_folder, "data.json")
            data = []
            if os.path.exists(data_path):
                with open(data_path, encoding="utf-8") as fjson:
                    data = json.load(fjson)
            data.append(new_item)
            with open(data_path, "w", encoding="utf-8") as fjson:
                json.dump(data, fjson, ensure_ascii=False, indent=2)

            return redirect(url_for("gallery.index"))

    return render_template("gallery/upload.html")



def view(item_id):
    """Zeigt die Detailansicht eines einzelnen Bildes."""
    data_path = os.path.join(current_app.static_folder, "data.json")
    items = []
    if os.path.exists(data_path):
        with open(data_path, encoding="utf-8") as f:
            items = json.load(f)

    item = next((x for x in items if x.get("id") == item_id), None)
    if not item:
        # einfache 404-Seite
        return render_template("gallery/not_found.html", item_id=item_id), 404

    return render_template("gallery/view.html", item=item)