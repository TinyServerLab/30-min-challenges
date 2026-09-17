import enum

from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Date, DateTime, Text,
    ForeignKey, Enum, func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class TxnType(str, enum.Enum):
    income = "income"
    expense = "expense"


class SourceKind(str, enum.Enum):
    cash = "cash"
    bank_account = "bank_account"
    credit_card = "credit_card"
    upi = "upi"
    wallet = "wallet"


class InvestmentKind(str, enum.Enum):
    equity = "equity"
    mutual_fund = "mutual_fund"
    fd = "fd"
    ppf = "ppf"
    other = "other"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transactions = relationship("Transaction", back_populates="user")
    investments = relationship("Investment", back_populates="user")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    type = Column(Enum(TxnType, name="txn_type"), nullable=False)
    icon = Column(String(50), default="")
    color = Column(String(20), default="#64748b")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transactions = relationship("Transaction", back_populates="category")


class PaymentSource(Base):
    __tablename__ = "payment_sources"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    kind = Column(Enum(SourceKind, name="source_kind"), nullable=False)
    running_balance = Column(Numeric(14, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transactions = relationship("Transaction", back_populates="source")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    txn_date = Column(Date, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("payment_sources.id"), nullable=False)
    type = Column(Enum(TxnType, name="txn_type"), nullable=False)
    note = Column(Text, default="")
    recurring = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")
    source = relationship("PaymentSource", back_populates="transactions")


class Investment(Base):
    __tablename__ = "investments"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind = Column(Enum(InvestmentKind, name="investment_kind"), nullable=False)
    label = Column(String(150), nullable=False)
    contribution_amount = Column(Numeric(14, 2), nullable=False, default=0)
    current_value = Column(Numeric(14, 2), nullable=False, default=0)
    entry_date = Column(Date, nullable=False)
    note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="investments")
