"""Северная Сага — платформер на Pyxel. Запуск: python main.py"""

import sys

from game.data import DataError

if __name__ == "__main__":
    try:
        from game.app import App
        App().run()
    except DataError as e:
        print("Ошибка в файлах данных:", e, file=sys.stderr)
        sys.exit(1)
