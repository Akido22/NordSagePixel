"""Сопоставление действий клавишам клавиатуры и геймпада."""

import pyxel

_BINDINGS = {
    "left": [pyxel.KEY_LEFT, pyxel.KEY_A, pyxel.GAMEPAD1_BUTTON_DPAD_LEFT],
    "right": [pyxel.KEY_RIGHT, pyxel.KEY_D, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT],
    "up": [pyxel.KEY_UP, pyxel.KEY_W, pyxel.GAMEPAD1_BUTTON_DPAD_UP],
    "down": [pyxel.KEY_DOWN, pyxel.KEY_S, pyxel.GAMEPAD1_BUTTON_DPAD_DOWN],
    "jump": [pyxel.KEY_SPACE, pyxel.KEY_Z, pyxel.KEY_K, pyxel.GAMEPAD1_BUTTON_A],
    "attack": [pyxel.KEY_X, pyxel.KEY_J, pyxel.GAMEPAD1_BUTTON_X],
    "block": [pyxel.KEY_C, pyxel.KEY_L, pyxel.GAMEPAD1_BUTTON_RIGHTSHOULDER],
    "roll": [pyxel.KEY_V, pyxel.KEY_SHIFT, pyxel.KEY_SEMICOLON, pyxel.GAMEPAD1_BUTTON_B],
    "heal": [pyxel.KEY_Q, pyxel.KEY_H, pyxel.GAMEPAD1_BUTTON_LEFTSHOULDER],
    "cast": [pyxel.KEY_F, pyxel.KEY_U, pyxel.GAMEPAD1_BUTTON_Y],
    "next_rune": [pyxel.KEY_E, pyxel.KEY_O, pyxel.GAMEPAD1_BUTTON_LEFTSTICK],
    "inventory": [pyxel.KEY_I, pyxel.KEY_TAB, pyxel.GAMEPAD1_BUTTON_BACK],
    "pause": [pyxel.KEY_ESCAPE, pyxel.KEY_P, pyxel.GAMEPAD1_BUTTON_START],
    # меню
    "confirm": [pyxel.KEY_RETURN, pyxel.KEY_KP_ENTER, pyxel.KEY_SPACE, pyxel.KEY_Z, pyxel.GAMEPAD1_BUTTON_A],
    "back": [pyxel.KEY_ESCAPE, pyxel.KEY_BACKSPACE, pyxel.KEY_X, pyxel.GAMEPAD1_BUTTON_B],
    "drop": [pyxel.KEY_R, pyxel.KEY_DELETE, pyxel.GAMEPAD1_BUTTON_Y],
}

_AXIS_DEAD = 12000


def held(action):
    if any(pyxel.btn(k) for k in _BINDINGS[action]):
        return True
    ax = pyxel.btnv(pyxel.GAMEPAD1_AXIS_LEFTX)
    ay = pyxel.btnv(pyxel.GAMEPAD1_AXIS_LEFTY)
    return (
        (action == "left" and ax < -_AXIS_DEAD)
        or (action == "right" and ax > _AXIS_DEAD)
        or (action == "up" and ay < -_AXIS_DEAD)
        or (action == "down" and ay > _AXIS_DEAD)
    )


def pressed(action, repeat=False):
    """Нажатие в этом кадре; repeat=True — автоповтор при удержании (для меню)."""
    hold, rep = (14, 5) if repeat else (0, 0)
    return any(pyxel.btnp(k, hold, rep) for k in _BINDINGS[action])


def released(action):
    return any(pyxel.btnr(k) for k in _BINDINGS[action])
