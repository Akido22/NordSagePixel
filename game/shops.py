"""Лавки: что продаёт каждый торговец и какие вкладки у его окна (data/shops.toml)."""

from dataclasses import dataclass

from . import data, items


@dataclass(frozen=True)
class Shop:
    title: str
    stock: tuple  # id предметов; запас бесконечный
    tabs: tuple = ("buy", "sell")


TAB_NAMES = {"buy": "Купить", "sell": "Продать", "forge": "Ковать"}


def _load():
    result = {}
    for shop_id, sec in data.sections("shops.toml"):
        stock = sec.get("stock", list)
        items.check_ids(stock, sec.where("stock"))
        tabs = sec.get("tabs", list, ["buy", "sell"])
        for tab in tabs:
            if tab not in TAB_NAMES:
                raise data.DataError(f"{sec.where('tabs')}: вкладки «{tab}» нет; можно: buy, sell, forge")
        result[shop_id] = Shop(sec.get("title", str), tuple(stock), tuple(tabs))
        sec.check_unknown()
    return result


SHOPS = _load()
