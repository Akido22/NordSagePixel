"""Приложение: инициализация Pyxel и переключение сцен."""

import pyxel

from . import audio, font, gfx, sprites
from .config import DISPLAY_SCALE, FPS, GAME_TITLE, PALETTE, SCREEN_H, SCREEN_W


class App:
    def __init__(self):
        pyxel.init(SCREEN_W, SCREEN_H, title=GAME_TITLE, fps=FPS,
                   quit_key=pyxel.KEY_NONE, display_scale=DISPLAY_SCALE)
        pyxel.colors[:] = PALETTE
        font.init()
        gfx.init()
        sprites.init()
        audio.init()
        from .scenes import TitleScene
        self.scene = TitleScene(self)

    def set_scene(self, scene):
        self.scene = scene

    def update(self):
        if pyxel.btnp(pyxel.KEY_M):
            audio.toggle_music()
        self.scene.update()

    def draw(self):
        self.scene.draw()

    def run(self):
        pyxel.run(self.update, self.draw)
