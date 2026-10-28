
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"

files = [
    ROOT / "config" / "project_config.json",
    ROOT / "docs" / "data_dictionary.md",
    ROOT / "README.md",
    ROOT / "requirements.txt",
    OUTPUT / "source_manifest.json",
    OUTPUT / "validation_summary.json",
    OUTPUT / "database_seed.sql",
]

files.extend(sorted(OUTPUT.glob("*.csv")))
files.extend(sorted(OUTPUT.glob("*.json")))

checksum_path = OUTPUT / "reproducibility_checksums.sha256"
results = []
missing = []

for path in files:
    if not path.is_file():
        missing.append(str(path.relative_to(ROOT)))
        continue

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    results.append(f"{digest.hexdigest()}  {path.relative_to(ROOT).as_posix()}")

checksum_path.write_text("\n".join(results) + "\n", encoding="utf-8")

print(f"Checksum file: {checksum_path}")
print(f"Files hashed: {len(results)}")

if missing:
    print("Missing files:")
    for name in missing:
        print(f"- {name}")
else:
    print("All requested files were found.")
