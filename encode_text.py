#!/usr/bin/env python3
"""
Консольная утилита для кодирования/декодирования текста.
Использует SHA-256-CTR + HMAC-SHA256 — тот же алгоритм, что и основной проект.

Формат: "secure:" + base64(nonce[16] + hmac[32] + ciphertext)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.crypto import derive_key, encrypt_field, decrypt_field


def main():
    print("=" * 50)
    print("  Утилита шифрования/дешифрования")
    print("=" * 50)
    print()

    text = input("Введите текст: ").strip()
    if not text:
        print("❌ Текст не может быть пустым!")
        return

    key = input("Введите ключ: ").strip()
    if not key:
        print("❌ Ключ не может быть пустым!")
        return

    print()
    print("Выберите операцию:")
    print("  1 - Закодировать")
    print("  2 - Раскодировать")
    print()

    choice = input("Ваш выбор (1/2): ").strip()

    # Выводим ключ один раз (PBKDF2, 600 000 итераций)
    key_bytes = derive_key(key)

    if choice == "1":
        result = encrypt_field(key_bytes, text)
        print()
        print("=" * 50)
        print("✅ Закодированный результат:")
        print("=" * 50)
        print(result)
        print()

    elif choice == "2":
        try:
            result = decrypt_field(key_bytes, text)
            print()
            print("=" * 50)
            print("✅ Раскодированный результат:")
            print("=" * 50)
            print(result)
            print()
        except Exception as e:
            print()
            print("=" * 50)
            print("❌ Ошибка при декодировании:")
            print("=" * 50)
            print(f"{type(e).__name__}: {e}")
            print()
            print("Возможно: неверный ключ или текст не зашифрован этим проектом")
            print()
    else:
        print(f"❌ Неверный выбор: {choice}")
        print("Используйте 1 для кодирования или 2 для декодирования")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Операция отменена пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)
