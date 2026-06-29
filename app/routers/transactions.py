from datetime import date, timedelta
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_user
from app.models.models import Transaction, Category, Account, PlaidItem
from app.services import plaid_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_filtered_transactions(
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: int | None = None,
    account_id: int | None = None,
    limit: int = 200,
):
    query = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .join(Category, Transaction.category_id == Category.id, isouter=True)
    )

    if date_from:
        query = query.filter(Transaction.date >= date_from)
    if date_to:
        query = query.filter(Transaction.date <= date_to)
    if category_id:
        query = query.filter(Transaction.category_id == category_id)
    if account_id:
        query = query.filter(Transaction.account_id == account_id)

    return query.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit).all()


@router.get("/transactions", response_class=HTMLResponse)
def transactions_page(
    request: Request,
    date_from: str | None = None,
    date_to: str | None = None,
    category_id: int | None = None,
    account_id: int | None = None,
    db: Session = Depends(get_db),
):
    user_or_redirect = require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user = user_or_redirect

    # Default date range: current month
    today = date.today()
    if not date_from:
        date_from_obj = date(today.year, today.month, 1)
    else:
        try:
            date_from_obj = date.fromisoformat(date_from)
        except ValueError:
            date_from_obj = date(today.year, today.month, 1)

    if not date_to:
        date_to_obj = today
    else:
        try:
            date_to_obj = date.fromisoformat(date_to)
        except ValueError:
            date_to_obj = today

    categories = db.query(Category).order_by(Category.name).all()
    accounts = db.query(Account).filter(Account.is_active == True).all()

    transactions = get_filtered_transactions(
        db,
        date_from=date_from_obj,
        date_to=date_to_obj,
        category_id=category_id,
        account_id=account_id,
    )

    return templates.TemplateResponse("transactions.html", {
        "request": request,
        "user": user,
        "transactions": transactions,
        "categories": categories,
        "accounts": accounts,
        "date_from": date_from_obj.isoformat(),
        "date_to": date_to_obj.isoformat(),
        "selected_category_id": category_id,
        "selected_account_id": account_id,
    })


@router.get("/transactions/rows", response_class=HTMLResponse)
def transaction_rows(
    request: Request,
    date_from: str | None = None,
    date_to: str | None = None,
    category_id: int | None = None,
    account_id: int | None = None,
    db: Session = Depends(get_db),
):
    user_or_redirect = require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    today = date.today()
    date_from_obj = None
    date_to_obj = None

    if date_from:
        try:
            date_from_obj = date.fromisoformat(date_from)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_obj = date.fromisoformat(date_to)
        except ValueError:
            pass

    categories = db.query(Category).order_by(Category.name).all()

    transactions = get_filtered_transactions(
        db,
        date_from=date_from_obj,
        date_to=date_to_obj,
        category_id=category_id,
        account_id=account_id,
    )

    return templates.TemplateResponse("partials/transaction_rows.html", {
        "request": request,
        "transactions": transactions,
        "categories": categories,
    })


@router.post("/transactions/{transaction_id}/category", response_class=HTMLResponse)
def update_transaction_category(
    request: Request,
    transaction_id: int,
    category_id: int = Form(...),
    db: Session = Depends(get_db),
):
    user_or_redirect = require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        return HTMLResponse("<tr><td colspan='6'>Transaction not found</td></tr>", status_code=404)

    transaction.category_id = category_id
    db.commit()
    db.refresh(transaction)

    categories = db.query(Category).order_by(Category.name).all()

    return templates.TemplateResponse("partials/transaction_rows.html", {
        "request": request,
        "transactions": [transaction],
        "categories": categories,
    })


@router.get("/transactions/sync")
def sync_transactions(request: Request, db: Session = Depends(get_db)):
    user_or_redirect = require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    from app.models.models import PlaidItem
    from app.services.plaid_service import get_plaid_client, sync_transactions as plaid_sync, map_plaid_category

    client = get_plaid_client()
    items = db.query(PlaidItem).all()
    total_synced = 0

    for item in items:
        try:
            added, modified, removed, next_cursor = plaid_sync(
                item.access_token, item.cursor, client
            )

            # Process removed transactions
            for removed_txn in removed:
                txn = db.query(Transaction).filter(
                    Transaction.plaid_transaction_id == removed_txn["transaction_id"]
                ).first()
                if txn:
                    db.delete(txn)

            # Process added and modified transactions
            for txn_data in added + modified:
                # Get account
                account = db.query(Account).filter(
                    Account.plaid_account_id == txn_data["account_id"]
                ).first()
                if not account:
                    continue

                # Map category
                plaid_cats = txn_data.get("category", []) or []
                category_name = map_plaid_category(plaid_cats)
                category = db.query(Category).filter(Category.name == category_name).first()
                if not category:
                    category = db.query(Category).filter(Category.name == "Other").first()

                plaid_cat_str = " > ".join(plaid_cats) if plaid_cats else ""
                logo_url = txn_data.get("logo_url")

                # Upsert transaction
                existing = db.query(Transaction).filter(
                    Transaction.plaid_transaction_id == txn_data["transaction_id"]
                ).first()

                if existing:
                    existing.amount = txn_data["amount"]
                    existing.date = txn_data["date"]
                    existing.name = txn_data["name"]
                    existing.merchant_name = txn_data.get("merchant_name")
                    existing.plaid_category = plaid_cat_str
                    existing.pending = txn_data.get("pending", False)
                    existing.logo_url = logo_url
                    if not existing.category_id:
                        existing.category_id = category.id if category else None
                else:
                    new_txn = Transaction(
                        plaid_transaction_id=txn_data["transaction_id"],
                        account_id=account.id,
                        category_id=category.id if category else None,
                        amount=txn_data["amount"],
                        date=txn_data["date"],
                        name=txn_data["name"],
                        merchant_name=txn_data.get("merchant_name"),
                        plaid_category=plaid_cat_str,
                        pending=txn_data.get("pending", False),
                        logo_url=logo_url,
                    )
                    db.add(new_txn)
                    total_synced += 1

            item.cursor = next_cursor
            db.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error syncing item {item.item_id}: {e}")
            db.rollback()

    return RedirectResponse(url="/transactions", status_code=302)
