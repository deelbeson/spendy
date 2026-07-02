import logging
from typing import Optional

import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.configuration import Configuration
from plaid.api_client import ApiClient

from app.config import settings

logger = logging.getLogger(__name__)

# Plaid environment mapping
PLAID_ENV_URLS = {
    "sandbox": "https://sandbox.plaid.com",
    "production": "https://production.plaid.com",
}

# Category mapping from Plaid categories to our custom categories
CATEGORY_MAPPING = {
    # Groceries
    ("food and drink", "groceries"): "Groceries",
    # Dining
    ("food and drink",): "Dining",
    # Fuel
    ("travel", "gas stations"): "Fuel",
    # Utilities
    ("service", "gas utilities"): "Utilities",
    ("service", "electric"): "Utilities",
    ("service", "water"): "Utilities",
    ("service", "utilities"): "Utilities",
    # Subscriptions
    ("service", "subscription"): "Subscriptions",
    ("service", "software"): "Subscriptions",
    # Healthcare
    ("healthcare",): "Healthcare",
    ("medical",): "Healthcare",
    # Insurance
    ("insurance",): "Insurance",
    # Entertainment
    ("entertainment",): "Entertainment",
    ("recreation",): "Entertainment",
    # Pet Care
    ("shops", "pet supplies"): "Pet Care",
    ("service", "veterinary services"): "Pet Care",
    ("pet",): "Pet Care",
    # Shopping
    ("shops",): "Shopping",
    # Income
    ("transfer", "credit"): "Income",
    ("payroll",): "Income",
    ("deposit",): "Income",
    ("income",): "Income",
    # Mortgage
    ("mortgage",): "Mortgage",
    ("real estate",): "Mortgage",
    # Transportation
    ("auto",): "Transportation",
    ("travel", "public transportation"): "Transportation",
    ("travel", "taxi"): "Transportation",
    ("transportation",): "Transportation",
    # Home Maintenance
    ("home improvement",): "Home Maintenance",
    ("service", "home improvement"): "Home Maintenance",
}


def get_plaid_client() -> plaid_api.PlaidApi:
    env_url = PLAID_ENV_URLS.get(settings.plaid_env.lower(), PLAID_ENV_URLS["production"])
    configuration = Configuration(
        host=env_url,
        api_key={
            "clientId": settings.plaid_client_id,
            "secret": settings.plaid_secret,
        },
    )
    api_client = ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


def create_link_token(client_user_id: str) -> str:
    client = get_plaid_client()
    request = LinkTokenCreateRequest(
        products=[Products("transactions")],
        client_name="Spendy",
        country_codes=[CountryCode("US")],
        language="en",
        user=LinkTokenCreateRequestUser(client_user_id=client_user_id),
    )
    try:
        response = client.link_token_create(request)
        return response["link_token"]
    except plaid.ApiException as e:
        logger.error(f"Error creating link token: {e}")
        raise


def exchange_public_token(public_token: str) -> dict:
    client = get_plaid_client()
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    try:
        response = client.item_public_token_exchange(request)
        return {
            "access_token": response["access_token"],
            "item_id": response["item_id"],
        }
    except plaid.ApiException as e:
        logger.error(f"Error exchanging public token: {e}")
        raise


def get_institution_name(institution_id: str, client: plaid_api.PlaidApi) -> str:
    try:
        request = InstitutionsGetByIdRequest(
            institution_id=institution_id,
            country_codes=[CountryCode("US")],
        )
        response = client.institutions_get_by_id(request)
        return response["institution"]["name"]
    except plaid.ApiException as e:
        logger.error(f"Error getting institution name: {e}")
        return "Unknown Institution"


def sync_transactions(
    access_token: str,
    cursor: Optional[str],
    client: plaid_api.PlaidApi,
) -> tuple:
    added = []
    modified = []
    removed = []
    next_cursor = cursor
    has_more = True

    try:
        while has_more:
            request_kwargs = {"access_token": access_token}
            if next_cursor:
                request_kwargs["cursor"] = next_cursor

            request = TransactionsSyncRequest(**request_kwargs)
            response = client.transactions_sync(request)

            added.extend(response["added"])
            modified.extend(response["modified"])
            removed.extend(response["removed"])
            next_cursor = response["next_cursor"]
            has_more = response["has_more"]

        return added, modified, removed, next_cursor
    except plaid.ApiException as e:
        logger.error(f"Error syncing transactions: {e}")
        raise


def get_accounts(access_token: str, client: plaid_api.PlaidApi) -> list:
    try:
        request = AccountsGetRequest(access_token=access_token)
        response = client.accounts_get(request)
        return response["accounts"]
    except plaid.ApiException as e:
        logger.error(f"Error getting accounts: {e}")
        raise


def map_plaid_category(plaid_categories: list) -> str:
    if not plaid_categories:
        return "Other"

    # Normalize categories to lowercase
    normalized = [c.lower().strip() for c in plaid_categories]

    # Try progressively more specific matches first (longer tuples first)
    # Build lookup keys from the normalized categories
    if len(normalized) >= 2:
        key2 = tuple(normalized[:2])
        if key2 in CATEGORY_MAPPING:
            return CATEGORY_MAPPING[key2]

    # Try the primary category alone
    key1 = (normalized[0],)
    if key1 in CATEGORY_MAPPING:
        return CATEGORY_MAPPING[key1]

    # Substring matching for flexibility
    primary = normalized[0]
    secondary = normalized[1] if len(normalized) > 1 else ""

    if "groceries" in secondary:
        return "Groceries"
    if "food" in primary or "restaurant" in secondary or "dining" in secondary:
        return "Dining"
    if "gas station" in secondary or "fuel" in secondary:
        return "Fuel"
    if "utilities" in secondary or "electric" in secondary or "water" in secondary:
        return "Utilities"
    if "subscription" in secondary or "software" in secondary:
        return "Subscriptions"
    if "health" in primary or "medical" in primary or "pharmacy" in secondary:
        return "Healthcare"
    if "insurance" in primary or "insurance" in secondary:
        return "Insurance"
    if "entertainment" in primary or "recreation" in secondary:
        return "Entertainment"
    if "pet" in secondary or "veterinar" in secondary:
        return "Pet Care"
    if "shop" in primary or "retail" in secondary:
        return "Shopping"
    if "payroll" in primary or "deposit" in primary or "income" in primary:
        return "Income"
    if "mortgage" in primary or "real estate" in secondary:
        return "Mortgage"
    if "auto" in primary or "transportation" in primary or "public transit" in secondary:
        return "Transportation"
    if "home improvement" in primary or "home improvement" in secondary:
        return "Home Maintenance"

    return "Other"
