"""
services/slack_service.py — Slack davet servisi.
KRİTİK KURAL: Bu fonksiyon YALNIZCA email_verified durumundaki kullanıcılar için çağrılır.
Bu kontrolü main.py'deki endpoint yönetir; bu servis kör bir araçtır.
"""
import httpx
from config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

SLACK_API_BASE = "https://slack.com/api"


async def kanala_davet_et(eposta: str) -> bool:
    """
    Kullanıcıyı e-posta adresiyle Slack kanalına davet eder.

    Returns:
        True  → Davet başarılı
        False → Davet başarısız (loglama yapıldı, sistem durmuyor)

    NOT: Slack'in /conversations.invite endpoint'i user ID ister.
         Önce /users.lookupByEmail ile user ID bulunur.
         Kullanıcı Slack'te yoksa davet linki workspace genel daveti olarak gönderilir.
    """
    # 1. E-postadan Slack kullanıcı ID'si bul
    user_id = await _kullanici_id_bul(eposta)

    if user_id:
        return await _kanala_ekle(user_id)
    else:
        # Kullanıcı Slack'te henüz yoksa → e-posta ile workspace daveti gönder
        logger.warning(f"[Slack] Kullanıcı bulunamadı, e-posta daveti gönderilecek: {eposta}")
        return await _eposta_ile_davet_et(eposta)


async def _kullanici_id_bul(eposta: str) -> str | None:
    """Slack kullanıcı ID'sini e-posta ile arar."""
    url = f"{SLACK_API_BASE}/users.lookupByEmail"
    params = {"email": eposta}
    headers = {"Authorization": f"Bearer {settings.slack_bot_token}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            data = resp.json()
            if data.get("ok"):
                user_id = data["user"]["id"]
                logger.info(f"[Slack] Kullanıcı bulundu: {eposta} → {user_id}")
                return user_id
            logger.info(f"[Slack] Kullanıcı Slack'te kayıtlı değil: {eposta}")
            return None
    except httpx.RequestError as exc:
        logger.error(f"[Slack] Kullanıcı arama hatası: {exc}")
        return None


async def _kanala_ekle(user_id: str) -> bool:
    """Mevcut Slack kullanıcısını kanala ekler."""
    url = f"{SLACK_API_BASE}/conversations.invite"
    headers = {
        "Authorization": f"Bearer {settings.slack_bot_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "channel": settings.slack_channel_id,
        "users": user_id,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            data = resp.json()
            if data.get("ok"):
                logger.info(f"[Slack] Kullanıcı kanala eklendi: {user_id}")
                return True
            # already_in_channel → başarı sayılır
            if data.get("error") == "already_in_channel":
                logger.info(f"[Slack] Kullanıcı zaten kanalda: {user_id}")
                return True
            logger.error(f"[Slack] Kanala ekleme hatası: {data.get('error')}")
            return False
    except httpx.RequestError as exc:
        logger.error(f"[Slack] Bağlantı hatası: {exc}")
        return False


async def _eposta_ile_davet_et(eposta: str) -> bool:
    """Slack'te hesabı olmayan kullanıcıya e-posta daveti gönderir."""
    url = f"{SLACK_API_BASE}/admin.users.invite"
    headers = {
        "Authorization": f"Bearer {settings.slack_bot_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "channel_ids": settings.slack_channel_id,
        "email": eposta,
        "resend": False,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            data = resp.json()
            if data.get("ok"):
                logger.info(f"[Slack] E-posta daveti gönderildi: {eposta}")
                return True
            logger.error(f"[Slack] E-posta daveti hatası: {data.get('error')}")
            return False
    except httpx.RequestError as exc:
        logger.error(f"[Slack] Bağlantı hatası: {exc}")
        return False
