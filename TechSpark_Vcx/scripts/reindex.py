"""Build the local MiniLM/Chroma legal index from the curated corpus."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.retrieval import LocalRetriever
from app.settings import settings

if __name__ == "__main__":
    count = LocalRetriever(settings).reindex()
    print(f"Indexed {count} legal sections into {settings.chroma_path}")
