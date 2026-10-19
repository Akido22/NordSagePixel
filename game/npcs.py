"""Жители: облик и реплики. Расставляются в разделе [npcs] файла уровня."""

from dataclasses import dataclass, field
from types import SimpleNamespace

HERO_NAME = "Ратмир"


@dataclass(frozen=True)
class NpcDef:
    name: str
    lines: list
    base_tint: dict = field(default_factory=dict)
    body_tint: dict = field(default_factory=dict)
    female: bool = False
    helmet: bool = False
    helmet_tint: dict = field(default_factory=dict)
    held: object = None  # предмет в руке (как оружие героя)
    facing: int = 1


SMITH_HAMMER = SimpleNamespace(icon="hammer", tint={"a": "5", "6": "6"})
GUARD_SPEAR = SimpleNamespace(icon="spear", tint={})

NPCS = {
    "elder": NpcDef(
        "Старейшина Всеслав",
        [
            f"А, {HERO_NAME}! Добро пожаловать на площадь Велеграда.",
            "Это Стела Предков. Поклонись ей - и предки запомнят твой путь.",
            "За восточными воротами завелись волки, а у старых камней бродят драугры.",
            "Ступай туда, витязь. Кузнец и купец помогут собраться в дорогу.",
        ],
        base_tint={"a": "6"},
        body_tint={"8": "c", "a": "a"},
    ),
    "smith": NpcDef(
        "Кузнец Добрыня",
        [
            "Мой молот не знает отдыха ни днём, ни ночью.",
            "Нож - не оружие для витязя. Говорят, в лесу есть сундук с добрым мечом.",
            "Будет серебро - приходи. Скую тебе и шлем, и кольчугу.",
        ],
        base_tint={"a": "2"},
        body_tint={"8": "4", "a": "2"},
        held=SMITH_HAMMER,
        facing=-1,
    ),
    "merchant": NpcDef(
        "Купец Торвальд",
        [
            "Хейль, друг! Я Торвальд, приплыл из Бирки по рекам.",
            "Мёд, хлеб, меха... Торговать начнём, как только разберу товар.",
            "Серебро в лесу не валяется. Хотя... может, и валяется.",
        ],
        base_tint={"a": "9"},
        body_tint={"8": "c", "a": "a"},
        helmet=True,
        helmet_tint={"6": "4", "a": "7", "1": "2"},
    ),
    "herbalist": NpcDef(
        "Травница Млада",
        [
            "Травы в лесу нынче шепчут тревожно...",
            "Мёд лечит лучше хлеба. В пути нажми Q, чтобы подкрепиться.",
            f"Береги себя, {HERO_NAME}.",
        ],
        base_tint={"a": "a"},
        body_tint={"8": "b", "a": "7"},
        female=True,
        facing=-1,
    ),
    "guard": NpcDef(
        "Стражник Ярополк",
        [
            "За воротами - Лесная тропа. Дальше начинается глушь.",
            "Подойди к воротам и нажми вверх, чтобы выйти из города.",
            "Держи щит повыше, витязь.",
        ],
        base_tint={"a": "4"},
        body_tint={"8": "6", "a": "5", "e": "6"},
        helmet=True,
        held=GUARD_SPEAR,
        facing=-1,
    ),
    "trainer": NpcDef(
        "Воевода Свенельд",
        [
            "Хочешь выжить за воротами - учись здесь, на чучелах.",
            "X - удар. Жми чаще - выйдет серия из трёх. Держи X - сильный удар, он ломает щиты.",
            "C - щит. Блок тратит силы - следи за зелёной полосой под жизнью.",
            "Подними щит прямо перед вражьим ударом - это парирование. Оглушённого бей - удар будет страшен.",
            "V - перекат. Пока катишься, вражий клинок тебя не тронет.",
            "В прыжке жми вниз и удар - обрушишься на врага сверху.",
        ],
        base_tint={"a": "5"},
        body_tint={"8": "8", "a": "a"},
        helmet=True,
        held=SimpleNamespace(icon="sword", tint={}),
    ),
}

NPC_INDEX = {npc_id: i for i, npc_id in enumerate(NPCS)}
