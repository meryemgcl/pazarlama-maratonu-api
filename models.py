"""
models.py — Pydantic request/response modelleri.
Tüm girdi/çıktı şemaları burada tanımlıdır.
"""
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from enum import Enum
import re


# ── Sabitler ────────────────────────────────────────────────────────────────

class KayitDurumu(str, Enum):
    ONAY_BEKLENIYOR = "pending_email"
    EPOSTA_ONAYLANDI = "email_verified"
    AKTIF = "active"
    PASIF = "passive"


# ── Request Modelleri ────────────────────────────────────────────────────────

class KayitIstegi(BaseModel):
    """POST /register için gelen istek gövdesi."""
    ad_soyad: str
    eposta: EmailStr
    telefon: Optional[str] = None

    @field_validator("ad_soyad")
    @classmethod
    def ad_soyad_dogrula(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Ad Soyad en az 2 karakter olmalıdır.")
        if len(v) > 100:
            raise ValueError("Ad Soyad en fazla 100 karakter olabilir.")
        return v

    @field_validator("telefon")
    @classmethod
    def telefon_dogrula(cls, v: Optional[str]) -> Optional[str]:
        """
        Telefon opsiyoneldir. Girilmişse Türkiye formatında olmalı:
        +905xxxxxxxxx veya 05xxxxxxxxx (10-13 karakter, sadece rakam ve +)
        """
        if v is None:
            return None
        v = v.strip().replace(" ", "").replace("-", "")
        # +905xxxxxxxxx veya 05xxxxxxxxx
        pattern = r"^(\+90|0)[5][0-9]{9}$"
        if not re.match(pattern, v):
            raise ValueError(
                "Telefon numarası geçersiz. "
                "Lütfen '+905xxxxxxxxx' veya '05xxxxxxxxx' formatında girin."
            )
        return v


# ── Response Modelleri ───────────────────────────────────────────────────────

class BasariliKayitYaniti(BaseModel):
    """POST /register başarılı yanıtı."""
    mesaj: str = "Kaydınız alındı. Lütfen e-postanızı onaylayın."
    eposta: str
    durum: KayitDurumu = KayitDurumu.ONAY_BEKLENIYOR


class OnayYaniti(BaseModel):
    """GET /verify-email başarılı yanıtı."""
    mesaj: str = "E-postanız başarıyla doğrulandı. Slack davetiniz gönderildi."
    durum: KayitDurumu = KayitDurumu.EPOSTA_ONAYLANDI


class HataYaniti(BaseModel):
    """Hata durumlarında dönen genel yanıt."""
    hata: str
    detay: Optional[str] = None
