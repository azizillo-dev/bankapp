# ◈ NexBank — Demo Bank Tizimi

Zamonaviy Flask-based demo bank platformasi. TATU talabasi tomonidan yaratilgan.

## Stack
- **Backend:** Python 3 + Flask
- **Database:** SQLite
- **Frontend:** Vanilla HTML/CSS/JS (Google Fonts)
- **AI:** Google Gemini 1.5 Flash
- **Valyuta API:** open.er-api.com (bepul)
- **Email:** Gmail SMTP (OTP kodlar)

## Funksiyalar
- ✅ Ro'yxatdan o'tish + Email OTP tasdiqlash
- ✅ Kirish + Email OTP tasdiqlash
- ✅ Avtomatik 16 xonali unikal karta raqami generatsiya
- ✅ Demo $10,000 boshlang'ich balans
- ✅ Karta raqami orqali pul o'tkazma
- ✅ Real-time balans yangilanishi (15 soniyada)
- ✅ Valyuta kurslari (60 soniyada yangilanadi)
- ✅ Tranzaksiya tarixi (doimiy SQLite da saqlanadi)
- ✅ Chek chiqarish + chop etish
- ✅ Gemini AI chatbot (moliyaviy tahlil)
- ✅ Bir nechta karta qo'shish imkoniyati
- ✅ Profil tahrirlash

---

## WebDock VPS ga deploy qilish

### 1. Fayllarni serverga yuklash
```bash
# SSH orqali ulaning
ssh ubuntu@your-server-ip

# Papka yarating
mkdir -p ~/nexbank && cd ~/nexbank

# Fayllarni yuklash (local kompyuterdan)
# scp -r nexbank/ ubuntu@your-server-ip:~/
```

### 2. Python va kutubxonalarni o'rnatish
```bash
sudo apt update
sudo apt install python3-pip python3-venv nginx -y

cd ~/nexbank
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. .env faylni sozlash
```bash
cp .env.example .env
nano .env
# Qiymatlarni to'ldiring (SECRET_KEY, GEMINI_API_KEY, SMTP_*)
```

### 4. Ma'lumotlar bazasini yaratish
```bash
source venv/bin/activate
python3 -c "from app import init_db; init_db()"
```

### 5. PM2 bilan ishga tushirish
```bash
npm install -g pm2
pm2 start ecosystem.config.yml
pm2 save
pm2 startup
```

### 6. Nginx sozlash
```bash
sudo cp nginx.conf.example /etc/nginx/sites-available/nexbank
sudo nano /etc/nginx/sites-available/nexbank  # domenni o'zgartiring
sudo ln -s /etc/nginx/sites-available/nexbank /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 7. SSL (Certbot)
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com
```

### Test uchun tezda ishga tushirish
```bash
# .env sozlanganidan keyin:
bash start.sh
# yoki
source venv/bin/activate
python3 app.py
# Brauzerda: http://localhost:8000
```

---

## Muhim eslatmalar

**Dev rejimida (SMTP sozlanmasa):**
OTP kodlar terminal/konsolda ko'rinadi — test uchun qulay.

**Gmail App Password olish:**
1. myaccount.google.com → Security
2. 2-Step Verification yoqing
3. App passwords → "Mail" tanlang
4. Hosil bo'lgan 16 ta belgili parolni SMTP_PASS ga kiriting

**Gemini API Key:**
aistudio.google.com → Get API Key (bepul)

---

## Loyiha tuzilmasi
```
nexbank/
├── app.py              # Asosiy Flask ilovasi
├── requirements.txt    # Python kutubxonalar
├── start.sh            # Ishga tushirish skripti
├── ecosystem.config.yml # PM2 konfiguratsiya
├── nginx.conf.example  # Nginx namuna
├── .env.example        # Muhit o'zgaruvchilari namunasi
├── nexbank.db          # SQLite DB (avtomatik yaratiladi)
├── static/
│   ├── css/style.css   # Dizayn tizimi
│   └── js/main.js      # Frontend logika
└── templates/
    ├── base.html
    ├── index.html          # Landing sahifa
    ├── register.html
    ├── login.html
    ├── verify_otp.html
    ├── dashboard.html      # Asosiy panel
    ├── transfer.html       # Pul o'tkazma
    ├── transaction_detail.html  # Chek
    └── profile.html
```

---

*© 2024 NexBank · TATU Demo Loyihasi*
