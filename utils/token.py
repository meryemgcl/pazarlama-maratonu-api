"""
utils/token.py — UUID tabanlı e-posta onay token'ı üretimi ve doğrulaması.
PyJWT kullanır (python-jose yerine — Rust derleme gerektirmez).
Sonsuz geçerlilik YOK; her token 24 saatte otomatik sona erer.
"""
import uuid
from datetime import datetime, timedelta, timezone
import jwt
from config import get_settings

settings = get_settings()
ALGORITHM = "HS256"


def token_olustur(eposta: str) -> str:
    """
    Verilen e-posta adresi için imzalı JWT token üretir.
    TTL: settings.token_ttl_hours (varsayılan: 24 saat)
    """
    son_gecerlilik = datetime.now(timezone.utc) + timedelta(hours=settings.token_ttl_hours)
    payload = {
        "sub": eposta,
        "jti": str(uuid.uuid4()),   # Her token benzersiz — tekrar kullanım engellenir
        "exp": son_gecerlilik,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def token_dogrula(token: str) -> str:
    """
    Token'ı doğrular ve e-posta adresini döner.

    Raises:
        ValueError: Token geçersiz veya süresi dolmuşsa.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        eposta: str = payload.get("sub")
        if not eposta:
            raise ValueError("Token içinde e-posta bulunamadı.")
        return eposta
    except jwt.ExpiredSignatureError as exc:
        raise ValueError("Token süresi dolmuş.") from exc
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"Token geçersiz: {exc}") from exc
