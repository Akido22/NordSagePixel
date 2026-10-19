"""Звуковые эффекты и фоновая музыка (синтез средствами Pyxel)."""

import pyxel

SFX_CHANNEL = 3

JUMP = 0
SWING = 1
HIT = 2
HURT = 3
COIN = 4
MOVE = 5
SELECT = 6
SAVE = 7
CHEST = 8
DEATH = 9
KILL = 10
DENY = 11
HEAL = 12

_SFX = {
    JUMP: ("c2e2g2", "p", "4", "s", 4),
    SWING: ("a3f3d3", "n", "432", "f", 3),
    HIT: ("c2a1", "n", "65", "f", 5),
    HURT: ("g1d1c1", "s", "654", "f", 6),
    COIN: ("e3b3e4", "p", "4", "n", 4),
    MOVE: ("a3", "p", "3", "n", 4),
    SELECT: ("c3g3c4", "p", "4", "n", 5),
    SAVE: ("d3f3a3d4a3d4", "t", "5", "vvvvvf", 10),
    CHEST: ("g2b2d3g3", "p", "4", "n", 6),
    DEATH: ("a2e2c2a1f1d1", "s", "6", "nnnnnf", 14),
    KILL: ("c2g1c1", "n", "64", "f", 6),
    DENY: ("c2c2", "s", "3", "n", 6),
    HEAL: ("c3e3g3c4", "t", "4", "n", 6),
}

# Музыка: дорийский лад от ре — напев в духе северных гуслей.
_MELODY = (
    "d3rf3g3 a3rrr g3f3e3c3 d3rrr "
    "f3g3a3c4 d4rc4a3 g3a3g3e3 d3rrr "
    "a3ra3g3 f3rg3a3 b3a3g3e3 f3rrr "
    "d4c4a3g3 f3g3e3c3 d3rd3r d3rrr"
)
_BASS = (
    "d1rd1r d1ra1r c1rc1r g0rg0r "
    "f1rf1r c1rc1r g0rg0r d1rd1r "
    "f1rf1r d1rd1r e1re1r a0ra0r "
    "b0rb0r c1rc1r d1rd1r d1rrr"
)
_DRONE = "d2rrr " * 16

# Городской напев: неторопливый, «гусельный» (щипок с затуханием).
_TOWN_MELODY = (
    "d3rf3a3 c4ra3r g3f3g3a3 f3rrr "
    "a3rc4d4 e4rd4c4 a3rg3f3 g3rrr "
    "f3rg3a3 c4rd4c4 a3g3f3e3 d3rrr "
    "c3re3g3 a3rg3e3 f3e3d3c3 d3rrr"
)
_TOWN_BASS = (
    "d1rrr d1rrr f1rrr f1rrr "
    "a0rrr a0rrr c1rrr c1rrr "
    "f1rrr f1rrr d1rrr d1rrr "
    "c1rrr c1rrr d1rrr d1rrr"
)

FOREST = 0
TOWN = 1


def init():
    for idx, (notes, tones, volumes, effects, speed) in _SFX.items():
        pyxel.sounds[idx].set(notes, tones, volumes, effects, speed)
    pyxel.sounds[20].set(_MELODY, "t", "4", "n", 18)
    pyxel.sounds[21].set(_BASS, "s", "2", "n", 18)
    pyxel.sounds[22].set(_DRONE, "t", "2", "f", 18)
    pyxel.musics[FOREST].set([20], [21], [22])
    pyxel.sounds[23].set(_TOWN_MELODY, "t", "5", "f", 22)
    pyxel.sounds[24].set(_TOWN_BASS, "t", "3", "f", 22)
    pyxel.musics[TOWN].set([23], [24], [])


def sfx(idx):
    pyxel.play(SFX_CHANNEL, idx)


_current = None
music_enabled = True


def music_start(track=None):
    """Включает трек (по умолчанию — последний игравший); тот же трек не перезапускается."""
    global _current
    track = _current if track is None else track
    if track is None:
        track = FOREST
    if not music_enabled:
        _current = track
        return
    if _current != track or not pyxel.play_pos(0):
        pyxel.playm(track, loop=True)
    _current = track


def music_stop():
    for ch in range(3):
        pyxel.stop(ch)


def toggle_music():
    global music_enabled
    music_enabled = not music_enabled
    if music_enabled:
        pyxel.playm(_current or FOREST, loop=True)
    else:
        music_stop()
