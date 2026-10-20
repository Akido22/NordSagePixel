"""Сума (инвентарь), снаряжение и показатели героя: уровень, опыт, очки, улучшения оружия."""

from . import items

BAG_COLS = 6
BAG_ROWS = 4
BAG_SIZE = BAG_COLS * BAG_ROWS
MAX_STACK = 9

BASE_HP = 10
BASE_ATK = 1
BASE_DEF = 0
BASE_STAMINA = 100

MAX_LEVEL = 20
# Сколько даёт одно очко в показатель.
STAT_HP = 2
STAT_ATK = 1
STAT_STAMINA = 12
STATS = ["str", "sta", "vit"]
STAT_NAMES = {"str": "Сила", "sta": "Стойкость", "vit": "Здоровье"}
STAT_HINTS = {"str": f"атака +{STAT_ATK}", "sta": f"силы +{STAT_STAMINA}", "vit": f"жизнь +{STAT_HP}"}

MAX_UPGRADE = 3
UPGRADE_COST = {1: (15, 1), 2: (30, 2), 3: (50, 3)}  # уровень -> (серебро, крицы)


def xp_needed(level):
    """Сколько опыта нужно, чтобы перейти с уровня level на следующий."""
    return 20 + 15 * (level - 1)


class Inventory:
    def __init__(self):
        self.bag = [None] * BAG_SIZE  # каждый элемент: [item_id, count] или None
        self.equipment = {slot: None for slot in items.SLOTS}
        self.silver = 0
        self.level = 1
        self.xp = 0
        self.points = 0
        self.stats = {s: 0 for s in STATS}
        self.upgrades = {}  # id оружия -> уровень заточки (+1..+3)

    # ------------------------------------------------------------ сума
    def add(self, item_id, count=1):
        """Кладёт предмет в суму. Возвращает False, если места нет."""
        item = items.get(item_id)
        if item.stackable:
            for cell in self.bag:
                if cell and cell[0] == item_id and cell[1] + count <= MAX_STACK:
                    cell[1] += count
                    return True
        for i, cell in enumerate(self.bag):
            if cell is None:
                self.bag[i] = [item_id, count]
                return True
        return False

    def remove_at(self, index, count=1):
        cell = self.bag[index]
        if cell is None:
            return
        cell[1] -= count
        if cell[1] <= 0:
            self.bag[index] = None

    def item_at(self, index):
        cell = self.bag[index]
        return items.get(cell[0]) if cell else None

    def count_at(self, index):
        cell = self.bag[index]
        return cell[1] if cell else 0

    def first_consumable(self):
        """Индекс самого слабого лечащего предмета (чтобы зря не тратить мёд)."""
        best = None
        for i, cell in enumerate(self.bag):
            if cell:
                item = items.get(cell[0])
                if item.heal and (best is None or item.heal < self.item_at(best).heal):
                    best = i
        return best

    # ------------------------------------------------------------ снаряжение
    def equipped(self, slot):
        item_id = self.equipment.get(slot)
        return items.get(item_id) if item_id else None

    def equip_from_bag(self, index):
        """Надевает предмет из сумы; снятый предмет встаёт на его место."""
        item = self.item_at(index)
        if item is None or item.kind not in self.equipment:
            return False
        previous = self.equipment[item.kind]
        self.equipment[item.kind] = item.id
        self.bag[index] = [previous, 1] if previous else None
        return True

    def unequip(self, slot):
        item_id = self.equipment.get(slot)
        if not item_id:
            return False
        for i, cell in enumerate(self.bag):
            if cell is None:
                self.bag[i] = [item_id, 1]
                self.equipment[slot] = None
                return True
        return False

    def count_of(self, item_id):
        return sum(c[1] for c in self.bag if c and c[0] == item_id)

    def take(self, item_id, count):
        """Забирает count штук предмета из сумы (с разных ячеек). False — если не хватает."""
        if self.count_of(item_id) < count:
            return False
        for i, cell in enumerate(self.bag):
            while cell and cell[0] == item_id and count > 0:
                self.remove_at(i)
                count -= 1
                cell = self.bag[i]
        return True

    # ------------------------------------------------------------ опыт и уровни
    def add_xp(self, amount):
        """Начисляет опыт. Возвращает число полученных уровней."""
        gained = 0
        self.xp += amount
        while self.level < MAX_LEVEL and self.xp >= xp_needed(self.level):
            self.xp -= xp_needed(self.level)
            self.level += 1
            self.points += 1
            gained += 1
        return gained

    def spend_point(self, stat):
        if self.points <= 0 or stat not in self.stats:
            return False
        self.points -= 1
        self.stats[stat] += 1
        return True

    # ------------------------------------------------------------ заточка оружия
    def upgrade_level(self, item_id):
        return self.upgrades.get(item_id, 0)

    def item_name(self, item):
        lvl = self.upgrade_level(item.id) if item.kind == "weapon" else 0
        return f"{item.name} +{lvl}" if lvl else item.name

    def item_atk(self, item):
        return item.atk + (self.upgrade_level(item.id) if item.kind == "weapon" else 0)

    def upgrade_cost(self, item_id):
        lvl = self.upgrade_level(item_id)
        return UPGRADE_COST.get(lvl + 1)

    def upgrade(self, item_id):
        """Заточить оружие на +1. Возвращает текст ошибки или None при успехе."""
        cost = self.upgrade_cost(item_id)
        if cost is None:
            return "Лучше уже не выковать"
        silver, ore = cost
        if self.silver < silver:
            return "Не хватает серебра"
        if self.count_of("ore") < ore:
            return "Не хватает криц"
        self.silver -= silver
        self.take("ore", ore)
        self.upgrades[item_id] = self.upgrade_level(item_id) + 1
        return None

    # ------------------------------------------------------------ показатели
    def _sum(self, attr):
        return sum(getattr(it, attr) for it in (self.equipped(s) for s in items.SLOTS) if it)

    @property
    def max_hp(self):
        return BASE_HP + self._sum("hp") + self.stats["vit"] * STAT_HP

    @property
    def attack(self):
        weapon = self.equipped("weapon")
        bonus = self.upgrade_level(weapon.id) if weapon else 0
        return BASE_ATK + self._sum("atk") + bonus + self.stats["str"] * STAT_ATK

    @property
    def max_stamina(self):
        return BASE_STAMINA + self.stats["sta"] * STAT_STAMINA

    @property
    def defense(self):
        return BASE_DEF + self._sum("defense")

    # ------------------------------------------------------------ сохранение
    def to_dict(self):
        return {"bag": self.bag, "equipment": self.equipment, "silver": self.silver,
                "level": self.level, "xp": self.xp, "points": self.points,
                "stats": self.stats, "upgrades": self.upgrades}

    @classmethod
    def from_dict(cls, data):
        inv = cls()
        for i, cell in enumerate(data.get("bag", [])[:BAG_SIZE]):
            if cell and cell[0] in items.ITEMS:
                inv.bag[i] = [cell[0], int(cell[1])]
        for slot, item_id in data.get("equipment", {}).items():
            if slot in inv.equipment and item_id in items.ITEMS:
                inv.equipment[slot] = item_id
        inv.silver = int(data.get("silver", 0))
        inv.level = max(1, int(data.get("level", 1)))
        inv.xp = int(data.get("xp", 0))
        inv.points = int(data.get("points", 0))
        for stat, value in data.get("stats", {}).items():
            if stat in inv.stats:
                inv.stats[stat] = int(value)
        inv.upgrades = {k: min(MAX_UPGRADE, int(v)) for k, v in data.get("upgrades", {}).items()
                        if k in items.ITEMS}
        return inv

    @classmethod
    def starting(cls):
        inv = cls()
        inv.equipment["weapon"] = "knife"
        inv.equipment["armor"] = "shirt"
        inv.add("bread", 2)
        return inv
