from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DEFAULT_CATEGORIES = [
    {"name": "Income", "color": "#10B981", "is_income": True},
    {"name": "Shopping", "color": "#F59E0B", "is_income": False},
    {"name": "Groceries", "color": "#84CC16", "is_income": False},
    {"name": "Fuel", "color": "#F97316", "is_income": False},
    {"name": "Mortgage", "color": "#6366F1", "is_income": False},
    {"name": "Utilities", "color": "#8B5CF6", "is_income": False},
    {"name": "Dining", "color": "#EC4899", "is_income": False},
    {"name": "Pet Care", "color": "#14B8A6", "is_income": False},
    {"name": "Subscriptions", "color": "#06B6D4", "is_income": False},
    {"name": "Healthcare", "color": "#EF4444", "is_income": False},
    {"name": "Insurance", "color": "#64748B", "is_income": False},
    {"name": "Entertainment", "color": "#A855F7", "is_income": False},
    {"name": "Transportation", "color": "#0EA5E9", "is_income": False},
    {"name": "Home Maintenance", "color": "#78716C", "is_income": False},
    {"name": "Other", "color": "#6B7280", "is_income": False},
]


def init_db():
    # Import models here to ensure they are registered with Base
    from app.models import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Seed categories
    from app.models.models import Category
    db = SessionLocal()
    try:
        existing_count = db.query(Category).count()
        if existing_count == 0:
            for cat_data in DEFAULT_CATEGORIES:
                category = Category(**cat_data)
                db.add(category)
            db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
