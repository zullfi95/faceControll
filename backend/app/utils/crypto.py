"""
Утилиты для шифрования и дешифрования данных.
Используется для безопасного хранения паролей устройств в БД.
"""
import os
from cryptography.fernet import Fernet
import base64


def get_encryption_key() -> bytes:
    """Получение ключа шифрования из переменной окружения."""
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        # Если ключ не задан, генерируем предупреждение
        # В production это должно быть обязательно задано
        raise ValueError("ENCRYPTION_KEY not set in environment variables")
    return key.encode()


def encrypt_password(password: str) -> str:
    """Шифрование пароля для хранения в БД."""
    try:
        key = get_encryption_key()
        f = Fernet(key)
        encrypted = f.encrypt(password.encode())
        return encrypted.decode()
    except Exception as e:
        raise ValueError(f"Failed to encrypt password: {e}")


def decrypt_password(encrypted_password: str) -> str:
    """Дешифрование пароля из БД."""
    try:
        key = get_encryption_key()
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except Exception as e:
        raise ValueError(f"Failed to decrypt password: {e}")


def generate_encryption_key() -> str:
    """Генерация нового ключа шифрования (использовать в init скрипте)."""
    return Fernet.generate_key().decode()

