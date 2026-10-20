"""
Конфигурация приложения — Password Manager.
"""

import sys
from pathlib import Path


def _is_frozen() -> bool:
    """Запущено ли приложение как собранный PyInstaller EXE."""
    return bool(getattr(sys, 'frozen', False))


def _bundle_dir() -> Path:
    """
    Каталог с ресурсами, упакованными в EXE.

    В onefile-режиме PyInstaller распаковывает данные во временную папку
    sys._MEIPASS, а не рядом с исполняемым файлом.
    """
    if _is_frozen():
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def _data_dir() -> Path:
    """Каталог для пользовательских данных (рядом с EXE или с проектом)."""
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


# Пути к файлам
BASE_DIR = _data_dir()
PASSWORDS_JSON = BASE_DIR / "passwords.json"
LOG_FILE = BASE_DIR / "password_manager.log"
STATIC_DIR = _bundle_dir() / "static"
ICON_PATH = _bundle_dir() / "assets" / "icon.ico"

# Настройки приложения.
# Слушаем только localhost: менеджер паролей не должен быть доступен из сети.
HOST = "127.0.0.1"
PORT = 8062
