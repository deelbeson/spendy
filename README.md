# Spendy — Family Finance Dashboard

A personal finance web application for tracking family spending, income, and savings capacity. Built with FastAPI, HTMX, Tailwind CSS, and Plaid for bank syncing.

## Features

- **Dashboard**: Monthly income, spending, net cash flow, and spending breakdown by category
- **Transactions**: Full transaction history with filtering by date, category, and account; inline category editing
- **Accounts**: Connect bank accounts via Plaid; view balances and account details
- **Auto-sync**: Transactions sync automatically from all connected banks using Plaid's cursor-based sync
- **15 spending categories**: Pre-seeded with colors and Plaid category mapping

## Tech Stack

- **Backend**: FastAPI (Python)
- **Templates**: Jinja2 + HTMX + Tailwind CSS (both via CDN)
- **Charts**: Chart.js (via CDN)
- **Database**: PostgreSQL via SQLAlchemy (sync, psycopg2)
- **Migrations**: Alembic
- **Auth**: Single-user session auth (Starlette SessionMiddleware + passlib bcrypt)
- **Bank Sync**: Plaid Python SDK v26.x

---

## Prerequisites

- Python 3.11+
- PostgreSQL (or a Supabase project — see below)
- A Plaid developer account (free sandbox available at [dashboard.plaid.com](https://dashboard.plaid.com))

---

## Setup

### 1. Clone / navigate to the project

```bash
cd /path/to/spendy
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/spendy
SECRET_KEY=some-long-random-string-change-me
PLAID_CLIENT_ID=your_plaid_client_id
PLAID_SECRET=your_plaid_sandbox_secret
PLAID_ENV=sandbox
```

### 5. Database setup

#### Option A: Local PostgreSQL

```bash
createdb spendy
```

#### Option B: Supabase (recommended for cloud)

1. Go to [supabase.com](https://supabase.com) and create a free project
2. In your project dashboard: **Settings → Database → Connection string → URI**
3. Copy the URI (replace `[YOUR-PASSWORD]` with your actual password)
4. Paste it as `DATABASE_URL` in your `.env` file

Example Supabase URL format:
```
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-us-east-1.pooler.supabase.com:5432/postgres
```

### 6. Run database migrations

```bash
alembic upgrade head
```

This creates all tables. The app will seed default categories on first startup.

### 7. Start the application

```bash
python run.py
```

The app runs on [http://localhost:8000](http://localhost:8000).

### 8. First-time setup

On first visit, you'll be redirected to `/setup` to create your admin account:

- Choose a username (3+ characters)
- Choose a password (8+ characters)
- Click "Create Account & Get Started"

### 9. Connect your bank accounts

1. Go to **Accounts** in the sidebar
2. Click **"Connect a Bank Account"**
3. Plaid Link will open — search for your bank and enter credentials
4. After connecting, your accounts and transactions will sync automatically

### 10. Plaid Sandbox Testing

In sandbox mode, you can use test credentials to simulate a bank connection:

- **Username**: `user_good`
- **Password**: `pass_good`
- Or use the institution "First Platypus Bank" for testing

Plaid sandbox generates realistic fake transaction data including various categories.

---

## Architecture Overview

```
app/
├── main.py          # FastAPI app, middleware, router registration, startup hook
├── config.py        # pydantic-settings (loads from .env)
├── database.py      # SQLAlchemy engine, session, Base, init_db() with category seeding
├── auth.py          # Password hashing, session-based auth helpers
├── models/
│   └── models.py    # User, PlaidItem, Account, Category, Transaction
├── routers/
│   ├── auth_router.py   # /login, /logout, /setup
│   ├── dashboard.py     # / (main dashboard)
│   ├── transactions.py  # /transactions (list, filter, category update, sync)
│   ├── accounts.py      # /accounts (list connected accounts)
│   └── plaid_router.py  # /plaid/* (link token, exchange token, sync)
├── services/
│   └── plaid_service.py # Plaid API client, link token, sync, category mapping
└── templates/
    ├── base.html         # Layout with sidebar nav
    ├── login.html        # Login form (standalone)
    ├── setup.html        # First-time account creation (standalone)
    ├── dashboard.html    # Main dashboard with Chart.js doughnut
    ├── transactions.html # Transaction table with HTMX filters
    ├── accounts.html     # Account list with Plaid Link integration
    └── partials/
        ├── transaction_rows.html  # HTMX partial for transaction table rows
        └── account_cards.html    # HTMX partial for account cards
```

### Key Design Decisions

**Transaction Amounts**: Plaid uses positive = expense, negative = income/refund. The UI displays positive amounts in red and negative in green (shown as a positive income figure).

**Category Mapping**: Plaid categories (hierarchical strings like `["Food and Drink", "Groceries"]`) are mapped to our 15 custom categories in `plaid_service.py`. Users can override any transaction's category via inline dropdowns in the transactions view.

**Sync Strategy**: Uses Plaid's cursor-based `/transactions/sync` endpoint. Each PlaidItem stores the last cursor, so syncs are incremental — only new/modified/removed transactions are fetched.

**Auth**: Single-user, session-based. The `require_user()` helper checks the session and redirects to `/setup` if no users exist, or `/login` if the session is invalid.

**HTMX**: The transactions filter form uses HTMX to swap only the table body on filter changes, avoiding full page reloads. Category dropdowns in transaction rows do an HTMX POST to update the category and swap only that row.

---

## Running in Production

For production deployment:

1. Set `PLAID_ENV=production` (requires a paid Plaid plan) or `development`
2. Generate a strong `SECRET_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"`
3. Use a production WSGI server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

4. Put behind a reverse proxy (nginx/Caddy) with HTTPS

---

## Development

To generate a new migration after model changes:

```bash
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
```

To reset the database (destructive!):

```bash
alembic downgrade base
alembic upgrade head
```
