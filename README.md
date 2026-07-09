# 🍴 Pazarlama Maratonu Kayıt API

> **Marka Mutfağı** ekibinin Pazarlama Maratonu etkinliği için geliştirilmiş temiz, döngüsüz ve tek veritabanı kullanan kayıt sistemi.

---

## 🎯 Ne Yapar?

Gönüllü adayların Pazarlama Maratonu'na kaydolmasını, e-posta doğrulamasını ve Slack kanalına otomatik eklenmesini yönetir.

```
Kullanıcı Formu Doldurur
        ↓
Validasyon (e-posta, telefon formatı)
        ↓
Çift Kayıt Kontrolü (idempotency)
        ↓
Notion'a Tek Kayıt (pending_email)
        ↓
Onay Maili Gönderilir (24h link)
        ↓
Kullanıcı Linke Tıklar
        ↓
Slack'e Davet + Hoş Geldin Maili
        ↓ (opsiyonel)
SMS Bildirimi
```

---

## ⚡ Teknolojiler

| Teknoloji | Kullanım |
|-----------|----------|
| **FastAPI** | Web framework |
| **Pydantic v2** | Veri doğrulama |
| **Notion API** | Tek veritabanı (ana kaynak) |
| **SMTP / Gmail** | E-posta gönderimi |
| **Slack API** | Kanal daveti |
| **Twilio** | Opsiyonel SMS |
| **PyJWT** | 24 saatlik onay token'ı |

---

## 🚀 Kurulum

### 1. Bağımlılıkları Yükle

```bash
pip install -r requirements.txt
```

### 2. Ortam Değişkenlerini Ayarla

```bash
copy .env.example .env
```

`.env` dosyasını aç ve API key'lerini gir:

```env
NOTION_API_KEY=secret_xxxxx
NOTION_DATABASE_ID=xxxxx
SMTP_USER=gmail@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
SLACK_BOT_TOKEN=xoxb-xxxxx
SLACK_CHANNEL_ID=Cxxxxxxxx
SECRET_KEY=en-az-32-karakter-rastgele-bir-deger
```

> 💡 SECRET_KEY üretmek için: `python -c "import secrets; print(secrets.token_hex(32))"`

### 3. Sunucuyu Başlat

```bash
uvicorn main:app --reload --port 8000
```

### 4. Tarayıcıda Aç

| URL | Açıklama |
|-----|----------|
| http://localhost:8000/docs | 🔵 Swagger UI — canlı test |
| http://localhost:8000/redoc | 📖 API Dokümantasyonu |
| http://localhost:8000/health | ✅ Sistem sağlık kontrolü |

---

## 📡 Endpoint'ler

### `POST /register` — Yeni Kayıt

```json
{
  "ad_soyad": "Ahmet Yılmaz",
  "eposta": "ahmet@example.com",
  "telefon": "05321234567"
}
```

**Yanıtlar:**
| Kod | Açıklama |
|-----|----------|
| `200` | Kayıt alındı, onay maili gönderildi |
| `409` | Bu e-posta zaten kayıtlı |
| `422` | Geçersiz e-posta veya telefon formatı |
| `500` | Sunucu hatası |

---

### `GET /verify-email?token=<TOKEN>` — E-posta Onayı

Kullanıcı onay mailindeki linke tıkladığında çalışır.

**Sırasıyla:**
1. JWT token doğrular (24 saatlik TTL)
2. Notion kaydını `email_verified` yapar
3. Slack kanalına davet gönderir
4. Hoş geldin maili atar
5. Kaydı `active` yapar
6. Opsiyonel SMS gönderir

---

### `GET /health` — Sağlık Kontrolü

```json
{"durum": "çalışıyor", "versiyon": "1.0.0"}
```

---

## 🗂️ Proje Yapısı

```
📁 pazarlama-maratonu-api/
├── main.py                  # FastAPI app — tüm akışın kalbi
├── config.py                # Ortam değişkenleri (pydantic-settings)
├── models.py                # Pydantic şemaları + validasyon
├── requirements.txt
├── .env.example             # API key kurulum şablonu
├── utils/
│   ├── logger.py            # Renkli, zaman damgalı merkezi log
│   └── token.py             # JWT token (24h TTL, UUID jti)
└── services/
    ├── notion_service.py    # TEK veritabanı operasyonları
    ├── email_service.py     # Onay + hoş geldin maili (max 2 mail)
    ├── slack_service.py     # Sadece email_verified sonrası çalışır
    └── sms_service.py       # Opsiyonel, 5s timeout, retry yok
```

---

## 🧹 Çözülen Teknik Borçlar

Bu API önceki "spagetti" sistemin yerini almak için sıfırdan yazılmıştır:

| Eski Sorun | Yeni Çözüm |
|------------|-----------|
| 3 farklı DB'ye çift yazma | Yalnızca **Notion** (tek kaynak) |
| Sonsuz SMS retry döngüsü | Tek deneme + 5s timeout |
| Onaysız Slack daveti | E-posta doğrulaması zorunlu kapı |
| Input validasyonu yok | Pydantic field validator |
| Aynı anda 4 mail | Max 2 mail, sıralı ve koşullu |
| Çift kayıt mümkün | E-posta ile idempotency kontrolü |
| Hata yönetimi yok | Her adımda try/catch + loglama |

---

## 🔒 Güvenlik

- `.env` dosyası `.gitignore`'a eklenmiştir — asla commit edilmez
- Token'lar JWT + HS256 + 24 saatlik TTL ile imzalanır
- Her token benzersiz UUID (`jti`) içerir — tekrar kullanım engellenir

---

## 📄 Lisans

MIT License — Marka Mutfağı Ekibi
