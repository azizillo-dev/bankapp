#!/bin/bash
# NexBank — Server ishga tushirish skripti

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ◈ NexBank — Ishga tushirilmoqda..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# .env faylni yuklash (agar mavjud bo'lsa)
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
    echo "✓ .env fayl yuklandi"
fi

PORT=${PORT:-8000}

# Virtual environment tekshirish
if [ ! -d "venv" ]; then
    echo "→ Virtual environment yaratilmoqda..."
    python3 -m venv venv
fi

echo "→ Kutubxonalar o'rnatilmoqda..."
source venv/bin/activate
pip install -r requirements.txt -q

echo "→ Ma'lumotlar bazasi yaratilmoqda..."
python3 -c "from app import init_db; init_db(); print('✓ DB tayyor')"

echo ""
echo "✓ NexBank http://0.0.0.0:$PORT portida ishlamoqda"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Gunicorn bilan ishga tushirish (production)
gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
