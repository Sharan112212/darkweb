"""
Pre-caches the Sentence-BERT (all-MiniLM-L6-v2) model weights locally
into the ./models/all-MiniLM-L6-v2 directory for true offline inference.

USAGE:
    python download_model.py
"""
import os
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
LOCAL_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models", "all-MiniLM-L6-v2")


def download_and_cache():
    print(f"[*] Pre-caching model '{MODEL_NAME}' to local path: {LOCAL_MODEL_DIR}")
    model = SentenceTransformer(MODEL_NAME)
    os.makedirs(LOCAL_MODEL_DIR, exist_ok=True)
    model.save(LOCAL_MODEL_DIR)
    print(f"[+] Model successfully saved locally at {LOCAL_MODEL_DIR}")


if __name__ == "__main__":
    download_and_cache()
