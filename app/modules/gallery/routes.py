import os
import json
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, current_app, jsonify
from werkzeug.utils import secure_filename
from PIL import Image
from app.modules.vision.embedder import upsert_embedding, image_to_embedding, _load_all, cosine

bp = Blueprint("gallery", __name__, url_prefix="/gallery")

UPLOAD_FOLDER = "app/static/images"
THUMB_FOLDER = "app/static/thumbs"


UPLOAD_TMP = os.path.join("app", "static", "tmp")
os.makedirs(UPLOAD_TMP, exist_ok=True)

# Maximale Abmessungen für Thumbnails & Bilder
THUMB_SIZE = (300, 300)
MAX_IMAGE_SIZE = (1920, 1080)  # z.B. Full HD für Originalbilder


@bp.route("/")
def index():
    return render_template("gallery/index.html")


@bp.route("/api/items")
def api_items():
    """Liefert nur Einträge aus data.json zurück, deren Bilddatei noch existiert."""
    data_path = os.path.join(current_app.static_folder, "data.json")
    valid_items = []

    if os.path.exists(data_path):
        with open(data_path, encoding="utf-8") as f:
            items = json.load(f)

        for item in items:
            img_path = item.get("image", "").lstrip("/")
            img_abs = os.path.join(current_app.root_path, img_path)
            if os.path.exists(img_abs):
                valid_items.append(item)

    return jsonify(valid_items)


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
                "artist": request.form.get("artist"),
                "year": int(request.form.get("year") or 0),
                "location_painted": request.form.get("location_painted"),
                "location_bought": request.form.get("location_bought"),
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

            
            upsert_embedding(unique_id, new_item["image"])

            return redirect(url_for("gallery.index", _anchor=unique_id), code=303)
        

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

DELETE_PASSWORD = "9596"

@bp.route("/delete/<item_id>", methods=["POST"])
def delete(item_id):
    """Löscht ein Bild nach Passwortprüfung."""
    pw = request.form.get("password")
    if pw != DELETE_PASSWORD:
        return jsonify({"success": False, "error": "Falsches Passwort"}), 403

    data_path = os.path.join(current_app.static_folder, "data.json")
    items = []

    if os.path.exists(data_path):
        with open(data_path, encoding="utf-8") as fjson:
            items = json.load(fjson)

    item = next((x for x in items if x.get("id") == item_id), None)
    if not item:
        return jsonify({"success": False, "error": "Item not found"}), 404

    # Dateien löschen
    for key in ["image", "thumb"]:
        if item.get(key):
            img_path = os.path.join(current_app.root_path, item[key].lstrip("/"))
            if os.path.exists(img_path):
                os.remove(img_path)

    # Metadaten aktualisieren
    items = [x for x in items if x.get("id") != item_id]
    with open(data_path, "w", encoding="utf-8") as fjson:
        json.dump(items, fjson, ensure_ascii=False, indent=2)

    return jsonify({"success": True})



@bp.route("/api/embeddings")
def api_embeddings():
    emb_path = os.path.join(current_app.static_folder, "embeddings.json")
    if os.path.exists(emb_path):
        with open(emb_path, encoding="utf-8") as f:
            return jsonify(json.load(f))
    return jsonify([])


@bp.route("/api/embeddings_info")
def api_embeddings_info():
    try:
        from app.modules.vision.embedder import embedding_dim_from_model, embedding_dim_from_file, load_all_embeddings
        model_dim = embedding_dim_from_model()
        file_dim = embedding_dim_from_file()
        recs = load_all_embeddings()
        return jsonify({
            "model_dim": model_dim,
            "file_dim": file_dim,
            "count": len(recs)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@bp.route("/search", methods=["POST"])
def search():
    """
    Nimmt ein hochgeladenes Bild, berechnet Embedding (Server),
    vergleicht gegen Embedding-DB und gibt bestes Match zurück.
    """
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "empty filename"}), 400

    # Temporär speichern
    fname = secure_filename(f.filename)
    tmp_path = os.path.join(UPLOAD_TMP, f"{uuid.uuid4().hex}_{fname}")
    f.save(tmp_path)

    try:
        qvec = image_to_embedding(tmp_path)
    except Exception as e:
        os.remove(tmp_path)
        return jsonify({"error": f"embedding failed: {e}"}), 500
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # DB laden
    db = _load_all()
    if not db:
        return jsonify({"error": "no embeddings in DB"}), 500

    # Cosine Similarities
    best = {"id": None, "score": -2}
    for r in db:
        v = r.get("vector")
        if not v: continue
        s = cosine(qvec, v)
        if s > best["score"]:
            best = {"id": r["id"], "score": float(s), "image": r["image"]}

    return jsonify(best)
