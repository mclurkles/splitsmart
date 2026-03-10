# SplitSmart 💸

A Splitwise-style expense splitting app built with Python/Flask. Split expenses for trips and events with friends, settle up with minimal transactions, and invite people via QR code.

## Features

- **Trips & Events** — A trip has multiple expenses; an event is a single expense
- **Flexible splits** — Equal, custom percentage, or fixed dollar amount
- **QR code invites** — Generate a QR code; friends scan to join your trip instantly
- **Add by phone/email** — Manually add registered users
- **Debt simplification** — Auto-calculates the fewest payments needed to settle up (e.g. if A owes B and B owes C, A pays C directly)
- **Multi-currency** — 20+ currencies supported; auto-converts to AUD via free [frankfurter.app](https://frankfurter.app) API
- **Anyone can open/close** — Any trip member can close or reopen a trip
- **Settlement tracking** — Mark individual payments as paid

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.11 / Flask |
| ORM | SQLAlchemy + Flask-Migrate |
| Database | PostgreSQL (Render free) / SQLite (local dev) |
| Auth | Flask-Login (email + password) |
| QR codes | `qrcode` library (server-side PNG generation) |
| Currency | [frankfurter.app](https://frankfurter.app) — free, no API key |
| Frontend | Jinja2 templates, vanilla JS, mobile-first CSS |
| Deployment | Render |

---

## Local Development

### 1. Clone and set up

```bash
git clone <your-repo>
cd splitsmart
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — the defaults work for local dev
```

### 3. Run

```bash
python run.py
```

Open [http://localhost:5000](http://localhost:5000)

---

## Deploy to Render

### Option A: render.yaml (recommended)

1. Push your code to GitHub
2. Go to [render.com](https://render.com) → New → Blueprint
3. Connect your repo
4. Render will read `render.yaml` and create the web service + PostgreSQL database automatically
5. **Update `BASE_URL`** in `render.yaml` to your actual Render URL (e.g. `https://splitsmart.onrender.com`)

### Option B: Manual

1. Create a new **Web Service** on Render
2. Connect your GitHub repo
3. Settings:
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `gunicorn run:app --bind 0.0.0.0:$PORT --workers 2`
4. Create a **PostgreSQL** database (free tier)
5. Add environment variables:
   - `DATABASE_URL` → from the Postgres connection string
   - `SECRET_KEY` → generate a random string
   - `BASE_URL` → your Render URL (for QR codes)

> **Note**: Render's free tier spins down after inactivity. First request may take 30–60s to wake up.

---

## How It Works

### Debt Simplification Algorithm

The settlement engine uses a greedy algorithm to minimise transactions:

1. Calculate each person's **net balance** (what they paid minus what they owe)
2. Separate into **creditors** (net positive) and **debtors** (net negative)
3. Greedily match largest creditor with largest debtor
4. Result: the minimum number of payments to settle everything

**Example:**
- Alice paid $150 dinner (split 3 ways)
- Bob paid $90 drinks (split 3 ways)
- Charlie paid nothing

Naive: Charlie pays Alice $50, Charlie pays Bob $30 = 2 transactions ✓
Complex: If A owes B $100 and B owes C $100 → A just pays C $100 = 1 transaction

### QR Code Flow

1. Trip creator clicks **QR Invite**
2. App generates a QR code linking to `/trips/join/<unique_token>`
3. Friend scans QR → lands on login/register page
4. After login, they're automatically added to the trip as a member

---

## Project Structure

```
splitsmart/
├── app/
│   ├── __init__.py          # App factory
│   ├── models.py            # SQLAlchemy models
│   ├── utils.py             # Debt simplification, currency, splits
│   ├── routes/
│   │   ├── auth.py          # Login, register, profile
│   │   ├── main.py          # Dashboard
│   │   ├── trips.py         # Trip CRUD, members, settlements
│   │   ├── expenses.py      # Expense CRUD
│   │   └── qr.py            # QR code generation
│   └── templates/
│       ├── base.html        # Base layout
│       ├── index.html       # Landing page
│       ├── dashboard.html
│       ├── qr_page.html
│       ├── auth/            # login, register, profile
│       ├── trips/           # new, view, members
│       └── expenses/        # new, edit
├── run.py                   # Entry point
├── requirements.txt
├── render.yaml              # Render deployment config
└── .env.example
```

---

## Future Enhancements

- Email/SMS notifications when added to a trip
- Push notifications via PWA
- Recurring expenses
- Receipt photo uploads (Azure Blob / Cloudinary)
- Export to PDF
- Beemit/PayID/BSB payment links for Australian settlements
- Google/Apple OAuth login
