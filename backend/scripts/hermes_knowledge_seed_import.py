from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import SessionLocal
from app.services.hermes_knowledge_seed_service import import_knowledge_seed


def main() -> None:
    db = SessionLocal()
    try:
        result = import_knowledge_seed(db)
        db.commit()
        print(f"imported {result['inserted_or_updated']} Hermes knowledge seed entries")
    finally:
        db.close()


if __name__ == "__main__":
    main()
