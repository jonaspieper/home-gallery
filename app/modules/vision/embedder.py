import os, json
from typing import List, Dict
from PIL import Image
import numpy as np

try:
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    from tensorflow.lite import Interpreter  # fallback für macOS-Tests (optional)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
STATIC_DIR = os.path.join(ROOT, "static")
IMAGES_DIR = os.path.join(STATIC_DIR, "images")
EMB_PATH = os.path.join(STATIC_DIR, "embeddings.json")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "mobilenet_v2_1.0_224.tflite")

_interpreter = None
_input = None
_output = None

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

def _preprocess(img_path: str) -> np.ndarray:
    # 224x224 RGB, float32 in [-1, 1]
    img = Image.open(img_path).convert("RGB").resize((224, 224))
    arr = np.asarray(img, dtype=np.float32)
    arr = (arr / 127.5) - 1.0
    return np.expand_dims(arr, 0)  # [1,224,224,3]

def _l2(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x)
    return x / (n + 1e-12)

def image_to_embedding(img_path: str) -> List[float]:
    _load_model()
    x = _preprocess(img_path)
    if _input["dtype"] == np.uint8:  # quantisierte Modelle unterstützen
        scale, zero = _input["quantization"]
        x = (x / scale + zero).astype(np.uint8)
    _interpreter.set_tensor(_input["index"], x)
    _interpreter.invoke()
    out = _interpreter.get_tensor(_output["index"]).squeeze().astype(np.float32)
    out = _l2(out)
    return out.tolist()

def _load_all() -> List[Dict]:
    if os.path.exists(EMB_PATH):
        with open(EMB_PATH, "r", encoding="utf-8") as f: return json.load(f)
    return []

def _save_all(recs: List[Dict]):
    with open(EMB_PATH, "w", encoding="utf-8") as f: json.dump(recs, f, ensure_ascii=False)

def upsert_embedding(item_id: str, img_rel_url: str):
    img_abs = os.path.join(ROOT, img_rel_url.lstrip("/"))
    vec = image_to_embedding(img_abs)
    recs = _load_all()
    for r in recs:
        if r.get("id") == item_id:
            r["vector"] = vec; r["image"] = img_rel_url
            break
    else:
        recs.append({"id": item_id, "image": img_rel_url, "vector": vec})
    _save_all(recs)

def reindex_all(images_dir: str = IMAGES_DIR):
    files = [f for f in sorted(os.listdir(images_dir)) if os.path.isfile(os.path.join(images_dir, f))]
    recs = []
    for fname in files:
        path = os.path.join(images_dir, fname)
        try:
            vec = image_to_embedding(path)
            recs.append({"id": os.path.splitext(fname)[0], "image": f"/static/images/{fname}", "vector": vec})
        except Exception as e:
            print("skip", fname, e)
    _save_all(recs)


def embedding_dim_from_model() -> int:
    _load_model()
    shp = _output["shape"]
    return int(shp[-1]) if isinstance(shp, (list, tuple, np.ndarray)) else int(shp)

def embedding_dim_from_file() -> int | None:
    recs = load_all_embeddings()
    for r in recs:
        v = r.get("vector")
        if isinstance(v, list) and v:
            return len(v)
    return None


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--reindex", action="store_true")
    args = ap.parse_args()
    if args.reindex:
        reindex_all()
        print("Reindex complete:", EMB_PATH)
