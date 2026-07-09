"""
services/notion_service.py — Tek veritabanı operasyonları.
Tüm kayıt işlemleri burada, başka hiçbir yerde DB yazısı olmaz.
"""
import httpx
from datetime import datetime, timezone
from typing import Optional
from models import KayitDurumu
from config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.notion_api_key}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_API_VERSION,
    }


async def kayit_var_mi(eposta: str) -> Optional[dict]:
    """
    Notion DB'de aynı e-posta ile kayıt var mı kontrol eder.
    Varsa sayfa objesini, yoksa None döner.
    """
    url = f"{NOTION_BASE_URL}/databases/{settings.notion_database_id}/query"
    payload = {
        "filter": {
            "property": "E-posta",
            "email": {"equals": eposta},
        }
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=_headers(), json=payload)
            resp.raise_for_status()
            sonuclar = resp.json().get("results", [])
            if sonuclar:
                logger.info(f"[Notion] Mevcut kayıt bulundu: {eposta}")
                return sonuclar[0]
            return None
    except httpx.HTTPStatusError as exc:
        logger.error(f"[Notion] Sorgu hatası: {exc.response.status_code} — {exc.response.text}")
        raise RuntimeError("Veritabanı sorgusu başarısız.") from exc
    except httpx.RequestError as exc:
        logger.error(f"[Notion] Bağlantı hatası: {exc}")
        raise RuntimeError("Notion'a bağlanılamadı.") from exc


async def yeni_kayit_olustur(
    ad_soyad: str,
    eposta: str,
    telefon: Optional[str] = None,
) -> str:
    """
    Notion DB'ye yeni kayıt ekler. Sayfa ID'sini döner.
    Durum başlangıçta her zaman 'pending_email' olarak set edilir.
    """
    url = f"{NOTION_BASE_URL}/pages"
    ozellikler: dict = {
        "Ad Soyad": {"title": [{"text": {"content": ad_soyad}}]},
        "E-posta": {"email": eposta},
        "Durum": {"select": {"name": KayitDurumu.ONAY_BEKLENIYOR.value}},
        "Kayıt Tarihi": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
    }
    if telefon:
        ozellikler["Telefon"] = {"phone_number": telefon}

    payload = {
        "parent": {"database_id": settings.notion_database_id},
        "properties": ozellikler,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=_headers(), json=payload)
            resp.raise_for_status()
            sayfa_id = resp.json()["id"]
            logger.info(f"[Notion] Kayıt oluşturuldu: {eposta} → ID={sayfa_id}")
            return sayfa_id
    except httpx.HTTPStatusError as exc:
        logger.error(f"[Notion] Kayıt oluşturma hatası: {exc.response.status_code} — {exc.response.text}")
        raise RuntimeError("Kayıt oluşturulamadı.") from exc
    except httpx.RequestError as exc:
        logger.error(f"[Notion] Bağlantı hatası: {exc}")
        raise RuntimeError("Notion'a bağlanılamadı.") from exc


async def durum_guncelle(sayfa_id: str, yeni_durum: KayitDurumu) -> None:
    """
    Mevcut bir kaydın durumunu günceller.
    Örnek: pending_email → email_verified → active
    """
    url = f"{NOTION_BASE_URL}/pages/{sayfa_id}"
    payload = {
        "properties": {
            "Durum": {"select": {"name": yeni_durum.value}},
        }
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(url, headers=_headers(), json=payload)
            resp.raise_for_status()
            logger.info(f"[Notion] Durum güncellendi: ID={sayfa_id} → {yeni_durum.value}")
    except httpx.HTTPStatusError as exc:
        logger.error(f"[Notion] Durum güncelleme hatası: {exc.response.status_code}")
        raise RuntimeError("Kayıt durumu güncellenemedi.") from exc


async def eposta_ile_sayfa_id_bul(eposta: str) -> Optional[str]:
    """E-postadan Notion sayfa ID'si döner (durum güncellemesi için)."""
    kayit = await kayit_var_mi(eposta)
    if kayit:
        return kayit["id"]
    return None
