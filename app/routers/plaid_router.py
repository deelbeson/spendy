import logging
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_user
from app.models.models import PlaidItem, Account, Transaction, Category
from app.services.plaid_service import (
    get_plaid_client,
    create_link_token,
    exchange_public_token,
    get_institution_name,
    sync_transactions,
    get_accounts,
    map_plaid_category,
)

router = APIRouter(prefix="/plaid")
logger = logging.getLogger(__name__)


@router.post("/link-token")
def plaid_link_token(request: Request, db: Session = Depends(get_db)):
    user_or_redirect = require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    user = user_or_redirect

    try:
        link_token = create_link_token(client_user_id=str(user.id))
        return JSONResponse({"link_token": link_token})
    except Exception as e:
        logger.error(f"Error creating link token: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/exchange-token")
async def plaid_exchange_token(request: Request, db: Session = Depends(get_db)):
    user_or_redirect = require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    body = await request.json()
    public_token = body.get("public_token")
    institution_name = body.get("institution_name", "Unknown Bank")
    institution_id = body.get("institution_id", "")

    if not public_token:
        return JSONResponse({"error": "Missing public_token"}, status_code=400)

    try:
        client = get_plaid_client()

        # Exchange token
        token_data = exchange_public_token(public_token)
        access_token = token_data["access_token"]
        item_id = token_data["item_id"]

        # Check if item already exists
        existing_item = db.query(PlaidItem).filter(PlaidItem.item_id == item_id).first()
        if existing_item:
            return JSONResponse({"status": "already_connected", "item_id": item_id})

        # Get full institution name from Plaid if we have the ID
        if institution_id:
            try:
                institution_name = get_institution_name(institution_id, client)
            except Exception:
                pass  # Use the name from metadata

        # Save PlaidItem
        plaid_item = PlaidItem(
            item_id=item_id,
            access_token=access_token,
            institution_name=institution_name,
            institution_id=institution_id,
        )
        db.add(plaid_item)
        db.flush()

        # Fetch and save accounts
        accounts_data = get_accounts(access_token, client)
        for acct in accounts_data:
            acct_dict = acct.to_dict() if hasattr(acct, "to_dict") else acct
            balances = acct_dict.get("balances") or {}
            # Plaid returns AccountType/AccountSubtype enums — convert to plain strings
            acct_type = acct_dict.get("type", "depository")
            acct_subtype = acct_dict.get("subtype")
            if hasattr(acct_type, "value"):
                acct_type = acct_type.value
            if hasattr(acct_subtype, "value"):
                acct_subtype = acct_subtype.value
            account = Account(
                plaid_account_id=acct_dict["account_id"],
                item_id=plaid_item.id,
                name=acct_dict["name"],
                official_name=acct_dict.get("official_name"),
                type=str(acct_type) if acct_type else "depository",
                subtype=str(acct_subtype) if acct_subtype else None,
                current_balance=balances.get("current"),
                available_balance=balances.get("available"),
                currency=balances.get("iso_currency_code") or "USD",
                mask=acct_dict.get("mask"),
                is_active=True,
            )
            db.add(account)

        db.commit()

        # Sync initial transactions
        _sync_item_transactions(plaid_item.id, access_token, db, client)

        return JSONResponse({"status": "success", "item_id": item_id})

    except Exception as e:
        logger.error(f"Error exchanging token: {e}")
        db.rollback()
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/sync")
def plaid_sync_all(request: Request, db: Session = Depends(get_db)):
    user_or_redirect = require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    client = get_plaid_client()
    items = db.query(PlaidItem).all()
    total_synced = 0

    for item in items:
        try:
            count = _sync_item_transactions(item.id, item.access_token, db, client)
            total_synced += count
        except Exception as e:
            logger.error(f"Error syncing item {item.item_id}: {e}")

    return JSONResponse({"synced": total_synced})


def _sync_item_transactions(item_id: int, access_token: str, db: Session, client) -> int:
    item = db.query(PlaidItem).filter(PlaidItem.id == item_id).first()
    if not item:
        return 0

    try:
        added, modified, removed, next_cursor = sync_transactions(
            access_token, item.cursor, client
        )

        synced_count = 0

        # Process removed
        for removed_txn in removed:
            txn_id = removed_txn.get("transaction_id") if isinstance(removed_txn, dict) else removed_txn["transaction_id"]
            txn = db.query(Transaction).filter(
                Transaction.plaid_transaction_id == txn_id
            ).first()
            if txn:
                db.delete(txn)

        # Process added + modified
        for txn_data in added + modified:
            if isinstance(txn_data, dict):
                txn_dict = txn_data
            else:
                # plaid-python model object
                txn_dict = txn_data.to_dict() if hasattr(txn_data, "to_dict") else dict(txn_data)

            acct_id = txn_dict.get("account_id")
            account = db.query(Account).filter(
                Account.plaid_account_id == acct_id
            ).first()
            if not account:
                continue

            # Map category
            plaid_cats = txn_dict.get("category") or []
            category_name = map_plaid_category(plaid_cats)
            category = db.query(Category).filter(Category.name == category_name).first()
            if not category:
                category = db.query(Category).filter(Category.name == "Other").first()

            plaid_cat_str = " > ".join(plaid_cats) if plaid_cats else ""
            logo_url = txn_dict.get("logo_url")
            txn_date = txn_dict.get("date")

            existing = db.query(Transaction).filter(
                Transaction.plaid_transaction_id == txn_dict["transaction_id"]
            ).first()

            if existing:
                existing.amount = txn_dict["amount"]
                existing.date = txn_date
                existing.name = txn_dict["name"]
                existing.merchant_name = txn_dict.get("merchant_name")
                existing.plaid_category = plaid_cat_str
                existing.pending = txn_dict.get("pending", False)
                existing.logo_url = logo_url
                if not existing.category_id:
                    existing.category_id = category.id if category else None
            else:
                new_txn = Transaction(
                    plaid_transaction_id=txn_dict["transaction_id"],
                    account_id=account.id,
                    category_id=category.id if category else None,
                    amount=txn_dict["amount"],
                    date=txn_date,
                    name=txn_dict["name"],
                    merchant_name=txn_dict.get("merchant_name"),
                    plaid_category=plaid_cat_str,
                    pending=txn_dict.get("pending", False),
                    logo_url=logo_url,
                )
                db.add(new_txn)
                synced_count += 1

        # Update account balances while we have the client
        try:
            from app.services.plaid_service import get_accounts
            accounts_data = get_accounts(access_token, client)
            for acct_data in accounts_data:
                if isinstance(acct_data, dict):
                    acct_dict = acct_data
                else:
                    acct_dict = acct_data.to_dict() if hasattr(acct_data, "to_dict") else dict(acct_data)

                account = db.query(Account).filter(
                    Account.plaid_account_id == acct_dict.get("account_id")
                ).first()
                if account:
                    balances = acct_dict.get("balances", {})
                    account.current_balance = balances.get("current")
                    account.available_balance = balances.get("available")
        except Exception as e:
            logger.warning(f"Could not update account balances: {e}")

        item.cursor = next_cursor
        db.commit()
        return synced_count

    except Exception as e:
        logger.error(f"Error in _sync_item_transactions: {e}")
        db.rollback()
        raise
