from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict

from app.models import TxnType, SourceKind, InvestmentKind


# ---- Auth ----
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: str


# ---- Categories ----
class CategoryBase(BaseModel):
    name: str
    type: TxnType
    icon: str = ""
    color: str = "#64748b"


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[TxnType] = None
    icon: Optional[str] = None
    color: Optional[str] = None


class CategoryOut(CategoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---- Payment sources ----
class SourceBase(BaseModel):
    name: str
    kind: SourceKind
    running_balance: Optional[Decimal] = None


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    kind: Optional[SourceKind] = None
    running_balance: Optional[Decimal] = None


class SourceOut(SourceBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---- Transactions ----
class TransactionBase(BaseModel):
    amount: Decimal
    txn_date: date
    category_id: int
    source_id: int
    type: TxnType
    note: str = ""
    recurring: bool = False


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    amount: Optional[Decimal] = None
    txn_date: Optional[date] = None
    category_id: Optional[int] = None
    source_id: Optional[int] = None
    type: Optional[TxnType] = None
    note: Optional[str] = None
    recurring: Optional[bool] = None


class TransactionOut(TransactionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    created_at: datetime


# ---- Investments ----
class InvestmentBase(BaseModel):
    kind: InvestmentKind
    label: str
    contribution_amount: Decimal = Decimal("0")
    current_value: Decimal = Decimal("0")
    entry_date: date
    note: str = ""


class InvestmentCreate(InvestmentBase):
    pass


class InvestmentUpdate(BaseModel):
    kind: Optional[InvestmentKind] = None
    label: Optional[str] = None
    contribution_amount: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    entry_date: Optional[date] = None
    note: Optional[str] = None


class InvestmentOut(InvestmentBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int


# ---- Dashboard / reports ----
class CategoryBreakdownItem(BaseModel):
    category_id: int
    category_name: str
    color: str
    total: Decimal


class DashboardSummary(BaseModel):
    start: date
    end: date
    total_income: Decimal
    total_expense: Decimal
    net: Decimal
    expense_by_category: list[CategoryBreakdownItem]


class SavingsTrendPoint(BaseModel):
    month: str  # "YYYY-MM"
    cumulative_savings: Decimal


class InvestmentTrendPoint(BaseModel):
    month: str  # "YYYY-MM"
    cumulative_contribution: Decimal
    cumulative_current_value: Decimal
