"""
Модуль для работы с файлами данных (JSON).
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.config import PASSWORDS_JSON, STATIC_DIR

logger = logging.getLogger(__name__)


def read_json_file(filepath: Path) -> List[Dict[str, Any]]:
    """
    Читает JSON файл и возвращает список словарей.
    """
    try:
        if not filepath.exists():
            return []

        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {filepath}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error reading {filepath}: {e}")
        return []


def save_json_file(filepath: Path, data: List[Dict[str, Any]]) -> bool:
    """
    Сохраняет данные в JSON файл.
    """
    try:
        temp_path = filepath.with_suffix(f"{filepath.suffix}.tmp")
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, filepath)

        logger.debug(f"Successfully saved {len(data)} entries to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Error saving to {filepath}: {e}")
        return False


# ========== Работа с passwords.json (менеджер паролей) ==========

def read_passwords_file() -> List[Dict[str, Any]]:
    """Читает файл с зашифрованными паролями."""
    return read_json_file(PASSWORDS_JSON)


def save_passwords_file(data: List[Dict[str, Any]]) -> bool:
    """Сохраняет файл с паролями."""
    return save_json_file(PASSWORDS_JSON, data)


def initialize_files():
    """
    Инициализирует необходимые файлы, если они отсутствуют.
    """
    if not PASSWORDS_JSON.exists():
        if save_passwords_file([]):
            logger.info(f"Created empty {PASSWORDS_JSON}")

    if not STATIC_DIR.exists():
        logger.warning(f"Static directory not found: {STATIC_DIR}")
