"""
main.py — Pazarlama Maratonu Kayıt API'si
FastAPI uygulaması. Tüm iş mantığı burada orkestre edilir.

Endpoint'ler:
  POST /register       → Kullanıcıyı kaydet, onay maili gönder
  GET  /verify-email   → Token'ı doğrula, Slack'e davet et
  GET  /health         → Sistem durumu kontrolü
"""
import asyncio
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from models import (
    KayitIstegi,
    BasariliKayitYaniti,
    OnayYaniti,
    HataYaniti,
    KayitDurumu,
)
from utils.logger import get_logger
from utils.token import token_olustur, token_dogrula
from services import notion_service, email_service, slack_service, sms_service

# ── Başlatma ─────────────────────────────────────────────────────────────────

logger = get_logger("main")
settings = get_settings()

app = FastAPI(
    title="Pazarlama Maratonu Kayıt API",
    description="Temiz, sonsuz döngüsüz, tek veritabanı kullanan kayıt sistemi.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Prod'da spesifik domain yaz
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoint 1: Kayıt ────────────────────────────────────────────────────────

@app.post(
    "/register",
    response_model=BasariliKayitYaniti,
    responses={
        400: {"model": HataYaniti, "description": "Geçersiz girdi"},
        409: {"model": HataYaniti, "description": "E-posta zaten kayıtlı"},
        500: {"model": HataYaniti, "description": "Sunucu hatası"},
    },
    summary="Yeni gönüllü kaydı oluştur",
    tags=["Kayıt"],
)
async def kayit_ol(istek: KayitIstegi) -> BasariliKayitYaniti:
    """
    ADIM 1-5: Kullanıcı bilgilerini al, doğrula, kaydet, onay maili gönder.

    - Validasyon Pydantic tarafından otomatik yapılır (models.py)
    - Çift kayıt: 409 Conflict döner
    - Hata: 500 döner, loglama yapılır
    """
    logger.info(f"[/register] Yeni kayıt isteği: {istek.eposta}")

    # ── ADIM 3: Çift kayıt kontrolü (Idempotency) ────────────────────────────
    try:
        mevcut = await notion_service.kayit_var_mi(istek.eposta)
    except RuntimeError as exc:
        logger.error(f"[/register] Notion sorgu hatası: {exc}")
        raise HTTPException(status_code=500, detail="Veritabanı kontrol hatası. Lütfen tekrar deneyin.")

    if mevcut:
        durum = (
            mevcut.get("properties", {})
            .get("Durum", {})
            .get("select", {})
            .get("name", "")
        )
        logger.warning(f"[/register] Çift kayıt girişimi: {istek.eposta} | Durum={durum}")

        if durum == KayitDurumu.ONAY_BEKLENIYOR.value:
            raise HTTPException(
                status_code=409,
                detail="Bu e-posta adresiyle bir kayıt zaten mevcut. "
                       "Onay mailini kontrol edin (spam klasörünü de inceleyin).",
            )
        raise HTTPException(
            status_code=409,
            detail="Bu e-posta adresiyle zaten kayıtlısınız.",
        )

    # ── ADIM 4: TEK veritabanına (Notion) kaydet ─────────────────────────────
    try:
        await notion_service.yeni_kayit_olustur(
            ad_soyad=istek.ad_soyad,
            eposta=istek.eposta,
            telefon=istek.telefon,
        )
    except RuntimeError as exc:
        logger.error(f"[/register] Kayıt oluşturulamadı: {exc}")
        raise HTTPException(status_code=500, detail="Kayıt sırasında bir sorun oluştu. Lütfen tekrar deneyin.")

    # ── ADIM 5: Tek onay maili gönder ────────────────────────────────────────
    token = token_olustur(istek.eposta)
    onay_linki = f"{settings.app_base_url}/verify-email?token={token}"

    try:
        email_service.onay_maili_gonder(
            eposta=istek.eposta,
            ad_soyad=istek.ad_soyad,
            onay_linki=onay_linki,
        )
    except RuntimeError as exc:
        # Mail gitmediyse kaydı sil veya kullanıcıyı bilgilendir
        logger.error(f"[/register] Onay maili gönderilemedi: {exc}")
        # Kaydı bırakıyoruz; kullanıcı /resend endpoint'i ile yeni mail isteyebilir
        raise HTTPException(
            status_code=500,
            detail="Kaydınız alındı ancak onay maili gönderilemedi. "
                   "Lütfen destek ekibiyle iletişime geçin.",
        )

    logger.info(f"[/register] Kayıt tamamlandı: {istek.eposta}")
    return BasariliKayitYaniti(eposta=istek.eposta)


# ── Endpoint 2: E-posta Onayı ────────────────────────────────────────────────

@app.get(
    "/verify-email",
    responses={
        200: {"description": "Onay başarılı — HTML yanıt"},
        400: {"model": HataYaniti, "description": "Geçersiz token"},
        404: {"model": HataYaniti, "description": "Kayıt bulunamadı"},
        500: {"model": HataYaniti, "description": "Sunucu hatası"},
    },
    summary="E-posta adresini doğrula",
    tags=["Kayıt"],
)
async def eposta_dogrula(token: str = Query(..., description="Onay e-postasındaki token")) -> HTMLResponse:
    """
    ADIM 6-8: Token'ı doğrula → Notion güncelle → Slack davet et → Hoş geldin maili at.

    KRİTİK KURAL: Slack daveti YALNIZCA bu endpoint başarıyla tamamlandıktan sonra gönderilir.
    """
    logger.info("[/verify-email] Onay isteği alındı.")

    # ── Token doğrulama ───────────────────────────────────────────────────────
    try:
        eposta = token_dogrula(token)
    except ValueError as exc:
        logger.warning(f"[/verify-email] Geçersiz token: {exc}")
        return _hata_html_yaniti(
            "❌ Geçersiz veya Süresi Dolmuş Link",
            "Bu onay linki geçersiz ya da 24 saatlik süresi dolmuş. "
            "Lütfen tekrar kayıt olmayı deneyin.",
        )

    logger.info(f"[/verify-email] Token geçerli: {eposta}")

    # ── Notion'da kaydı bul ───────────────────────────────────────────────────
    try:
        kayit = await notion_service.kayit_var_mi(eposta)
    except RuntimeError as exc:
        logger.error(f"[/verify-email] Notion sorgu hatası: {exc}")
        return _hata_html_yaniti("⚠️ Sunucu Hatası", "Veritabanına erişilemedi. Lütfen tekrar deneyin.")

    if not kayit:
        logger.error(f"[/verify-email] Kayıt bulunamadı: {eposta}")
        return _hata_html_yaniti("❌ Kayıt Bulunamadı", "Bu e-posta ile bir kayıt bulunamadı.")

    sayfa_id = kayit["id"]
    mevcut_durum = (
        kayit.get("properties", {})
        .get("Durum", {})
        .get("select", {})
        .get("name", "")
    )
    ad_soyad = (
        kayit.get("properties", {})
        .get("Ad Soyad", {})
        .get("title", [{}])[0]
        .get("text", {})
        .get("content", "Katılımcı")
    )
    telefon = (
        kayit.get("properties", {})
        .get("Telefon", {})
        .get("phone_number")
    )

    # Zaten onaylanmışsa tekrar işlem yapma (idempotent)
    if mevcut_durum == KayitDurumu.AKTIF.value:
        logger.info(f"[/verify-email] Zaten onaylanmış: {eposta}")
        return _basari_html_yaniti(ad_soyad, zaten_aktif=True)

    # ── ADIM 6: Notion durumunu güncelle ─────────────────────────────────────
    try:
        await notion_service.durum_guncelle(sayfa_id, KayitDurumu.EPOSTA_ONAYLANDI)
    except RuntimeError as exc:
        logger.error(f"[/verify-email] Notion güncelleme hatası: {exc}")
        return _hata_html_yaniti("⚠️ Güncelleme Hatası", "Kayıt durumu güncellenemedi. Lütfen destek ekibiyle iletişime geçin.")

    # ── ADIM 7: Slack daveti (SADECE onay sonrası) ───────────────────────────
    slack_basarili = await slack_service.kanala_davet_et(eposta)
    if not slack_basarili:
        logger.error(f"[/verify-email] Slack daveti başarısız: {eposta} — manuel müdahale gerekebilir")
        # Sistem devam eder; ekip manuel olarak ekleyebilir

    # Slack başarılıysa kaydı "Aktif" yap
    if slack_basarili:
        try:
            await notion_service.durum_guncelle(sayfa_id, KayitDurumu.AKTIF)
        except RuntimeError:
            logger.warning(f"[/verify-email] Aktif durumu yazılamadı: {eposta}")

    # ── ADIM 7: Hoş geldin maili (tek mail) ─────────────────────────────────
    try:
        email_service.hosgeldin_maili_gonder(
            eposta=eposta,
            ad_soyad=ad_soyad,
            slack_kanal=f"https://slack.com/app_redirect?channel={settings.slack_channel_id}",
        )
    except RuntimeError as exc:
        logger.error(f"[/verify-email] Hoş geldin maili gönderilemedi: {exc}")
        # Kritik değil; Slack daveti zaten gitti

    # ── ADIM 8: Opsiyonel SMS (sistemi bloklamaz) ────────────────────────────
    if telefon:
        # fire-and-forget: SMS hatası ana akışı etkilemez
        asyncio.create_task(sms_service.sms_gonder(telefon, ad_soyad))
    else:
        logger.info(f"[/verify-email] Telefon girilmemiş, SMS atlanıyor: {eposta}")

    logger.info(f"[/verify-email] Onay tamamlandı ✅: {eposta}")
    return _basari_html_yaniti(ad_soyad)


# ── Endpoint 3: Sağlık Kontrolü ──────────────────────────────────────────────

@app.get("/health", tags=["Sistem"], summary="API sağlık durumu")
async def saglik_kontrolu() -> dict:
    return {"durum": "çalışıyor", "versiyon": "1.0.0"}


# ── Hata Yönetimi ────────────────────────────────────────────────────────────

@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc) -> JSONResponse:
    """Pydantic validasyon hatalarını kullanıcı dostu formata çevirir."""
    hatalar = []
    for hata in exc.errors():
        alan = " → ".join(str(x) for x in hata["loc"] if x != "body")
        hatalar.append(f"{alan}: {hata['msg']}")
    logger.warning(f"[Validasyon] {request.url.path} — {hatalar}")
    return JSONResponse(
        status_code=422,
        content={"hata": "Girdi doğrulama hatası", "detay": hatalar},
    )


# ── HTML Yardımcıları ────────────────────────────────────────────────────────

def _basari_html_yaniti(ad_soyad: str, zaten_aktif: bool = False) -> HTMLResponse:
    mesaj = (
        "Zaten aktif bir katılımcısınız! Slack kanalımızda görüşürüz."
        if zaten_aktif
        else "E-posta adresiniz doğrulandı. Slack davetiniz gönderildi! 🎉"
    )
    html = f"""
    <!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
    <title>Onay Başarılı</title>
    <style>
      body{{font-family:Arial,sans-serif;background:#f0fdf4;display:flex;
           align-items:center;justify-content:center;min-height:100vh;margin:0}}
      .kart{{background:white;border-radius:16px;padding:48px;text-align:center;
             box-shadow:0 4px 20px rgba(0,0,0,0.1);max-width:440px}}
      h1{{color:#16a34a;font-size:48px;margin:0 0 16px}}
      h2{{color:#1a1a2e;margin:0 0 12px}}
      p{{color:#555;line-height:1.6}}
    </style></head>
    <body><div class="kart">
      <h1>✅</h1>
      <h2>Merhaba {ad_soyad}!</h2>
      <p>{mesaj}</p>
    </div></body></html>
    """
    return HTMLResponse(content=html, status_code=200)


def _hata_html_yaniti(baslik: str, aciklama: str) -> HTMLResponse:
    html = f"""
    <!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
    <title>Hata</title>
    <style>
      body{{font-family:Arial,sans-serif;background:#fff5f5;display:flex;
           align-items:center;justify-content:center;min-height:100vh;margin:0}}
      .kart{{background:white;border-radius:16px;padding:48px;text-align:center;
             box-shadow:0 4px 20px rgba(0,0,0,0.1);max-width:440px}}
      h1{{color:#dc2626;font-size:48px;margin:0 0 16px}}
      h2{{color:#1a1a2e;margin:0 0 12px}}
      p{{color:#555;line-height:1.6}}
    </style></head>
    <body><div class="kart">
      <h1>⚠️</h1>
      <h2>{baslik}</h2>
      <p>{aciklama}</p>
    </div></body></html>
    """
    return HTMLResponse(content=html, status_code=400)
