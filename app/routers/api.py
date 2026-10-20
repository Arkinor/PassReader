"""
REST API роутеры для Password Manager.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.storage import read_passwords_file, save_passwords_file
from app.crypto import derive_key, decrypt_password_item, encrypt_password_item
from app.models import PasswordDelete

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])


def _get_key_bytes(request: Request) -> bytes:
    """Получает и возвращает байтовый ключ из заголовка."""
    key = request.headers.get("X-Encrypt-Key")
    if not key:
        raise HTTPException(status_code=400, detail="Encryption key required in X-Encrypt-Key header")
    return derive_key(key)


@router.get("/passwords")
async def get_passwords(request: Request):
    """Возвращает список паролей. С ключом — расшифрованные, без ключа — зашифрованные."""
    try:
        key = request.headers.get("X-Encrypt-Key")
        passwords = read_passwords_file()

        if not key:
            return passwords

        key_bytes = derive_key(key)
        try:
            return [decrypt_password_item(key_bytes, item) for item in passwords]
        except ValueError:
            # HMAC не сошёлся: неверный мастер-ключ или повреждённый файл.
            raise HTTPException(
                status_code=400,
                detail="Invalid encryption key or corrupted data"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting passwords: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/passwords")
async def save_passwords(data: list[dict], request: Request):
    """Сохраняет список паролей (шифрует чувствительные поля)."""
    try:
        if not all(isinstance(item, dict) for item in data):
            raise HTTPException(status_code=400, detail="Each entry must be an object")

        key_bytes = _get_key_bytes(request)
        encrypted_data = [encrypt_password_item(key_bytes, item) for item in data]

        if save_passwords_file(encrypted_data):
            logger.info(f"Successfully saved {len(data)} password entries")
            return {"message": "Passwords saved successfully", "count": len(data)}
        else:
            raise HTTPException(status_code=500, detail="Failed to save passwords")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving passwords: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/passwords/item")
async def save_password_item(data: dict, request: Request):
    """Сохраняет одну запись пароля (добавление или обновление)."""
    try:
        key_bytes = _get_key_bytes(request)

        passwords = read_passwords_file()
        item_index = data.get('_index')
        if item_index is not None:
            try:
                item_index = int(item_index)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="Invalid index")

        data_to_encrypt = {k: v for k, v in data.items() if k != '_index'}
        encrypted_item = encrypt_password_item(key_bytes, data_to_encrypt)

        if item_index is not None and 0 <= item_index < len(passwords):
            passwords[item_index] = encrypted_item
            logger.info(f"Updated password at index {item_index}: {data.get('name')}")
        else:
            passwords.append(encrypted_item)
            logger.info(f"Added new password: {data.get('name')}")

        if save_passwords_file(passwords):
            return {"message": "Password saved successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save password")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving password item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/passwords")
async def delete_password(data: PasswordDelete, request: Request):
    """Удаляет запись пароля по индексу."""
    try:
        passwords = read_passwords_file()
        index = data.index

        if 0 <= index < len(passwords):
            passwords.pop(index)
            if save_passwords_file(passwords):
                logger.info(f"Deleted password at index {index}")
                return {"message": "Password deleted successfully"}
            else:
                raise HTTPException(status_code=500, detail="Failed to save passwords")
        else:
            raise HTTPException(status_code=400, detail="Invalid index")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting password: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/passwords/import")
async def import_passwords(data: list[dict], request: Request):
    """Импорт паролей."""
    try:
        key = request.headers.get("X-Encrypt-Key")
        if not key:
            raise HTTPException(status_code=400, detail="Encryption key required in X-Encrypt-Key header")

        if not all(isinstance(item, dict) for item in data):
            raise HTTPException(status_code=400, detail="Each entry must be an object")

        key_bytes = derive_key(key)
        encrypted_data = [encrypt_password_item(key_bytes, item) for item in data]

        if not save_passwords_file(encrypted_data):
            raise HTTPException(status_code=500, detail="Failed to save passwords")

        logger.info(f"Successfully imported {len(data)} password entries")
        return {
            "message": "Passwords imported successfully",
            "count": len(data)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing passwords: {e}")
        raise HTTPException(status_code=500, detail=str(e))


