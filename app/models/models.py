from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime,
    ForeignKey, Text
)
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PlaidItem(Base):
    __tablename__ = "plaid_items"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(String(255), unique=True, nullable=False, index=True)
    access_token = Column(String(255), nullable=False)
    institution_name = Column(String(255), nullable=True)
    institution_id = Column(String(255), nullable=True)
    cursor = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    accounts = relationship("Account", back_populates="item", cascade="all, delete-orphan")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    plaid_account_id = Column(String(255), unique=True, nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("plaid_items.id"), nullable=False)
    name = Column(String(255), nullable=False)
    official_name = Column(String(255), nullable=True)
    type = Column(String(50), nullable=False)  # depository, credit, loan, investment
    subtype = Column(String(50), nullable=True)
    current_balance = Column(Float, nullable=True)
    available_balance = Column(Float, nullable=True)
    currency = Column(String(10), default="USD")
    mask = Column(String(10), nullable=True)
    is_active = Column(Boolean, default=True)

    item = relationship("PlaidItem", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    color = Column(String(20), nullable=False, default="#6B7280")
    is_income = Column(Boolean, default=False)

    transactions = relationship("Transaction", back_populates="category")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    plaid_transaction_id = Column(String(255), unique=True, nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    amount = Column(Float, nullable=False)  # Plaid: positive=expense, negative=income/refund
    date = Column(Date, nullable=False)
    name = Column(String(500), nullable=False)
    merchant_name = Column(String(500), nullable=True)
    plaid_category = Column(String(500), nullable=True)
    pending = Column(Boolean, default=False)
    logo_url = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("Account", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")
