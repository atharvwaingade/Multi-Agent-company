"""
Vector memory — semantic search over prior generated code.

sentence-transformers and faiss are OPTIONAL. If not installed, or if the
model can't be downloaded (no internet), all functions become silent no-ops
so the rest of the pipeline continues unaffected.

The embedding model is loaded LAZILY on first use. If the model files are
already cached locally (~/.cache/huggingface) it works fully offline.
If they're not cached and there's no internet, it logs a warning and
disables itself for the session — no crash, no hang.
"""

import os
import pickle
from pathlib import Path
from utils.logger import Logger

_THIS_DIR  = Path(__file__).parent
INDEX_FILE = str(_THIS_DIR / "vector.index")
DATA_FILE  = str(_THIS_DIR / "vector_data.pkl")

_model            = None
_deps_available   = None   # None = not yet checked
_model_available  = None   # None = not yet tried to load


def _check_deps() -> bool:
    global _deps_available
    if _deps_available is not None:
        return _deps_available
    try:
        import sentence_transformers  # noqa: F401
        import faiss                  # noqa: F401
        import numpy                  # noqa: F401
        _deps_available = True
    except ImportError as exc:
        Logger.log("MEMORY", f"⚠️  Vector memory disabled — missing packages: {exc}")
        Logger.log("MEMORY", "   Run: pip install sentence-transformers faiss-cpu numpy")
        _deps_available = False
    return _deps_available


def _get_model():
    """
    Load the embedding model. Returns None if unavailable (no internet,
    not cached, or load error) — callers must check for None.
    """
    global _model, _model_available

    if _model_available is False:
        return None          # already failed this session, don't retry
    if _model is not None:
        return _model        # already loaded

    try:
        from sentence_transformers import SentenceTransformer
        import socket

        model_name = "all-MiniLM-L6-v2"
        Logger.log("MEMORY", f"Loading embedding model '{model_name}'...")

        # Check if model is cached locally before attempting network load
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        is_cached = any(model_name.replace("/", "--") in str(p) for p in cache_dir.rglob("*")) \
                    if cache_dir.exists() else False

        if not is_cached:
            # Quick connectivity check — don't hang for 30s on no-internet
            try:
                socket.setdefaulttimeout(3)
                socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(
                    ("huggingface.co", 443)
                )
            except (socket.error, OSError):
                Logger.log("MEMORY", "⚠️  Vector memory disabled — model not cached and no internet")
                Logger.log("MEMORY", "   To enable: connect to internet once so the model downloads (~90MB)")
                Logger.log("MEMORY", "   Or pre-cache: python -c \"from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')\"")
                _model_available = False
                return None

        _model = SentenceTransformer(model_name)
        _model_available = True
        Logger.log("MEMORY", "✅ Embedding model ready")
        return _model

    except Exception as exc:
        Logger.log("MEMORY", f"⚠️  Could not load embedding model: {exc}")
        Logger.log("MEMORY", "   Vector memory disabled for this session")
        _model_available = False
        return None


def load_index():
    import faiss
    if os.path.exists(INDEX_FILE) and os.path.exists(DATA_FILE):
        try:
            index = faiss.read_index(INDEX_FILE)
            with open(DATA_FILE, "rb") as f:
                data = pickle.load(f)
            return index, data
        except Exception as exc:
            Logger.log("MEMORY", f"⚠️  Corrupt index, starting fresh: {exc}")
    return faiss.IndexFlatL2(384), []


def save_index(index, data):
    import faiss
    os.makedirs(os.path.dirname(INDEX_FILE) or ".", exist_ok=True)
    faiss.write_index(index, INDEX_FILE)
    with open(DATA_FILE, "wb") as f:
        pickle.dump(data, f)


def add_vector_memory(text: str, code: str) -> None:
    if not _check_deps():
        return
    model = _get_model()
    if model is None:
        return
    try:
        import numpy as np
        index, data = load_index()
        embedding   = model.encode([text])
        index.add(np.array(embedding, dtype="float32"))
        data.append({"text": text, "code": code})
        save_index(index, data)
    except Exception as exc:
        Logger.log("MEMORY", f"⚠️  add_vector_memory failed: {exc}")


def search_similar(query: str, k: int = 3) -> list:
    if not _check_deps():
        return []
    model = _get_model()
    if model is None:
        return []
    try:
        import numpy as np
        index, data = load_index()
        if not data:
            return []
        query_vec = model.encode([query])
        D, I      = index.search(np.array(query_vec, dtype="float32"), min(k, len(data)))
        return [data[i] for i in I[0] if 0 <= i < len(data)]
    except Exception as exc:
        Logger.log("MEMORY", f"⚠️  search_similar failed: {exc}")
        return []
