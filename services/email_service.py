"""
services/email_service.py — E-posta gönderim servisi.
Kural: Yalnızca 1 onay maili + 1 hoş geldin maili. Asla daha fazla değil.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _smtp_baglan() -> smtplib.SMTP:
    """SMTP bağlantısı oluşturur ve kimlik doğrular."""
    server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
    server.ehlo()
    server.starttls()
    server.login(settings.smtp_user, settings.smtp_password)
    return server


def _mail_gonder(alici: str, konu: str, html_govde: str) -> None:
    """
    Tek bir e-posta gönderir. Hata durumunda loglayıp exception fırlatır.
    Retry yoktur — çağıran katman karar verir.
    """
    mesaj = MIMEMultipart("alternative")
    mesaj["Subject"] = konu
    mesaj["From"] = settings.email_from
    mesaj["To"] = alici
    mesaj.attach(MIMEText(html_govde, "html", "utf-8"))

    server = None
    try:
        server = _smtp_baglan()
        server.sendmail(settings.email_from, alici, mesaj.as_string())
        logger.info(f"[Email] Mail gönderildi → {alici} | Konu: {konu}")
    except smtplib.SMTPException as exc:
        logger.error(f"[Email] SMTP hatası → {alici}: {exc}")
        raise RuntimeError(f"E-posta gönderilemedi: {exc}") from exc
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass


def onay_maili_gonder(eposta: str, ad_soyad: str, onay_linki: str) -> None:
    """
    ADIM 5: Tek onay maili. 24 saatlik link içerir.
    Bu fonksiyon yalnızca kayıt sonrası 1 kez çağrılır.
    """
    konu = "📬 Pazarlama Maratonu — E-posta Adresinizi Onaylayın"
    html = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:30px;">
      <div style="max-width:500px;margin:auto;background:white;border-radius:12px;
                  padding:40px;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
        <h2 style="color:#e63946;">🍴 Marka Mutfağı</h2>
        <p>Merhaba <strong>{ad_soyad}</strong>,</p>
        <p>Pazarlama Maratonu'na başvurunuzu aldık! Kaydınızı tamamlamak için
           lütfen aşağıdaki butona tıklayın:</p>
        <div style="text-align:center;margin:30px 0;">
          <a href="{onay_linki}"
             style="background:#e63946;color:white;padding:14px 28px;
                    border-radius:8px;text-decoration:none;font-weight:bold;
                    font-size:16px;">
            E-postamı Onayla ✅
          </a>
        </div>
        <p style="color:#888;font-size:13px;">
          Bu link <strong>24 saat</strong> geçerlidir. Başvurmadıysanız bu
          e-postayı dikkate almayınız.
        </p>
        <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
        <p style="color:#aaa;font-size:12px;">Marka Mutfağı Ekibi</p>
      </div>
    </body>
    </html>
    """
    _mail_gonder(eposta, konu, html)


def hosgeldin_maili_gonder(eposta: str, ad_soyad: str, slack_kanal: str) -> None:
    """
    ADIM 7: Tek hoş geldin maili. SADECE e-posta onayı sonrası çağrılır.
    Program bilgisi + Slack linki içerir; başka mail atılmaz.
    """
    konu = "🎉 Pazarlama Maratonu'na Hoş Geldiniz!"
    html = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:30px;">
      <div style="max-width:500px;margin:auto;background:white;border-radius:12px;
                  padding:40px;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
        <h2 style="color:#e63946;">🍴 Marka Mutfağı</h2>
        <p>Merhaba <strong>{ad_soyad}</strong>,</p>
        <p>E-posta adresiniz doğrulandı ve <strong>Pazarlama Maratonu</strong>'na
           resmi olarak kabul edildiniz! 🎊</p>
        <p><strong>Sonraki adım:</strong> Slack kanalımıza katılın ve kendinizi tanıtın.</p>
        <div style="text-align:center;margin:30px 0;">
          <a href="{slack_kanal}"
             style="background:#4a154b;color:white;padding:14px 28px;
                    border-radius:8px;text-decoration:none;font-weight:bold;
                    font-size:16px;">
            Slack Kanalına Katıl 💬
          </a>
        </div>
        <p style="color:#888;font-size:13px;">
          Sorularınız için ekip koordinatörüyle iletişime geçebilirsiniz.
        </p>
        <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
        <p style="color:#aaa;font-size:12px;">Marka Mutfağı Ekibi</p>
      </div>
    </body>
    </html>
    """
    _mail_gonder(eposta, konu, html)
