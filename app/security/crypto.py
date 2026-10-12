from cryptography.fernet import Fernet, InvalidToken
from ..config import get_settings

settings = get_settings()
_fernet = Fernet(settings.fernet_key)


def encrypt_text(plaintext: str) -> bytes:
    return _fernet.encrypt(plaintext.encode("utf-8"))


def decrypt_text(ciphertext: bytes) -> str:
    try:
        return _fernet.decrypt(ciphertext).decode("utf-8")
    except InvalidToken:
        raise ValueError("Не удалось расшифровать данные: неверный ключ или повреждённый шифротекст")