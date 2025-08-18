import os, json
from typing import List, Dict
from PIL import Image
import numpy as np

try:
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    from tensorflow.lite import Interpreter  # fallback für macOS-Tests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
STATIC_DIR = os.path.join(ROOT, "static")
IMAGES_DIR = os.path.join(STATIC_DIR, "images")
EMB_PATH = os.path.join(STATIC_DIR, "embeddings.json")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "mobilenet_v2_1.0_224.tflite")

_interpreter = None
_input = None
_output = None
_feature_tensor_index = None  # << neu: merken, falls wir die Feature-Schicht finden

# ---------------- Model handling ----------------

def _load_model():
    global _interpreter, _input, _output
    if _interpreter is not None:
        return
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"TFLite model not found: {MODEL_PATH}")
    _interpreter = Interpreter(model_path=MODEL_PATH, num_threads=2)
    _interpreter.allocate_tensors()
    _input = _interpreter.get_input_details()[0]
    _output = _interpreter.get_output_details()[0]

def _find_feature_tensor_index():
    """Suche eine geeignete Feature-Schicht (1280D) im TFLite-Graph."""
    global _feature_tensor_index
    if _feature_tensor_index is not None:
        return _feature_tensor_index
    _load_model()
    candidates = []
    for td in _interpreter.get_tensor_details():
        shape = td.get("shape", [])
        last = int(shape[-1]) if len(shape) else None
        if last == 1280:  # typische Dimension MobileNetV2 bottleneck
            name = td.get("name", "").lower()
            score = 0
            for key in ("avg", "pool", "global", "feature", "bottleneck"):
                if key in name:
                    score += 1
            candidates.append((score, td))
    if candidates:
        candidates.sort(key=lambda x: (-x[0], x[1]["index"]))
        _feature_tensor_index = candidates[0][1]["index"]
    else:
        _feature_tensor_index = None
    return _feature_tensor_index

# ---------------- Preprocessing ----------------

def _preprocess(img_path: str) -> np.ndarray:
    img = Image.open(img_path).convert("RGB").resize((224, 224))
    arr = np.asarray(img, dtype=np.float32)
    arr = (arr / 127.5) - 1.0
    return np.expand_dims(arr, 0)  # [1,224,224,3]

def _l2(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x)
    return x / (n + 1e-12)

# ---------------- Embedding ----------------

def image_to_embedding(img_path: str) -> List[float]:
    """Berechne robustes Embedding: Feature (1280D) oder Fallback Logits (1001D)."""
    _load_model()
    x = _preprocess(img_path)
    if _input["dtype"] == np.uint8:
        scale, zero = _input["quantization"]
        x = (x / scale + (zero or 0)).astype(np.uint8)

    _interpreter.set_tensor(_input["index"], x)
    _interpreter.invoke()

    vec = None
    feat_idx = _find_feature_tensor_index()
    if feat_idx is not None:
        try:
            vec = _interpreter.get_tensor(feat_idx).squeeze().astype(np.float32)
        except Exception as e:
            print("⚠️ Feature tensor not accessible, fallback to logits:", e)

    if vec is None:
        vec = _interpreter.get_tensor(_output["index"]).squeeze().astype(np.float32)

    return _l2(vec).tolist()

# ---------------- JSON I/O ----------------

def _load_all() -> List[Dict]:
    if not os.path.exists(EMB_PATH):
        return []
    try:
        with open(EMB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def _save_all(recs: List[Dict]):
    os.makedirs(STATIC_DIR, exist_ok=True)
    tmp_path = EMB_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False)
    os.replace(tmp_path, EMB_PATH)

def load_all_embeddings() -> List[Dict]:
    return _load_all()

def save_all_embeddings(recs: List[Dict]):
    _save_all(recs)

# ---------------- Ops ----------------

def upsert_embedding(item_id: str, img_rel_url: str):
    img_abs = os.path.join(ROOT, img_rel_url.lstrip("/"))
    vec = image_to_embedding(img_abs)
    recs = _load_all()
    for r in recs:
        if r.get("id") == item_id:
            r["vector"] = vec
            r["image"] = img_rel_url
            break
    else:
        recs.append({"id": item_id, "image": img_rel_url, "vector": vec})
    _save_all(recs)

def reindex_all(images_dir: str = IMAGES_DIR):
    if not os.path.isdir(images_dir):
        _save_all([])
        return
    recs = []
    for fname in sorted(os.listdir(images_dir)):
        path = os.path.join(images_dir, fname)
        if not os.path.isfile(path):
            continue
        try:
            vec = image_to_embedding(path)
            recs.append({
                "id": os.path.splitext(fname)[0],
                "image": f"/static/images/{fname}",
                "vector": vec
            })
        except Exception as e:
            print("skip", fname, e)
    _save_all(recs)

def embedding_dim_from_model() -> int:
    _load_model()
    feat_idx = _find_feature_tensor_index()
    if feat_idx is not None:
        shp = _interpreter.get_tensor_details()[feat_idx]["shape"]
    else:
        shp = _output["shape"]
    return int(shp[-1]) if isinstance(shp, (list, tuple, np.ndarray)) else int(shp)

def embedding_dim_from_file() -> int | None:
    recs = _load_all()
    for r in recs:
        v = r.get("vector")
        if isinstance(v, list) and v:
            return len(v)
    return None

# ---------------- Similarity ----------------

def cosine(a, b):
    a = np.array(a, dtype=np.float32)
    b = np.array(b, dtype=np.float32)
    dot = float(np.dot(a, b))
    denom = np.linalg.norm(a) * np.linalg.norm(b) or 1.0
    return dot / denom

# ---------------- CLI ----------------

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--reindex", action="store_true")
    args = ap.parse_args()
    if args.reindex:
        reindex_all()
        print("Reindex complete:", EMB_PATH)