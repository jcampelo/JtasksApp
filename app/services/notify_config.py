import glob
import json
import os

_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "configs")
os.makedirs(_CONFIG_DIR, exist_ok=True)

# Migra config.json antigo (global) para o formato por usuário
_OLD_CONFIG = os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
if os.path.exists(_OLD_CONFIG):
    try:
        with open(_OLD_CONFIG, "r", encoding="utf-8") as f:
            _old = json.load(f)
        uid = _old.get("user_id")
        if uid:
            _new_path = os.path.join(_CONFIG_DIR, f"notify_{uid}.json")
            if not os.path.exists(_new_path):
                with open(_new_path, "w", encoding="utf-8") as f:
                    json.dump(_old, f, ensure_ascii=False, indent=2)
        os.rename(_OLD_CONFIG, _OLD_CONFIG + ".migrated")
    except Exception:
        pass


def _user_path(user_id: str) -> str:
    return os.path.join(_CONFIG_DIR, f"notify_{user_id}.json")


def load_config(user_id: str) -> dict:
    path = _user_path(user_id)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg: dict, user_id: str) -> None:
    path = _user_path(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_all_configs() -> list[dict]:
    """Retorna todas as configs de usuários (para o scheduler)."""
    configs = []
    for path in glob.glob(os.path.join(_CONFIG_DIR, "notify_*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                configs.append(json.load(f))
        except Exception:
            continue
    return configs
