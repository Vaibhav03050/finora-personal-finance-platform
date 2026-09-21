"""
Database models.

IMPORTANT: all money fields are stored as integers in the currency's
minor unit (paise for INR, cents for USD). We NEVER use float for money.
"""
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import SQLModel, Field


class Role(str, Enum):
    user = "user"
    admin = "admin"


class TxnType(str, Enum):
    income = "income"
    expense = "expense"


class CategorySource(str, Enum):
    rule = "rule"
    ml = "ml"
    manual = "manual"
    ocr = "ocr"


class TxnSource(str, Enum):
    manual = "manual"
    csv = "csv"
    ocr_statement = "ocr_statement"
    ocr_receipt = "ocr_receipt"
    nl_entry = "nl_entry"          # "spent 250 on lunch"
    seed_estimate = "seed_estimate"  # beginner-mode estimated profile


class GoalStatus(str, Enum):
    ahead = "ahead"
    on_track = "on_track"
    slightly_behind = "slightly_behind"
    behind = "behind"
    achieved = "achieved"


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    name: str = ""
    role: Role = Role.user
    language: str = "en"           # "en" | "hi"
    is_beginner: bool = False      # started with no data
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    txn_date: date = Field(index=True)
    merchant: str = ""
    description: str = ""
    amount_minor: int             # always positive; sign implied by `type`
    currency: str = "INR"
    txn_type: TxnType
    category: str = Field(default="Other", index=True)
    category_source: CategorySource = CategorySource.manual
    confidence: float = 1.0
    source: TxnSource = TxnSource.manual
    dedupe_hash: str = Field(index=True)
    needs_review: bool = False     # true for freshly-OCR'd rows pre-confirmation
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Goal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    name: str
    category: str = "Custom"       # Laptop, Phone, Travel, Emergency Fund, ...
    target_amount_minor: int
    target_date: date
    current_saved_minor: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    achieved: bool = False


class FinancialProfile(SQLModel, table=True):
    """Used for beginner-mode users who have little/no transaction history."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id", unique=True)
    monthly_income_minor: int = 0
    fixed_expenses_minor: int = 0     # rent, EMI, bills etc.
    lifestyle_expenses_minor: int = 0  # food, shopping, entertainment etc.
    debt_emi_minor: int = 0
    existing_savings_minor: int = 0
    emergency_savings_minor: int = 0
    is_estimate: bool = True
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, index=True)
    action: str
    detail: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
