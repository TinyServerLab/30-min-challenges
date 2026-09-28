from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

AssetStatus = Literal["active", "in_repair", "disposed", "sold", "lost", "gifted"]
AttachmentKind = Literal["invoice", "warranty_card", "photo", "manual", "receipt", "other"]
ServiceKind = Literal["repair", "service", "claim", "installation", "other"]


def _blank_to_none(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------- auth/users
class LoginIn(BaseModel):
    login: str = Field(min_length=1, max_length=200)     # email or username
    password: str = Field(min_length=1, max_length=200)


class UserOut(ORM):
    id: int
    email: str
    username: str | None
    display_name: str
    is_admin: bool
    is_active: bool
    notify_email: bool
    last_login_at: datetime | None = None


class UserCreate(BaseModel):
    email: EmailStr
    username: str | None = Field(default=None, max_length=50)
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=10, max_length=200)
    is_admin: bool = False
    v_blank_user = field_validator("username", mode="before")(_blank_to_none)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    username: str | None = Field(default=None, max_length=50)
    is_admin: bool | None = None
    is_active: bool | None = None
    notify_email: bool | None = None


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    notify_email: bool | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=200)


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=10, max_length=200)


# ------------------------------------------------------------------- categories
class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    icon: str = "box"
    color: str = Field(default="#64748b", pattern=r"^#[0-9a-fA-F]{6}$")
    sort_order: int = 0


class CategoryOut(ORM):
    id: int
    name: str
    icon: str
    color: str
    sort_order: int
    asset_count: int = 0


# ------------------------------------------------------------------ attachments
class AttachmentOut(ORM):
    id: int
    asset_id: int | None
    kind: str
    original_filename: str
    content_type: str
    size_bytes: int
    has_thumb: bool = False
    created_at: datetime


class AttachmentUpdate(BaseModel):
    asset_id: int | None = None
    kind: AttachmentKind | None = None


class ExtractedFields(BaseModel):
    name: str | None = None
    brand: str | None = None
    model: str | None = None
    serial_number: str | None = None
    vendor: str | None = None
    invoice_number: str | None = None
    purchase_date: date | None = None
    purchase_price: Decimal | None = None
    warranty_months: int | None = None
    gstin: str | None = None


class UploadResult(BaseModel):
    attachment: AttachmentOut
    extracted: ExtractedFields | None = None
    ocr_available: bool = False
    duplicate_of_asset_id: int | None = None


# ---------------------------------------------------------------------- assets
class AssetBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    serial_number: str | None = Field(default=None, max_length=100)
    category_id: int | None = None
    location: str | None = Field(default=None, max_length=100)
    owner_name: str | None = Field(default=None, max_length=100)

    purchase_date: date
    purchase_price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    vendor: str | None = Field(default=None, max_length=150)
    invoice_number: str | None = Field(default=None, max_length=100)
    payment_method: str | None = Field(default=None, max_length=50)

    warranty_months: int = Field(default=12, ge=0, le=600)
    warranty_start_date: date | None = None
    warranty_expiry_manual: bool = False
    warranty_expiry_date: date | None = None     # only honoured when warranty_expiry_manual

    ext_warranty_provider: str | None = Field(default=None, max_length=100)
    ext_warranty_months: int | None = Field(default=None, ge=0, le=600)
    ext_warranty_expiry_date: date | None = None  # used if ext_warranty_months is empty
    ext_warranty_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)

    support_contact: str | None = Field(default=None, max_length=200)
    status: AssetStatus = "active"
    notes: str | None = Field(default=None, max_length=5000)

    v_blank = field_validator(
        "brand", "model", "serial_number", "location", "owner_name", "vendor", "invoice_number",
        "payment_method", "ext_warranty_provider", "support_contact", "notes", mode="before",
    )(_blank_to_none)

    @field_validator("currency", mode="before")
    @classmethod
    def _cur(cls, v):
        return (v or "INR").upper()


class AssetIn(AssetBase):
    attachment_ids: list[int] = []   # draft uploads to link on create


class ServiceIn(BaseModel):
    service_date: date
    kind: ServiceKind = "repair"
    description: str = Field(min_length=1, max_length=2000)
    vendor: str | None = Field(default=None, max_length=150)
    cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    under_warranty: bool = False
    reference_number: str | None = Field(default=None, max_length=100)
    v_blank = field_validator("vendor", "reference_number", mode="before")(_blank_to_none)


class ServiceOut(ORM):
    id: int
    asset_id: int
    service_date: date
    kind: str
    description: str
    vendor: str | None
    cost: Decimal
    under_warranty: bool
    reference_number: str | None
    created_at: datetime


class AssetOut(ORM):
    id: int
    name: str
    brand: str | None
    model: str | None
    serial_number: str | None
    category_id: int | None
    category_name: str | None = None
    category_color: str | None = None
    category_icon: str | None = None
    location: str | None
    owner_name: str | None
    purchase_date: date
    purchase_price: Decimal
    currency: str
    vendor: str | None
    invoice_number: str | None
    payment_method: str | None
    warranty_months: int
    warranty_start_date: date | None
    warranty_expiry_date: date | None
    warranty_expiry_manual: bool
    ext_warranty_provider: str | None
    ext_warranty_months: int | None
    ext_warranty_expiry_date: date | None
    ext_warranty_cost: Decimal | None
    support_contact: str | None
    status: str
    notes: str | None
    effective_expiry_date: date | None = None
    warranty_state: str = "none"
    days_left: int | None = None
    attachment_count: int = 0
    thumb_attachment_id: int | None = None
    created_at: datetime
    updated_at: datetime


class AssetDetail(AssetOut):
    attachments: list[AttachmentOut] = []
    services: list[ServiceOut] = []
    service_cost_total: Decimal = Decimal("0")


class AssetPage(BaseModel):
    items: list[AssetOut]
    total: int
    page: int
    page_size: int
    total_value: Decimal
