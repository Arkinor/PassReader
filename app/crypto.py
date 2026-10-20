"""
Модуль шифрования/дешифрования данных: SHA-256-CTR + HMAC-SHA256.

Алгоритм:
  1. Мастер-ключ (из памяти пользователя) + соль (из salt.bin) -> PBKDF2-HMAC-SHA256
     с 600 000 итераций -> 32-байтовый ключ.
  2. Из ключа выводятся два подключа:
     - enc_key = HMAC-SHA256(key, b"enc") — для шифрования
     - mac_key = HMAC-SHA256(key, b"mac") — для аутентификации
  3. Шифрование: SHA-256 в режиме CTR (keystream = SHA256(enc_key + nonce + counter))
     XOR с открытым текстом. Не подвержен bias-атакам RC4.
  4. Аутентификация: HMAC-SHA256(mac_key, nonce + ciphertext) — защита от подделки.
  5. Формат: "secure:" + base64(nonce[16] + hmac[32] + ciphertext)

Безопасность:
  - 600 000 итераций PBKDF2 (OWASP 2023) замедляют офлайн-брутфорс.
  - Случайная соль в salt.bin предотвращает предвычисленные радужные таблицы.
  - Разделение ключей (enc/mac) исключает проблемы переиспользования.
  - Уникальный nonce (16 байт) для каждого шифрования.
  - HMAC проверяется ДО дешифрования (защита от oracle-атак).
  - Ключ выводится один раз за запрос, переиспользуется для всех полей.
  - Не использует внешних библиотек — только стандартная библиотека Python.
"""

import base64
import hashlib
import hmac
import os
from typing import Any, Optional

# Префикс для зашифрованных значений
ENCRYPTED_PREFIX = "secure:"

# Константы
NONCE_SIZE = 16            # 128-bit nonce
HMAC_SIZE = 32             # SHA-256 output
KEY_SIZE = 32              # 256-bit ключ
PBKDF2_ITERATIONS = 600_000  # Рекомендация OWASP 2023

# Захардкоженная соль для PBKDF2.
# Не является секретом — её задача лишь в том, чтобы сделать уникальной
# для данного проекта. 600 000 итераций делают радужные таблицы непрактичными.
_PBKDF2_SALT = b"pm_v2_a8f3k2x9q7m1c4r6t0z5w8e3y6u1i4o7p2a5d8f3h6j9l2"

def derive_key(master_key: str, salt: bytes = None) -> bytes:
    """
    Выводит 32-байтовый ключ из мастер-ключа через PBKDF2-HMAC-SHA256.

    Вызывается один раз за запрос (~0.3-0.5 сек), результат переиспользуется.
    """
    if salt is None:
        salt = _PBKDF2_SALT
    return hashlib.pbkdf2_hmac(
        'sha256',
        master_key.encode('utf-8'),
        salt,
        PBKDF2_ITERATIONS,
        dklen=KEY_SIZE
    )


def _derive_subkeys(key_bytes: bytes) -> tuple:
    """
    Выводит два подключа из мастер-ключа: для шифрования и для HMAC.
    Разделение ключей — стандартная практика (encrypt-then-MAC).
    """
    enc_key = hmac.new(key_bytes, b"encryption", hashlib.sha256).digest()
    mac_key = hmac.new(key_bytes, b"authentication", hashlib.sha256).digest()
    return enc_key, mac_key


def _ctr_keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
    """
    Генерирует keystream через SHA-256 в режиме CTR.

    Каждый блок: SHA256(enc_key + nonce + counter)
    counter — 8 байт big-endian, инкрементируется на 1 для каждого блока.
    """
    stream = bytearray()
    counter = 0
    while len(stream) < length:
        block = hashlib.sha256(enc_key + nonce + counter.to_bytes(8, 'big')).digest()
        stream.extend(block)
        counter += 1
    return bytes(stream[:length])


def is_encrypted_value(value: Any) -> bool:
    """Проверяет, зашифровано ли значение."""
    return isinstance(value, str) and value.startswith(ENCRYPTED_PREFIX)


def encrypt_field(key_bytes: bytes, value: Optional[str]) -> Optional[str]:
    """
    Шифрует строковое поле: SHA-256-CTR + HMAC-SHA256.

    Args:
        key_bytes: 32-байтовый ключ (результат derive_key)
        value: Значение для шифрования

    Returns:
        Зашифрованная строка "secure:base64(nonce + hmac + ciphertext)" или None
    """
    if value is None or value == "":
        return None

    if is_encrypted_value(value):
        return value

    enc_key, mac_key = _derive_subkeys(key_bytes)

    # Генерируем уникальный nonce
    nonce = os.urandom(NONCE_SIZE)

    # Шифрование: XOR с SHA-256-CTR keystream
    plaintext_bytes = value.encode('utf-8')
    keystream = _ctr_keystream(enc_key, nonce, len(plaintext_bytes))
    ciphertext = bytes(a ^ b for a, b in zip(plaintext_bytes, keystream))

    # Аутентификация: HMAC от nonce + ciphertext
    mac = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()

    # Упаковка: nonce + hmac + ciphertext
    combined = nonce + mac + ciphertext
    return f"{ENCRYPTED_PREFIX}{base64.b64encode(combined).decode('utf-8')}"


def decrypt_field(key_bytes: bytes, encrypted_value: Optional[str]) -> Optional[str]:
    """
    Дешифрует строковое поле с проверкой HMAC.

    Args:
        key_bytes: 32-байтовый ключ (результат derive_key)
        encrypted_value: Зашифрованная строка

    Returns:
        Расшифрованная строка или оригинальное значение если не зашифровано

    Raises:
        ValueError: Если ключ неверный или данные повреждены (HMAC не прошёл проверку)
    """
    if encrypted_value is None or encrypted_value == "":
        return None

    if not is_encrypted_value(encrypted_value):
        return encrypted_value

    combined = base64.b64decode(encrypted_value[len(ENCRYPTED_PREFIX):])

    if len(combined) < NONCE_SIZE + HMAC_SIZE:
        raise ValueError("Invalid encrypted value length")

    nonce = combined[:NONCE_SIZE]
    mac = combined[NONCE_SIZE:NONCE_SIZE + HMAC_SIZE]
    ciphertext = combined[NONCE_SIZE + HMAC_SIZE:]

    enc_key, mac_key = _derive_subkeys(key_bytes)

    # Проверяем HMAC ДО дешифрования (защита от oracle-атак)
    expected_mac = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected_mac):
        raise ValueError("HMAC verification failed - wrong key or data tampered")

    # Дешифрование: XOR с тем же keystream
    keystream = _ctr_keystream(enc_key, nonce, len(ciphertext))
    plaintext = bytes(a ^ b for a, b in zip(ciphertext, keystream))

    return plaintext.decode('utf-8')


def encrypt_password_item(key_bytes: bytes, item: dict) -> dict:
    """Шифрует чувствительные поля записи."""
    encrypted_item = item.copy()
    fields_to_encrypt = ["name", "login", "password", "email", "comment", "group"]
    for field in fields_to_encrypt:
        if field in encrypted_item and encrypted_item[field] is not None:
            encrypted_item[field] = encrypt_field(key_bytes, encrypted_item[field])
    return encrypted_item


def decrypt_password_item(key_bytes: bytes, item: dict) -> dict:
    """Расшифровывает запись."""
    decrypted_item = item.copy()
    fields_to_decrypt = ["name", "login", "password", "email", "comment", "group"]
    for field in fields_to_decrypt:
        if field in decrypted_item and decrypted_item[field] is not None:
            decrypted_item[field] = decrypt_field(key_bytes, decrypted_item[field])
    return decrypted_item