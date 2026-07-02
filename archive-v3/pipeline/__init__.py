# Parker Pipeline — shared constants and helpers
import os
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
STRUCT_DIR = DATA_DIR / "structured"
DB_PATH = DATA_DIR / "parker.db"

PHASES = ["fetch", "structure", "store", "analyze"]
STATUSES = ["pending", "running", "done", "failed", "skipped"]
