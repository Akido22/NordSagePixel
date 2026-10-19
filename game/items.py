"""База предметов."""

from dataclasses import dataclass, field

# Слоты экипировки в порядке отображения.
SLOTS = ["weapon", "shield", "helmet", "armor", "amulet"]
SLOT_NAMES = {
    "weapon": "Оружие",
    "shield": "Щит",
    "helmet": "Шлем",
    "armor": "Доспех",
    "amulet": "Оберег",
}


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    kind: str  # слот из SLOTS или "consumable"
    icon: str
    desc: str
    atk: int = 0
    defense: int = 0
    hp: int = 0
    heal: int = 0
    tint: dict = field(default_factory=dict)
    # Оружие: дальность удара (пикс.) и длительность замаха (кадры).
    reach: int = 0
    swing: int = 0
    # Щит: (обод, поле, умбон).
    shield_colors: tuple = (2, 4, 6)
    # Доспех: перекраска туловища героя; шлем: перекраска шлема.
    body_tint: dict = field(default_factory=dict)
    helmet_tint: dict = field(default_factory=dict)

    @property
    def stackable(self):
        return self.kind == "consumable"

    def stat_lines(self):
        lines = []
        if self.atk:
            lines.append(f"Атака +{self.atk}")
        if self.defense:
            lines.append(f"Защита +{self.defense}")
        if self.hp:
            lines.append(f"Здоровье +{self.hp}")
        if self.heal:
            lines.append(f"Лечит {self.heal}")
        if self.reach:
            speed = "быстрый" if self.swing <= 16 else "средний" if self.swing <= 22 else "медленный"
            lines.append(f"Удар: {speed}")
        return lines


ITEMS = {
    it.id: it
    for it in [
        Item("knife", "Охотничий нож", "weapon", "knife",
             "Простой нож из болотного железа.",
             atk=1, reach=12, swing=14),
        Item("sword", "Варяжский меч", "weapon", "sword",
             "Клинок, выменянный у заморских купцов.",
             atk=3, reach=16, swing=18),
        Item("axe", "Секира викинга", "weapon", "axe",
             "Тяжёлый топор северян. Рубит и щит, и шлем.",
             atk=5, reach=15, swing=26),
        Item("spear", "Рогатина", "weapon", "spear",
             "Копьё с перекладиной, с ним ходят на медведя.",
             atk=3, reach=24, swing=22),
        Item("shield_round", "Круглый щит", "shield", "shield",
             "Липовые доски, обтянутые кожей.",
             defense=1),
        Item("shield_red", "Червлёный щит", "shield", "shield",
             "Алый щит дружинника, окованный медью.",
             defense=2, tint={"4": "8", "2": "a", "6": "a"}, shield_colors=(10, 8, 10)),
        Item("cap", "Меховая шапка", "helmet", "cap",
             "Тёплая шапка с лисьей опушкой.",
             defense=1, helmet_tint={"6": "4", "a": "7", "1": "2"}),
        Item("shishak", "Шлем-шишак", "helmet", "helmet",
             "Островерхий шлем с наносником.",
             defense=2),
        Item("shirt", "Вышитая рубаха", "armor", "shirt",
             "Мать вышила обережный узор на вороте.",
             defense=0, hp=1, body_tint={"8": "7", "a": "8"}),
        Item("leather", "Кожаный доспех", "armor", "shirt",
             "Вываренная кожа в несколько слоёв.",
             defense=1, tint={"7": "4", "8": "2"}, body_tint={"8": "4", "a": "2"}),
        Item("mail", "Кольчуга", "armor", "shirt",
             "Тысячи стальных колец. Тяжела, но надёжна.",
             defense=3, tint={"7": "6", "8": "5"}, body_tint={"8": "6", "a": "5", "e": "6"}),
        Item("hammer", "Оберег-молот", "amulet", "hammer",
             "Знак громовержца. Рука бьёт крепче.",
             atk=1),
        Item("lunnitsa", "Лунница", "amulet", "lunnitsa",
             "Серебряный полумесяц, хранит от хвори.",
             hp=3),
        Item("honey", "Горшок мёда", "consumable", "honey",
             "Густой липовый мёд. Восстанавливает силы.",
             heal=5),
        Item("bread", "Каравай", "consumable", "bread",
             "Румяный хлеб в дорогу.",
             heal=2),
    ]
}


def get(item_id):
    return ITEMS[item_id]
