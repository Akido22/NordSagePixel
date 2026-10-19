"""Глобальные настройки игры."""

import os

GAME_TITLE = "Северная Сага"
SCREEN_W = 256
SCREEN_H = 192
FPS = 60
DISPLAY_SCALE = 3

TILE = 8

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE_DIR = os.path.join(ROOT_DIR, "saves")
SAVE_FILE = os.path.join(SAVE_DIR, "save.json")
LEVELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "levels")

# Палитра: землистые тона, северное небо, червлёный и золото.
PALETTE = [
    0x0B0B12,  # 0  почти чёрный (прозрачный в спрайтах)
    0x1A1C2C,  # 1  ночная синь / контур
    0x4A2F23,  # 2  тёмное дерево
    0x25402A,  # 3  хвоя
    0x8A5432,  # 4  дерево
    0x4E5A6A,  # 5  камень
    0x9AA6B2,  # 6  сталь
    0xECE3C9,  # 7  лён / пергамент
    0xA8322D,  # 8  червлёный
    0xD97A2B,  # 9  огонь
    0xE8C254,  # 10 золото
    0x5F8F3E,  # 11 мох
    0x3D6E9E,  # 12 фьорд
    0x6B5679,  # 13 сумерки
    0xE0A87A,  # 14 кожа
    0xF4F4F4,  # 15 снег
]

C_BLACK = 0
C_NIGHT = 1
C_DARKWOOD = 2
C_PINE = 3
C_WOOD = 4
C_STONE = 5
C_STEEL = 6
C_LINEN = 7
C_RED = 8
C_FIRE = 9
C_GOLD = 10
C_MOSS = 11
C_FJORD = 12
C_DUSK = 13
C_SKIN = 14
C_SNOW = 15
