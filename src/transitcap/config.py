"""Pre-analysis plan loading and freezing.

`freeze()` records the SHA-256 of config/pap.yaml in config/pap.lock. `require_frozen()` is called
before any step that touches outcome contrasts; it fails if the plan was edited after freezing.
"""

import datetime as dt
import hashlib
import json

import yaml

from transitcap.paths import CONFIG

PAP = CONFIG / "pap.yaml"
LOCK = CONFIG / "pap.lock"


class PlanNotFrozen(RuntimeError):
    pass


def load_pap() -> dict:
    return yaml.safe_load(PAP.read_text())


def _digest() -> str:
    return hashlib.sha256(PAP.read_bytes()).hexdigest()


def freeze() -> str:
    if LOCK.exists():
        lock = json.loads(LOCK.read_text())
        if lock["sha256"] != _digest():
            raise PlanNotFrozen("pap.yaml differs from the frozen plan; record a decision in "
                                "docs/decisions/ and re-freeze deliberately with --force")
        return lock["sha256"]
    LOCK.write_text(json.dumps({"sha256": _digest(),
                                "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat()}, indent=2))
    return _digest()


def refreeze(reason: str) -> str:
    """Re-freeze after a recorded deviation. The reason is appended to the lock's history."""
    old = json.loads(LOCK.read_text()) if LOCK.exists() else {}
    history = old.get("history", []) + ([{"sha256": old["sha256"], "frozen_at": old["frozen_at"],
                                          "replaced_because": reason}] if old else [])
    LOCK.write_text(json.dumps({"sha256": _digest(),
                                "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                                "history": history}, indent=2))
    return _digest()


def require_frozen() -> dict:
    if not LOCK.exists():
        raise PlanNotFrozen("Run `transitcap freeze` before estimation.")
    if json.loads(LOCK.read_text())["sha256"] != _digest():
        raise PlanNotFrozen("config/pap.yaml changed after it was frozen.")
    return load_pap()
