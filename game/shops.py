"""Лавки: что продаёт каждый торговец и какие вкладки у его окна."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Shop:
    title: str
    stock: tuple  # id предметов; запас бесконечный
    tabs: tuple = ("buy", "sell")


TAB_NAMES = {"buy": "Купить", "sell": "Продать", "forge": "Ковать"}

SHOPS = {
    "merchant": Shop(
        "ЛАВКА ТОРВАЛЬДА",
        ("honey", "bread", "shield_round", "shield_red", "lunnitsa", "hammer"),
    ),
    "smith": Shop(
        "КУЗНИЦА ДОБРЫНИ",
        ("cap", "shishak", "leather", "mail", "sword", "spear", "ore"),
        tabs=("buy", "sell", "forge"),
    ),
}
