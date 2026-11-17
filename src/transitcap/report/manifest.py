"""Replication manifest: SHA-256 of every raw input, processed table, result, and source file."""

import datetime as dt
import hashlib
import json

from transitcap.paths import CONFIG, OUTPUTS, PROCESSED, RAW, REFERENCE, ROOT


def _sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write() -> dict:
    groups = {"raw": RAW, "reference": REFERENCE, "processed": PROCESSED,
              "results": OUTPUTS / "results", "config": CONFIG, "code": ROOT / "src"}
    out = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "files": {}}
    for name, base in groups.items():
        for p in sorted(base.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                out["files"][str(p.relative_to(ROOT))] = {"sha256": _sha(p), "bytes": p.stat().st_size}
    code = hashlib.sha256("".join(v["sha256"] for k, v in out["files"].items()
                                  if k.startswith("src/")).encode()).hexdigest()
    data = hashlib.sha256("".join(v["sha256"] for k, v in out["files"].items()
                                  if k.startswith("data/raw/")).encode()).hexdigest()
    out["code_hash"], out["raw_data_hash"] = code, data
    (OUTPUTS / "manifest.json").write_text(json.dumps(out, indent=2))
    return out
