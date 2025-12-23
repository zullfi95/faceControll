"""
Утилиты для шифрования и дешифрования данных.
Используется для безопасного хранения паролей устройств в БД.
"""
from cryptography.fernet import Fernet
import base64
from ..config import settings


def get_encryption_key() -> bytes:
    """Получение ключа шифрования из конфигурации."""
    return settings.encryption_key.encode()


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
        error_msg = str(e)
        error_type = type(e).__name__
        
        # Более информативные сообщения об ошибках
        if "InvalidToken" in error_type or "signature" in error_msg.lower() or "Invalid" in error_type:
            raise ValueError(
                "Не удалось расшифровать пароль устройства. Пароль был зашифрован другим ключом шифрования. "
                "Решение: Перейдите в 'Настройки' → 'Устройства' и обновите пароль устройства, "
                "или удалите и создайте устройство заново с правильным паролем."
            )
        else:
            raise ValueError(f"Ошибка расшифровки пароля: {error_msg}")


def generate_encryption_key() -> str:
    """Генерация нового ключа шифрования (использовать в init скрипте)."""
    return Fernet.generate_key().decode()

