"""Esporta la specifica OpenAPI dell'app in docs/openapi.json."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app

output_path = Path(__file__).parent.parent / "docs" / "openapi.json"
output_path.parent.mkdir(parents=True, exist_ok=True)

schema = app.openapi()

output_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"OpenAPI spec salvata in {output_path}")
print(f"Endpoint trovati: {list(schema.get('paths', {}).keys())}")
