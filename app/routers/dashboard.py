from datetime import date, datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.auth import require_user
from app.models.models import Transaction, Category, Account, PlaidItem

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user_or_redirect = require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user = user_or_redirect

    today = date.today()
    month_start = date(today.year, today.month, 1)

    # Total balance across all active accounts
    total_balance = db.query(func.sum(Account.current_balance)).filter(
        Account.is_active == True
    ).scalar() or 0.0

    # Monthly income: transactions where category is_income=True AND amount < 0 (Plaid negative = income)
    income_category_ids = [
        c.id for c in db.query(Category).filter(Category.is_income == True).all()
    ]

    monthly_income_raw = db.query(func.sum(Transaction.amount)).join(
        Category, Transaction.category_id == Category.id
    ).filter(
        Transaction.date >= month_start,
        Transaction.date <= today,
        Category.is_income == True,
        Transaction.amount < 0,
        Transaction.pending == False,
    ).scalar() or 0.0
    monthly_income = abs(monthly_income_raw)

    # Monthly spending: transactions where category is not income AND amount > 0
    monthly_spending = db.query(func.sum(Transaction.amount)).join(
        Category, Transaction.category_id == Category.id
    ).filter(
        Transaction.date >= month_start,
        Transaction.date <= today,
        Category.is_income == False,
        Transaction.amount > 0,
        Transaction.pending == False,
    ).scalar() or 0.0

    net_cashflow = monthly_income - monthly_spending

    # Spending by category for chart (current month, expenses only)
    spending_by_cat_rows = db.query(
        Category.name,
        Category.color,
        func.sum(Transaction.amount).label("total"),
    ).join(
        Transaction, Transaction.category_id == Category.id
    ).filter(
        Transaction.date >= month_start,
        Transaction.date <= today,
        Category.is_income == False,
        Transaction.amount > 0,
        Transaction.pending == False,
    ).group_by(Category.id, Category.name, Category.color).all()

    spending_by_category = [
        {
            "name": row.name,
            "color": row.color,
            "total": round(row.total, 2),
        }
        for row in spending_by_cat_rows
        if row.total and row.total > 0
    ]

    # Recent transactions (last 10)
    recent_transactions = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .join(Category, Transaction.category_id == Category.id, isouter=True)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(10)
        .all()
    )

    # Accounts with institution info
    accounts = (
        db.query(Account)
        .filter(Account.is_active == True)
        .join(PlaidItem, Account.item_id == PlaidItem.id)
        .all()
    )

    current_month_name = today.strftime("%B %Y")

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "total_balance": round(total_balance, 2),
        "monthly_income": round(monthly_income, 2),
        "monthly_spending": round(monthly_spending, 2),
        "net_cashflow": round(net_cashflow, 2),
        "spending_by_category": spending_by_category,
        "recent_transactions": recent_transactions,
        "accounts": accounts,
        "current_month_name": current_month_name,
    })
