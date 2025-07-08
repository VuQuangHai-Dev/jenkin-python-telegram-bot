# security.py
import base64
from cryptography.fernet import Fernet
import config
import logging
from typing import Optional

# Cấu hình logging
logger = logging.getLogger(__name__)

def get_key():
    """Lấy khóa mã hóa từ config."""
    return config.SECRET_KEY

def encrypt_data(data: str) -> Optional[str]:
    """Mã hóa dữ liệu."""
    try:
        key = get_key()
        f = Fernet(key)
        encrypted_data = f.encrypt(data.encode())
        return encrypted_data.decode()
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        return None

def decrypt_data(encrypted_data: str) -> Optional[str]:
    """Giải mã dữ liệu."""
    try:
        key = get_key()
        f = Fernet(key)
        decrypted_data = f.decrypt(encrypted_data.encode())
        return decrypted_data.decode()
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        return None