"""Жители: облик и реплики. Расставляются в разделе [npcs] файла уровня."""

from dataclasses import dataclass, field
from types import SimpleNamespace

HERO_NAME = "Ратмир"


def look(torso="hero_torso_plain", torso_tint=None, head="hero_head_male", head_tint=None,
         helmet=None, helmet_tint=None, legs_tint=None):
    """Облик жителя: слои спрайтов с перекраской (см. sprites.py)."""
    layers = [("hero_legs", legs_tint), (torso, torso_tint), (head, head_tint)]
    if helmet:
        layers.append((helmet, helmet_tint))
    return tuple(layers)


@dataclass(frozen=True)
class NpcDef:
    name: str
    lines: list
    look: tuple = field(default_factory=look)
    held: object = None  # предмет в руке (как оружие героя)
    facing: int = 1
    shop: str = None  # id лавки из shops.py, если житель торгует


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
        look=look("hero_torso_dress", {"8": "c", "a": "a"}, head_tint={"a": "6"}),
    ),
    "smith": NpcDef(
        "Кузнец Добрыня",
        [
            "Мой молот не знает отдыха ни днём, ни ночью.",
            "Нож - не оружие для витязя. Говорят, в лесу есть сундук с добрым мечом.",
            "Принеси железные крицы - драугры таскают их с собой. Перекую твой клинок, станет злее.",
        ],
        look=look("hero_torso_leather", head_tint={"a": "2"}),
        held=SMITH_HAMMER,
        facing=-1,
        shop="smith",
    ),
    "merchant": NpcDef(
        "Купец Торвальд",
        [
            "Хейль, друг! Я Торвальд, приплыл из Бирки по рекам.",
            "Мёд, хлеб, щиты, обереги - всё за честное серебро. Куплю и твоё добро.",
            "Погибнешь - серебро останется там, где упал. Вернись за ним, пока не поздно.",
        ],
        look=look("hero_torso_shirt", {"7": "c", "8": "a"}, head_tint={"a": "9"}, helmet="hero_helmet_cap", legs_tint={"5": "c"}),
        shop="merchant",
    ),
    "herbalist": NpcDef(
        "Травница Млада",
        [
            "Травы в лесу нынче шепчут тревожно...",
            "Настой зверобоя вернёт силу чар. А руна Беркана заживит раны - только твори её не под ударом.",
            f"Береги себя, {HERO_NAME}.",
        ],
        look=look("hero_torso_dress", {"8": "b", "a": "7"}, head="hero_head_female"),
        shop="herbalist",
        facing=-1,
    ),
    "guard": NpcDef(
        "Стражник Ярополк",
        [
            "За воротами - Лесная тропа. Дальше начинается глушь.",
            "Подойди к воротам и нажми вверх, чтобы выйти из города.",
            "Держи щит повыше, витязь.",
        ],
        look=look("hero_torso_mail", head_tint={"a": "4"}, helmet="hero_helmet_shishak"),
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
            "F - чары выученной руны, E - сменить руну. Синяя полоса - твоя мана.",
        ],
        look=look("hero_torso_shirt", {"7": "8", "8": "a"}, head_tint={"a": "5"}, helmet="hero_helmet_shishak"),
        held=SimpleNamespace(icon="sword", tint={}),
    ),
}

NPC_INDEX = {npc_id: i for i, npc_id in enumerate(NPCS)}
