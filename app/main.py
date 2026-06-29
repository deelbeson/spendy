import logging
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from app.config import settings
from app.database import init_db
from app.routers import auth_router, dashboard, transactions, accounts, plaid_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(title="Spendy", description="Personal Family Finance Dashboard")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=86400 * 7,  # 7 days
)

app.include_router(auth_router.router)
app.include_router(dashboard.router)
app.include_router(transactions.router)
app.include_router(accounts.router)
app.include_router(plaid_router.router)


@app.on_event("startup")
def startup():
    init_db()
