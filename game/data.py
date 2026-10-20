"""Загрузка игровых данных из TOML-файлов папки data/.

В коде остаётся только поведение; числа, названия, реплики и цены — в data/*.toml.
При ошибке в файле игра не запускается и пишет, в каком файле, разделе и поле беда.
"""

import os
import tomllib

from .config import ROOT_DIR

DATA_DIR = os.path.join(ROOT_DIR, "data")


class DataError(Exception):
    """Ошибка в файле данных — с понятным описанием места."""


def load(filename):
    path = os.path.join(DATA_DIR, filename)
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        raise DataError(f"нет файла data/{filename}") from None
    except tomllib.TOMLDecodeError as e:
        raise DataError(f"data/{filename}: ошибка разметки — {e}. Подсказка: текст пишется "
                        f"в кавычках \"...\", числа и true/false — без кавычек, "
                        f"у таблиц {{ }} и списков [ ] не должно быть лишних запятых") from None


class Section:
    """Раздел TOML с проверкой полей: section.get("hp", int) и т.п."""

    def __init__(self, filename, name, table):
        if not isinstance(table, dict):
            raise DataError(f"data/{filename}: [{name}] должен быть разделом")
        self.filename = filename
        self.name = name
        self.table = table
        self.used = set()

    def where(self, key=None):
        place = f"data/{self.filename} [{self.name}]"
        return f"{place} поле «{key}»" if key else place

    def get(self, key, kind, default=...):
        """Значение поля; kind — тип (int, float, str, bool, list, dict) или кортеж типов."""
        self.used.add(key)
        if key not in self.table:
            if default is ...:
                raise DataError(f"{self.where()}: нет обязательного поля «{key}»")
            return default
        value = self.table[key]
        if kind is float and isinstance(value, int) and not isinstance(value, bool):
            value = float(value)
        kinds = kind if isinstance(kind, tuple) else (kind,)
        if isinstance(value, bool) and bool not in kinds:
            raise DataError(f"{self.where(key)}: ожидается {_kind_name(kind)}, а записано {value!r}")
        if not isinstance(value, kinds):
            raise DataError(f"{self.where(key)}: ожидается {_kind_name(kind)}, а записано {value!r}")
        return value

    def check_unknown(self):
        """Неизвестные поля — почти всегда опечатка."""
        extra = set(self.table) - self.used
        if extra:
            names = ", ".join(f"«{k}»" for k in sorted(extra))
            raise DataError(f"{self.where()}: неизвестные поля {names} (опечатка?)")


def _kind_name(kind):
    names = {int: "целое число", float: "число", str: "строка", bool: "true/false",
             list: "список [..]", dict: "таблица {..}"}
    kinds = kind if isinstance(kind, tuple) else (kind,)
    return " или ".join(names.get(k, k.__name__) for k in kinds)


def sections(filename, table=None):
    """Все разделы файла по порядку: [(имя, Section), ...]."""
    table = load(filename) if table is None else table
    return [(name, Section(filename, name, value)) for name, value in table.items()]


def tint(sec, key):
    """Перекраска цветов: таблица {"4" = "8", ...} -> dict строк-шестнадцатеричных цифр."""
    value = sec.get(key, dict, {})
    for src, dst in value.items():
        for c in (src, str(dst)):
            if len(c) != 1 or c not in "0123456789abcdef":
                raise DataError(f"{sec.where(key)}: цвет должен быть одной цифрой 0-9 или a-f, а записано «{c}»")
    return {k: str(v) for k, v in value.items()}


def apply(cls, sec, mapping):
    """Переносит поля раздела в атрибуты класса: mapping {"поле": ("АТРИБУТ", тип)}."""
    for key, (attr, kind) in mapping.items():
        if key in sec.table:
            value = sec.get(key, kind)
            if attr == "silver" or isinstance(value, list):
                value = tuple(value)
            setattr(cls, attr, value)
        else:
            sec.used.add(key)
    sec.check_unknown()
