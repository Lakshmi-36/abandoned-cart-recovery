
import csv
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"

tables = [
    "customers",
    "consent_events",
    "sessions",
    "carts",
    "cart_lines",
    "cart_events",
    "campaigns",
    "message_templates",
    "campaign_templates",
    "campaign_carts",
    "send_attempts",
    "message_events",
    "orders",
    "order_lines",
    "order_events",
    "attributions",
]

results = {}
errors = []

for table in tables:
    csv_path = OUTPUT / f"{table}.csv"
    json_path = OUTPUT / f"{table}.json"

    if not csv_path.exists():
        errors.append(f"Missing CSV: {csv_path.name}")
        continue

    if not json_path.exists():
        errors.append(f"Missing JSON: {json_path.name}")
        continue

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        csv_count = sum(1 for _ in csv.DictReader(file))

    with json_path.open("r", encoding="utf-8-sig") as file:
        json_data = json.load(file)

    if isinstance(json_data, list):
        json_count = len(json_data)
    else:
        errors.append(f"Unexpected JSON structure: {json_path.name}")
        continue

    results[table] = {
        "csv_rows": csv_count,
        "json_rows": json_count,
        "counts_match": csv_count == json_count,
    }

    if csv_count != json_count:
        errors.append(f"CSV/JSON count mismatch: {table}")

summary = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "database": "abandoned_cart_full_db",
    "tables_checked": len(results),
    "total_csv_rows": sum(item["csv_rows"] for item in results.values()),
    "total_json_rows": sum(item["json_rows"] for item in results.values()),
    "table_results": results,
    "errors": errors,
    "result": "PASS" if not errors and len(results) == len(tables) else "FAIL",
}

summary_path = OUTPUT / "validation_summary.json"
summary_path.write_text(
    json.dumps(summary, indent=2),
    encoding="utf-8",
)

print(json.dumps({
    "summary_file": str(summary_path),
    "tables_checked": summary["tables_checked"],
    "total_csv_rows": summary["total_csv_rows"],
    "total_json_rows": summary["total_json_rows"],
    "result": summary["result"],
    "errors": errors,
}, indent=2))
