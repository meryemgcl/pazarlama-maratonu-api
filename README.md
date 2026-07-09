# 🍴 Pazarlama Maratonu Kayıt API

Temiz, döngüsüz, tek veritabanı kullanan FastAPI uygulaması.

## Kurulum

```bash
# 1. Bağımlılıkları yükle
pip install -r requirements.txt

# 2. Ortam değişkenlerini hazırla
copy .env.example .env
# .env dosyasını açıp gerçek değerleri girin

# 3. Sunucuyu başlat
uvicorn main:app --reload --port 8000
```

## Notion Veritabanı Kurulumu

Notion'da aşağıdaki özelliklere sahip bir veritabanı oluşturun:

| Özellik Adı  | Tür          |
|--------------|--------------|
| Ad Soyad     | Title        |
| E-posta      | Email        |
| Telefon      | Phone Number |
| Durum        | Select       |
| Kayıt Tarihi | Date         |

**Durum** seçenekleri:
- `pending_email`
- `email_verified`
- `active`
- `passive`

## Endpoint'ler

### `POST /register`
```json
{
  "ad_soyad": "Ahmet Yılmaz",
  "eposta": "ahmet@example.com",
  "telefon": "05321234567"   // opsiyonel
}
```

**Başarılı yanıt (200):**
```json
{
  "mesaj": "Kaydınız alındı. Lütfen e-postanızı onaylayın.",
  "eposta": "ahmet@example.com",
  "durum": "pending_email"
}
```

**Hata yanıtları:**
- `422` — Geçersiz e-posta / telefon formatı
- `409` — E-posta zaten kayıtlı
- `500` — Sunucu hatası

---

### `GET /verify-email?token=<TOKEN>`

Kullanıcı onay mailindeki linke tıkladığında bu endpoint çalışır.
Başarılı olursa HTML onay sayfası gösterilir.

**Akış:**
1. Token doğrula (24h TTL)
2. Notion kaydı → `email_verified`
3. Slack daveti gönder
4. Hoş geldin maili gönder
5. Notion kaydı → `active`
6. SMS gönder (opsiyonel, asenkron)

---

### `GET /health`
```json
{"durum": "çalışıyor", "versiyon": "1.0.0"}
```

## Test (curl)

```bash
# Kayıt ol
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"ad_soyad":"Test Kullanıcı","eposta":"test@example.com"}'

# Swagger UI
# http://localhost:8000/docs

# ReDoc
# http://localhost:8000/redoc
```

## Proje Yapısı

```
├── main.py                  # FastAPI app, endpoint'ler
├── config.py                # Ortam değişkenleri
├── models.py                # Pydantic şemaları
├── requirements.txt
├── .env.example             # API key şablonu
├── utils/
│   ├── logger.py            # Merkezi loglama
│   └── token.py             # JWT token yönetimi
└── services/
    ├── notion_service.py    # Tek DB operasyonları
    ├── email_service.py     # Onay + hoş geldin maili
    ├── slack_service.py     # Kanal daveti
    └── sms_service.py       # Opsiyonel SMS
```

## Teknik Borç Önlemleri

| Sorun | Çözüm |
|-------|-------|
| Sonsuz SMS döngüsü | Single attempt + 5s timeout |
| Çift kayıt | E-posta ile idempotency kontrolü |
| Onaysız Slack daveti | `/verify-email` kapı prensibi |
| 3 DB tutarsızlığı | Yalnızca Notion (tek kaynak) |
| Sessiz hatalar | Her adımda logger + try/catch |
