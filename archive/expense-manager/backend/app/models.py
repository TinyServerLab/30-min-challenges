from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(10))  # "expense" | "income"
    icon: Mapped[str] = mapped_column(String(16), default="•")
    color: Mapped[str] = mapped_column(String(9), default="#6B7C75")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_categories_type_name", "type", "name", unique=True),)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    kind: Mapped[str] = mapped_column(String(20))  # cash | bank | credit_card | upi | wallet
    track_balance: Mapped[bool] = mapped_column(Boolean, default=False)
    opening_balance: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(10))  # expense | income
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    date: Mapped[date] = mapped_column(Date, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    category: Mapped["Category"] = relationship(lazy="joined")
    source: Mapped["Source"] = relationship(lazy="joined")
    user: Mapped["User"] = relationship(lazy="joined")

    __table_args__ = (Index("ix_transactions_type_date", "type", "date"),)


class Investment(Base):
    """One holding (e.g. 'Parag Parikh Flexi Cap') with contributions and value snapshots."""

    __tablename__ = "investments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))  # equity | mutual_fund | fd | ppf | other
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    entries: Mapped[list["InvestmentEntry"]] = relationship(
        back_populates="investment", cascade="all, delete-orphan", order_by="InvestmentEntry.date"
    )


class InvestmentEntry(Base):
    __tablename__ = "investment_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    investment_id: Mapped[int] = mapped_column(ForeignKey("investments.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date, index=True)
    contribution: Mapped[float] = mapped_column(Numeric(14, 2), default=0)  # money put in (negative = withdrawal)
    current_value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)  # manual mark-to-market
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

    investment: Mapped["Investment"] = relationship(back_populates="entries")
