import os
import sqlite3
import random
import string
import hashlib
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, g, flash
)
import requests as req_lib

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "nexbank-super-secret-2024-xyz")

DATABASE = "nexbank.db"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ─── Email config (Gmail SMTP örnek) ──────────────────────────────────────────
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)


# ─── DB helpers ───────────────────────────────────────────────────────────────
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
    return db


@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name  TEXT NOT NULL,
            email      TEXT UNIQUE NOT NULL,
            password   TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS cards (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            card_number TEXT UNIQUE NOT NULL,
            balance     REAL DEFAULT 10000.0,
            currency    TEXT DEFAULT 'USD',
            color       TEXT DEFAULT 'blue',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS otp_codes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT NOT NULL,
            code       TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used       INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_card     TEXT NOT NULL,
            receiver_card   TEXT NOT NULL,
            amount          REAL NOT NULL,
            currency        TEXT DEFAULT 'USD',
            note            TEXT,
            sender_name     TEXT,
            receiver_name   TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );
    """)
    db.commit()
    db.close()


# ─── Auth decorator ───────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


# ─── Utility functions ────────────────────────────────────────────────────────
def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()


def generate_card_number(db):
    while True:
        num = "".join(random.choices(string.digits, k=16))
        existing = db.execute(
            "SELECT id FROM cards WHERE card_number=?", (num,)
        ).fetchone()
        if not existing:
            return num


def send_otp_email(email, code):
    if not SMTP_USER:
        print(f"[DEV MODE] OTP for {email}: {code}")
        return True
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "NexBank - Tasdiqlash kodi"
        msg["From"] = SMTP_FROM
        msg["To"] = email
        html = f"""
        <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:32px;
                    background:#0a0f1e;color:#fff;border-radius:12px">
          <h2 style="color:#00d4ff;margin-bottom:8px">NexBank</h2>
          <p>Sizning bir martalik kirish kodingiz:</p>
          <div style="font-size:36px;font-weight:700;letter-spacing:8px;
                      color:#00d4ff;padding:24px;background:#111827;
                      border-radius:8px;text-align:center;margin:24px 0">{code}</div>
          <p style="color:#9ca3af;font-size:13px">Kod 10 daqiqa davomida amal qiladi.</p>
        </div>"""
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_FROM, email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


CARD_COLORS = ["blue", "purple", "green", "orange", "pink"]


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


# ── Register ──────────────────────────────────────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name  = request.form.get("last_name", "").strip()
        email      = request.form.get("email", "").strip().lower()
        password   = request.form.get("password", "")
        if not all([first_name, last_name, email, password]):
            flash("Barcha maydonlarni to'ldiring", "error")
            return render_template("register.html")
        db = get_db()
        if db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            flash("Bu email allaqachon ro'yxatdan o'tgan", "error")
            return render_template("register.html")
        code = "".join(random.choices(string.digits, k=6))
        expires = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
        db.execute(
            "INSERT INTO otp_codes (email, code, expires_at) VALUES (?,?,?)",
            (email, code, expires)
        )
        db.commit()
        send_otp_email(email, code)
        session["pending_register"] = {
            "first_name": first_name, "last_name": last_name,
            "email": email, "password": hash_pw(password)
        }
        return redirect(url_for("verify_otp", purpose="register"))
    return render_template("register.html")


# ── Login ─────────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, hash_pw(password))
        ).fetchone()
        if not user:
            flash("Email yoki parol noto'g'ri", "error")
            return render_template("login.html")
        code    = "".join(random.choices(string.digits, k=6))
        expires = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
        db.execute(
            "INSERT INTO otp_codes (email, code, expires_at) VALUES (?,?,?)",
            (email, code, expires)
        )
        db.commit()
        send_otp_email(email, code)
        session["pending_login_email"] = email
        return redirect(url_for("verify_otp", purpose="login"))
    return render_template("login.html")


# ── OTP verify ────────────────────────────────────────────────────────────────
@app.route("/verify-otp/<purpose>", methods=["GET", "POST"])
def verify_otp(purpose):
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        db   = get_db()
        now  = datetime.utcnow().isoformat()

        if purpose == "register":
            pending = session.get("pending_register")
            if not pending:
                return redirect(url_for("register"))
            email = pending["email"]
        else:
            email = session.get("pending_login_email")
            if not email:
                return redirect(url_for("login"))

        otp = db.execute(
            "SELECT * FROM otp_codes WHERE email=? AND code=? AND used=0 AND expires_at>?",
            (email, code, now)
        ).fetchone()
        if not otp:
            flash("Kod noto'g'ri yoki muddati o'tgan", "error")
            return render_template("verify_otp.html", purpose=purpose)

        db.execute("UPDATE otp_codes SET used=1 WHERE id=?", (otp["id"],))

        if purpose == "register":
            p = pending
            db.execute(
                "INSERT INTO users (first_name,last_name,email,password) VALUES (?,?,?,?)",
                (p["first_name"], p["last_name"], p["email"], p["password"])
            )
            db.commit()
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            card_num = generate_card_number(db)
            color    = random.choice(CARD_COLORS)
            db.execute(
                "INSERT INTO cards (user_id,card_number,balance,color) VALUES (?,?,?,?)",
                (user["id"], card_num, 10000.0, color)
            )
            db.commit()
            session.pop("pending_register", None)
        else:
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            db.commit()
            session.pop("pending_login_email", None)

        session["user_id"] = user["id"]
        session["user_name"] = f"{user['first_name']} {user['last_name']}"
        return redirect(url_for("dashboard"))

    return render_template("verify_otp.html", purpose=purpose)


# ── Logout ────────────────────────────────────────────────────────────────────
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    db    = get_db()
    user  = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    cards = db.execute("SELECT * FROM cards WHERE user_id=?", (session["user_id"],)).fetchall()
    txns  = db.execute("""
        SELECT * FROM transactions
        WHERE sender_card IN (SELECT card_number FROM cards WHERE user_id=?)
           OR receiver_card IN (SELECT card_number FROM cards WHERE user_id=?)
        ORDER BY created_at DESC LIMIT 20
    """, (session["user_id"], session["user_id"])).fetchall()
    user_cards = [c["card_number"] for c in cards]
    return render_template("dashboard.html", user=user, cards=cards,
                           transactions=txns, user_cards=user_cards)


# ── Transfer ──────────────────────────────────────────────────────────────────
@app.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():
    db = get_db()
    my_cards = db.execute(
        "SELECT * FROM cards WHERE user_id=?", (session["user_id"],)
    ).fetchall()

    if request.method == "POST":
        from_card  = request.form.get("from_card", "").strip()
        to_card    = request.form.get("to_card", "").strip().replace(" ", "")
        amount     = float(request.form.get("amount", 0))
        note       = request.form.get("note", "")

        if amount <= 0:
            flash("Miqdor 0 dan katta bo'lishi kerak", "error")
            return render_template("transfer.html", cards=my_cards)

        sender_card = db.execute(
            "SELECT * FROM cards WHERE card_number=? AND user_id=?",
            (from_card, session["user_id"])
        ).fetchone()
        if not sender_card:
            flash("Kartangiz topilmadi", "error")
            return render_template("transfer.html", cards=my_cards)
        if sender_card["card_number"] == to_card:
            flash("O'z kartangizga o'tkazma qilib bo'lmaydi", "error")
            return render_template("transfer.html", cards=my_cards)
        if sender_card["balance"] < amount:
            flash("Hisobingizda yetarli mablag' yo'q", "error")
            return render_template("transfer.html", cards=my_cards)

        receiver_card = db.execute(
            "SELECT cards.*, users.first_name, users.last_name FROM cards JOIN users ON cards.user_id=users.id WHERE cards.card_number=?", (to_card,)
        ).fetchone()
        if not receiver_card:
            flash("Qabul qiluvchi karta topilmadi", "error")
            return render_template("transfer.html", cards=my_cards)

        sender_user = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()

        db.execute(
            "UPDATE cards SET balance=balance-? WHERE card_number=?",
            (amount, from_card)
        )
        db.execute(
            "UPDATE cards SET balance=balance+? WHERE card_number=?",
            (amount, to_card)
        )
        txn_id = db.execute(
            """INSERT INTO transactions
               (sender_card,receiver_card,amount,currency,note,sender_name,receiver_name)
               VALUES (?,?,?,?,?,?,?)""",
            (from_card, to_card, amount, "USD", note,
             f"{sender_user['first_name']} {sender_user['last_name']}",
             f"{receiver_card['first_name']} {receiver_card['last_name']}")
        ).lastrowid
        db.commit()
        flash("O'tkazma muvaffaqiyatli amalga oshirildi!", "success")
        return redirect(url_for("transaction_detail", txn_id=txn_id))

    return render_template("transfer.html", cards=my_cards)


# ── Transaction detail / check ────────────────────────────────────────────────
@app.route("/transaction/<int:txn_id>")
@login_required
def transaction_detail(txn_id):
    db  = get_db()
    txn = db.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()
    if not txn:
        flash("Tranzaksiya topilmadi", "error")
        return redirect(url_for("dashboard"))
    return render_template("transaction_detail.html", txn=txn)


# ── Add new card ──────────────────────────────────────────────────────────────
@app.route("/add-card", methods=["POST"])
@login_required
def add_card():
    db       = get_db()
    card_num = generate_card_number(db)
    color    = random.choice(CARD_COLORS)
    db.execute(
        "INSERT INTO cards (user_id,card_number,balance,color) VALUES (?,?,?,?)",
        (session["user_id"], card_num, 0.0, color)
    )
    db.commit()
    flash("Yangi karta qo'shildi!", "success")
    return redirect(url_for("dashboard"))


# ─── API: balance (realtime polling) ─────────────────────────────────────────
@app.route("/api/balance")
@login_required
def api_balance():
    db    = get_db()
    cards = db.execute(
        "SELECT card_number, balance, currency, color FROM cards WHERE user_id=?",
        (session["user_id"],)
    ).fetchall()
    return jsonify([dict(c) for c in cards])


# ─── API: exchange rates ──────────────────────────────────────────────────────
@app.route("/api/rates")
def api_rates():
    try:
        r = req_lib.get(
            "https://open.er-api.com/v6/latest/USD", timeout=5
        )
        data = r.json()
        rates = {k: data["rates"][k] for k in ["EUR","GBP","JPY","UZS","RUB","CNY","KRW"] if k in data.get("rates",{})}
        return jsonify({"success": True, "rates": rates, "base": "USD"})
    except Exception as e:
        # fallback static rates
        return jsonify({"success": True, "base": "USD", "rates": {
            "EUR":0.92,"GBP":0.79,"JPY":149.5,"UZS":12700,"RUB":91.5,"CNY":7.24,"KRW":1340
        }})


# ─── API: Gemini chatbot ──────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    if not GEMINI_API_KEY:
        return jsonify({"reply": "Gemini API kaliti sozlanmagan. .env faylga GEMINI_API_KEY qo'shing."})

    db    = get_db()
    cards = db.execute(
        "SELECT card_number, balance FROM cards WHERE user_id=?",
        (session["user_id"],)
    ).fetchall()
    txns  = db.execute("""
        SELECT * FROM transactions
        WHERE sender_card IN (SELECT card_number FROM cards WHERE user_id=?)
           OR receiver_card IN (SELECT card_number FROM cards WHERE user_id=?)
        ORDER BY created_at DESC LIMIT 10
    """, (session["user_id"], session["user_id"])).fetchall()

    balance_info = "; ".join([f"Karta {c['card_number'][-4:]}: ${c['balance']:.2f}" for c in cards])
    txn_summary  = "; ".join([
        f"{t['created_at'][:10]}: ${t['amount']:.2f} {'chiqim' if t['sender_card'] in [c['card_number'] for c in cards] else 'kirim'}"
        for t in txns
    ])

    user_msg = request.json.get("message", "")
    context  = f"""Sen NexBank sun'iy intellekt moliyaviy maslahatchisin. 
Foydalanuvchi ma'lumotlari: {session.get('user_name','')}.
Kartalar va balans: {balance_info}.
Oxirgi tranzaksiyalar: {txn_summary}.
Foydalanuvchi savoliga qisqa, aniq va foydali javob ber. O'zbek tilida javob ber."""

    try:
        resp = req_lib.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            json={
                "contents": [
                    {"role": "user", "parts": [{"text": context + "\n\nSavol: " + user_msg}]}
                ]
            },
            timeout=15
        )
        data  = resp.json()
        reply = data["candidates"][0]["content"]["parts"][0]["text"]
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": f"Xato yuz berdi: {str(e)}"})


# ─── Profile ──────────────────────────────────────────────────────────────────
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name  = request.form.get("last_name", "").strip()
        db.execute(
            "UPDATE users SET first_name=?, last_name=? WHERE id=?",
            (first_name, last_name, session["user_id"])
        )
        db.commit()
        session["user_name"] = f"{first_name} {last_name}"
        flash("Profil yangilandi!", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", user=user)


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
