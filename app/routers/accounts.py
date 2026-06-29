from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_user
from app.models.models import Account, PlaidItem

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/accounts", response_class=HTMLResponse)
def accounts_page(request: Request, db: Session = Depends(get_db)):
    user_or_redirect = require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user = user_or_redirect

    items = db.query(PlaidItem).all()
    accounts = db.query(Account).filter(Account.is_active == True).all()

    # Group accounts by institution
    items_with_accounts = []
    for item in items:
        item_accounts = [a for a in accounts if a.item_id == item.id]
        items_with_accounts.append({
            "item": item,
            "accounts": item_accounts,
        })

    return templates.TemplateResponse("accounts.html", {
        "request": request,
        "user": user,
        "items_with_accounts": items_with_accounts,
        "total_accounts": len(accounts),
    })


@router.get("/accounts/partials", response_class=HTMLResponse)
def account_cards_partial(request: Request, db: Session = Depends(get_db)):
    user_or_redirect = require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect

    items = db.query(PlaidItem).all()
    accounts = db.query(Account).filter(Account.is_active == True).all()

    items_with_accounts = []
    for item in items:
        item_accounts = [a for a in accounts if a.item_id == item.id]
        items_with_accounts.append({
            "item": item,
            "accounts": item_accounts,
        })

    return templates.TemplateResponse("partials/account_cards.html", {
        "request": request,
        "items_with_accounts": items_with_accounts,
    })
