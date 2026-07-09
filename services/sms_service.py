"""
services/sms_service.py — SMS bildirim servisi (Twilio).

ALTIN KURALLAR:
  1. SMS tamamen opsiyoneldir — telefon girilmemişse bu servis hiç çağrılmaz.
  2. Tek deneme, 5 sn timeout — hiçbir koşulda retry döngüsü olmaz.
  3. Hata sessizce loglanır — kullanıcıya SMS hatası gösterilmez.
  4. Sistem SMS yüzünden asla bloke olmaz.
"""
import asyncio
import httpx
from config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


async def sms_gonder(telefon: str, ad_soyad: str) -> None:
    """
    Kullanıcıya hoş geldin SMS'i gönderir.

    Bu fonksiyon hata alsa bile exception FIRLATMAZ.
    Sistem akışı SMS durumundan bağımsız devam eder.
    """
    if not settings.sms_enabled:
        logger.info("[SMS] SMS devre dışı (sms_enabled=False). Atlanıyor.")
        return

    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        logger.warning("[SMS] Twilio kimlik bilgileri eksik. SMS atlanıyor.")
        return

    mesaj = (
        f"Merhaba {ad_soyad.split()[0]}! "
        "Pazarlama Maratonu'na hoş geldiniz 🎉 "
        "Slack davetiniz e-posta adresinize gönderildi."
    )

    url = f"{TWILIO_API_BASE}/Accounts/{settings.twilio_account_sid}/Messages.json"
    payload = {
        "From": settings.twilio_from_number,
        "To": _telefon_formatla(telefon),
        "Body": mesaj,
    }

    try:
        # Timeout: 5 saniye — bu süreyi geçerse sessizce geç
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                url,
                data=payload,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            )
            if resp.status_code in (200, 201):
                sid = resp.json().get("sid", "?")
                logger.info(f"[SMS] Gönderildi: {telefon} | SID={sid}")
            else:
                logger.error(
                    f"[SMS] Gönderim başarısız: {resp.status_code} — {resp.text[:200]}"
                )
    except httpx.TimeoutException:
        logger.error(f"[SMS] Timeout (5s aşıldı): {telefon} — sistem akışı devam ediyor")
    except httpx.RequestError as exc:
        logger.error(f"[SMS] Bağlantı hatası: {exc} — sistem akışı devam ediyor")
    # Her türlü beklenmedik hata da sessizce loglanır, yukarı fırlatılmaz
    except Exception as exc:
        logger.error(f"[SMS] Beklenmedik hata: {exc} — sistem akışı devam ediyor")


def _telefon_formatla(telefon: str) -> str:
    """
    '05xxxxxxxxx' → '+905xxxxxxxxx' dönüşümü.
    Twilio uluslararası format (+) bekler.
    """
    if telefon.startswith("0") and not telefon.startswith("+"):
        return "+9" + telefon
    return telefon
