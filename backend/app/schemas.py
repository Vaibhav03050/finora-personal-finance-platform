from datetime import date, datetime
from datetime import date as _date_type  # aliased import to avoid a field-name/type-name collision below
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, EmailStr, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = {}


class Envelope(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None
    meta: dict = {}


def ok(data: Any = None, meta: dict = None) -> dict:
    return {"success": True, "data": data, "error": None, "meta": meta or {}}


def fail(code: str, message: str, details: dict = None) -> dict:
    return {"success": False, "data": None, "error": {"code": code, "message": message, "details": details or {}}, "meta": {}}


# ---------- Auth ----------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: str
    email: str
    is_beginner: bool


# ---------- Transactions ----------
class TransactionCreate(BaseModel):
    date: date
    merchant: str = ""
    description: str = ""
    amount_rupees: float = Field(gt=0, description="Amount in whole currency units e.g. rupees")
    type: str  # "income" | "expense"
    category: Optional[str] = None  # if omitted, auto-categorized


class TransactionUpdate(BaseModel):
    date: Optional[_date_type] = None
    merchant: Optional[str] = None
    description: Optional[str] = None
    amount_rupees: Optional[float] = None
    type: Optional[str] = None
    category: Optional[str] = None


class TransactionOut(BaseModel):
    id: int
    date: date
    merchant: str
    description: str
    amount_rupees: float
    currency: str
    type: str
    category: str
    category_source: str
    confidence: float
    source: str
    needs_review: bool


class NaturalLanguageEntry(BaseModel):
    text: str


# ---------- Goals ----------
class GoalCreate(BaseModel):
    name: str
    category: str = "Custom"
    target_amount_rupees: float = Field(gt=0)
    target_date: date
    current_saved_rupees: float = Field(default=0, ge=0)


class GoalUpdate(BaseModel):
    name: Optional[str] = None
    target_amount_rupees: Optional[float] = None
    target_date: Optional[date] = None
    current_saved_rupees: Optional[float] = Field(default=None, ge=0)


# ---------- Financial profile (beginner mode) ----------
class ProfileEstimate(BaseModel):
    monthly_income_rupees: float = 0
    fixed_expenses_rupees: float = 0
    lifestyle_expenses_rupees: float = 0
    debt_emi_rupees: float = 0
    existing_savings_rupees: float = 0
    emergency_savings_rupees: float = 0


# ---------- Assistant ----------
class AssistantQuery(BaseModel):
    question: str


# ---------- Simulator ----------
class CompoundSimRequest(BaseModel):
    monthly_contribution_rupees: float = Field(gt=0)
    years: float = Field(gt=0, le=60)
    annual_return_pct: float = Field(ge=0, le=30)
