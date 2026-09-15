from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

TxType = Literal["expense", "income"]
SourceKind = Literal["cash", "bank", "credit_card", "upi", "wallet"]
InvestmentKind = Literal["equity", "mutual_fund", "fd", "ppf", "other"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth / users ----
class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(ORMModel):
    id: int
    email: str
    name: str
    is_admin: bool
    is_active: bool


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200)
    is_admin: bool = False


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    password: str | None = Field(default=None, min_length=8, max_length=200)
    is_admin: bool | None = None
    is_active: bool | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


# ---- categories ----
class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    type: TxType
    icon: str = Field(default="•", max_length=16)
    color: str = Field(default="#6B7C75", pattern=r"^#[0-9a-fA-F]{6}$")


class CategoryOut(CategoryIn, ORMModel):
    id: int
    is_archived: bool


# ---- sources ----
class SourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: SourceKind
    track_balance: bool = False
    opening_balance: Decimal = Decimal("0")


class SourceOut(SourceIn, ORMModel):
    id: int
    is_archived: bool
    balance: Decimal | None = None  # computed when track_balance


# ---- transactions ----
class TransactionIn(BaseModel):
    type: TxType
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    date: date
    category_id: int
    source_id: int
    note: str | None = Field(default=None, max_length=500)
    is_recurring: bool = False


class TransactionOut(ORMModel):
    id: int
    type: TxType
    amount: Decimal
    date: date
    category_id: int
    source_id: int
    note: str | None
    is_recurring: bool
    created_by: int
    created_at: datetime
    category_name: str
    category_icon: str
    category_color: str
    source_name: str
    user_name: str


class Paged(BaseModel):
    items: list[TransactionOut]
    total: int
    page: int
    page_size: int


# ---- dashboard / reports ----
class CategorySlice(BaseModel):
    category_id: int
    name: str
    icon: str
    color: str
    total: Decimal
    count: int


class MonthPoint(BaseModel):
    month: str  # YYYY-MM
    income: Decimal
    expense: Decimal
    net: Decimal
    cumulative: Decimal


class DashboardOut(BaseModel):
    start: date
    end: date
    income: Decimal
    expense: Decimal
    net: Decimal
    expense_by_category: list[CategorySlice]
    income_by_category: list[CategorySlice]
    trend: list[MonthPoint]
    investments_invested: Decimal
    investments_value: Decimal


# ---- investments ----
class InvestmentEntryIn(BaseModel):
    date: date
    contribution: Decimal = Decimal("0")
    current_value: Decimal | None = None


class InvestmentEntryOut(InvestmentEntryIn, ORMModel):
    id: int


class InvestmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: InvestmentKind
    note: str | None = Field(default=None, max_length=500)


class InvestmentOut(InvestmentIn, ORMModel):
    id: int
    is_archived: bool
    invested: Decimal
    current_value: Decimal | None
    last_valued: date | None
    entries: list[InvestmentEntryOut]
