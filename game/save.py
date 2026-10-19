"""Сохранение и загрузка игры (JSON-файл в папке saves/)."""

import json
import os
import time

from .config import SAVE_DIR, SAVE_FILE

SAVE_VERSION = 2


def exists():
    return load() is not None


def write(data):
    """Атомарно записывает сохранение. Возвращает True при успехе."""
    payload = dict(data, version=SAVE_VERSION, saved_at=time.strftime("%d.%m.%Y %H:%M"))
    try:
        os.makedirs(SAVE_DIR, exist_ok=True)
        tmp = SAVE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SAVE_FILE)
        return True
    except OSError:
        return False


def load():
    """Читает сохранение; при отсутствии или порче файла возвращает None."""
    try:
        with open(SAVE_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("version") == 1:
        data = _migrate_v1(data)
    if data.get("version") != SAVE_VERSION:
        return None
    return data


def _migrate_v1(data):
    """Версия 1 знала только одну локацию — лесную тропу."""
    lvl = "test_level"
    return dict(
        data,
        version=2,
        level=lvl,
        collected=[f"{lvl}:{u}" for u in data.get("collected", [])],
        chests={f"{lvl}:{k}": v for k, v in data.get("chests", {}).items()},
        save_point=f"{lvl}:{data['runestone']}" if data.get("runestone") else None,
    )


def delete():
    try:
        os.remove(SAVE_FILE)
    except OSError:
        pass
