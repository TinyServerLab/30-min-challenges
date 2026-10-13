from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict, Field

from app.models import (
    TxnType, SourceKind, InvestmentKind,
    BillingCycle, SubscriptionStatus, SubscriptionUsage,
)


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
    essential: bool = True


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[TxnType] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    essential: Optional[bool] = None


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


# ---- Subscriptions ----
class SubscriptionBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    amount: Decimal = Field(gt=0)
    billing_cycle: BillingCycle = BillingCycle.monthly
    next_due_date: date
    category_id: Optional[int] = None
    source_id: Optional[int] = None
    status: SubscriptionStatus = SubscriptionStatus.active
    usage: SubscriptionUsage = SubscriptionUsage.regular
    note: str = ""


class SubscriptionCreate(SubscriptionBase):
    pass


class SubscriptionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    amount: Optional[Decimal] = Field(default=None, gt=0)
    billing_cycle: Optional[BillingCycle] = None
    next_due_date: Optional[date] = None
    category_id: Optional[int] = None
    source_id: Optional[int] = None
    status: Optional[SubscriptionStatus] = None
    usage: Optional[SubscriptionUsage] = None
    note: Optional[str] = None


class SubscriptionOut(SubscriptionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    cancelled_on: Optional[date] = None
    monthly_cost: Decimal
    yearly_cost: Decimal


class SubscriptionSummary(BaseModel):
    active_count: int
    monthly_total: Decimal
    yearly_total: Decimal
    # Monthly cost of active subs rated "rarely" or "unused" — what
    # cancelling them would free up.
    potential_monthly_savings: Decimal
    upcoming: list[SubscriptionOut]  # active, due within the next 30 days


class SubscriptionCandidate(BaseModel):
    """A repeated expense in transactions that looks like a subscription
    nobody is tracking yet."""
    name: str
    amount: Decimal
    category_id: int
    source_id: int
    billing_cycle: BillingCycle
    occurrences: int
    last_date: date
    suggested_next_due_date: date


# ---- Savings plan ----
class SpendingCapIn(BaseModel):
    monthly_limit: Decimal = Field(gt=0)


class CategorySavingsItem(BaseModel):
    category_id: int
    category_name: str
    color: str
    essential: bool
    avg_monthly: Decimal
    this_month: Decimal
    cap: Optional[Decimal] = None
    suggested_cap: Optional[Decimal] = None  # None for essentials
    suggested_saving: Decimal


class SubscriptionSavingsItem(BaseModel):
    subscription_id: int
    name: str
    usage: SubscriptionUsage
    monthly_cost: Decimal


class SavingsPlan(BaseModel):
    window_start: date
    window_end: date
    months: int
    cut_pct: int
    avg_monthly_income: Decimal
    avg_monthly_expense: Decimal
    current_savings_rate: Optional[Decimal]  # percent; None when no income
    cancel_subscriptions: list[SubscriptionSavingsItem]
    categories: list[CategorySavingsItem]
    subscription_savings: Decimal
    category_savings: Decimal
    total_monthly_savings: Decimal
    total_yearly_savings: Decimal
    projected_savings_rate: Optional[Decimal]
