"""Общие вещи: конфиг, секреты, хранилище состояния."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "data.json"   # GitHub Pages отдаёт его дашборду


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def env(name: str, default: str | None = None, required: bool = False) -> str | None:
    val = os.environ.get(name) or default  # пустая переменная GitHub = не задана
    if required and not val:
        raise SystemExit(f"Не задан секрет {name}. Добавь его в Settings → Secrets → Actions.")
    return val


DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_state() -> dict:
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    else:
        state = {}
    state.setdefault("posts", [])
    state.setdefault("account_history", [])
    state.setdefault("telegram_history", [])
    state.setdefault("tg_update_offset", 0)
    state.setdefault("errors", [])
    return state


def save_state(state: dict) -> None:
    state["updated_at"] = now_iso()
    state["errors"] = state["errors"][-30:]
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def log_error(state: dict, where: str, err: Exception | str) -> None:
    msg = f"{where}: {err}"
    print("ERROR", msg)
    state["errors"].append({"at": now_iso(), "msg": msg[:500]})
