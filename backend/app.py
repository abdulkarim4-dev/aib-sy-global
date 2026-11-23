from datetime import datetime, timedelta, timezone
from typing import Optional, Any
import os, secrets, json, ast, base64, binascii, smtplib, hashlib, html, logging, re
from urllib.parse import urlencode
from email.message import EmailMessage
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import HTTPError, URLError
import jwt
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from pwdlib import PasswordHash
from sqlalchemy import create_engine, String, Boolean, DateTime, Integer, ForeignKey, JSON, Text, Numeric, UniqueConstraint, select, func, text, or_, case
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://aib:aib_change_me@db:5432/aib"
    jwt_secret: str = "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET_BEFORE_DEPLOYMENT"
    jwt_minutes: int = 30
    owner_username: str = "abdulkarim"
    owner_password: str = ""
    owner_name: str = "عبد الكريم محمد بن خيرو"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    brevo_api_key: str = ""
    gemini_api_key: str = ""
    brevo_sender_email: str = ""
    brevo_sender_name: str = "مجموعة AIB التجارية"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "https://aib-sy-global.onrender.com/store/auth/google/callback"
    class Config: env_file = ".env"
settings = Settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
class Base(DeclarativeBase): pass

class User(Base):
    __tablename__="users"
    id: Mapped[int]=mapped_column(primary_key=True)
    username: Mapped[str]=mapped_column(String(80), unique=True, index=True)
    full_name: Mapped[str]=mapped_column(String(160))
    email: Mapped[Optional[str]]=mapped_column(String(254), nullable=True, unique=True, index=True)
    email_verified: Mapped[bool]=mapped_column(Boolean, default=False, nullable=False)
    password_hash: Mapped[str]=mapped_column(String(300))
    role: Mapped[str]=mapped_column(String(20), default="employee")
    owner_commission_rate: Mapped[Any]=mapped_column(Numeric(7,3), default=1.5, nullable=False)
    company_name: Mapped[str]=mapped_column(String(200), default="", nullable=False)
    company_logo: Mapped[Optional[str]]=mapped_column(Text, nullable=True)
    business_scopes: Mapped[list]=mapped_column(JSON, default=list, nullable=False)
    profile_data: Mapped[dict]=mapped_column(JSON, default=dict, nullable=False)
    permissions: Mapped[dict]=mapped_column(JSON, default=dict, nullable=False)
    active: Mapped[bool]=mapped_column(Boolean, default=True)
    deleted: Mapped[bool]=mapped_column(Boolean, default=False, nullable=False)
    failed_logins: Mapped[int]=mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True), nullable=True)
    must_change_password: Mapped[bool]=mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
class EmployeeEmailApproval(Base):
    __tablename__="employee_email_approvals"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    code_hash: Mapped[str]=mapped_column(String(300))
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    attempts: Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    used_at: Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class AccountingLoginVerification(Base):
    __tablename__="accounting_login_verifications"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    code_hash: Mapped[str]=mapped_column(String(300))
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    attempts: Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    used_at: Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class AccountingPasswordReset(Base):
    __tablename__="accounting_password_resets"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    token_hash: Mapped[str]=mapped_column(String(64),unique=True,index=True)
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    used_at: Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class StoreCustomer(Base):
    __tablename__="store_customers"
    id: Mapped[int]=mapped_column(primary_key=True)
    email: Mapped[str]=mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str]=mapped_column(String(160))
    password_hash: Mapped[str]=mapped_column(String(300))
    cart: Mapped[list]=mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool]=mapped_column(Boolean, default=True, nullable=False)
    failed_logins: Mapped[int]=mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    first_name: Mapped[str]=mapped_column(String(80),default="")
    last_name: Mapped[str]=mapped_column(String(80),default="")
    shipping_address: Mapped[str]=mapped_column(Text,default="")
    phone_country_code: Mapped[str]=mapped_column(String(8),default="+963")
    phone_verified_at: Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    phone_number: Mapped[str]=mapped_column(String(32),default="")
    avatar_data: Mapped[Optional[str]]=mapped_column(Text,nullable=True)
    google_sub: Mapped[Optional[str]]=mapped_column(String(255),nullable=True,unique=True,index=True)

class OnlinePurchaseOrder(Base):
    __tablename__="online_purchase_orders"
    id: Mapped[int]=mapped_column(primary_key=True)
    customer_id: Mapped[int]=mapped_column(ForeignKey("store_customers.id"),index=True)
    customer_data: Mapped[dict]=mapped_column(JSON,default=dict,nullable=False)
    items: Mapped[list]=mapped_column(JSON,default=list,nullable=False)
    total: Mapped[Any]=mapped_column(Numeric(18,2))
    currency: Mapped[str]=mapped_column(String(8),default="USD")
    payment_proof: Mapped[str]=mapped_column(Text)
    proof_type: Mapped[str]=mapped_column(String(80),default="application/octet-stream")
    status: Mapped[str]=mapped_column(String(20),default="pending",index=True)
    record_id: Mapped[Optional[int]]=mapped_column(ForeignKey("records.id"),nullable=True)
    review_note: Mapped[str]=mapped_column(Text,default="")
    reviewed_by: Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    reviewed_at: Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)

class StorePasswordReset(Base):
    __tablename__="store_password_resets"
    id: Mapped[int]=mapped_column(primary_key=True)
    customer_id: Mapped[int]=mapped_column(ForeignKey("store_customers.id"), index=True)
    code_hash: Mapped[str]=mapped_column(String(300))
    pending_password_hash: Mapped[Optional[str]]=mapped_column(String(300),nullable=True)
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    attempts: Mapped[int]=mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))

class StoreEmailVerification(Base):
    __tablename__="store_email_verifications"
    id: Mapped[int]=mapped_column(primary_key=True)
    customer_id: Mapped[int]=mapped_column(ForeignKey("store_customers.id"), index=True)
    code_hash: Mapped[str]=mapped_column(String(300))
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    attempts: Mapped[int]=mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))

class StoreLoginVerification(Base):
    __tablename__="store_login_verifications"
    id: Mapped[int]=mapped_column(primary_key=True)
    customer_id: Mapped[int]=mapped_column(ForeignKey("store_customers.id"), index=True)
    code_hash: Mapped[str]=mapped_column(String(300))
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    attempts: Mapped[int]=mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))

class CompanyProfile(Base):
    __tablename__="company_profile"
    id: Mapped[int]=mapped_column(primary_key=True)
    data: Mapped[dict]=mapped_column(JSON, default=dict)
    updated_by: Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))

class Record(Base):
    __tablename__="records"
    id: Mapped[int]=mapped_column(primary_key=True)
    section: Mapped[str]=mapped_column(String(40), index=True)
    invoice_no: Mapped[Optional[str]]=mapped_column(String(40), index=True, nullable=True)
    currency: Mapped[str]=mapped_column(String(8), default="USD")
    data: Mapped[dict]=mapped_column(JSON, default=dict)
    created_by: Mapped[int]=mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    deleted: Mapped[bool]=mapped_column(Boolean, default=False)
class InventoryProduct(Base):
    __tablename__="inventory_products"
    id: Mapped[int]=mapped_column(primary_key=True)
    sku: Mapped[str]=mapped_column(String(80), unique=True, index=True)
    name: Mapped[str]=mapped_column(String(240))
    model: Mapped[str]=mapped_column(String(160), default="")
    description: Mapped[str]=mapped_column(Text, default="", nullable=False)
    owned_stock: Mapped[Any]=mapped_column(Numeric(18,3), default=0)
    consigned_stock: Mapped[Any]=mapped_column(Numeric(18,3), default=0)
    active: Mapped[bool]=mapped_column(Boolean, default=True)
    is_store_visible: Mapped[bool]=mapped_column(Boolean, default=True, nullable=False)
    images: Mapped[list]=mapped_column(JSON, default=list, nullable=False)
    shipping_included: Mapped[bool]=mapped_column(Boolean, default=False, nullable=False)
    video_url: Mapped[Optional[str]]=mapped_column(Text, nullable=True)
    owner_user_id: Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    sale_price: Mapped[Optional[Any]]=mapped_column(Numeric(18,2), nullable=True)
    profit_margin: Mapped[Any]=mapped_column(Numeric(7,2), default=35, nullable=False)
    sale_currency: Mapped[str]=mapped_column(String(8), default="USD", nullable=False)
    condition: Mapped[str]=mapped_column(String(16), default="new", nullable=False)
    opening_quantity: Mapped[Any]=mapped_column(Numeric(18,3), default=0, nullable=False)
    store_family: Mapped[Optional[str]]=mapped_column(String(40), nullable=True)
    store_category: Mapped[Optional[str]]=mapped_column(String(60), nullable=True)
    vehicle_details: Mapped[dict]=mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))

class InvoicePayment(Base):
    __tablename__="invoice_payments"
    id: Mapped[int]=mapped_column(primary_key=True)
    record_id: Mapped[int]=mapped_column(ForeignKey("records.id"), index=True)
    amount: Mapped[Any]=mapped_column(Numeric(18,2))
    method: Mapped[str]=mapped_column(String(40))
    cash_box: Mapped[str]=mapped_column(String(100), default="صندوق المبيع")
    paid_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    created_by: Mapped[int]=mapped_column(ForeignKey("users.id"))

class CashMove(Base):
    __tablename__="cash_moves"
    id: Mapped[int]=mapped_column(primary_key=True)
    box_name: Mapped[str]=mapped_column(String(100), index=True)
    movement: Mapped[str]=mapped_column(String(20))
    amount: Mapped[Any]=mapped_column(Numeric(18,2))
    currency: Mapped[str]=mapped_column(String(8))
    description: Mapped[str]=mapped_column(Text, default="")
    created_by: Mapped[int]=mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    transfer_group: Mapped[Optional[str]]=mapped_column(String(36), nullable=True, index=True)
    record_id: Mapped[Optional[int]]=mapped_column(ForeignKey("records.id"), nullable=True, index=True)
    voided: Mapped[bool]=mapped_column(Boolean, default=False, nullable=False)
    voided_by: Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"), nullable=True)
    voided_at: Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True), nullable=True)
class UserWallet(Base):
    __tablename__="user_wallets"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id"), index=True)
    currency: Mapped[str]=mapped_column(String(8), nullable=False)
    balance: Mapped[Any]=mapped_column(Numeric(18,2), default=0, nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    __table_args__=(UniqueConstraint("user_id","currency",name="uq_user_wallet_currency"),)

class WalletTransaction(Base):
    __tablename__="wallet_transactions"
    id: Mapped[int]=mapped_column(primary_key=True)
    wallet_id: Mapped[int]=mapped_column(ForeignKey("user_wallets.id"), index=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[Any]=mapped_column(Numeric(18,2), nullable=False)
    currency: Mapped[str]=mapped_column(String(8), nullable=False)
    direction: Mapped[str]=mapped_column(String(12), nullable=False)
    reason: Mapped[str]=mapped_column(Text, default="")
    reference_type: Mapped[Optional[str]]=mapped_column(String(40), nullable=True)
    reference_id: Mapped[Optional[int]]=mapped_column(Integer, nullable=True)
    created_by: Mapped[int]=mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))

class WalletRequest(Base):
    __tablename__="wallet_requests"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    movement: Mapped[str]=mapped_column(String(16),nullable=False)
    amount: Mapped[Any]=mapped_column(Numeric(18,2),nullable=False)
    currency: Mapped[str]=mapped_column(String(8),nullable=False)
    note: Mapped[str]=mapped_column(Text,default="")
    withdrawal_method: Mapped[str]=mapped_column(String(40),nullable=False,default="")
    review_note: Mapped[str]=mapped_column(Text,default="")
    status: Mapped[str]=mapped_column(String(16),default="pending",index=True)
    reviewed_by: Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True)
    reviewed_at: Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class ChangeRequest(Base):
    __tablename__="record_change_requests"
    id: Mapped[int]=mapped_column(primary_key=True)
    record_id: Mapped[int]=mapped_column(ForeignKey("records.id"))
    requested_by: Mapped[int]=mapped_column(ForeignKey("users.id"))
    action: Mapped[str]=mapped_column(String(20))
    proposed_data: Mapped[Optional[dict]]=mapped_column(JSON, nullable=True)
    reason: Mapped[str]=mapped_column(Text)
    status: Mapped[str]=mapped_column(String(20), default="pending")
    reviewed_by: Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    reviewed_at: Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True), nullable=True)
class EmailVerification(Base):
    __tablename__="email_verifications"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id"), index=True)
    email: Mapped[str]=mapped_column(String(254))
    code_hash: Mapped[str]=mapped_column(String(300))
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    attempts: Mapped[int]=mapped_column(Integer, default=0)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
class OperationVerification(Base):
    __tablename__="operation_verifications"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    action: Mapped[str]=mapped_column(String(40),index=True)
    code_hash: Mapped[str]=mapped_column(String(300))
    grant_hash: Mapped[Optional[str]]=mapped_column(String(64),nullable=True)
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    attempts: Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    verified_at: Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    used_at: Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class PasswordChangeRequest(Base):
    __tablename__="password_change_requests"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id"), index=True)
    requested_by: Mapped[int]=mapped_column(ForeignKey("users.id"))
    new_password_hash: Mapped[str]=mapped_column(String(300))
    status: Mapped[str]=mapped_column(String(20), default="pending")
    reviewed_by: Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    reviewed_at: Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True), nullable=True)
class AuditEvent(Base):
    __tablename__="audit_events"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str]=mapped_column(String(80))
    entity: Mapped[str]=mapped_column(String(80))
    entity_id: Mapped[Optional[int]]=mapped_column(Integer, nullable=True)
    details: Mapped[dict]=mapped_column(JSON, default=dict)
    ip_address: Mapped[str]=mapped_column(String(64), default="")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))

password_hash=PasswordHash.recommended()
oauth=OAuth2PasswordBearer(tokenUrl="/auth/login",auto_error=False)
app=FastAPI(title="AIB Accounting API", version="1.0.0")

class _SensitiveQueryLogFilter(logging.Filter):
    """Redact authentication secrets from Uvicorn access-log request targets."""
    _sensitive_query = re.compile(
        r"(?i)([?&](?:code|state|password_change_token)=)[^&\s\"'<>]*"
    )

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    self._sensitive_query.sub(r"\1[REDACTED]", value)
                    if isinstance(value, str) else value
                    for value in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    key: self._sensitive_query.sub(r"\1[REDACTED]", value)
                    if isinstance(value, str) else value
                    for key, value in record.args.items()
                }
            if isinstance(record.msg, str):
                record.msg = self._sensitive_query.sub(r"\1[REDACTED]", record.msg)
        except Exception:
            # Logging must never interfere with authentication or request handling.
            pass
        return True


_access_logger = logging.getLogger("uvicorn.access")
_access_logger.addFilter(_SensitiveQueryLogFilter())
for _access_handler in _access_logger.handlers:
    _access_handler.addFilter(_SensitiveQueryLogFilter())
app.add_middleware(GZipMiddleware, minimum_size=900, compresslevel=5)

@app.middleware("http")
async def log_public_products_exceptions(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        if request.url.path == "/public/products":
            logging.getLogger("aib.search").exception(
                "Unhandled public products request failure"
            )
        raise

def db():
    s=SessionLocal()
    try: yield s
    finally: s.close()
def audit(s:Session, user:Optional[User], action:str, entity:str, entity_id:Optional[int], details:dict, request:Optional[Request]=None):
    audit_details=dict(details or {})
    impersonator_id=getattr(user,"_impersonated_by_owner_id",None) if user else None
    if impersonator_id:
        audit_details["impersonated_by_owner_id"]=impersonator_id
    s.add(AuditEvent(user_id=user.id if user else None, action=action, entity=entity, entity_id=entity_id, details=audit_details, ip_address=request.client.host if request and request.client else ""))
def token_for(user:User,email_otp_verified:bool=False,impersonated_by_owner_id:Optional[int]=None):
    # Accounting sessions remain valid across browser restarts and do not expire
    # automatically; the user signs out explicitly from the accounting app.
    now=datetime.now(timezone.utc)
    claims={"sub":str(user.id),"iat":now,"email_otp_verified":bool(email_otp_verified)}
    if impersonated_by_owner_id:
        claims["impersonated_by_owner_id"]=int(impersonated_by_owner_id)
    return jwt.encode(claims,settings.jwt_secret,algorithm="HS256")
def current_user(request:Request, token:Optional[str]=Depends(oauth), s:Session=Depends(db)):
    if not token:
        raise HTTPException(401,"جلسة الدخول غير صالحة أو انتهت")
    try:
        payload=jwt.decode(token,settings.jwt_secret,algorithms=["HS256"])
        if payload.get("typ")=="store_customer": raise ValueError("store token")
        uid=int(payload["sub"])
        impersonator_id=int(payload["impersonated_by_owner_id"]) if payload.get("impersonated_by_owner_id") else None
    except Exception: raise HTTPException(401,"جلسة الدخول غير صالحة أو انتهت")
    u=s.get(User,uid)
    if not u or not u.active or u.deleted: raise HTTPException(401,"الحساب غير فعال")
    if impersonator_id:
        owner=s.get(User,impersonator_id)
        if not owner or not owner.active or owner.deleted or owner.role!="owner" or u.role=="owner":
            raise HTTPException(401,"جلسة الدخول بالنيابة غير صالحة")
        u._impersonated_by_owner_id=owner.id
    if u.must_change_password and not impersonator_id and request.url.path not in {"/auth/me","/auth/first-login-password"}:
        raise HTTPException(403,"يجب تغيير كلمة المرور المؤقتة قبل استخدام الحساب")
    return u
def require_store_same_origin(request:Request):
    # SameSite=Lax is reinforced with strict Origin validation for cookie-authenticated mutations.
    if request.method in {"POST","PUT","PATCH","DELETE"}:
        origin=request.headers.get("origin","").rstrip("/")
        forwarded_proto=request.headers.get("x-forwarded-proto","").split(",")[0].strip()
        scheme=forwarded_proto or request.url.scheme
        host=request.headers.get("x-forwarded-host",request.url.netloc).split(",")[0].strip()
        expected=f"{scheme}://{host}"
        if not origin or origin!=expected:
            raise HTTPException(403,"تم رفض الطلب لعدم تطابق مصدره")

def current_store_customer(request:Request, s:Session=Depends(db)):
    require_store_same_origin(request)
    # Store sessions are accepted only from the HttpOnly cookie, never from browser-readable bearer storage.
    token=request.cookies.get("aib_store_session","")
    if not token:
        raise HTTPException(401,"يرجى تسجيل الدخول إلى حساب المتجر")
    try:
        payload=jwt.decode(token,settings.jwt_secret,algorithms=["HS256"])
        if payload.get("typ")!="store_customer": raise ValueError("wrong token type")
        cid=int(payload["sub"])
    except Exception:
        raise HTTPException(401,"يرجى تسجيل الدخول إلى حساب المتجر")
    customer=s.get(StoreCustomer,cid)
    if not customer or not customer.active: raise HTTPException(401,"حساب المتجر غير فعال")
    return customer

def manager(u:User=Depends(current_user)):
    if u.role!="owner": raise HTTPException(403,"هذا الإجراء متاح للمدير فقط")
    return u
def can_add(u:User=Depends(current_user)): return u

PERMISSION_SCHEMA={"inventory":{"view","create","edit"},"invoices":{"view","create","edit","delete","print"},"vehicles":{"sell"},"cash":{"view","create","edit","delete","print"}}
def has_permission(user:User,module:str,action:str)->bool:
    if user.role=="owner": return True
    return bool(((user.permissions or {}).get(module) or {}).get(action,False))
def require_permission(module:str,action:str):
    def checker(u:User=Depends(current_user)):
        if not has_permission(u,module,action):
            raise HTTPException(403,"ليست لديك صلاحية تنفيذ هذا الإجراء. راجع المالك لمنحك الإذن.")
        return u
    return checker

def require_inventory_product_management():
    def checker(u:User=Depends(current_user)):
        if not (has_permission(u,"inventory","create") or has_permission(u,"inventory","edit")):
            raise HTTPException(403,"تحتاج إلى صلاحية إضافة أو تعديل المنتجات لإدارة منتجات مخزونك.")
        return u
    return checker

@app.on_event("startup")
def startup():
    if settings.jwt_secret.startswith("CHANGE_THIS") and os.getenv("ENVIRONMENT")=="production":
        raise RuntimeError("Set a strong JWT_SECRET before production")
    # Serialize schema creation/migrations across concurrent Render instances.
    # Keep the advisory transaction lock on the same connection as create_all and ALTERs.
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(741920261115)"))
        Base.metadata.create_all(conn)
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS permissions JSONB NOT NULL DEFAULT '{}'::jsonb"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS company_name VARCHAR(200) NOT NULL DEFAULT ''"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS company_logo TEXT"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS business_scopes JSONB NOT NULL DEFAULT '[]'::jsonb"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_data JSONB NOT NULL DEFAULT '{}'::jsonb"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(254)"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS owner_commission_rate NUMERIC(7,3) NOT NULL DEFAULT 1.5"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email_unique ON users (email) WHERE email IS NOT NULL"))
        conn.execute(text("ALTER TABLE inventory_products ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT ''"))
        conn.execute(text("ALTER TABLE inventory_products ADD COLUMN IF NOT EXISTS images JSONB NOT NULL DEFAULT '[]'::jsonb"))
        conn.execute(text("ALTER TABLE inventory_products ADD COLUMN IF NOT EXISTS shipping_included BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE inventory_products ADD COLUMN IF NOT EXISTS is_store_visible BOOLEAN NOT NULL DEFAULT TRUE"))
        conn.execute(text("ALTER TABLE inventory_products ADD COLUMN IF NOT EXISTS owner_user_id INTEGER REFERENCES users(id)"))
        conn.execute(text("ALTER TABLE inventory_products ADD COLUMN IF NOT EXISTS sale_price NUMERIC(18,2)"))
        conn.execute(text("ALTER TABLE inventory_products ADD COLUMN IF NOT EXISTS profit_margin NUMERIC(7,2) NOT NULL DEFAULT 35"))
        conn.execute(text("ALTER TABLE inventory_products ADD COLUMN IF NOT EXISTS sale_currency VARCHAR(8) NOT NULL DEFAULT 'USD'"))
        conn.execute(text("ALTER TABLE inventory_products ADD COLUMN IF NOT EXISTS condition VARCHAR(16) NOT NULL DEFAULT 'new'"))
        conn.execute(text("ALTER TABLE inventory_products ADD COLUMN IF NOT EXISTS opening_quantity NUMERIC(18,3) NOT NULL DEFAULT 0"))
        conn.execute(text("ALTER TABLE inventory_products ADD COLUMN IF NOT EXISTS store_family VARCHAR(40)"))
        conn.execute(text("ALTER TABLE inventory_products ADD COLUMN IF NOT EXISTS store_category VARCHAR(60)"))
        conn.execute(text("ALTER TABLE inventory_products ADD COLUMN IF NOT EXISTS vehicle_details JSONB NOT NULL DEFAULT '{}'::jsonb"))
        conn.execute(text("ALTER TABLE store_password_resets ADD COLUMN IF NOT EXISTS pending_password_hash VARCHAR(300)"))
        conn.execute(text("ALTER TABLE store_customers ADD COLUMN IF NOT EXISTS first_name VARCHAR(80) NOT NULL DEFAULT ''"))
        conn.execute(text("ALTER TABLE store_customers ADD COLUMN IF NOT EXISTS last_name VARCHAR(80) NOT NULL DEFAULT ''"))
        conn.execute(text("ALTER TABLE store_customers ADD COLUMN IF NOT EXISTS shipping_address TEXT NOT NULL DEFAULT ''"))
        conn.execute(text("ALTER TABLE store_customers ADD COLUMN IF NOT EXISTS phone_country_code VARCHAR(8) NOT NULL DEFAULT '+963'"))
        conn.execute(text("ALTER TABLE store_customers ADD COLUMN IF NOT EXISTS phone_number VARCHAR(32) NOT NULL DEFAULT ''"))
        conn.execute(text("ALTER TABLE store_customers ADD COLUMN IF NOT EXISTS avatar_data TEXT"))
        conn.execute(text("ALTER TABLE store_customers ADD COLUMN IF NOT EXISTS phone_verified_at TIMESTAMP WITH TIME ZONE"))
        conn.execute(text("ALTER TABLE store_customers ADD COLUMN IF NOT EXISTS google_sub VARCHAR(255)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_store_customers_google_sub ON store_customers (google_sub) WHERE google_sub IS NOT NULL"))

        conn.execute(text("ALTER TABLE cash_moves ADD COLUMN IF NOT EXISTS voided BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_inventory_products_owner_user_id ON inventory_products(owner_user_id)"))
        # PostgreSQL trigram indexes accelerate the storefront's leading-wildcard ILIKE search.
        # Keep this optional so restricted database roles do not prevent the API from starting.
        try:
            with conn.begin_nested():
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_inventory_products_name_trgm
                    ON inventory_products USING GIN (name gin_trgm_ops)
                    WHERE active IS TRUE
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_inventory_products_model_trgm
                    ON inventory_products USING GIN (model gin_trgm_ops)
                    WHERE active IS TRUE
                """))
        except Exception:
            logging.getLogger("aib.search").warning(
                "Store search trigram indexes could not be ensured; continuing without them",
                exc_info=True,
            )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_wallet_transactions_user_id ON wallet_transactions(user_id)"))
        conn.execute(text("ALTER TABLE cash_moves ADD COLUMN IF NOT EXISTS record_id INTEGER REFERENCES records(id)"))
        conn.execute(text("ALTER TABLE cash_moves ADD COLUMN IF NOT EXISTS voided_by INTEGER REFERENCES users(id)"))
        conn.execute(text("ALTER TABLE cash_moves ADD COLUMN IF NOT EXISTS voided_at TIMESTAMP WITH TIME ZONE"))
        conn.execute(text("ALTER TABLE wallet_requests ADD COLUMN IF NOT EXISTS review_note TEXT NOT NULL DEFAULT ''"))
        conn.execute(text("ALTER TABLE wallet_requests ADD COLUMN IF NOT EXISTS withdrawal_method VARCHAR(40) NOT NULL DEFAULT ''"))
    with SessionLocal() as s:
        if not s.get(CompanyProfile,1):
            s.add(CompanyProfile(id=1,data={
                "national_no":"5420047617",
                "first_name":"عبدالكريم",
                "last_name":"محمد",
                "father_name":"خيرو",
                "mother_name":"فوزية هردوش",
                "birth_place_date":"تل الكرامة 01.01.2004",
                "document_type":"هوية شخصية",
                "document_no":"030260726",
                "issuing_authority":"الدانا",
                "registry":"صلوة ٣٠",
                "residence":"تل الكرامة"
            }))
            s.commit()
    with SessionLocal() as s:
        section_codes={"directSale":"A","purchase":"B","consignSale":"C","deposit":"D","repair":"E","carPurchase":"F","carSale":"G"}
        for section,code in section_codes.items():
            rows=s.scalars(select(Record).where(Record.section==section).order_by(Record.id)).all()
            for serial,row in enumerate(rows,1):
                if not row.invoice_no:
                    row.invoice_no=f"{code}-{serial:05d}-B"
        s.commit()
    # One-time legacy cash-box rename using set-based SQL instead of loading every row.
    with engine.begin() as conn:
        conn.execute(text("UPDATE cash_moves SET box_name=:new WHERE box_name=:old"), {"new":"صندوق الأمانة","old":"صندوق مبيع الأمانة"})
        conn.execute(text("UPDATE invoice_payments SET cash_box=:new WHERE cash_box=:old"), {"new":"صندوق الأمانة","old":"صندوق مبيع الأمانة"})
        conn.execute(text("""
            UPDATE records
            SET data = jsonb_set(data::jsonb, '{cash_box}', to_jsonb(CAST(:new AS text)))::json
            WHERE data->>'cash_box' = :old
        """), {"new":"صندوق الأمانة","old":"صندوق مبيع الأمانة"})
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE cash_moves ADD COLUMN IF NOT EXISTS transfer_group VARCHAR(36)"))
        conn.execute(text("ALTER TABLE cash_moves ADD COLUMN IF NOT EXISTS voided BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE cash_moves ADD COLUMN IF NOT EXISTS voided_by INTEGER REFERENCES users(id)"))
        conn.execute(text("ALTER TABLE cash_moves ADD COLUMN IF NOT EXISTS voided_at TIMESTAMP WITH TIME ZONE"))
        conn.execute(text("ALTER TABLE invoice_payments ADD COLUMN IF NOT EXISTS cash_box VARCHAR(100) NOT NULL DEFAULT 'صندوق المبيع'"))
    if settings.owner_password:
        with SessionLocal() as s:
            if not s.scalar(select(User).where(User.username==settings.owner_username)):
                s.add(User(username=settings.owner_username,full_name=settings.owner_name,password_hash=password_hash.hash(settings.owner_password),role="owner")); s.commit()

@app.get("/health")
def health(s:Session=Depends(db)):
    s.execute(text("SELECT 1"))
    return {"status":"ok","service":"AIB Accounting API","database":"ok"}
class AccountingPasswordResetRequestPayload(BaseModel):
    email: str = Field(min_length=5,max_length=254)
class AccountingPasswordResetConfirmPayload(BaseModel):
    token: str = Field(min_length=32,max_length=256)
    new_password: str = Field(min_length=8,max_length=256)

class AccountingLoginConfirmPayload(BaseModel):
    challenge_id:int
    code:str=Field(min_length=6,max_length=6)

class AccountingLoginResendPayload(BaseModel):
    challenge_id:int

def accounting_login_user_payload(u:User):
    return {"id":u.id,"username":u.username,"name":u.full_name,"email":u.email,"role":u.role,"permissions":u.permissions or {},"must_change_password":bool(u.must_change_password)}

@app.post("/auth/login")
def login(form:OAuth2PasswordRequestForm=Depends(), request:Request=None, s:Session=Depends(db)):
    u=s.scalar(select(User).where(or_(User.username==form.username, (User.email==form.username) & (User.email_verified==True))))
    now=datetime.now(timezone.utc)
    if not u:
        audit(s,None,"login_failed","user",None,{"username":form.username},request); s.commit(); raise HTTPException(401,"اسم المستخدم أو كلمة المرور غير صحيحة")
    if u.locked_until and u.locked_until>now: raise HTTPException(423,"الحساب مقفل مؤقتاً، حاول لاحقاً")
    if not password_hash.verify(form.password,u.password_hash):
        u.failed_logins+=1
        if u.failed_logins>=3: u.locked_until=now+timedelta(minutes=5); u.failed_logins=0
        audit(s,u,"login_failed","user",u.id,{},request); s.commit(); raise HTTPException(401,"اسم المستخدم أو كلمة المرور غير صحيحة")
    if not u.active: raise HTTPException(403,"الحساب غير فعال")
    u.failed_logins=0; u.locked_until=None
    audit(s,u,"login","user",u.id,{"method":"password","email_otp_skipped":True},request)
    s.commit()
    return {"access_token":token_for(u,email_otp_verified=True),"token_type":"bearer","user":accounting_login_user_payload(u)}

@app.post("/auth/password-reset/request")
def request_accounting_password_reset(p:AccountingPasswordResetRequestPayload,request:Request,s:Session=Depends(db)):
    email=p.email.strip().lower()
    generic={"ok":True,"message":"تم قبول الطلب. إذا كان البريد مرتبطاً بحساب محاسبة، فسيصلك رابط إعادة التعيين خلال دقائق."}
    u=s.scalar(select(User).where(func.lower(User.email)==email,User.active==True,User.deleted==False))
    if not u:
        raise HTTPException(404,"هذا البريد الإلكتروني غير مسجل في حساب محاسبة نشط على الموقع. تحقق من البريد وحاول مجدداً.")
    now=datetime.now(timezone.utc)
    recent=s.scalar(select(AccountingPasswordReset).where(
        AccountingPasswordReset.user_id==u.id,
        AccountingPasswordReset.created_at>now-timedelta(minutes=1)
    ).order_by(AccountingPasswordReset.created_at.desc()).limit(1))
    if recent:
        return generic
    raw_token=secrets.token_urlsafe(40)
    token_digest=hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    s.query(AccountingPasswordReset).filter(
        AccountingPasswordReset.user_id==u.id,
        AccountingPasswordReset.used_at.is_(None)
    ).update({AccountingPasswordReset.used_at:now},synchronize_session=False)
    reset=AccountingPasswordReset(user_id=u.id,token_hash=token_digest,expires_at=now+timedelta(minutes=30))
    s.add(reset);s.flush()
    base_url=str(request.base_url).rstrip("/")
    reset_url=base_url+"/accounting?reset_token="+raw_token
    try:
        send_aib_email(u.email,"إعادة تعيين كلمة مرور المحاسبة – مجموعة AIB",
            "وصلنا طلب لإعادة تعيين كلمة مرور حسابك في تطبيق AIB. افتح الرابط التالي خلال 30 دقيقة لإعداد كلمة مرور جديدة: "+reset_url+"\nإذا لم تطلب ذلك، تجاهل هذه الرسالة.",
            f"""<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><body style="margin:0;background:#f2f5f7;padding:24px;font-family:Tahoma,Arial"><div style="max-width:520px;margin:auto;background:#fff;border:1px solid #e4eaf0;border-radius:16px;overflow:hidden"><div style="background:#172b3b;padding:22px;text-align:center;color:#fff"><b style="font-size:27px">AIB</b><div>مجموعة AIB التجارية</div></div><div style="padding:28px;text-align:center;color:#243342"><h2>إعادة تعيين كلمة المرور</h2><p style="line-height:2">اضغط الزر أدناه لإعداد كلمة مرور جديدة لحساب المحاسبة. الرابط صالح لمدة 30 دقيقة ولمرة واحدة فقط.</p><a href="{html.escape(reset_url,quote=True)}" style="display:inline-block;background:#e58a42;color:#fff;text-decoration:none;padding:13px 25px;border-radius:9px;font-weight:bold">إعادة تعيين كلمة المرور</a><p style="font-size:12px;color:#697887;margin-top:22px">إذا لم تطلب إعادة التعيين، تجاهل هذه الرسالة. لن تتغير كلمة مرورك دون إكمال الخطوات.</p></div></div></body></html>""")
    except Exception:
        s.rollback()
        raise HTTPException(503,"تعذر إرسال رابط إعادة التعيين. تحقق من إعدادات البريد وحاول لاحقاً.")
    audit(s,u,"accounting_password_reset_requested","user",u.id,{"reset_id":reset.id},request)
    s.commit()
    return generic

@app.post("/auth/password-reset/confirm")
def confirm_accounting_password_reset(p:AccountingPasswordResetConfirmPayload,request:Request,s:Session=Depends(db)):
    value=p.new_password
    if not re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).{8,256}$",value):
        raise HTTPException(400,"كلمة المرور يجب أن تتضمن 8 خانات على الأقل وحرفاً كبيراً وصغيراً ورقماً ورمزاً.")
    digest=hashlib.sha256(p.token.encode("utf-8")).hexdigest()
    now=datetime.now(timezone.utc)
    reset=s.scalar(select(AccountingPasswordReset).where(AccountingPasswordReset.token_hash==digest))
    if not reset or reset.used_at or reset.expires_at<now:
        raise HTTPException(400,"رابط إعادة التعيين غير صالح أو منتهي. اطلب رابطاً جديداً.")
    u=s.get(User,reset.user_id)
    if not u or not u.active or u.deleted:
        raise HTTPException(400,"تعذر إعادة تعيين كلمة المرور لهذا الحساب.")
    reset.used_at=now
    u.password_hash=password_hash.hash(value)
    u.failed_logins=0
    u.locked_until=None
    u.must_change_password=False
    s.query(AccountingPasswordReset).filter(
        AccountingPasswordReset.user_id==u.id,
        AccountingPasswordReset.used_at.is_(None),
        AccountingPasswordReset.id!=reset.id
    ).update({AccountingPasswordReset.used_at:now},synchronize_session=False)
    audit(s,u,"accounting_password_reset_completed","user",u.id,{"reset_id":reset.id},request)
    s.commit()
    return {"ok":True,"message":"تم تعيين كلمة المرور الجديدة بنجاح. يمكنك تسجيل الدخول الآن."}

@app.post("/auth/login/resend")
def resend_accounting_login_code(p:AccountingLoginResendPayload,request:Request,s:Session=Depends(db)):
    now=datetime.now(timezone.utc)
    previous=s.get(AccountingLoginVerification,p.challenge_id)
    if not previous or previous.used_at: raise HTTPException(400,"طلب التحقق غير صالح. ابدأ تسجيل الدخول من جديد.")
    u=s.get(User,previous.user_id)
    if not u or not u.active or not u.email or (u.role!="owner" and not u.email_verified): raise HTTPException(403,"الحساب غير مؤهل لتأكيد الدخول")
    if previous.created_at>now-timedelta(seconds=30): raise HTTPException(429,"انتظر 30 ثانية قبل إعادة إرسال الرمز.")
    code=f"{secrets.randbelow(1000000):06d}"
    challenge=AccountingLoginVerification(user_id=u.id,code_hash=password_hash.hash(code),expires_at=now+timedelta(minutes=10))
    s.add(challenge);s.flush()
    try:
        send_aib_email(u.email,"رمز الدخول إلى المحاسبة – مجموعة AIB",
            f"رمز الدخول الجديد هو: {code}\\nصالح لمدة 10 دقائق ولمرة واحدة فقط.",
            f"""<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><body style="margin:0;background:#f2f5f7;padding:24px;font-family:Tahoma,Arial"><div style="max-width:520px;margin:auto;background:#fff;border-radius:16px;overflow:hidden;border:1px solid #e4eaf0"><div style="background:#172b3b;padding:22px;text-align:center;color:#fff"><b style="font-size:27px">AIB</b><div>مجموعة AIB التجارية</div></div><div style="padding:28px;text-align:center;color:#243342"><h2>رمز دخول جديد</h2><div style="font-size:32px;letter-spacing:8px;font-weight:900;color:#168447;background:#f1f7f3;border:1px dashed #168447;border-radius:12px;padding:18px">{code}</div><p style="color:#697887">صالح لمدة 10 دقائق ولمرة واحدة فقط.</p></div></div></body></html>""")
    except Exception:
        s.rollback();raise HTTPException(503,"تعذر إرسال الرمز. حاول لاحقاً.")
    audit(s,u,"accounting_login_code_resent","user",u.id,{"challenge_id":challenge.id},request);s.commit()
    return {"ok":True,"challenge_id":challenge.id,"masked_email":masked_email(u.email),"expires_in":600}

@app.post("/auth/login/confirm")
def confirm_accounting_login(p:AccountingLoginConfirmPayload,request:Request,s:Session=Depends(db)):
    now=datetime.now(timezone.utc)
    row=s.get(AccountingLoginVerification,p.challenge_id)
    if not row or row.used_at or row.expires_at<now: raise HTTPException(400,"رمز الدخول منتهي أو غير صالح. اطلب رمزاً جديداً.")
    u=s.get(User,row.user_id)
    if not u or not u.active or not u.email or (u.role!="owner" and not u.email_verified): raise HTTPException(403,"الحساب غير مؤهل لتأكيد الدخول")
    if row.attempts>=5: raise HTTPException(429,"تجاوزت عدد محاولات إدخال الرمز. اطلب رمزاً جديداً.")
    if not password_hash.verify(p.code,row.code_hash):
        row.attempts+=1; audit(s,u,"accounting_login_code_failed","user",u.id,{"challenge_id":row.id},request); s.commit()
        raise HTTPException(401,"رمز التحقق غير صحيح")
    row.used_at=now
    if u.role=="owner": u.email_verified=True
    s.query(AccountingLoginVerification).filter(AccountingLoginVerification.user_id==u.id,AccountingLoginVerification.used_at.is_(None),AccountingLoginVerification.id!=row.id).update({AccountingLoginVerification.used_at:now},synchronize_session=False)
    audit(s,u,"login","user",u.id,{"method":"email_otp"},request); s.commit()
    return {"access_token":token_for(u,email_otp_verified=True),"token_type":"bearer","user":accounting_login_user_payload(u)}

@app.get("/auth/me")
def me(request:Request,u:User=Depends(current_user)):
    impersonated_by=getattr(u,"_impersonated_by_owner_id",None)
    return {"id":u.id,"username":u.username,"name":u.full_name,"email":u.email,"role":u.role,"permissions":u.permissions or {},"business_scopes":u.business_scopes or [],"company_name":u.company_name or "","must_change_password":bool(u.must_change_password) if not impersonated_by else False,"is_impersonating":bool(impersonated_by),"impersonated_by_owner_id":impersonated_by}

@app.post("/auth/impersonate/{user_id}")
def impersonate_user(user_id:int,request:Request,s:Session=Depends(db),owner:User=Depends(manager)):
    target=s.get(User,user_id)
    if not target or target.deleted or not target.active or target.role=="owner":
        raise HTTPException(404,"حساب المستخدم غير موجود أو غير فعال")
    audit(s,owner,"owner_impersonation_started","user",target.id,{"target_username":target.username},request)
    s.commit()
    return {"access_token":token_for(target,email_otp_verified=False,impersonated_by_owner_id=owner.id),"token_type":"bearer","user":{**accounting_login_user_payload(target),"business_scopes":target.business_scopes or [],"company_name":target.company_name or "","must_change_password":False,"is_impersonating":True,"impersonated_by_owner_id":owner.id}}

class AccountSettingsPayload(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
def validate_account_password(value:str):
    if len(value)<8 or not re.search(r"[A-Z]",value) or not re.search(r"[a-z]",value) or not re.search(r"\d",value) or not re.search(r"[^A-Za-z0-9]",value):
        raise HTTPException(400,"كلمة المرور يجب أن تكون 8 خانات على الأقل وتتضمن حرفاً كبيراً وحرفاً صغيراً ورقماً ورمزاً.")
    return value

class PasswordChangePayload(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)
    verification_token: Optional[str] = None
class EmailVerificationStartPayload(BaseModel):
    email: str = Field(min_length=5, max_length=254)
class EmailVerificationConfirmPayload(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    code: str = Field(min_length=6, max_length=6)
@app.get("/account-settings")
def get_account_settings(u:User=Depends(current_user)):
    return {"id":u.id,"username":u.username,"full_name":u.full_name,"email":u.email if u.email_verified else None,"email_verified":u.email_verified,"role":u.role}
@app.patch("/account-settings")
def update_account_settings(p:AccountSettingsPayload, request:Request, s:Session=Depends(db), u:User=Depends(current_user)):
    if p.email is not None: raise HTTPException(400,"لا يمكن اعتماد البريد مباشرة. اطلب رمز تحقق وأكده أولاً")
    old_name=u.full_name
    if p.full_name is not None:
        name=p.full_name.strip()
        if not name: raise HTTPException(400,"الاسم لا يمكن أن يكون فارغاً")
        u.full_name=name
    audit(s,u,"account_settings_updated","user",u.id,{"name_updated":p.full_name is not None},request)
    s.commit()
    if p.full_name is not None and old_name!=u.full_name:
        notify_account_change(u.email,f"تغيير الاسم من «{old_name}» إلى «{u.full_name}»")
    return {"ok":True,"email":u.email,"full_name":u.full_name}

def send_aib_email(email:str, subject:str, body:str, html_body:Optional[str]=None):
    if not email or "@" not in email:
        raise HTTPException(400,"عنوان البريد الإلكتروني غير صالح")
    if settings.smtp_host and settings.smtp_user and settings.smtp_password and settings.smtp_from:
        message=EmailMessage()
        message["Subject"]=subject
        message["From"]=settings.smtp_from
        message["To"]=email
        message.set_content(body)
        if html_body: message.add_alternative(html_body,subtype="html")
        try:
            with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=25) as server:
                server.ehlo();server.starttls();server.ehlo()
                server.login(settings.smtp_user,settings.smtp_password)
                server.send_message(message)
            return
        except (smtplib.SMTPException,OSError,TimeoutError) as exc:
            print(f"SMTP delivery failed: {type(exc).__name__}; smtp_code={getattr(exc,'smtp_code',None)}",flush=True)
    if not settings.brevo_api_key or not settings.brevo_sender_email:
        raise HTTPException(503,"خدمة البريد غير مهيأة. تحقق من إعدادات Gmail SMTP في Render")
    payload={"sender":{"name":settings.brevo_sender_name,"email":settings.brevo_sender_email},
             "to":[{"email":email}],"subject":subject,"textContent":body,**({"htmlContent":html_body} if html_body else {})}
    req=UrlRequest("https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
        headers={"api-key":settings.brevo_api_key,"accept":"application/json","content-type":"application/json"},
        method="POST")
    try:
        with urlopen(req,timeout=20) as response:
            if response.status not in (200,201,202):
                raise HTTPException(502,f"رفض مزود البريد إرسال الرسالة (HTTP {response.status})")
    except HTTPError as exc:
        raise HTTPException(502,f"رفض مزود البريد إرسال الرسالة (HTTP {exc.code})")
    except (URLError,TimeoutError,OSError):
        raise HTTPException(502,"تعذر الاتصال بخدمة البريد. تحقق من إعدادات Render")

def aib_email_html(title:str, intro:str, rows:list[tuple[str,str]], accent:str="#bd9654", note:str="هذه رسالة آلية من مجموعة AIB التجارية."):
    safe_rows="".join(f"<tr><td style='padding:11px 14px;color:#718096;border-bottom:1px solid #e8edf1;width:34%;font-weight:700'>{html.escape(str(k))}</td><td style='padding:11px 14px;color:#243342;border-bottom:1px solid #e8edf1;font-weight:600'>{v}</td></tr>" for k,v in rows)
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"></head><body style="margin:0;background:#f2f5f7;font-family:Tahoma,Arial,sans-serif;color:#243342;padding:24px 10px"><div style="max-width:620px;margin:0 auto;background:#fff;border:1px solid #e3e9ee;border-radius:18px;overflow:hidden;box-shadow:0 12px 35px rgba(23,42,58,.08)"><div style="background:#172b3b;padding:23px 26px;text-align:center;border-bottom:4px solid {accent}"><div style="font-size:27px;font-weight:900;letter-spacing:3px;color:#fff">AIB</div><div style="color:#dce5ec;font-size:13px;margin-top:5px">مجموعة AIB التجارية</div></div><div style="padding:27px 25px"><h2 style="margin:0 0 14px;color:#203447;font-size:21px">{html.escape(title)}</h2><p style="margin:0 0 20px;line-height:2;color:#536474">{html.escape(intro)}</p><table role="presentation" style="width:100%;border-collapse:collapse;background:#fbfcfd;border:1px solid #e8edf1;border-radius:12px">{safe_rows}</table><p style="margin:22px 0 0;padding:13px 15px;border-right:4px solid {accent};background:#f7f9fa;color:#617181;font-size:12px;line-height:1.9">{html.escape(note)}</p></div><div style="padding:16px;text-align:center;background:#f8fafb;border-top:1px solid #e8edf1;color:#7b8994;font-size:11px">مجموعة AIB التجارية · للاستفسار تواصل مع فريقنا</div></div></body></html>"""

def send_notification_email(email:str, subject:str, body:str, html_body:Optional[str]=None):
    try:
        send_aib_email(email,subject,body,html_body)
    except Exception as exc:
        print(f"AIB notification email failed: {type(exc).__name__}",flush=True)

def send_verification_email(email:str, code:str):
    send_aib_email(email,"رمز التحقق - مجموعة AIB",
        f"رمز التحقق الخاص بك في تطبيق AIB هو: {code}\nصلاحية الرمز 10 دقائق. لا تشاركه مع أحد.")

def operation_verification_required(u:User, action:str)->bool:
    if action in {"cash_movement","cash_transfer","password_change"}:
        return True
    if action in {"company_profile_edit"}: return u.role=="owner"
    return u.role!="owner" and action in {"invoice_create","invoice_payment"}

def masked_email(email:str)->str:
    local,_,domain=email.partition("@")
    visible=local[:2] if len(local)>2 else local[:1]
    return visible+"***@"+domain

class OperationVerificationStartPayload(BaseModel):
    action: str
    current_password: Optional[str] = None
class OperationVerificationConfirmPayload(BaseModel):
    challenge_id: int
    code: str = Field(min_length=6,max_length=6)

@app.post("/operation-verifications/start")
def start_operation_verification(p:OperationVerificationStartPayload,request:Request,s:Session=Depends(db),u:User=Depends(current_user)):
    if p.action not in {"invoice_create","invoice_payment","cash_movement","cash_transfer","password_change","company_profile_edit"}:
        raise HTTPException(400,"نوع العملية غير مدعوم للتحقق")
    if not operation_verification_required(u,p.action):
        return {"required":False}
    if p.action in {"password_change","company_profile_edit"} and (not p.current_password or not password_hash.verify(p.current_password,u.password_hash)):
        raise HTTPException(401,"كلمة المرور الحالية غير صحيحة")
    if p.action=="company_profile_edit" and u.role!="owner":
        raise HTTPException(403,"تعديل بيانات صاحب الشركة متاح لحساب المالك فقط")
    email=(u.email or "").strip().lower()
    if not email or (p.action != "password_change" and not u.email_verified):
        raise HTTPException(400,"يجب إضافة بريد إلكتروني موثق لحسابك قبل تنفيذ هذه العملية. راجع إعدادات الحساب.")
    now=datetime.now(timezone.utc)
    latest=s.scalar(select(OperationVerification).where(
        OperationVerification.user_id==u.id,
        OperationVerification.action==p.action
    ).order_by(OperationVerification.id.desc()))
    if latest and latest.created_at>now-timedelta(seconds=30):
        raise HTTPException(429,"تم إرسال رمز قبل قليل. انتظر 30 ثانية ثم أعد المحاولة.")
    s.query(OperationVerification).filter(
        OperationVerification.user_id==u.id,
        OperationVerification.action==p.action,
        OperationVerification.used_at.is_(None)
    ).update({"expires_at":now},synchronize_session=False)
    code=f"{secrets.randbelow(1000000):06d}"
    row=OperationVerification(user_id=u.id,action=p.action,code_hash=password_hash.hash(code),expires_at=now+timedelta(minutes=10))
    s.add(row);s.flush()
    try:
        send_verification_email(email,code)
    except Exception:
        s.rollback()
        raise
    audit(s,u,"operation_verification_sent","operation",row.id,{"action":p.action},request)
    s.commit()
    return {"required":True,"challenge_id":row.id,"email":masked_email(email),"expires_in":600,"message":"تم إرسال رمز تأكيد العملية إلى بريدك الإلكتروني"}

@app.post("/operation-verifications/confirm")
def confirm_operation_verification(p:OperationVerificationConfirmPayload,request:Request,s:Session=Depends(db),u:User=Depends(current_user)):
    row=s.get(OperationVerification,p.challenge_id)
    now=datetime.now(timezone.utc)
    if not row or row.user_id!=u.id or row.used_at is not None or row.verified_at is not None or row.expires_at<now or row.attempts>=5:
        raise HTTPException(400,"رمز التحقق منتهي أو غير صالح. اطلب رمزاً جديداً.")
    if not password_hash.verify(p.code,row.code_hash):
        row.attempts+=1;s.commit()
        raise HTTPException(400,"رمز التحقق غير صحيح")
    grant=secrets.token_urlsafe(32)
    row.grant_hash=hashlib.sha256(grant.encode("utf-8")).hexdigest()
    row.verified_at=now
    audit(s,u,"operation_verification_confirmed","operation",row.id,{"action":row.action},request)
    s.commit()
    return {"ok":True,"verification_token":grant,"expires_in":600}

def consume_operation_verification(s:Session,u:User,action:str,token:Optional[str]):
    if not operation_verification_required(u,action):
        return
    if not token:
        raise HTTPException(403,"يلزم تأكيد العملية برمز البريد الإلكتروني")
    token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest()
    row=s.scalar(select(OperationVerification).where(
        OperationVerification.user_id==u.id,
        OperationVerification.action==action,
        OperationVerification.grant_hash==token_hash
    ).with_for_update())
    now=datetime.now(timezone.utc)
    if not row or row.verified_at is None or row.used_at is not None or row.expires_at<now:
        raise HTTPException(403,"رمز تأكيد العملية غير صالح أو منتهي أو مستخدم مسبقاً")
    row.used_at=now

def notify_account_change(email:str, details:str):
    if email:
        send_notification_email(email,"تنبيه أمان: تغيير بيانات حساب AIB",
            f"مرحباً، تم إجراء تغيير على بيانات حسابك في مجموعة AIB.\nالتفاصيل: {details}\nإذا لم تكن أنت من أجرى هذا التغيير، يرجى التواصل مع إدارة AIB فوراً.")

@app.post("/account-settings/email-verification")
def start_email_verification(p:EmailVerificationStartPayload, request:Request, s:Session=Depends(db), u:User=Depends(current_user)):
    email=p.email.strip().lower()
    if "@" not in email or "." not in email.rsplit("@",1)[-1]: raise HTTPException(400,"البريد الإلكتروني غير صالح")
    duplicate=s.scalar(select(User).where(User.email==email,User.id!=u.id))
    if duplicate: raise HTTPException(409,"البريد الإلكتروني مستخدم لحساب آخر")
    code=f"{secrets.randbelow(1000000):06d}"
    row=EmailVerification(user_id=u.id,email=email,code_hash=password_hash.hash(code),expires_at=datetime.now(timezone.utc)+timedelta(minutes=10))
    s.add(row);s.flush()
    send_verification_email(email,code)
    audit(s,u,"email_verification_sent","user",u.id,{"email":email},request)
    s.commit()
    return {"ok":True,"message":"تم إرسال رمز التحقق إلى البريد"}
@app.post("/account-settings/email-verification/confirm")
def confirm_email_verification(p:EmailVerificationConfirmPayload, request:Request, s:Session=Depends(db), u:User=Depends(current_user)):
    email=p.email.strip().lower()
    row=s.scalar(select(EmailVerification).where(EmailVerification.user_id==u.id,EmailVerification.email==email).order_by(EmailVerification.id.desc()))
    now=datetime.now(timezone.utc)
    if not row or row.expires_at<now or row.attempts>=5: raise HTTPException(400,"رمز التحقق منتهي أو غير موجود. اطلب رمزاً جديداً")
    if not password_hash.verify(p.code,row.code_hash):
        row.attempts+=1;s.commit()
        raise HTTPException(400,"رمز التحقق غير صحيح")
    duplicate=s.scalar(select(User).where(User.email==email,User.id!=u.id))
    if duplicate: raise HTTPException(409,"البريد الإلكتروني مستخدم لحساب آخر")
    old_email=u.email
    u.email=email
    u.email_verified=True
    s.query(EmailVerification).filter(EmailVerification.user_id==u.id).delete(synchronize_session=False)
    audit(s,u,"email_verified","user",u.id,{"email":email},request)
    s.commit()
    notify_account_change(old_email,"تم تغيير البريد الإلكتروني المرتبط بحسابك")
    notify_account_change(email,"تم ربط هذا البريد الإلكتروني بحساب AIB")
    return {"ok":True,"email":u.email,"verified":True}
class FirstLoginPasswordPayload(BaseModel):
    new_password: str = Field(min_length=8, max_length=256)

@app.post("/auth/first-login-password")
def first_login_password(p:FirstLoginPasswordPayload,request:Request,s:Session=Depends(db),u:User=Depends(current_user)):
    if not u.must_change_password or u.role=="owner":
        raise HTTPException(400,"لا يوجد تغيير كلمة مرور أولي مطلوب لهذا الحساب")
    validate_account_password(p.new_password)
    u.password_hash=password_hash.hash(p.new_password)
    u.must_change_password=False
    u.failed_logins=0
    u.locked_until=None
    audit(s,u,"employee_initial_password_changed","user",u.id,{"required_on_first_login":True},request)
    s.commit()
    notify_account_change(u.email,"تم تغيير كلمة المرور المؤقتة لحسابك")
    return {"ok":True,"message":"تم تغيير كلمة المرور بنجاح","must_change_password":False}

@app.post("/auth/change-password")
def change_owner_password(p:PasswordChangePayload, request:Request, s:Session=Depends(db), u:User=Depends(current_user)):
    validate_account_password(p.new_password)
    if u.role != "owner":
        raise HTTPException(403,"تغيير كلمة المرور مباشرة متاح لحساب المالك فقط")
    if not password_hash.verify(p.current_password,u.password_hash):
        raise HTTPException(401,"كلمة المرور الحالية غير صحيحة")
    consume_operation_verification(s,u,"password_change",p.verification_token)
    u.password_hash=password_hash.hash(p.new_password)
    u.failed_logins=0
    u.locked_until=None
    audit(s,u,"owner_password_changed","user",u.id,{"method":"email_otp"},request)
    s.commit()
    notify_account_change(u.email,"تم تغيير كلمة المرور")
    return {"ok":True,"message":"تم تغيير كلمة المرور بنجاح"}

@app.post("/password-change-requests")
def create_password_change_request(p:PasswordChangePayload, request:Request, s:Session=Depends(db), u:User=Depends(current_user)):
    validate_account_password(p.new_password)
    if u.role == "owner":
        raise HTTPException(400,"استخدم نموذج تغيير كلمة مرور المالك")
    if not password_hash.verify(p.current_password,u.password_hash):
        raise HTTPException(401,"كلمة المرور الحالية غير صحيحة")
    consume_operation_verification(s,u,"password_change",p.verification_token)
    u.password_hash=password_hash.hash(p.new_password)
    u.failed_logins=0
    u.locked_until=None
    audit(s,u,"user_password_changed","user",u.id,{"method":"email_otp"},request)
    s.commit()
    notify_account_change(u.email,"تم تغيير كلمة المرور بعد التحقق من رمز البريد الإلكتروني")
    return {"ok":True,"status":"changed","message":"تم تغيير كلمة المرور بنجاح بعد تأكيد البريد الإلكتروني"}
@app.get("/password-change-requests")
def list_password_change_requests(s:Session=Depends(db), _:User=Depends(manager)):
    rows=s.scalars(select(PasswordChangeRequest).order_by(PasswordChangeRequest.id.desc()).limit(200)).all()
    return [{"id":x.id,"user_id":x.user_id,"username":(s.get(User,x.user_id).username if s.get(User,x.user_id) else "—"),"status":x.status,"created_at":x.created_at} for x in rows]
@app.get("/my-password-change-requests")
def my_password_change_requests(s:Session=Depends(db), u:User=Depends(current_user)):
    rows=s.scalars(select(PasswordChangeRequest).where(PasswordChangeRequest.user_id==u.id).order_by(PasswordChangeRequest.id.desc()).limit(100)).all()
    return [{"id":x.id,"status":x.status,"created_at":x.created_at} for x in rows]
@app.post("/password-change-requests/{request_id}/review")
def review_password_change_request(request_id:int, approve:bool, request:Request, s:Session=Depends(db), u:User=Depends(manager)):
    row=s.get(PasswordChangeRequest,request_id)
    if not row or row.status!="pending": raise HTTPException(404,"طلب تغيير كلمة المرور غير موجود أو تمت معالجته")
    target=s.get(User,row.user_id)
    if not target or not target.active: raise HTTPException(404,"حساب الموظف غير موجود أو غير فعال")
    if approve: target.password_hash=row.new_password_hash
    row.status="approved" if approve else "rejected"
    row.reviewed_by=u.id; row.reviewed_at=datetime.now(timezone.utc)
    audit(s,u,"password_change_"+row.status,"user",target.id,{"request_id":row.id},request)
    s.commit()
    if approve:
        notify_account_change(target.email,"تم اعتماد تغيير كلمة المرور من قبل المالك")
    return {"status":row.status}

def manufacturer_scope_tokens()->set[str]:
    try:
        catalog=json.loads((FRONTEND_DIR / "data" / "manufacturers.json").read_text(encoding="utf-8"))
        return {"manufacturer:"+str(item.get("key") or "").strip() for item in catalog.get("manufacturers",[]) if item.get("key")}
    except Exception:
        return set()

USER_BUSINESS_SCOPES={"fuel:gasoline","fuel:diesel","fuel:electric","fuel:hybrid","fuel:cng","fuel:lpg","fuel:other","condition:new","condition:used","car","truck","heavy","agri","special","cars","car_parts","car_engines","car_engine_parts","trucks","truck_parts","truck_engines","truck_engine_parts","heavy_parts","heavy_engines","heavy_engine_parts","agri_parts","agri_engines","agri_engine_parts","trailer","trailers","car_trailers","caravans","cargo_trailers","flatbed_trailers","equipment_trailers","tanker_trailers","dump_trailers","livestock_trailers","other_trailers","generators","hydraulic_compressors","water_pumps","road_equipment","special_parts","special_engines"}
class UserCreate(BaseModel):
    username:str=Field(min_length=3,max_length=80)
    full_name:str=Field(min_length=2,max_length=160)
    email:str=Field(min_length=5,max_length=254)
    email_confirm:str|None=None
    password:str=Field(min_length=8,max_length=256)
    role:str="employee"
    company_name:str=Field(default="",max_length=200)
    business_scopes:list[str]=Field(default_factory=list)
    owner_commission_rate:float=Field(default=1.5,ge=0,le=100)

class UserProfilePayload(BaseModel):
    company_name:str=Field(min_length=2,max_length=200)
    company_logo:Optional[str]=Field(default=None,max_length=1400000)
    profile_data:dict=Field(default_factory=dict)

@app.get("/my-profile")
def get_my_profile(u:User=Depends(current_user)):
    return {"user_id":u.id,"company_name":u.company_name or "","company_logo":u.company_logo,"profile_data":u.profile_data or {}}

@app.put("/my-profile")
def update_my_profile(p:UserProfilePayload,request:Request,s:Session=Depends(db),u:User=Depends(current_user)):
    logo=(p.company_logo or "").strip() or None
    if logo and not (logo.startswith("https://") or logo.startswith("http://") or logo.startswith("data:image/png;base64,") or logo.startswith("data:image/jpeg;base64,") or logo.startswith("data:image/webp;base64,")):
        raise HTTPException(400,"صيغة الشعار غير مدعومة")
    if logo and logo.startswith("data:image/"):
        try: raw=base64.b64decode(logo.split(",",1)[1],validate=True)
        except (ValueError,binascii.Error): raise HTTPException(400,"ملف الشعار غير صالح")
        if not raw or len(raw)>1024*1024: raise HTTPException(413,"يجب ألا يتجاوز حجم الشعار 1 ميغابايت")
    required_profile_fields={"first_name","last_name","father_name","mother_name","national_no","birth_place_date","document_type","document_no","issuing_authority","registry","residence","address"}
    missing=[key for key in sorted(required_profile_fields) if not str((p.profile_data or {}).get(key) or "").strip()]
    if missing: raise HTTPException(400,"أكمل جميع بيانات الهوية المطلوبة قبل الحفظ")
    u.company_name=p.company_name.strip()
    u.company_logo=logo
    u.profile_data=p.profile_data or {}
    audit(s,u,"user_profile_updated","user",u.id,{"company_name":u.company_name,"has_logo":bool(logo),"profile_fields":sorted(u.profile_data.keys())},request)
    s.commit()
    return {"ok":True,"company_name":u.company_name,"has_logo":bool(logo)}

class UserScopesPayload(BaseModel):
    business_scopes:list[str]=Field(default_factory=list)

@app.patch("/users/{user_id}/business-scopes")
def update_user_business_scopes(user_id:int,p:UserScopesPayload,request:Request,s:Session=Depends(db),u:User=Depends(manager)):
    target=s.get(User,user_id)
    if not target or target.deleted or target.role=="owner": raise HTTPException(404,"المستخدم غير موجود")
    scopes=sorted(set(p.business_scopes or []))
    if set(scopes)-USER_BUSINESS_SCOPES: raise HTTPException(400,"يوجد مجال عمل غير معروف")
    target.business_scopes=scopes
    audit(s,u,"user_business_scopes_updated","user",target.id,{"business_scopes":scopes},request)
    s.commit()
    return {"ok":True,"business_scopes":scopes}

@app.get("/users/{user_id}/profile")
def get_user_profile(user_id:int,s:Session=Depends(db),u:User=Depends(current_user)):
    if u.role!="owner" and u.id!=user_id: raise HTTPException(403,"لا يمكنك عرض بيانات مستخدم آخر")
    target=s.get(User,user_id)
    if not target or target.deleted: raise HTTPException(404,"المستخدم غير موجود")
    return {"user_id":target.id,"company_name":target.company_name or "","company_logo":target.company_logo,"profile_data":target.profile_data or {}}

@app.get("/users/{user_id}/inventory")
def get_user_inventory(user_id:int,s:Session=Depends(db),u:User=Depends(manager)):
    target=s.get(User,user_id)
    if not target or target.deleted: raise HTTPException(404,"المستخدم غير موجود")
    # Compact, read-only summary for the owner's user-inventory modal.
    # Select only displayed columns; do not load large image/video JSON fields.
    rows=s.execute(
        select(
            InventoryProduct.id, InventoryProduct.sku, InventoryProduct.name,
            InventoryProduct.model, InventoryProduct.owned_stock,
            InventoryProduct.consigned_stock, InventoryProduct.sale_price,
            InventoryProduct.sale_currency,
        )
        .where(InventoryProduct.owner_user_id==user_id,InventoryProduct.active.is_(True))
        .order_by(InventoryProduct.sku)
    ).all()
    products=[{
        "id":p.id,"sku":p.sku,"name":p.name,"model":p.model,
        "owned_stock":float(p.owned_stock or 0),
        "consigned_stock":float(p.consigned_stock or 0),
        "sale_price":float(p.sale_price) if p.sale_price is not None else None,
        "sale_currency":p.sale_currency,
    } for p in rows]
    return {"user_id":target.id,"username":target.username,"company_name":target.company_name or "","products":products}

class CompanyProfilePayload(BaseModel):
    data: dict
    verification_token: Optional[str] = None

@app.get("/company-profile")
def get_company_profile(s:Session=Depends(db), u:User=Depends(current_user)):
    profile=s.get(CompanyProfile,1)
    return profile.data if profile else {}

@app.put("/company-profile")
def update_company_profile(p:CompanyProfilePayload, request:Request, s:Session=Depends(db), u:User=Depends(current_user)):
    if u.role!="owner": raise HTTPException(403,"تعديل بيانات صاحب الشركة متاح لحساب المالك فقط")
    consume_operation_verification(s,u,"company_profile_edit",p.verification_token)
    profile=s.get(CompanyProfile,1)
    if not profile:
        profile=CompanyProfile(id=1,data=p.data,updated_by=u.id)
        s.add(profile)
    else:
        profile.data=p.data
        profile.updated_by=u.id
        profile.updated_at=datetime.now(timezone.utc)
    audit(s,u,"company_profile_updated","company_profile",1,{"fields":sorted(p.data.keys())},request)
    s.commit()
    return {"ok":True,"data":profile.data}

class PublicSiteSettingsPayload(BaseModel):
    show_stats: bool = True

@app.get("/public-site-settings")
def get_public_site_settings(s:Session=Depends(db), u:User=Depends(manager)):
    profile=s.get(CompanyProfile,1)
    data=profile.data if profile and isinstance(profile.data,dict) else {}
    return {"show_stats":data.get("public_show_stats",True) is not False}

@app.put("/public-site-settings")
def update_public_site_settings(p:PublicSiteSettingsPayload, request:Request, s:Session=Depends(db), u:User=Depends(manager)):
    profile=s.get(CompanyProfile,1)
    if not profile:
        profile=CompanyProfile(id=1,data={"public_show_stats":p.show_stats},updated_by=u.id)
        s.add(profile)
    else:
        data=dict(profile.data or {})
        data["public_show_stats"]=p.show_stats
        profile.data=data
        profile.updated_by=u.id
        profile.updated_at=datetime.now(timezone.utc)
    audit(s,u,"public_site_settings_updated","company_profile",1,{"show_stats":p.show_stats},request)
    s.commit()
    return {"ok":True,"show_stats":p.show_stats}

@app.get("/users")
def list_users(s:Session=Depends(db), _:User=Depends(manager)):
    return [{"id":u.id,"username":u.username,"name":u.full_name,"email":u.email,"role":u.role,"active":u.active,"permissions":u.permissions or {},"company_name":u.company_name or "","business_scopes":u.business_scopes or [],"owner_commission_rate":float(u.owner_commission_rate if u.owner_commission_rate is not None else 1.5)} for u in s.scalars(select(User).where(User.deleted.is_(False))).all()]
@app.post("/users")
def add_user(payload:UserCreate, request:Request, s:Session=Depends(db), u:User=Depends(manager)):
    validate_account_password(payload.password)
    if payload.role not in ("employee","owner"): raise HTTPException(400,"دور غير صالح")
    invalid_scopes={x for x in (payload.business_scopes or []) if x not in USER_BUSINESS_SCOPES and x not in manufacturer_scope_tokens()}
    if invalid_scopes: raise HTTPException(400,"يوجد مجال عمل غير معروف")
    if payload.role=="owner" and payload.business_scopes: raise HTTPException(400,"لا تُحدد مجالات عمل لحساب المالك")
    if s.scalar(select(User).where(User.username==payload.username)): raise HTTPException(409,"اسم المستخدم مستخدم")
    email=(payload.email or "").strip().lower()
    if (not email) or ("@" not in email) or ("." not in email.rsplit("@",1)[-1]) or len(email)>254: raise HTTPException(400,"البريد الإلكتروني مطلوب ويجب أن يكون صالحاً")
    if s.scalar(select(User).where(User.email==email,User.deleted.is_(False))): raise HTTPException(409,"البريد الإلكتروني مستخدم لحساب نشط")
    # Older soft-deleted accounts may still hold the unique email value.
    for archived in s.scalars(select(User).where(User.email==email,User.deleted.is_(True))).all():
        archived.email=None
        archived.email_verified=False
    nu=User(username=payload.username,full_name=payload.full_name,email=email,email_verified=False,password_hash=password_hash.hash(payload.password),role="employee",company_name=payload.company_name.strip(),business_scopes=sorted(set(payload.business_scopes or [])),owner_commission_rate=payload.owner_commission_rate,profile_data={})
    nu.permissions={}; s.add(nu); s.flush()
    for wallet_currency in ("USD","SYP"):
        s.add(UserWallet(user_id=nu.id,currency=wallet_currency,balance=0))
    code=f"{secrets.randbelow(1000000):06d}"
    approval=EmployeeEmailApproval(user_id=nu.id,code_hash=password_hash.hash(code),expires_at=datetime.now(timezone.utc)+timedelta(minutes=15))
    s.add(approval)
    try:
        send_aib_email(email,"رمز تأكيد حساب الموظف – مجموعة AIB",
            f"مرحباً {nu.full_name}، رمز تأكيد بريدك لتفعيل حساب AIB هو: {code}\\nأرسل الرمز إلى مسؤول الشركة عبر قناة واتساب الرسمية. الرمز صالح 15 دقيقة ولمرة واحدة.",
            f"""<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><body style="margin:0;background:#f2f5f7;padding:24px;font-family:Tahoma,Arial"><div style="max-width:520px;margin:auto;background:white;border:1px solid #e4eaf0;border-radius:16px;overflow:hidden"><header style="background:#172b3b;color:white;text-align:center;padding:22px"><b style="font-size:28px">AIB</b><div>مجموعة AIB التجارية</div></header><main style="padding:28px;text-align:center;color:#243342"><h2>تأكيد البريد الإلكتروني</h2><p>مرحباً {html.escape(nu.full_name)}، أرسل هذا الرمز إلى مسؤول الشركة عبر واتساب لإكمال تفعيل حسابك.</p><div style="font-size:34px;letter-spacing:9px;font-weight:bold;color:#168447;background:#f1f7f3;border:1px dashed #168447;border-radius:12px;padding:18px">{code}</div><p>صالح لمدة 15 دقيقة ولمرة واحدة.</p><small>لا تشارك الرمز مع أي شخص غير مسؤول الشركة.</small></main></div></body></html>""")
    except Exception:
        s.rollback(); raise HTTPException(503,"تعذر إرسال رمز التأكيد إلى بريد الموظف. لم يتم إنشاء الحساب.")
    audit(s,u,"user_created_pending_email_approval","user",nu.id,{"username":nu.username},request); s.commit()
    return {"id":nu.id,"username":nu.username,"email":email,"email_verified":False,"approval_required":True,"company_name":nu.company_name,"business_scopes":nu.business_scopes}
class EmployeeEmailApprovalPayload(BaseModel):
    code:str=Field(min_length=1,max_length=32)

@app.post("/users/{user_id}/confirm-email")
def approve_employee_email(user_id:int,p:EmployeeEmailApprovalPayload,request:Request,s:Session=Depends(db),u:User=Depends(manager)):
    target=s.get(User,user_id)
    if not target or target.deleted or target.role=="owner": raise HTTPException(404,"الموظف غير موجود")
    if target.email_verified: return {"ok":True,"email_verified":True}
    row=s.scalar(select(EmployeeEmailApproval).where(EmployeeEmailApproval.user_id==user_id,EmployeeEmailApproval.used_at.is_(None)).order_by(EmployeeEmailApproval.id.desc()))
    now=datetime.now(timezone.utc)
    if not row or row.expires_at<now: raise HTTPException(400,"رمز التأكيد منتهي. أعد إنشاء الحساب أو اطلب رمزاً جديداً.")
    if row.attempts>=5: raise HTTPException(429,"تم تجاوز محاولات الرمز. يلزم إصدار رمز جديد.")
    # Normalize Arabic/Persian numerals and accidental spaces before checking the emailed code.
    normalized_code="".join(str(int(ch)) for ch in __import__("unicodedata").normalize("NFKC",str(p.code)) if ch.isdigit())
    if len(normalized_code)!=6 or not password_hash.verify(normalized_code,row.code_hash):
        row.attempts+=1;s.commit();raise HTTPException(400,"رمز تأكيد البريد غير صحيح. أدخل الأرقام الستة كما ظهرت في الرسالة.")
    row.used_at=now;target.email_verified=True
    audit(s,u,"employee_email_confirmed_by_owner","user",target.id,{"email":target.email},request);s.commit()
    return {"ok":True,"email_verified":True,"username":target.username}

class UserCommissionPayload(BaseModel):
    rate:float=Field(ge=0,le=100)

@app.patch("/users/{user_id}/commission")
def update_user_commission(user_id:int,p:UserCommissionPayload,request:Request,s:Session=Depends(db),u:User=Depends(manager)):
    target=s.get(User,user_id)
    if not target or target.deleted or target.role=="owner": raise HTTPException(404,"المستخدم غير موجود")
    target.owner_commission_rate=round(float(p.rate),3)
    audit(s,u,"user_commission_rate_updated","user",target.id,{"owner_commission_rate":float(target.owner_commission_rate)},request)
    s.commit()
    return {"ok":True,"user_id":target.id,"owner_commission_rate":float(target.owner_commission_rate)}

class UserPermissionsPayload(BaseModel):
    permissions: dict
    business_scopes: list[str] = Field(default_factory=list)
@app.patch("/users/{user_id}/permissions")
def update_user_permissions(user_id:int,p:UserPermissionsPayload,request:Request,s:Session=Depends(db),u:User=Depends(manager)):
    target=s.get(User,user_id)
    if not target: raise HTTPException(404,"المستخدم غير موجود")
    if target.role=="owner": raise HTTPException(400,"لا يمكن تعديل صلاحيات حساب المالك")
    clean={}
    for module,actions in PERMISSION_SCHEMA.items():
        values=p.permissions.get(module,{})
        if not isinstance(values,dict): raise HTTPException(400,"صيغة الصلاحيات غير صحيحة")
        clean[module]={action:bool(values.get(action,False)) for action in actions}
    if any(clean["inventory"][k] for k in ("create","edit")):
        clean["inventory"]["view"]=True
    if any(clean["invoices"][k] for k in ("create","edit","delete","print")):
        clean["invoices"]["view"]=True
    if any(clean["cash"][k] for k in ("create","edit","delete","print")):
        clean["cash"]["view"]=True
    invalid_scopes={x for x in (p.business_scopes or []) if x not in USER_BUSINESS_SCOPES and x not in manufacturer_scope_tokens()}
    if invalid_scopes: raise HTTPException(400,"يوجد قسم أو قسم فرعي غير معروف")
    target.business_scopes=sorted(set(p.business_scopes or []))
    target.permissions=clean
    audit(s,u,"user_permissions_updated","user",user_id,{"permissions":clean,"business_scopes":target.business_scopes},request)
    s.commit()
    return {"ok":True,"permissions":clean}
class UserPasswordResetPayload(BaseModel):
    password: Optional[str] = None

@app.patch("/users/{user_id}/password")
def reset_user_password(user_id:int, p:UserPasswordResetPayload, request:Request, s:Session=Depends(db), u:User=Depends(manager)):
    target=s.get(User,user_id)
    if not target: raise HTTPException(404,"المستخدم غير موجود")
    if target.role=="owner": raise HTTPException(400,"لا يمكن إصدار بطاقة دخول لحساب المالك من هذه الصفحة")
    alphabet_upper="ABCDEFGHJKLMNPQRSTUVWXYZ"
    alphabet_lower="abcdefghijkmnopqrstuvwxyz"
    alphabet_digits="23456789"
    alphabet_symbols="!@#$%*-_"
    temporary_password="".join([secrets.choice(alphabet_upper),secrets.choice(alphabet_lower),secrets.choice(alphabet_digits),secrets.choice(alphabet_symbols)]+[secrets.choice(alphabet_upper+alphabet_lower+alphabet_digits+alphabet_symbols) for _ in range(4)])
    chars=list(temporary_password);secrets.SystemRandom().shuffle(chars);temporary_password="".join(chars)
    validate_account_password(temporary_password)
    target.password_hash=password_hash.hash(temporary_password)
    target.must_change_password=True
    target.failed_logins=0
    target.locked_until=None
    audit(s,u,"user_credentials_reissued","user",user_id,{"username":target.username,"must_change_password":True,"temporary_password_length":8},request)
    s.commit()
    return {"ok":True,"username":target.username,"full_name":target.full_name,"email":target.email,"temporary_password":temporary_password}

@app.delete("/users/{user_id}")
def delete_user(user_id:int, request:Request, s:Session=Depends(db), u:User=Depends(manager)):
    target=s.get(User,user_id)
    if not target: raise HTTPException(404,"المستخدم غير موجود")
    if target.role=="owner": raise HTTPException(400,"لا يمكن حذف حساب المالك")
    details={"username":target.username,"full_name":target.full_name}
    audit(s,u,"user_deleted","user",user_id,details,request)
    target.active=False
    target.deleted=True
    target.locked_until=None
    # Release the unique email so a newly created employee can reuse it.
    target.email=None
    target.email_verified=False
    s.commit()
    return {"ok":True,"deleted_id":user_id}

@app.patch("/users/{user_id}/active")
def set_user_active(user_id:int, active:bool, request:Request, s:Session=Depends(db), u:User=Depends(manager)):
    target=s.get(User,user_id)
    if not target: raise HTTPException(404,"المستخدم غير موجود")
    if target.role=="owner": raise HTTPException(400,"لا يمكن تعطيل حساب المالك")
    target.active=active; audit(s,u,"user_status_changed","user",user_id,{"active":active},request); s.commit(); return {"ok":True}

def next_inventory_sku(s:Session)->str:
    s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key":"aib-inventory-sku"})
    serial=int(s.scalar(select(func.count(InventoryProduct.id))) or 0)+1
    while True:
        sku=f"AIB-{serial:06d}"
        if not s.scalar(select(InventoryProduct.id).where(InventoryProduct.sku==sku)):
            return sku
        serial+=1

def prepare_record_inventory(s:Session, section:str, raw_data:dict, allow_legacy:bool=False, user:Optional[User]=None)->dict:
    data=dict(raw_data or {})
    items=data.get("items") if isinstance(data.get("items"),list) else []
    prepared=[]
    stock_sections={"purchase","carPurchase","directSale","deposit","consignSale"}
    # Legacy vehicle-purchase invoices keep vehicle data in the record header;
    # normalize it into a stock item so the vehicle enters inventory and the shop.
    if section=="carPurchase":
        if not items:
            items=[{"quantity":1,"price":float(data.get("amount") or data.get("price") or 0)}]
        first=next((x for x in items if isinstance(x,dict)),None)
        if first is not None:
            legacy_map={"vehicle_type":"سيارة كاملة","vehicle_make":data.get("car_make"),"vehicle_model":data.get("car_model"),"vehicle_year":data.get("car_year"),"vehicle_odometer":data.get("car_odometer"),"vehicle_color":data.get("car_color"),"chassis":data.get("car_vin")}
            for key,value in legacy_map.items():
                if value not in (None,"") and first.get(key) in (None,""):
                    first[key]=value
            if not first.get("store_family"): first["store_family"]="car"
            if not first.get("store_category"): first["store_category"]="cars"
            if not str(first.get("description") or "").strip():
                first["description"]=" ".join(str(data.get(k) or "").strip() for k in ("car_make","car_model")).strip() or "سيارة كاملة"
            if not str(first.get("model") or "").strip():
                first["model"]=str(data.get("car_model") or "").strip()
            if not first.get("quantity"): first["quantity"]=1
            if not first.get("price") and data.get("amount"): first["price"]=float(data.get("amount") or 0)
        data["items"]=items
    for raw in items:
        if not isinstance(raw,dict): continue
        item=dict(raw)
        # Normalize dedicated vehicle fields before the empty-line guard.
        # This ensures a vehicle purchase creates an inventory product even
        # when the generic description/model inputs were left blank.
        vehicle_make=str(item.get("vehicle_make") or "").strip()
        vehicle_model=str(item.get("vehicle_model") or "").strip()
        vehicle_type=str(item.get("vehicle_type") or "").strip()
        if vehicle_make or vehicle_model:
            if not str(item.get("description") or "").strip():
                item["description"]=" ".join(x for x in (vehicle_make,vehicle_model) if x).strip() or vehicle_type or "مركبة كاملة"
            if not str(item.get("model") or "").strip():
                item["model"]=vehicle_model
        name=str(item.get("description") or item.get("model") or "").strip()
        model=str(item.get("model") or "").strip()
        sku=str(item.get("sku") or "").strip().upper()
        if not name and not sku:
            prepared.append(item); continue
        if section not in stock_sections:
            prepared.append(item); continue
        product=s.scalar(select(InventoryProduct).where(InventoryProduct.sku==sku)) if sku else None
        if not sku:
            if section not in {"purchase","deposit"}:
                if allow_legacy:
                    prepared.append(item)
                    continue
                raise HTTPException(400,"أدخل رقم القطعة أو اختر قطعة موجودة عند المبيع. لا يمكن إنشاء رقم جديد لقطعة مباعة دون رصيد سابق.")
            sku=next_inventory_sku(s)
        if not product:
            if section not in {"purchase","deposit"}:
                raise HTTPException(400,f"رقم القطعة {sku} غير موجود في المخزون. أضفها أولاً عبر الشراء أو الأمانة.")
            product=InventoryProduct(sku=sku,name=name or sku,model=model,description=str(item.get("product_description") or "").strip(),owner_user_id=(user.id if user and user.role!="owner" else None))
            s.add(product)
            try: s.flush()
            except Exception:
                s.rollback()
                raise HTTPException(409,f"رقم القطعة {sku} مستخدم مسبقاً. ابحث عنها واخترها.")
        else:
            if not product.active: raise HTTPException(400,f"القطعة {sku} غير مفعلة")
            if user and user.role!="owner" and product.owner_user_id!=user.id:
                raise HTTPException(403,f"القطعة {sku} ليست ضمن مخزون حسابك")
            if not name: item["description"]=product.name
            if not model: item["model"]=product.model
            if not str(item.get("product_description") or "").strip():
                item["product_description"]=product.description or ""
        item["sku"]=sku
        family=str(item.get("store_family") or "").strip()
        category=str(item.get("store_category") or "").strip()
        allowed={"car":{"cars","car_parts","car_engines","car_engine_parts"},"truck":{"trucks","truck_parts","truck_engines","truck_engine_parts"},"heavy":{"heavy","heavy_parts","heavy_engines","heavy_engine_parts"},"agri":{"agri","agri_parts","agri_engines","agri_engine_parts"},"special":{"generators","hydraulic_compressors","water_pumps","road_equipment","special_parts","special_engines"}}
        if section in {"purchase","deposit"} and name and (not family or not category):
            raise HTTPException(400,"يجب اختيار القسم الرئيسي والقسم الفرعي للمنتج عند الشراء أو وضع الأمانة")
        if family or category:
            if category not in allowed.get(family,set()):
                raise HTTPException(400,"اختر القسم الرئيسي والفرعي للمنتج بشكل صحيح قبل الحفظ")
            if user and user.role!="owner":
                scopes=set(user.business_scopes or [])
                # A broad family permission unlocks its categories; a specific category can be granted alone.
                if family not in scopes and category not in scopes:
                    raise HTTPException(403,"هذا القسم خارج مجالات العمل المصرح بها لحسابك. راجع المالك.")
        prepared.append(item)
    data["items"]=prepared
    return data

def recalculate_inventory(s:Session):
    # Serialize every stock-ledger rebuild so concurrent purchases, sales, edits,
    # deletions, and manual adjustments cannot overwrite one another's balances.
    s.execute(text("SELECT pg_advisory_xact_lock(741920261116)"))
    totals={p.id:{"owned":float(p.opening_quantity or 0),"consigned":0.0} for p in s.scalars(select(InventoryProduct)).all()}
    for record in s.scalars(select(Record).where(Record.deleted.is_(False))).all():
        if record.section not in {"purchase","carPurchase","directSale","deposit","consignSale"}: continue
        items=record.data.get("items") if isinstance(record.data,dict) else []
        for item in items if isinstance(items,list) else []:
            if not isinstance(item,dict) or not item.get("sku"): continue
            product=s.scalar(select(InventoryProduct).where(InventoryProduct.sku==str(item["sku"]).strip().upper()))
            if not product: raise HTTPException(400,f"القطعة {item['sku']} غير مسجلة في دليل المخزون")
            qty=float(item.get("quantity") or 0)
            if qty<=0: raise HTTPException(400,f"كمية القطعة {product.sku} يجب أن تكون أكبر من صفر")
            # Online orders may draw from both owned and consigned stock.
            # Their allocation is recorded explicitly so each stock bucket remains accurate.
            if record.section=="directSale" and ("owned_quantity" in item or "consigned_quantity" in item):
                owned_qty=float(item.get("owned_quantity") or 0)
                consigned_qty=float(item.get("consigned_quantity") or 0)
                if owned_qty<0 or consigned_qty<0 or abs((owned_qty+consigned_qty)-qty)>0.0001:
                    raise HTTPException(400,f"توزيع كمية القطعة {product.sku} بين المخزون غير صحيح")
                totals[product.id]["owned"]-=owned_qty
                totals[product.id]["consigned"]-=consigned_qty
            else:
                bucket="owned" if record.section in {"purchase","carPurchase","directSale"} else "consigned"
                sign=-1 if record.section in {"directSale","consignSale"} else 1
                totals[product.id][bucket]+=sign*qty
    # Apply audited manual stock adjustments after invoice-derived movements.
    for event in s.scalars(select(AuditEvent).where(AuditEvent.action=="inventory_stock_adjustment",AuditEvent.entity=="inventory_product")).all():
        details=event.details if isinstance(event.details,dict) else {}
        adjustment=details.get("stock_adjustment") if isinstance(details.get("stock_adjustment"),dict) else {}
        product_id=event.entity_id
        if product_id in totals:
            totals[product_id]["owned"]+=float(adjustment.get("owned_delta") or 0)
            totals[product_id]["consigned"]+=float(adjustment.get("consigned_delta") or 0)
    for product in s.scalars(select(InventoryProduct)).all():
        owned=round(totals[product.id]["owned"],3)
        consigned=round(totals[product.id]["consigned"],3)
        if owned < -0.0001: raise HTTPException(400,f"الرصيد المملوك للقطعة {product.sku} غير كافٍ. الرصيد الحالي لا يسمح بهذه الكمية.")
        if consigned < -0.0001: raise HTTPException(400,f"رصيد الأمانة للقطعة {product.sku} غير كافٍ. تحقق من إيداعات الأمانة السابقة.")
        product.owned_stock=max(0,owned)
        product.consigned_stock=max(0,consigned)

_store_catalog_cache={"at":0.0,"value":None}
# Short-lived in-process cache for public storefront searches; keeps repeat searches off the database.
_public_products_cache={"at":{},"value":{}}
_PUBLIC_PRODUCTS_CACHE_TTL=20
_PUBLIC_PRODUCTS_CACHE_MAX=120

def record_item_landed_unit_cost(record:Record,item:dict)->float:
    """Allocate invoice-level extra costs across item lines by line value, then return landed unit cost."""
    data=record.data if isinstance(record.data,dict) else {}
    costs=data.get("extra_costs") if isinstance(data.get("extra_costs"),dict) else {}
    extra_keys={
        "loading":("loading_cost","loading"),
        "packaging":("packaging_cost","packaging"),
        "local_transport":("local_transport_cost","local_transport"),
        "shipping":("shipping_cost","shipping"),
        "customs":("customs_cost","customs"),
        "clearance":("clearance_cost","clearance"),
    }
    extra_total=sum(max(0.0,float(data.get(field,costs.get(key,0)) or 0)) for field,key in extra_keys.values())
    items=[x for x in data.get("items",[]) if isinstance(x,dict)] if isinstance(data.get("items"),list) else []
    subtotal=sum(max(0.0,float(x.get("price") or 0))*max(0.0,float(x.get("quantity") or 0)) for x in items)
    unit_price=max(0.0,float(item.get("price") or 0))
    if subtotal<=0 or unit_price<=0 or extra_total<=0:
        return unit_price
    return unit_price+(extra_total*unit_price/subtotal)

def latest_store_catalog_data(s:Session)->tuple[dict,dict]:
    """Reuse the recent catalog snapshot instead of rescanning all invoice history on every request."""
    import time
    now=time.monotonic()
    cached=_store_catalog_cache["value"]
    if cached is not None and now-_store_catalog_cache["at"]<45:
        return cached
    latest_categories={}
    latest_prices={}
    allowed={"car":{"cars","car_parts","car_engines","car_engine_parts"},"truck":{"trucks","truck_parts","truck_engines","truck_engine_parts"},"heavy":{"heavy","heavy_parts","heavy_engines","heavy_engine_parts"},"agri":{"agri","agri_parts","agri_engines","agri_engine_parts"},"special":{"generators","hydraulic_compressors","water_pumps","road_equipment","special_parts","special_engines"}}
    rows=s.scalars(select(Record).where(
        Record.deleted.is_(False),
        Record.section.in_(["purchase","carPurchase","deposit"])
    ).order_by(Record.created_at.desc(),Record.id.desc())).all()
    for record in rows:
        for item in (record.data or {}).get("items",[]):
            if not isinstance(item,dict): continue
            sku=str(item.get("sku") or "").strip().upper()
            if not sku: continue
            if record.section in {"purchase","carPurchase"} and sku not in latest_prices:
                price=record_item_landed_unit_cost(record,item)
                if price>0:
                    latest_prices[sku]={"purchase_price":round(price,2),"sale_price":round(price*1.35,2),"currency":record.currency or "USD"}
            if sku not in latest_categories:
                family=str(item.get("store_family") or "").strip()
                category=str(item.get("store_category") or "").strip()
                if category in allowed.get(family,set()):
                    vehicle_owner={}
                    if record.section=="carPurchase":
                        vehicle_owner={k:record.data.get(k) for k in ("seller_first_name","seller_last_name","seller_full_name","seller_father_name","seller_mother_name","seller_national_no","seller_birth_place_date","seller_id_type","seller_id_no","seller_id_issuer","seller_registry","seller_residence","seller_address") if record.data.get(k) not in (None,"")}
                    latest_categories[sku]={"store_family":family,"store_category":category,"vehicle_details":{k:item.get(k) for k in ("vehicle_name","vehicle_type","vehicle_make","vehicle_model","vehicle_class","vehicle_generation","vehicle_year","vehicle_odometer","vehicle_fuel","vehicle_color","chassis") if item.get(k) not in (None,"")},"vehicle_owner":vehicle_owner}
    result=(latest_categories,latest_prices)
    _store_catalog_cache["value"]=result
    _store_catalog_cache["at"]=now
    return result

def latest_inventory_store_categories(s:Session)->dict:
    return latest_store_catalog_data(s)[0]

class InventoryProductCreate(BaseModel):
    sku: Optional[str]=Field(default=None,max_length=80)
    name: str=Field(min_length=2,max_length=240)
    model: str=Field(default="",max_length=160)
    description: str=Field(default="",max_length=5000)
    sale_price: Optional[float]=Field(default=None,ge=0)
    profit_margin: float=Field(default=35,ge=0,le=1000)
    sale_currency: str="USD"
    condition: str=Field(min_length=3,max_length=16)
    fuel_type: str=Field(min_length=1,max_length=30)
    quantity: float=Field(default=0,ge=0)
    store_family: str
    store_category: str
    manufacturer: str=Field(min_length=1,max_length=160)
    vehicle_details: Optional[dict]=None

@app.post("/inventory/products")
def create_inventory_product(p:InventoryProductCreate,request:Request,s:Session=Depends(db),u:User=Depends(require_permission("inventory","create"))):
    if p.sale_currency not in {"USD","SYP"}: raise HTTPException(400,"عملة سعر البيع غير مدعومة")
    if p.condition not in {"new","used"}: raise HTTPException(400,"اختر حالة المنتج: جديد أو مستعمل")
    allowed_fuels={"gasoline","diesel","electric","hybrid","cng","lpg","other"}
    if p.fuel_type not in allowed_fuels: raise HTTPException(400,"اختر نوع وقود صحيحاً")
    if u.role!="owner":
        scopes=set(u.business_scopes or [])
        if "fuel:"+p.fuel_type not in scopes: raise HTTPException(403,"نوع الوقود هذا غير مسموح لك بالنشر به. اطلب من المالك تفعيله في صلاحيات المستخدم.")
        if "condition:"+p.condition not in scopes: raise HTTPException(403,"حالة القطعة أو السيارة هذه غير مسموح لك بالنشر بها. اطلب من المالك تفعيلها في صلاحيات المستخدم.")
    allowed={"car":{"cars","car_parts","car_engines","car_engine_parts"},"truck":{"trucks","truck_parts","truck_engines","truck_engine_parts"},"heavy":{"heavy","heavy_parts","heavy_engines","heavy_engine_parts"},"agri":{"agri","agri_parts","agri_engines","agri_engine_parts"},"special":{"generators","hydraulic_compressors","water_pumps","road_equipment","special_parts","special_engines"}}
    if p.store_category not in allowed.get(p.store_family,set()): raise HTTPException(400,"اختر قسم المتجر بشكل صحيح")
    vehicle_categories={"car":"cars","truck":"trucks","heavy":"heavy","agri":"agri"}
    is_complete_vehicle=p.store_category==vehicle_categories.get(p.store_family)
    manufacturer=p.manufacturer.strip()
    catalog_manufacturers={str(item.get("key")):str(item.get("name")) for item in json.loads((FRONTEND_DIR / "data" / "manufacturers.json").read_text(encoding="utf-8")).get("manufacturers",[]) if item.get("key") and item.get("name")}
    manufacturer_item=next((item for item in catalog_manufacturers.values() if item.casefold()==manufacturer.casefold()),None)
    if not manufacturer_item: raise HTTPException(400,"اختر شركة مصنّعة صحيحة من القائمة")
    if u.role!="owner" and "manufacturer:"+next((key for key,name in catalog_manufacturers.items() if name.casefold()==manufacturer.casefold()),"") not in set(u.business_scopes or []):
        raise HTTPException(403,"هذه الشركة المصنّعة غير مسموح لك بالنشر باسمها. اطلب من المالك تفعيلها في صلاحيات المستخدم.")
    vehicle_details={str(k):str(v).strip() for k,v in (p.vehicle_details or {}).items() if k in {"manufacturer","vehicle_name","vehicle_type","vehicle_make","vehicle_model","vehicle_class","vehicle_generation","vehicle_year","vehicle_odometer","vehicle_fuel","vehicle_color","chassis"} and v not in (None,"")}
    vehicle_details["manufacturer"]=manufacturer_item
    vehicle_details["vehicle_fuel"]={"gasoline":"بنزين","diesel":"ديزل","electric":"كهرباء","hybrid":"هجين","cng":"غاز طبيعي","lpg":"غاز بترولي","other":"أخرى"}[p.fuel_type]
    if is_complete_vehicle:
        vehicle_details["vehicle_make"]=manufacturer_item
    if is_complete_vehicle and not vehicle_details.get("vehicle_name"):
        raise HTTPException(400,"أدخل اسم السيارة أو المركبة")
    if not is_complete_vehicle and any(k not in {"manufacturer","vehicle_fuel"} for k in vehicle_details):
        raise HTTPException(400,"بيانات المركبة متاحة للأقسام الكاملة فقط")
    if u.role!="owner":
        scopes=set(u.business_scopes or [])
        if p.store_family not in scopes and p.store_category not in scopes: raise HTTPException(403,"هذا القسم خارج مجالات العمل المصرح بها لحسابك")
    sku=(p.sku or "").strip().upper() or next_inventory_sku(s)
    if s.scalar(select(InventoryProduct.id).where(func.upper(InventoryProduct.sku)==sku)):
        raise HTTPException(409,"رقم القطعة مستخدم مسبقاً")
    product=InventoryProduct(sku=sku,name=p.name.strip(),model=p.model.strip(),description=p.description.strip(),owner_user_id=(None if u.role=="owner" else u.id),sale_price=p.sale_price,profit_margin=p.profit_margin,sale_currency=p.sale_currency,condition=p.condition,opening_quantity=p.quantity,store_family=p.store_family,store_category=p.store_category,vehicle_details=vehicle_details,owned_stock=p.quantity,consigned_stock=0,active=True)
    s.add(product);s.flush()
    audit(s,u,"inventory_product_created","inventory_product",product.id,{"sku":sku,"owner_user_id":product.owner_user_id,"sale_price":p.sale_price,"sale_currency":p.sale_currency,"condition":p.condition,"fuel_type":p.fuel_type,"opening_quantity":p.quantity,"store_family":p.store_family,"store_category":p.store_category},request)
    s.commit()
    _store_catalog_cache["value"]=None
    _store_catalog_cache["at"]=0
    _public_products_cache["value"].clear()
    _public_products_cache["at"].clear()
    return {"id":product.id,"sku":product.sku,"name":product.name,"model":product.model,"description":product.description or "","owner_user_id":product.owner_user_id,"sale_price":float(product.sale_price) if product.sale_price is not None else None,**({"profit_margin":float(product.profit_margin)} if u.role=="owner" else {}),"sale_currency":product.sale_currency,"condition":product.condition,"opening_quantity":float(product.opening_quantity or 0),"store_family":product.store_family,"store_category":product.store_category,"vehicle_details":product.vehicle_details or {},"owned_stock":float(product.owned_stock or 0),"consigned_stock":0}

@app.get("/inventory/products")
def list_inventory_products(q:Optional[str]=None, s:Session=Depends(db), u:User=Depends(require_permission("inventory","view"))):
    # Legacy products with no owner remain in the owner's inventory only.
    query=select(InventoryProduct).where(InventoryProduct.active.is_(True))
    if u.role=="owner": query=query.where(InventoryProduct.owner_user_id.is_(None))
    else: query=query.where(InventoryProduct.owner_user_id==u.id)
    if q:
        term=f"%{q.strip()}%"
        query=query.where(or_(InventoryProduct.sku.ilike(term),InventoryProduct.name.ilike(term),InventoryProduct.model.ilike(term)))
    rows=s.scalars(query.order_by(InventoryProduct.sku).limit(300)).all()
    # Only show products referenced by at least one non-deleted invoice record.
    # A product whose only invoice was deleted is hidden as well; no rows or
    # stock values are deleted or modified by this display filter.
    # Extract only invoice SKUs in PostgreSQL instead of loading every full invoice
    # (including unrelated fields) into Python whenever inventory is opened.
    invoiced_skus={
        str(value).strip().upper()
        for value in s.execute(text("""
            SELECT DISTINCT UPPER(BTRIM(item->>'sku'))
            FROM records AS r
            CROSS JOIN LATERAL jsonb_array_elements(
                CASE
                    WHEN jsonb_typeof(CAST(r.data AS JSONB)->'items')='array'
                    THEN CAST(r.data AS JSONB)->'items'
                    ELSE '[]'::jsonb
                END
            ) AS item
            WHERE r.deleted IS FALSE
              AND NULLIF(BTRIM(item->>'sku'),'') IS NOT NULL
        """)).scalars().all()
    }
    rows=[p for p in rows if (u.role=="owner" and p.owner_user_id is None and str(p.sku or "").strip().upper() in invoiced_skus) or (u.role!="owner" and p.owner_user_id==u.id)]
    store_categories,latest_purchase=latest_store_catalog_data(s)
    return [{"id":p.id,"sku":p.sku,"name":p.name,"model":p.model,"description":p.description or "","owner_user_id":p.owner_user_id,"condition":p.condition or "new","is_store_visible":bool(p.is_store_visible),"opening_quantity":float(p.opening_quantity or 0),"store_family":p.store_family,"store_category":p.store_category,"owned_stock":float(p.owned_stock or 0),**({"consigned_stock":float(p.consigned_stock or 0)} if u.role=="owner" else {}),"image_count":len(p.images or []),"shipping_included":bool(p.shipping_included),"video_url":p.video_url or "",**store_categories.get(p.sku,{}),"vehicle_details":(p.vehicle_details or store_categories.get(p.sku,{}).get("vehicle_details") or {}),**latest_purchase.get(p.sku,{"purchase_price":0,"sale_price":0,"currency":"—"}),"sale_price":round(float(latest_purchase[p.sku]["purchase_price"])*(1+float(p.profit_margin if p.profit_margin is not None else 35)/100),2) if p.sku in latest_purchase and latest_purchase[p.sku].get("purchase_price") else (float(p.sale_price) if p.sale_price is not None else latest_purchase.get(p.sku,{}).get("sale_price")),**({"profit_margin":float(p.profit_margin or 35)} if u.role=="owner" else {}),"sale_currency":p.sale_currency if p.sale_price is not None else latest_purchase.get(p.sku,{}).get("currency","")} for p in rows]

class InventoryProductUpdate(BaseModel):
    name: str=Field(min_length=2,max_length=240)
    model: str=Field(default="",max_length=160)
    description: str=Field(default="",max_length=5000)
    sale_price: Optional[float]=Field(default=None,ge=0)
    profit_margin: Optional[float]=Field(default=None,ge=0,le=1000)
    sale_currency: str="USD"
    condition: str="new"
    store_family: str
    store_category: str
    vehicle_details: Optional[dict]=None
    owned_stock: Optional[float]=Field(default=None,ge=0)
    consigned_stock: Optional[float]=Field(default=None,ge=0)

@app.put("/inventory/products/{product_id}")
def edit_inventory_product(product_id:int,p:InventoryProductUpdate,request:Request,s:Session=Depends(db),u:User=Depends(require_inventory_product_management())):
    product=s.get(InventoryProduct,product_id)
    if not product or not product.active or (u.role!="owner" and product.owner_user_id!=u.id):
        raise HTTPException(404,"المنتج غير موجود في مخزون حسابك")
    if p.sale_currency not in {"USD","SYP"}:
        raise HTTPException(400,"عملة سعر البيع غير مدعومة")
    if p.condition not in {"new","used"}:
        raise HTTPException(400,"اختر حالة المنتج: جديد أو مستعمل")
    allowed={"car":{"cars","car_parts","car_engines","car_engine_parts"},"truck":{"trucks","truck_parts","truck_engines","truck_engine_parts"},"heavy":{"heavy","heavy_parts","heavy_engines","heavy_engine_parts"},"agri":{"agri","agri_parts","agri_engines","agri_engine_parts"},"special":{"generators","hydraulic_compressors","water_pumps","road_equipment","special_parts","special_engines"}}
    if p.store_category not in allowed.get(p.store_family,set()):
        raise HTTPException(400,"اختر قسم المتجر بشكل صحيح")
    if u.role!="owner":
        scopes=set(u.business_scopes or [])
        if p.store_family not in scopes and p.store_category not in scopes:
            raise HTTPException(403,"هذا القسم خارج مجالات العمل المصرح بها لحسابك")
    if u.role!="owner" and p.consigned_stock is not None:
        raise HTTPException(403,"لا يمكن لحساب المستخدم تعديل بيانات مخزون الأمانة")
    if p.owned_stock is not None or (u.role=="owner" and p.consigned_stock is not None):
        recalculate_inventory(s)
    old_owned=float(product.owned_stock or 0)
    old_consigned=float(product.consigned_stock or 0)
    new_owned=float(p.owned_stock) if p.owned_stock is not None else old_owned
    # Employee edits must never reset or alter the owner-controlled consigned balance.
    new_consigned=(float(p.consigned_stock) if p.consigned_stock is not None else old_consigned) if u.role=="owner" else old_consigned
    stock_adjustment={"owned_delta":round(new_owned-old_owned,3),"consigned_delta":round(new_consigned-old_consigned,3)}
    before={"name":product.name,"model":product.model,"description":product.description or "","sale_price":float(product.sale_price) if product.sale_price is not None else None,"sale_currency":product.sale_currency,"condition":product.condition,"store_family":product.store_family,"store_category":product.store_category,"owned_stock":old_owned,"consigned_stock":old_consigned}
    product.owned_stock=new_owned
    product.consigned_stock=new_consigned
    product.name=p.name.strip()
    product.model=p.model.strip()
    product.description=p.description.strip()
    product.sale_price=p.sale_price
    if u.role=="owner" and p.profit_margin is not None:
        product.profit_margin=p.profit_margin
    _,latest_purchase=latest_store_catalog_data(s)
    purchase=latest_purchase.get(product.sku)
    if purchase and float(purchase.get("purchase_price") or 0)>0:
        product.sale_price=round(float(purchase["purchase_price"])*(1+float(product.profit_margin)/100),2)
        product.sale_currency=purchase.get("currency") or p.sale_currency
    product.sale_currency=product.sale_currency or p.sale_currency
    product.condition=p.condition
    product.store_family=p.store_family
    product.store_category=p.store_category
    vehicle_categories={"car":"cars","truck":"trucks","heavy":"heavy","agri":"agri"}
    is_complete_vehicle=p.store_category==vehicle_categories.get(p.store_family)
    if p.vehicle_details is not None:
        product.vehicle_details={str(k):str(v).strip() for k,v in p.vehicle_details.items() if k in {"vehicle_name","vehicle_type","vehicle_make","vehicle_model","vehicle_class","vehicle_generation","vehicle_year","vehicle_odometer","vehicle_fuel","vehicle_color","chassis"} and v not in (None,"")} if is_complete_vehicle else {}
    elif not is_complete_vehicle:
        product.vehicle_details={}
    audit(s,u,"inventory_product_updated","inventory_product",product.id,{"sku":product.sku,"before":before,"after":{"name":product.name,"model":product.model,"sale_price":float(product.sale_price) if product.sale_price is not None else None,"profit_margin":float(product.profit_margin),"sale_currency":product.sale_currency,"condition":p.condition,"store_family":p.store_family,"store_category":p.store_category,"owned_stock":new_owned,"consigned_stock":new_consigned},"stock_adjustment":stock_adjustment},request)
    if abs(stock_adjustment["owned_delta"])>0.0001 or abs(stock_adjustment["consigned_delta"])>0.0001:
        audit(s,u,"inventory_stock_adjustment","inventory_product",product.id,{"sku":product.sku,"stock_adjustment":stock_adjustment},request)
    s.commit()
    _store_catalog_cache["value"]=None
    _store_catalog_cache["at"]=0
    _public_products_cache["value"].clear()
    _public_products_cache["at"].clear()
    return {"ok":True,"id":product.id,"sku":product.sku,"name":product.name,"model":product.model,"sale_price":float(product.sale_price) if product.sale_price is not None else None,"sale_currency":product.sale_currency,"condition":product.condition,"store_family":product.store_family,"store_category":product.store_category,"vehicle_details":product.vehicle_details or {}}

@app.delete("/inventory/products/{product_id}")
def delete_inventory_product(product_id:int,request:Request,s:Session=Depends(db),u:User=Depends(require_inventory_product_management())):
    product=s.get(InventoryProduct,product_id)
    if not product or not product.active or (u.role!="owner" and product.owner_user_id!=u.id):
        raise HTTPException(404,"المنتج غير موجود في مخزون حسابك")
    if float(product.owned_stock or 0)>0 or float(product.consigned_stock or 0)>0:
        raise HTTPException(409,"لا يمكن حذف منتج لديه كمية متبقية. صفّر المخزون عبر العمليات النظامية أولاً.")
    product.active=False
    audit(s,u,"inventory_product_archived","inventory_product",product.id,{"sku":product.sku,"name":product.name,"reason":"user_requested_soft_delete"},request)
    s.commit()
    _store_catalog_cache["value"]=None
    _store_catalog_cache["at"]=0
    _public_products_cache["value"].clear()
    _public_products_cache["at"].clear()
    return {"ok":True,"deleted":True,"sku":product.sku}

class InventoryImagesPayload(BaseModel):
    images: list[str] = Field(default_factory=list, max_length=20)

@app.get("/inventory/products/{product_id}/images")
def get_inventory_product_images(product_id:int, s:Session=Depends(db), u:User=Depends(require_permission("inventory","view"))):
    product=s.get(InventoryProduct,product_id)
    if not product or not product.active or (u.role!="owner" and product.owner_user_id!=u.id):
        raise HTTPException(404,"القطعة غير موجودة في مخزون حسابك")
    return {"images":product.images or [],"count":len(product.images or [])}

@app.get("/public/products/{product_id}/image/{image_index}")
def get_public_product_image(product_id:int,image_index:int,s:Session=Depends(db)):
    product=s.get(InventoryProduct,product_id)
    if not product or not product.active or not product.is_store_visible:
        raise HTTPException(404,"الصورة غير موجودة")
    images=product.images or []
    if image_index<0 or image_index>=len(images):
        raise HTTPException(404,"الصورة غير موجودة")
    image_data=images[image_index]
    if not isinstance(image_data,str) or "," not in image_data:
        raise HTTPException(404,"الصورة غير صالحة")
    header,encoded=image_data.split(",",1)
    media_type={"data:image/jpeg;base64":"image/jpeg","data:image/png;base64":"image/png","data:image/webp;base64":"image/webp"}.get(header)
    if not media_type:
        raise HTTPException(404,"صيغة الصورة غير مدعومة")
    try:
        raw=base64.b64decode(encoded,validate=True)
    except (binascii.Error,ValueError):
        raise HTTPException(404,"بيانات الصورة غير صالحة")
    return Response(content=raw,media_type=media_type,headers={"Cache-Control":"public, max-age=60"})

class InventoryShippingPayload(BaseModel):
    included: bool = False

class InventoryVideoPayload(BaseModel):
    video_url: str = Field(default="", max_length=2000)

class InventoryStoreVisibilityPayload(BaseModel):
    visible: bool

@app.put("/inventory/products/{product_id}/store-visibility")
def update_inventory_product_store_visibility(product_id:int,p:InventoryStoreVisibilityPayload,request:Request,s:Session=Depends(db),u:User=Depends(current_user)):
    if u.role!="owner":
        raise HTTPException(403,"هذا الخيار متاح لحساب المالك فقط")
    product=s.get(InventoryProduct,product_id)
    if not product or not product.active or product.owner_user_id is not None:
        raise HTTPException(404,"المنتج غير موجود في مخزون المالك")
    product.is_store_visible=bool(p.visible)
    audit(s,u,"inventory_store_visibility_updated","inventory_product",product.id,{"sku":product.sku,"is_store_visible":product.is_store_visible},request)
    s.commit()
    _public_products_cache["value"].clear()
    _public_products_cache["at"].clear()
    return {"ok":True,"id":product.id,"is_store_visible":product.is_store_visible}

@app.put("/inventory/products/{product_id}/video")
def update_inventory_product_video(product_id:int,p:InventoryVideoPayload,request:Request,s:Session=Depends(db),u:User=Depends(require_permission("inventory","edit"))):
    product=s.get(InventoryProduct,product_id)
    if not product or not product.active or (u.role!="owner" and product.owner_user_id!=u.id): raise HTTPException(404,"المنتج غير موجود في مخزون حسابك")
    url=(p.video_url or "").strip()
    if url and not url.startswith(("https://","http://")): raise HTTPException(400,"أدخل رابط فيديو صحيحاً يبدأ بـ https:// أو http://")
    product.video_url=url or None
    audit(s,u,"inventory_video_updated","inventory_product",product.id,{"sku":product.sku,"has_video":bool(url)},request)
    s.commit()
    return {"ok":True,"video_url":product.video_url or ""}

@app.put("/inventory/products/{product_id}/shipping")
def update_inventory_product_shipping(product_id:int, p:InventoryShippingPayload, request:Request, s:Session=Depends(db), u:User=Depends(require_permission("inventory","edit"))):
    product=s.get(InventoryProduct,product_id)
    if not product or not product.active or (u.role!="owner" and product.owner_user_id!=u.id): raise HTTPException(404,"القطعة غير موجودة في مخزون حسابك")
    product.shipping_included=bool(p.included)
    audit(s,u,"inventory_shipping_updated","inventory_product",product.id,{"sku":product.sku,"shipping_included":product.shipping_included},request)
    s.commit()
    return {"ok":True,"shipping_included":product.shipping_included}

@app.put("/inventory/products/{product_id}/images")
def update_inventory_product_images(product_id:int, p:InventoryImagesPayload, request:Request, s:Session=Depends(db), u:User=Depends(require_permission("inventory","edit"))):
    product=s.get(InventoryProduct,product_id)
    if not product or not product.active or (u.role!="owner" and product.owner_user_id!=u.id): raise HTTPException(404,"القطعة غير موجودة في مخزون حسابك")
    total_bytes=0
    for image_data in p.images:
        if not isinstance(image_data,str) or "," not in image_data: raise HTTPException(400,"صيغة إحدى الصور غير صالحة")
        header,encoded=image_data.split(",",1)
        if header not in ("data:image/jpeg;base64","data:image/png;base64","data:image/webp;base64"): raise HTTPException(400,"يسمح فقط بصور JPG أو PNG أو WEBP")
        try: raw=base64.b64decode(encoded,validate=True)
        except (binascii.Error,ValueError): raise HTTPException(400,"بيانات إحدى الصور غير صالحة")
        if not raw or len(raw)>4*1024*1024: raise HTTPException(413,"يجب ألا يتجاوز حجم الصورة الواحدة 4 ميغابايت بعد الضغط")
        total_bytes+=len(raw)
    if total_bytes>80*1024*1024: raise HTTPException(413,"الحجم الإجمالي للصور يتجاوز 80 ميغابايت (20 صورة × 4 ميغابايت)")
    product.images=p.images
    audit(s,u,"inventory_images_updated","inventory_product",product.id,{"sku":product.sku,"image_count":len(p.images)},request)
    s.commit()
    _public_products_cache["value"].clear()
    _public_products_cache["at"].clear()
    return {"ok":True,"count":len(product.images or [])}

VEHICLE_CONTRACT_CATEGORIES={"cars","trucks","heavy","agri"}
def inventory_vehicle_seller_snapshot(s:Session,item:dict,fallback_user:User)->dict:
    sku=str(item.get("sku") or "").strip().upper()
    product=s.scalar(select(InventoryProduct).where(InventoryProduct.sku==sku)) if sku else None
    seller_id=product.owner_user_id if product and product.owner_user_id is not None else fallback_user.id
    seller=s.get(User,seller_id) or fallback_user
    profile=seller.profile_data if isinstance(seller.profile_data,dict) else {}
    first_name=str(profile.get("first_name") or seller.full_name or seller.username).strip()
    last_name=str(profile.get("last_name") or "").strip()
    return {**profile,"first_name":first_name,"last_name":last_name,"seller_full_name":" ".join(x for x in (first_name,last_name) if x),"company_name":seller.company_name or "","seller_user_id":seller.id}

class RecordCreate(BaseModel): section:str; invoice_no:Optional[str]=None; currency:str="USD"; data:dict; verification_token:Optional[str]=None
@app.post("/records")
def create_record(p:RecordCreate, request:Request, s:Session=Depends(db), u:User=Depends(require_permission("invoices","create"))):
    if p.section not in {"deposit","purchase","consignSale","directSale","repair","carPurchase","carSale"}: raise HTTPException(400,"قسم غير معروف")
    if u.role!="owner" and p.section!="directSale":
        raise HTTPException(403,"يمكن لحساب المستخدم تسجيل مبيعات منتجاته فقط. الشراء والإيداع وبقية الأقسام متاحة للمالك.")
    if p.currency not in {"USD","SYP"}: raise HTTPException(400,"عملة غير مدعومة")
    section_codes={"directSale":"A","purchase":"B","consignSale":"C","deposit":"D","repair":"E","carPurchase":"F","carSale":"G"}
    # Serialize numbering per section so simultaneous users cannot receive the same sequence.
    s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key":"aib-invoice:"+p.section})
    serial=int(s.scalar(select(func.count(Record.id)).where(Record.section==p.section)) or 0)+1
    invoice_no=f"{section_codes[p.section]}-{serial:05d}-B"
    prepared_data=prepare_record_inventory(s,p.section,p.data,user=u)
    if p.section in {"directSale","carSale"}:
        for item in prepared_data.get("items",[]) if isinstance(prepared_data.get("items"),list) else []:
            if isinstance(item,dict) and str(item.get("store_category") or "") in VEHICLE_CONTRACT_CATEGORIES:
                item["seller_profile_snapshot"]=inventory_vehicle_seller_snapshot(s,item,u)
    # Employee outside-store sales remain financially pending until the owner
    # verifies the transfer and explicitly confirms receipt.
    employee_sale = u.role!="owner" and p.section=="directSale"
    commission_base=0.0
    commission_amount=0.0
    seller_net=0.0
    commission_rate=0.0
    if employee_sale:
        items=prepared_data.get("items") if isinstance(prepared_data.get("items"),list) else []
        commission_base=round(sum(max(0.0,float(x.get("quantity") or 0))*max(0.0,float(x.get("price") or 0)) for x in items if isinstance(x,dict)),2)
        if commission_base<=0: raise HTTPException(400,"لا يمكن تسجيل بيع خارج المتجر دون منتجات مسعّرة من المخزون")
        commission_rate=round(float(u.owner_commission_rate if u.owner_commission_rate is not None else 1.5),3)
        commission_amount=round(commission_base*commission_rate/100,2)
        seller_net=round(commission_base-commission_amount,2)
        if seller_net<0: raise HTTPException(400,"تعذر احتساب صافي مستحقات المستخدم")
        prepared_data["outside_store_sale"]=True
        prepared_data["owner_commission"]={"rate":commission_rate/100,"rate_percent":commission_rate,"base_amount":commission_base,"amount":commission_amount,"seller_net":seller_net,"currency":p.currency,"status":"pending","payment_status":"pending","payment_type":None,"payment_amount":None,"payment_method":None,"payment_reference":None,"payment_proof":None,"payment_submitted_at":None,"paid_at":None,"paid_by":None,"note":"بانتظار إرسال إثبات التحويل وموافقة المالك"}
    consume_operation_verification(s,u,"invoice_create",p.verification_token)
    r=Record(section=p.section,invoice_no=invoice_no,currency=p.currency,data=prepared_data,created_by=u.id)
    s.add(r); s.flush()
    recalculate_inventory(s)
    audit(s,u,"record_created","record",r.id,{"section":r.section,"invoice_no":r.invoice_no,"seller_wallet_credit":0,"seller_wallet_credit_pending":seller_net if employee_sale else 0,"owner_commission":commission_amount if employee_sale else 0,"commission_rate_percent":commission_rate if employee_sale else 0,"owner_confirmation_required":bool(employee_sale),"currency":p.currency},request)
    s.commit()
    # Invalidate shop catalog caches immediately after a stock-changing record.
    if p.section in {"purchase","carPurchase","deposit","directSale","consignSale"}:
        _store_catalog_cache["value"]=None
        _store_catalog_cache["at"]=0
        _public_products_cache["value"].clear()
        _public_products_cache["at"].clear()
    return {"id":r.id,"invoice_no":r.invoice_no,"created_at":r.created_at}
@app.get("/records")
def list_records(section:Optional[str]=None, s:Session=Depends(db), u:User=Depends(require_permission("invoices","view"))):
    q=select(Record).where(Record.deleted==False)
    if u.role!="owner": q=q.where(Record.created_by==u.id,Record.section.not_in(["deposit","consignSale"]))
    if section: q=q.where(Record.section==section)
    rows=s.scalars(q.order_by(Record.id.desc())).all()
    if not rows: return []
    record_ids=[r.id for r in rows]
    payments=s.scalars(
        select(InvoicePayment).where(InvoicePayment.record_id.in_(record_ids)).order_by(InvoicePayment.record_id,InvoicePayment.id)
    ).all()
    payments_by_record={}
    for payment in payments:
        payments_by_record.setdefault(payment.record_id,[]).append(payment)
    out=[]
    for r in rows:
        pays=payments_by_record.get(r.id,[])
        total=float(r.data.get("amount",r.data.get("price",r.data.get("sale",0))) or 0)
        paid=sum(float(x.amount) for x in pays)
        record_data=dict(r.data or {})
        if r.section in {"directSale","carSale"} and isinstance(record_data.get("items"),list):
            enriched_items=[]
            for raw_item in record_data["items"]:
                item=dict(raw_item) if isinstance(raw_item,dict) else raw_item
                if isinstance(item,dict) and str(item.get("store_category") or "") in VEHICLE_CONTRACT_CATEGORIES and not isinstance(item.get("seller_profile_snapshot"),dict):
                    item["seller_profile_snapshot"]=inventory_vehicle_seller_snapshot(s,item,u)
                enriched_items.append(item)
            record_data["items"]=enriched_items
        out.append({"id":r.id,"section":r.section,"invoice_no":r.invoice_no,"currency":r.currency,"data":record_data,"created_by":r.created_by,"created_at":r.created_at,"updated_at":r.updated_at,"payments":[{"id":x.id,"amount":float(x.amount),"method":x.method,"cash_box":x.cash_box,"paid_at":x.paid_at} for x in pays],"paid_total":round(paid,2),"remaining":round(max(total-paid,0),2),"payment_status":"paid" if total>0 and paid>=total else "partial" if paid>0 else "unpaid"})
    return out

@app.get("/sales-summary/mine")
def my_sales_summary(s:Session=Depends(db),u:User=Depends(current_user)):
    # Store sales are attributed from approved online orders by the actual owner
    # and quantity of each user's inventory line, not by the employee who approved it.
    summary={
        "store":{"USD":0.0,"SYP":0.0},
        "outside_store":{"USD":0.0,"SYP":0.0},
    }
    rows=s.scalars(
        select(Record).where(Record.section=="directSale",Record.deleted.is_(False))
    ).all()
    for record in rows:
        data=record.data if isinstance(record.data,dict) else {}
        currency=record.currency if record.currency in ("USD","SYP") else "USD"
        if record.created_by==u.id and data.get("outside_store_sale"):
            commission=data.get("owner_commission") if isinstance(data.get("owner_commission"),dict) else {}
            amount=commission.get("base_amount")
            if amount is None:
                amount=data.get("amount",data.get("price",data.get("sale",0)))
            try:
                summary["outside_store"][currency]=round(summary["outside_store"][currency]+max(0.0,float(amount or 0)),2)
            except (TypeError,ValueError):
                pass
            continue
        if data.get("outside_store_sale"):
            continue
        items=data.get("items") if isinstance(data.get("items"),list) else []
        for item in items:
            if not isinstance(item,dict) or str(item.get("owner_user_id") or "")!=str(u.id):
                continue
            try:
                quantity=max(0.0,float(item.get("user_owned_quantity") or 0))
                price=max(0.0,float(item.get("price") or 0))
                summary["store"][currency]=round(summary["store"][currency]+quantity*price,2)
            except (TypeError,ValueError):
                continue
    return summary

class PaymentPayload(BaseModel):
    amount: float = Field(gt=0)
    method: str
    paid_at: Optional[datetime] = None
    cash_box: str = "صندوق المبيع"
    verification_token: Optional[str] = None

def invoice_cash_description(record:Record, action:str="دفعة فاتورة")->str:
    data=record.data or {}
    section=record.section or ""
    invoice=record.invoice_no or str(record.id)
    section_names={"directSale":"مبيع مباشر","consignSale":"مبيع أمانة","purchase":"شراء","deposit":"وديعة أمانة","repair":"تصليح","carPurchase":"شراء سيارة","carSale":"مبيع سيارة"}
    item_label="المشتريات" if section in {"purchase","carPurchase"} else "المباع" if section in {"directSale","consignSale","carSale"} else "البنود"
    items=data.get("items") if isinstance(data.get("items"),list) else []
    names=[]
    for item in items:
        if not isinstance(item,dict): continue
        name=str(item.get("description") or item.get("model") or item.get("chassis") or "").strip()
        if name:
            qty=item.get("quantity")
            names.append((f"{name} (عدد {qty})" if qty not in (None,"",1,"1") else name))
    if not names:
        fallback=data.get("description") or data.get("details") or data.get("model")
        if fallback: names=[str(fallback).strip()]
        elif data.get("car_make") or data.get("car_model"):
            names=[" ".join(str(data.get(k) or "").strip() for k in ("car_make","car_model","car_year") if data.get(k))]
    parts=[action,section_names.get(section,section)]
    if names: parts.append(item_label+": "+ "، ".join(names))
    party=data.get("customer") or data.get("supplier")
    if party: parts.append(("المورد: " if section in {"purchase","carPurchase"} else "العميل: ")+str(party).strip())
    return " | ".join(x for x in parts if x)

@app.post("/records/{record_id}/payments")
def add_invoice_payment(record_id:int,p:PaymentPayload,request:Request,s:Session=Depends(db),u:User=Depends(require_permission("invoices","create"))):
    r=s.get(Record,record_id)
    if not r or r.deleted or (u.role!="owner" and (r.created_by!=u.id or r.section in {"deposit","consignSale"})): raise HTTPException(404,"الفاتورة غير موجودة")
    if p.method not in {"cash","baraka_bank","sham_cash","syria_gulf"}: raise HTTPException(400,"طريقة الدفع غير صالحة")
    total=float(r.data.get("amount",r.data.get("price",r.data.get("sale",0))) or 0)
    paid=float(s.scalar(select(func.coalesce(func.sum(InvoicePayment.amount),0)).where(InvoicePayment.record_id==record_id)) or 0)
    if round(paid+p.amount,2)>round(total,2): raise HTTPException(400,"مجموع الدفعات يتجاوز إجمالي الفاتورة")
    if not p.cash_box.strip(): raise HTTPException(400,"اختر الصندوق الذي ستدخل إليه الدفعة")
    if u.role!="owner" and p.cash_box.strip() in {"صندوق الأمانة","صندوق مبيع الأمانة","صندوق قل أمانة","صندوق قُل أمانة"}:
        raise HTTPException(403,"لا يمكن لحساب المستخدم تسجيل دفعة في صندوق الأمانة")
    consume_operation_verification(s,u,"invoice_payment",p.verification_token)
    x=InvoicePayment(record_id=record_id,amount=p.amount,method=p.method,cash_box=p.cash_box,paid_at=p.paid_at or datetime.now(timezone.utc),created_by=u.id)
    s.add(x); s.flush()
    movement="withdrawal" if r.section in {"purchase","carPurchase","deposit"} else "deposit"
    if movement=="withdrawal": ensure_cash_balance(s,p.cash_box,r.currency,p.amount)
    s.add(CashMove(box_name=p.cash_box,movement=movement,amount=p.amount,currency=r.currency,description=invoice_cash_description(r,"قبض" if movement=="deposit" else "صرف"),created_by=u.id,record_id=r.id))
    audit(s,u,"invoice_payment_created","invoice_payment",x.id,{"record_id":record_id,"amount":p.amount,"method":p.method,"cash_box":p.cash_box,"cash_movement":movement},request); s.commit()
    return {"id":x.id,"record_id":record_id,"amount":float(x.amount),"method":x.method,"cash_box":x.cash_box,"paid_at":x.paid_at}

@app.get("/records/{record_id}/payments")
def list_invoice_payments(record_id:int,s:Session=Depends(db),u:User=Depends(require_permission("invoices","view"))):
    r=s.get(Record,record_id)
    if not r or r.deleted or (u.role!="owner" and (r.created_by!=u.id or r.section in {"deposit","consignSale"})): raise HTTPException(404,"الفاتورة غير موجودة")
    trust_boxes={"صندوق الأمانة","صندوق مبيع الأمانة","صندوق قل أمانة","صندوق قُل أمانة"}
    return [{"id":x.id,"amount":float(x.amount),"method":x.method,"cash_box":(x.cash_box if u.role=="owner" or x.cash_box not in trust_boxes else "صندوق المبيع"),"paid_at":x.paid_at} for x in s.scalars(select(InvoicePayment).where(InvoicePayment.record_id==record_id).order_by(InvoicePayment.id)).all()]

class PaymentUpdatePayload(BaseModel):
    amount: float = Field(gt=0)
    method: str
    paid_at: Optional[datetime] = None
    cash_box: str

def reverse_payment_cash_move(s:Session, r:Record, payment:InvoicePayment, u:User, reason:str):
    movement="withdrawal" if r.section in {"purchase","carPurchase","deposit"} else "deposit"
    reverse="deposit" if movement=="withdrawal" else "withdrawal"
    if reverse=="withdrawal": ensure_cash_balance(s,payment.cash_box,r.currency,float(payment.amount))
    s.add(CashMove(box_name=payment.cash_box,movement=reverse,amount=payment.amount,currency=r.currency,description=invoice_cash_description(r,f"تسوية عكسية للدفعة {payment.id} ({reason})"),created_by=u.id,record_id=r.id))

@app.put("/records/{record_id}/payments/{payment_id}")
def update_invoice_payment(record_id:int,payment_id:int,p:PaymentUpdatePayload,request:Request,s:Session=Depends(db),u:User=Depends(require_permission("invoices","edit"))):
    if u.role!="owner": raise HTTPException(403,"تعديل الدفعات المسجلة متاح للمالك فقط")
    r=s.get(Record,record_id); x=s.get(InvoicePayment,payment_id)
    if not r or r.deleted or (u.role!="owner" and (r.created_by!=u.id or r.section in {"deposit","consignSale"})) or not x or x.record_id!=record_id: raise HTTPException(404,"الدفعة غير موجودة")
    if p.method not in {"cash","baraka_bank","sham_cash","syria_gulf"}: raise HTTPException(400,"طريقة الدفع غير صالحة")
    if not p.cash_box.strip(): raise HTTPException(400,"اختر الصندوق")
    trust_boxes={"صندوق الأمانة","صندوق مبيع الأمانة","صندوق قل أمانة","صندوق قُل أمانة"}
    if u.role!="owner" and (p.cash_box.strip() in trust_boxes or x.cash_box in trust_boxes):
        raise HTTPException(403,"لا يمكن لحساب المستخدم تعديل دفعة مرتبطة بصندوق الأمانة")
    paid=float(s.scalar(select(func.coalesce(func.sum(InvoicePayment.amount),0)).where(InvoicePayment.record_id==record_id)) or 0)
    total=float(r.data.get("amount",r.data.get("price",r.data.get("sale",0))) or 0)
    if round(paid-float(x.amount)+p.amount,2)>round(total,2): raise HTTPException(400,"مجموع الدفعات بعد التعديل يتجاوز إجمالي الفاتورة")
    changed=(round(float(x.amount),2)!=round(p.amount,2) or x.method!=p.method or x.cash_box!=p.cash_box or (p.paid_at and x.paid_at!=p.paid_at))
    if not changed: return {"ok":True,"unchanged":True}
    reverse_payment_cash_move(s,r,x,u,"تعديل")
    movement="withdrawal" if r.section in {"purchase","carPurchase","deposit"} else "deposit"
    if movement=="withdrawal": ensure_cash_balance(s,p.cash_box,r.currency,p.amount)
    s.add(CashMove(box_name=p.cash_box,movement=movement,amount=p.amount,currency=r.currency,description=invoice_cash_description(r,f"تسجيل بديل للدفعة {x.id}"),created_by=u.id,record_id=r.id))
    old={"amount":float(x.amount),"method":x.method,"cash_box":x.cash_box,"paid_at":str(x.paid_at)}
    x.amount=p.amount; x.method=p.method; x.cash_box=p.cash_box
    if p.paid_at: x.paid_at=p.paid_at
    audit(s,u,"invoice_payment_updated","invoice_payment",x.id,{"record_id":record_id,"old":old,"new":{"amount":p.amount,"method":p.method,"cash_box":p.cash_box,"paid_at":str(x.paid_at)},"cash_adjustment":"automatic_reversal_and_replacement"},request)
    s.commit()
    return {"ok":True,"id":x.id}

@app.delete("/records/{record_id}/payments/{payment_id}")
def delete_invoice_payment(record_id:int,payment_id:int,request:Request,s:Session=Depends(db),u:User=Depends(require_permission("invoices","delete"))):
    if u.role!="owner": raise HTTPException(403,"حذف الدفعات المسجلة متاح للمالك فقط")
    r=s.get(Record,record_id); x=s.get(InvoicePayment,payment_id)
    if not r or r.deleted or (u.role!="owner" and (r.created_by!=u.id or r.section in {"deposit","consignSale"})) or not x or x.record_id!=record_id: raise HTTPException(404,"الدفعة غير موجودة")
    if u.role!="owner" and x.cash_box in {"صندوق الأمانة","صندوق مبيع الأمانة","صندوق قل أمانة","صندوق قُل أمانة"}:
        raise HTTPException(403,"لا يمكن لحساب المستخدم حذف دفعة مرتبطة بصندوق الأمانة")
    reverse_payment_cash_move(s,r,x,u,"حذف")
    audit(s,u,"invoice_payment_deleted","invoice_payment",x.id,{"record_id":record_id,"amount":float(x.amount),"method":x.method,"cash_box":x.cash_box,"cash_adjustment":"automatic_reversal"},request)
    s.delete(x); s.commit()
    return {"ok":True}

class ChangePayload(BaseModel): action:str; proposed_data:Optional[dict]=None; reason:str=Field(min_length=3)
@app.post("/records/{record_id}/change-requests")
def request_change(record_id:int,p:ChangePayload,request:Request,s:Session=Depends(db),u:User=Depends(current_user)):
    if p.action not in ("update","delete"): raise HTTPException(400,"نوع الطلب غير صالح")
    needed="edit" if p.action=="update" else "delete"
    if not has_permission(u,"invoices",needed): raise HTTPException(403,"ليست لديك صلاحية طلب هذا الإجراء")
    record=s.get(Record,record_id)
    if not record or record.deleted or (u.role!="owner" and (record.created_by!=u.id or record.section in {"deposit","consignSale"})): raise HTTPException(404,"السجل غير موجود")
    if p.action=="update" and p.proposed_data is None: raise HTTPException(400,"البيانات المقترحة مطلوبة")
    cr=ChangeRequest(record_id=record_id,requested_by=u.id,action=p.action,proposed_data=p.proposed_data,reason=p.reason)
    s.add(cr); s.flush(); audit(s,u,"change_requested","record",record_id,{"request_id":cr.id,"action":p.action},request); s.commit(); return {"request_id":cr.id,"status":"pending"}
@app.get("/change-requests")
def requests(s:Session=Depends(db),_:User=Depends(manager)):
    rows=s.scalars(select(ChangeRequest).order_by(ChangeRequest.id.desc()).limit(200)).all()
    out=[]
    for x in rows:
        rec=s.get(Record,x.record_id); requester=s.get(User,x.requested_by)
        out.append({"id":x.id,"record_id":x.record_id,"section":rec.section if rec else None,"invoice_no":rec.invoice_no if rec else None,"requested_by":x.requested_by,"requester_name":requester.full_name if requester else "—","action":x.action,"proposed_data":x.proposed_data,"reason":x.reason,"status":x.status,"created_at":x.created_at})
    return out
def ensure_total_covers_payments(s:Session, record_id:int, new_data:dict):
    total=float(new_data.get("amount",new_data.get("price",new_data.get("sale",0))) or 0)
    paid=float(s.scalar(select(func.coalesce(func.sum(InvoicePayment.amount),0)).where(InvoicePayment.record_id==record_id)) or 0)
    if round(total,2)<round(paid,2):
        raise HTTPException(400,"لا يمكن تخفيض إجمالي الفاتورة إلى أقل من مجموع الدفعات المسجلة")

@app.post("/change-requests/{request_id}/approve")
def approve(request_id:int,approve:bool,request:Request,s:Session=Depends(db),u:User=Depends(manager)):
    cr=s.get(ChangeRequest,request_id)
    if not cr or cr.status!="pending": raise HTTPException(404,"الطلب غير موجود أو تمت معالجته")
    if approve and cr.action not in {"update","delete"}: raise HTTPException(400,"نوع الطلب غير صالح")
    cr.status="approved" if approve else "rejected"
    cr.reviewed_by=u.id; cr.reviewed_at=datetime.now(timezone.utc)
    audit(s,u,"change_request_"+cr.status,"record",cr.record_id,{"request_id":cr.id,"action":cr.action},request)
    s.commit()
    return {"status":cr.status}

class ApprovedChangeApplyPayload(BaseModel):
    data: Optional[dict] = None
    currency: Optional[str] = None
@app.post("/change-requests/{request_id}/apply")
def apply_approved_change(request_id:int,p:ApprovedChangeApplyPayload,request:Request,s:Session=Depends(db),u:User=Depends(current_user)):
    cr=s.get(ChangeRequest,request_id)
    if cr and not has_permission(u,"invoices","edit" if cr.action=="update" else "delete"):
        raise HTTPException(403,"ليست لديك صلاحية تنفيذ هذا التعديل أو الحذف")
    if not cr or cr.requested_by!=u.id or cr.status!="approved":
        raise HTTPException(403,"لا يوجد طلب موافق عليه ومتاح لهذا الحساب")
    rec=s.get(Record,cr.record_id)
    if not rec or rec.deleted: raise HTTPException(404,"السجل غير موجود")
    if cr.action=="update":
        if p.data is None: raise HTTPException(400,"بيانات التعديل مطلوبة")
        currency=p.currency or rec.currency
        if currency not in {"USD","SYP"}: raise HTTPException(400,"عملة غير مدعومة")
        if currency!=rec.currency and s.scalar(select(func.count(InvoicePayment.id)).where(InvoicePayment.record_id==rec.id)):
            raise HTTPException(409,"لا يمكن تغيير عملة الفاتورة بعد تسجيل دفعات؛ احذف الدفعات أو سوّها أولاً")
        ensure_total_covers_payments(s,rec.id,p.data)
        rec.data=prepare_record_inventory(s,rec.section,p.data,allow_legacy=True); rec.currency=currency; rec.updated_at=datetime.now(timezone.utc)
        recalculate_inventory(s)
    elif cr.action=="delete":
        if (rec.data or {}).get("outside_store_sale") and ((rec.data or {}).get("owner_commission") or {}).get("status")=="paid":
            raise HTTPException(409,"لا يمكن حذف هذه الفاتورة لأن عمولة المالك سُدّدت وأُضيفت إلى محفظته")
        related_cash_moves={m.id:m for m in (sale_cash_moves_for_record(s,rec)+s.scalars(select(CashMove).where(CashMove.record_id==rec.id)).all())}
        ensure_cash_reversal_safe(s,list(related_cash_moves.values()))
        rec.deleted=True; rec.updated_at=datetime.now(timezone.utc)
        recalculate_inventory(s)
        for payment in s.scalars(select(InvoicePayment).where(InvoicePayment.record_id==rec.id)).all(): s.delete(payment)
        for cash_move in sale_cash_moves_for_record(s,rec): s.delete(cash_move)
        for cash_move in s.scalars(select(CashMove).where(CashMove.record_id==rec.id)).all(): s.delete(cash_move)
    else: raise HTTPException(400,"نوع الطلب غير صالح")
    cr.status="completed"
    audit(s,u,"change_request_completed","record",rec.id,{"request_id":cr.id,"action":cr.action},request)
    s.commit()
    return {"ok":True,"status":"completed"}
class CashPayload(BaseModel): box_name:str; movement:str; amount:float=Field(gt=0); currency:str="USD"; description:str=""; verification_token:Optional[str]=None
class CashTransferPayload(BaseModel):
    source_box:str
    destination_box:str
    amount:float=Field(gt=0)
    currency:str="USD"
    description:str=""
    verification_token:Optional[str]=None
def ensure_cash_balance(s:Session, box_name:str, currency:str, amount:float):
    # Serialize all withdrawals/transfers for the same box and currency.
    s.execute(select(func.pg_advisory_xact_lock(func.hashtext(box_name),func.hashtext(currency))))
    rows=s.scalars(select(CashMove).where(CashMove.box_name==box_name,CashMove.currency==currency,CashMove.voided.is_(False))).all()
    balance=sum((1 if x.movement in ("deposit","transfer_in") else -1)*float(x.amount) for x in rows)
    if round(balance,2)<round(float(amount),2):
        raise HTTPException(400,f"رصيد الصندوق غير كافٍ. الرصيد المتاح: {balance:.2f} {currency}")
    return balance

def is_sale_cash_move(s:Session, move:CashMove)->bool:
    # Protect sale proceeds by explicit record linkage; also recognize legacy sale-payment rows.
    if move.record_id:
        rec=s.get(Record,move.record_id)
        if rec and rec.section in {"directSale","consignSale","carSale"}:
            return True
    if move.movement not in {"deposit","transfer_in"}:
        return False
    legacy=s.scalars(select(Record).where(
        Record.section.in_(["directSale","consignSale","carSale"]),
        Record.deleted.is_(False)
    )).all()
    desc=(move.description or "")
    return any((r.invoice_no and r.invoice_no in desc) or
               (("فاتورة "+str(r.id)) in desc) for r in legacy)

def is_purchase_cash_move(s:Session, move:CashMove)->bool:
    if move.movement not in {"withdrawal","transfer_out"}:
        return False
    if move.record_id:
        rec=s.get(Record,move.record_id)
        if rec and rec.section in {"purchase","carPurchase"}:
            return True
    desc=move.description or ""
    legacy=s.scalars(select(Record).where(
        Record.section.in_(["purchase","carPurchase"]),
        Record.deleted.is_(False)
    )).all()
    return any((r.invoice_no and r.invoice_no in desc) or
               (("فاتورة "+str(r.id)) in desc) for r in legacy)

def ensure_cash_reversal_safe(s:Session, moves:list[CashMove]):
    active=[m for m in moves if not m.voided]
    if not active: return
    ids=[m.id for m in active]
    keys=sorted({(m.box_name,m.currency) for m in active})
    for box_name,currency in keys:
        s.execute(select(func.pg_advisory_xact_lock(func.hashtext(box_name),func.hashtext(currency))))
        rows=s.scalars(select(CashMove).where(CashMove.box_name==box_name,CashMove.currency==currency,CashMove.voided.is_(False),CashMove.id.not_in(ids))).all()
        balance=sum((1 if x.movement in ("deposit","transfer_in") else -1)*float(x.amount) for x in rows)
        if round(balance,2)<0:
            raise HTTPException(400,f"لا يمكن إلغاء أو حذف هذه العملية لأن ذلك سيجعل رصيد {box_name} بالسالب ({balance:.2f} {currency})")

@app.post("/cash-movements")
def cash_move(p:CashPayload,request:Request,s:Session=Depends(db),u:User=Depends(require_permission("cash","create"))):
    if u.role!="owner" and p.box_name.strip() in {"صندوق الأمانة","صندوق مبيع الأمانة","صندوق قل أمانة","صندوق قُل أمانة"}:
        raise HTTPException(403,"صندوق الأمانة متاح للمالك فقط")
    if p.movement not in ("deposit","withdrawal"): raise HTTPException(400,"اختر إيداعاً أو سحباً؛ التحويل بين الصناديق له عملية مستقلة")
    if p.currency not in ("USD","SYP"): raise HTTPException(400,"عملة غير مدعومة")
    if p.movement=="withdrawal": ensure_cash_balance(s,p.box_name,p.currency,p.amount)
    consume_operation_verification(s,u,"cash_movement",p.verification_token)
    m=CashMove(**p.model_dump(exclude={"verification_token"}),created_by=u.id); s.add(m); s.flush(); audit(s,u,"cash_movement_created","cash",m.id,{"box":p.box_name,"movement":p.movement,"amount":p.amount,"currency":p.currency},request); s.commit(); return {"id":m.id}
@app.post("/cash-transfers")
def cash_transfer(p:CashTransferPayload,request:Request,s:Session=Depends(db),u:User=Depends(require_permission("cash","create"))):
    trust_boxes={"صندوق الأمانة","صندوق مبيع الأمانة","صندوق قل أمانة","صندوق قُل أمانة"}
    if u.role!="owner" and ({p.source_box.strip(),p.destination_box.strip()} & trust_boxes):
        raise HTTPException(403,"التحويل من صندوق الأمانة أو إليه متاح للمالك فقط")
    if p.source_box==p.destination_box: raise HTTPException(400,"يجب اختيار صندوقين مختلفين")
    if p.currency not in ("USD","SYP"): raise HTTPException(400,"عملة غير مدعومة")
    ensure_cash_balance(s,p.source_box,p.currency,p.amount)
    consume_operation_verification(s,u,"cash_transfer",p.verification_token)
    import uuid
    group=str(uuid.uuid4())
    source=CashMove(box_name=p.source_box,movement="withdrawal",amount=p.amount,currency=p.currency,description=("تحويل إلى "+p.destination_box+" · "+p.description).strip(" ·"),created_by=u.id,transfer_group=group)
    dest=CashMove(box_name=p.destination_box,movement="deposit",amount=p.amount,currency=p.currency,description=("تحويل من "+p.source_box+" · "+p.description).strip(" ·"),created_by=u.id,transfer_group=group)
    s.add_all([source,dest]); s.flush()
    audit(s,u,"cash_transfer_created","cash_transfer",source.id,{"transfer_group":group,"from":p.source_box,"to":p.destination_box,"amount":p.amount,"currency":p.currency},request)
    s.commit()
    return {"ok":True,"transfer_group":group,"source_movement_id":source.id,"destination_movement_id":dest.id}

def cash_move_display_description(s:Session, move:CashMove)->str:
    record=s.get(Record,move.record_id) if move.record_id else None
    if not record and move.description:
        candidates=s.scalars(select(Record).where(Record.deleted.is_(False))).all()
        record=next((r for r in candidates if r.invoice_no and r.invoice_no in move.description),None)
    if record and not record.deleted:
        action="قبض" if move.movement in {"deposit","transfer_in"} else "صرف" if move.movement in {"withdrawal","transfer_out"} else "حركة"
        return invoice_cash_description(record,action)
    return move.description or ""

@app.get("/cash-boxes/{box_name}/movements")
def cash_box_movements(box_name:str,s:Session=Depends(db),u:User=Depends(require_permission("cash","view"))):
    if u.role!="owner" and box_name.strip() in {"صندوق الأمانة","صندوق مبيع الأمانة","صندوق قل أمانة","صندوق قُل أمانة"}:
        raise HTTPException(403,"حركات صندوق الأمانة متاحة للمالك فقط")
    rows=s.scalars(select(CashMove).where(CashMove.box_name==box_name,CashMove.voided.is_(False)).order_by(CashMove.id.desc())).all()
    return [{"id":m.id,"box_name":m.box_name,"movement":m.movement,"amount":float(m.amount),"currency":m.currency,"description":cash_move_display_description(s,m),"created_by":m.created_by,"created_at":m.created_at,"transfer_group":m.transfer_group,"voided":m.voided,"voided_by":m.voided_by,"voided_at":m.voided_at,"sale_locked":is_sale_cash_move(s,m),"purchase_locked":is_purchase_cash_move(s,m)} for m in rows]

@app.get("/cash-movements")
def cash_list(s:Session=Depends(db),u:User=Depends(require_permission("cash","view"))):
    query=select(CashMove).where(CashMove.voided.is_(False))
    if u.role!="owner": query=query.where(CashMove.box_name.not_in(["صندوق الأمانة","صندوق مبيع الأمانة","صندوق قل أمانة","صندوق قُل أمانة"]))
    rows=s.scalars(query.order_by(CashMove.id.desc())).all()
    return [{"id":m.id,"box_name":m.box_name,"movement":m.movement,"amount":float(m.amount),"currency":m.currency,"description":cash_move_display_description(s,m),"created_by":m.created_by,"created_at":m.created_at,"transfer_group":m.transfer_group,"voided":m.voided,"voided_by":m.voided_by,"voided_at":m.voided_at,"sale_locked":is_sale_cash_move(s,m),"purchase_locked":is_purchase_cash_move(s,m)} for m in rows]

@app.patch("/cash-movements/{move_id}/void")
def void_cash_movement(move_id:int,request:Request,s:Session=Depends(db),u:User=Depends(require_permission("cash","edit"))):
    if u.role!="owner": raise HTTPException(403,"إلغاء حركات الصندوق متاح للمالك فقط")
    move=s.get(CashMove,move_id)
    if not move: raise HTTPException(404,"حركة الصندوق غير موجودة")
    if u.role!="owner" and move.box_name in {"صندوق الأمانة","صندوق مبيع الأمانة","صندوق قل أمانة","صندوق قُل أمانة"}:
        raise HTTPException(403,"حركات صندوق الأمانة متاحة للمالك فقط")
    if is_sale_cash_move(s,move): raise HTTPException(403,"واردات المبيعات مرتبطة بالبيعة ولا يمكن إلغاؤها أو حذفها منفردة")
    if is_purchase_cash_move(s,move): raise HTTPException(403,"مبالغ الشراء مرتبطة بفاتورة الشراء ولا يمكن إلغاؤها من الصندوق منفردة")
    if move.voided: raise HTTPException(400,"هذه الحركة ملغاة مسبقاً")
    related=[move]
    if move.transfer_group:
        related=s.scalars(select(CashMove).where(CashMove.transfer_group==move.transfer_group,CashMove.voided.is_(False))).all()
    ensure_cash_reversal_safe(s,related)
    now=datetime.now(timezone.utc)
    for item in related:
        item.voided=True; item.voided_by=u.id; item.voided_at=now
    audit(s,u,"cash_movement_voided","cash",move.id,{"movement_ids":[x.id for x in related],"transfer_group":move.transfer_group,"box":move.box_name,"movement":move.movement,"amount":float(move.amount),"currency":move.currency},request)
    s.commit(); return {"ok":True,"voided_ids":[x.id for x in related]}

@app.delete("/cash-movements/{move_id}")
def delete_cash_movement(move_id:int,request:Request,s:Session=Depends(db),u:User=Depends(require_permission("cash","delete"))):
    if u.role!="owner": raise HTTPException(403,"حذف حركات الصندوق متاح للمالك فقط")
    move=s.get(CashMove,move_id)
    if not move: raise HTTPException(404,"حركة الصندوق غير موجودة")
    if u.role!="owner" and move.box_name in {"صندوق الأمانة","صندوق مبيع الأمانة","صندوق قل أمانة","صندوق قُل أمانة"}:
        raise HTTPException(403,"حركات صندوق الأمانة متاحة للمالك فقط")
    if is_sale_cash_move(s,move): raise HTTPException(403,"لا يمكن حذف واردات المبيعات منفردة؛ احذف البيعة كاملة")
    if is_purchase_cash_move(s,move): raise HTTPException(403,"مبالغ الشراء مرتبطة بفاتورة الشراء ولا يمكن حذفها من الصندوق منفردة")
    related=[move]
    if move.transfer_group:
        related=s.scalars(select(CashMove).where(CashMove.transfer_group==move.transfer_group)).all()
    ensure_cash_reversal_safe(s,related)
    details={"movement_ids":[x.id for x in related],"transfer_group":move.transfer_group,"box":move.box_name,"movement":move.movement,"amount":float(move.amount),"currency":move.currency,"permanent":True}
    audit(s,u,"cash_movement_permanently_deleted","cash",move.id,details,request)
    for item in related: s.delete(item)
    s.commit(); return {"ok":True,"deleted_ids":details["movement_ids"]}
class OwnerCommissionConfirmPayload(BaseModel):
    note: str = ""

class OutsideStorePaymentPayload(BaseModel):
    method: str
    payment_type: str = "full_amount"
    reference: str = Field(default="",max_length=160)
    proof_image: str = Field(default="",max_length=4200000)

@app.get("/outside-store-sales/mine")
def my_outside_store_sales(s:Session=Depends(db),u:User=Depends(current_user)):
    rows=s.scalars(select(Record).where(Record.created_by==u.id,Record.deleted.is_(False),Record.section=="directSale").order_by(Record.id.desc())).all()
    return [{"id":r.id,"invoice_no":r.invoice_no,"currency":r.currency,"created_at":r.created_at,"commission":(r.data or {}).get("owner_commission"),"items":(r.data or {}).get("items",[])} for r in rows if (r.data or {}).get("outside_store_sale")]

@app.get("/outside-store-sales/pending")
def pending_outside_store_sales(s:Session=Depends(db),u:User=Depends(manager)):
    rows=s.scalars(select(Record).where(Record.deleted.is_(False),Record.section=="directSale").order_by(Record.id.desc())).all()
    out=[]
    for r in rows:
        data=r.data if isinstance(r.data,dict) else {}
        commission=data.get("owner_commission") or {}
        if data.get("outside_store_sale") and commission.get("status")!="paid":
            seller=s.get(User,r.created_by)
            out.append({"id":r.id,"invoice_no":r.invoice_no,"currency":r.currency,"created_at":r.created_at,"seller":seller.full_name if seller else "—","username":seller.username if seller else "—","commission":commission,"items":data.get("items",[])})
    return out

@app.post("/outside-store-sales/{record_id}/submit-payment")
def submit_outside_store_payment(record_id:int,p:OutsideStorePaymentPayload,request:Request,s:Session=Depends(db),u:User=Depends(current_user)):
    if p.method not in {"baraka_bank","sham_cash","syria_gulf"}:
        raise HTTPException(400,"طريقة الدفع غير مدعومة")
    payment_reference=p.reference.strip()
    proof_image=(p.proof_image or "").strip()
    if payment_reference and len(payment_reference)<3:
        raise HTTPException(400,"مرجع التحويل غير صالح")
    if not payment_reference and not proof_image:
        raise HTTPException(400,"أدخل رقم مرجع التحويل أو أرفق صورة إثبات الدفع")
    if proof_image:
        match=re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/]+={0,2})",proof_image)
        if not match: raise HTTPException(400,"صيغة صورة الإثبات غير مدعومة")
        try: image_bytes=base64.b64decode(match.group(2),validate=True)
        except (ValueError,binascii.Error): raise HTTPException(400,"ملف صورة الإثبات غير صالح")
        if not image_bytes or len(image_bytes)>3*1024*1024: raise HTTPException(400,"يجب ألا يتجاوز حجم صورة الإثبات 3 ميغابايت")
    record=s.scalar(select(Record).where(Record.id==record_id).with_for_update())
    if not record or record.deleted or record.created_by!=u.id or record.section!="directSale" or not (record.data or {}).get("outside_store_sale"):
        raise HTTPException(404,"عملية البيع خارج المتجر غير موجودة")
    data=dict(record.data or {})
    commission=dict(data.get("owner_commission") or {})
    if commission.get("status")=="paid":
        raise HTTPException(409,"تم تأكيد الدفع لهذه العملية مسبقاً")
    if commission.get("payment_status")=="submitted":
        raise HTTPException(409,"تم إرسال بيانات الدفع بالفعل، وهي بانتظار مراجعة المالك")
    if p.payment_type not in {"full_amount","commission_only"}:
        raise HTTPException(400,"نوع التحويل غير مدعوم")
    transfer_amount=round(float(commission.get("base_amount") or 0),2) if p.payment_type=="full_amount" else round(float(commission.get("amount") or 0),2)
    if transfer_amount<=0:
        raise HTTPException(409,"قيمة التحويل غير صالحة")
    commission.update({"payment_status":"submitted","payment_type":p.payment_type,"payment_amount":transfer_amount,"payment_method":p.method,"payment_reference":payment_reference or None,"payment_proof":proof_image or None,"payment_submitted_at":datetime.now(timezone.utc).isoformat()})
    data["owner_commission"]=commission
    record.data=data
    record.updated_at=datetime.now(timezone.utc)
    audit(s,u,"outside_store_commission_payment_submitted","record",record.id,{"invoice_no":record.invoice_no,"amount":commission.get("amount"),"transfer_amount":transfer_amount,"payment_type":p.payment_type,"currency":record.currency,"method":p.method,"reference":payment_reference,"proof_attached":bool(proof_image)},request)
    s.commit()
    owners=s.scalars(select(User).where(User.role=="owner",User.deleted.is_(False),User.active.is_(True),User.email.is_not(None))).all()
    seller_name=u.full_name or u.username
    transfer_label="كامل سعر القطعة" if p.payment_type=="full_amount" else "عمولة البائع 1.5٪ فقط"
    subject="AIB: طلب تأكيد تحويل خارج المتجر"
    body="تم إرسال طلب تأكيد تحويل خارج المتجر.\nالمستخدم: "+str(seller_name)+"\nالفاتورة: "+str(record.invoice_no or record.id)+"\nنوع التحويل: "+transfer_label+"\nالمبلغ المحوّل: "+str(transfer_amount)+" "+str(record.currency)+"\nعمولة البائع: "+str(commission.get("amount"))+" "+str(record.currency)+"\nيرجى فتح صفحة المخزون في تطبيق AIB ومراجعة إثبات التحويل."
    email_html=aib_email_html("طلب تأكيد تحويل خارج المتجر","أرسل أحد المستخدمين بيانات تحويل جديدة، وتحتاج إلى مراجعة الإثبات وتأكيد وصول المبلغ.",[("المستخدم",seller_name),("الفاتورة",record.invoice_no or record.id),("نوع التحويل",transfer_label),("المبلغ المحوّل",str(transfer_amount)+" "+str(record.currency)),("عمولة البائع 1.5٪",str(commission.get("amount"))+" "+str(record.currency))],accent="#d97706",note="يرجى التحقق من وصول المبلغ فعلياً قبل تأكيد العملية.")
    for owner in owners:
        if owner.email:
            send_notification_email(owner.email,subject,body,email_html)
    return {"ok":True,"payment_status":"submitted","owner_notifications_sent":len([o for o in owners if o.email])}

@app.post("/outside-store-sales/{record_id}/reject-payment")
def reject_outside_store_payment(record_id:int,p:OwnerCommissionConfirmPayload,request:Request,s:Session=Depends(db),u:User=Depends(manager)):
    record=s.scalar(select(Record).where(Record.id==record_id).with_for_update())
    if not record or record.deleted or record.section!="directSale" or not (record.data or {}).get("outside_store_sale"):
        raise HTTPException(404,"عملية البيع خارج المتجر غير موجودة")
    data=dict(record.data or {})
    commission=dict(data.get("owner_commission") or {})
    if commission.get("status")=="paid" or commission.get("payment_status")=="confirmed":
        raise HTTPException(409,"لا يمكن رفض دفعة تم تأكيدها مسبقاً")
    if commission.get("payment_status")!="submitted":
        raise HTTPException(409,"لا يوجد طلب تحويل مرسل بانتظار المراجعة")
    now=datetime.now(timezone.utc)
    note=p.note.strip()[:500]
    commission.update({"payment_status":"rejected","rejected_at":now.isoformat(),"rejected_by":u.id,"rejection_note":note})
    data["owner_commission"]=commission
    record.data=data
    record.updated_at=now
    audit(s,u,"owner_commission_payment_rejected","record",record.id,{"invoice_no":record.invoice_no,"payment_type":commission.get("payment_type"),"payment_amount":commission.get("payment_amount"),"currency":record.currency,"payment_method":commission.get("payment_method"),"payment_reference":commission.get("payment_reference"),"note":note},request)
    s.commit()
    return {"ok":True,"record_id":record.id,"payment_status":"rejected","note":note}

@app.post("/outside-store-sales/{record_id}/confirm-commission")
def confirm_outside_store_commission(record_id:int,p:OwnerCommissionConfirmPayload,request:Request,s:Session=Depends(db),u:User=Depends(manager)):
    record=s.scalar(select(Record).where(Record.id==record_id).with_for_update())
    if not record or record.deleted or record.section!="directSale" or not (record.data or {}).get("outside_store_sale"):
        raise HTTPException(404,"عملية البيع خارج المتجر غير موجودة")
    data=dict(record.data or {})
    commission=dict(data.get("owner_commission") or {})
    if commission.get("status")=="paid":
        raise HTTPException(409,"تم تأكيد تسديد عمولة هذه الفاتورة مسبقاً")
    if commission.get("payment_status")!="submitted" or not (commission.get("payment_reference") or commission.get("payment_proof")):
        raise HTTPException(409,"لا يمكن تأكيد الدفعة قبل أن يرسل المستخدم بيانات التحويل")
    amount=round(float(commission.get("amount") or 0),2)
    seller_net=round(float(commission.get("seller_net") or 0),2)
    if amount<=0 or seller_net<0: raise HTTPException(409,"قيمة العمولة أو مستحقات المستخدم غير صالحة")
    seller=s.get(User,record.created_by)
    if not seller or seller.deleted: raise HTTPException(409,"حساب المستخدم صاحب عملية البيع غير متاح")
    ensure_user_wallets(s,u.id)
    ensure_user_wallets(s,seller.id)
    owner_wallet=s.scalar(select(UserWallet).where(UserWallet.user_id==u.id,UserWallet.currency==record.currency).with_for_update())
    payment_type=commission.get("payment_type") or "commission_only"
    seller_wallet=None
    if payment_type=="full_amount":
        ensure_user_wallets(s,seller.id)
        seller_wallet=s.scalar(select(UserWallet).where(UserWallet.user_id==seller.id,UserWallet.currency==record.currency).with_for_update())
    if not owner_wallet or (payment_type=="full_amount" and not seller_wallet): raise HTTPException(500,"تعذر تجهيز المحافظ بعملة الفاتورة")
    now=datetime.now(timezone.utc)
    owner_wallet.balance=float(owner_wallet.balance or 0)+amount
    owner_wallet.updated_at=now
    owner_tx=WalletTransaction(wallet_id=owner_wallet.id,user_id=u.id,amount=amount,currency=record.currency,direction="in",reason="عمولة بيع خارج المتجر · "+str(record.invoice_no or record.id),reference_type="outside_store_commission",reference_id=record.id,created_by=u.id)
    seller_tx=None
    if payment_type=="full_amount":
        seller_wallet.balance=float(seller_wallet.balance or 0)+seller_net
        seller_wallet.updated_at=now
        seller_tx=WalletTransaction(wallet_id=seller_wallet.id,user_id=seller.id,amount=seller_net,currency=record.currency,direction="in",reason="صافي مستحق بيع خارج المتجر بعد تحويل كامل سعر القطعة · "+str(record.invoice_no or record.id),reference_type="outside_store_sale_net",reference_id=record.id,created_by=u.id)
        s.add(seller_tx)
    s.add(owner_tx);s.flush()
    commission.update({"status":"paid","payment_status":"confirmed","paid_at":now.isoformat(),"paid_by":u.id,"note":p.note.strip()[:500],"wallet_transaction_id":owner_tx.id,"seller_wallet_transaction_id":seller_tx.id if seller_tx else None})
    data["owner_commission"]=commission
    data["seller_wallet_credit"]={"amount":seller_net if payment_type=="full_amount" else 0,"currency":record.currency,"wallet_transaction_id":seller_tx.id if seller_tx else None,"reason":"full_amount_transferred" if payment_type=="full_amount" else "commission_only_no_seller_credit"}
    record.data=data
    record.updated_at=now
    audit(s,u,"owner_commission_payment_confirmed","record",record.id,{"invoice_no":record.invoice_no,"commission_amount":amount,"seller_net":seller_net if payment_type=="full_amount" else 0,"payment_type":payment_type,"payment_amount":commission.get("payment_amount"),"currency":record.currency,"rate":float(commission.get("rate") or 0),"rate_percent":float(commission.get("rate_percent") or 0),"seller_id":seller.id,"owner_wallet_id":owner_wallet.id,"seller_wallet_id":seller_wallet.id if seller_wallet else None,"owner_wallet_transaction_id":owner_tx.id,"seller_wallet_transaction_id":seller_tx.id if seller_tx else None,"payment_method":commission.get("payment_method"),"payment_reference":commission.get("payment_reference"),"note":commission["note"]},request)
    s.commit()
    return {"ok":True,"record_id":record.id,"status":"paid","seller_credit":seller_net if payment_type=="full_amount" else 0,"payment_type":payment_type,"amount":amount,"currency":record.currency}

@app.post("/audit-log/print")
def audit_invoice_print(request:Request, record_id:int, invoice_no:str="", section:str="", s:Session=Depends(db), u:User=Depends(require_permission("invoices","print"))):
    record=s.get(Record,record_id)
    if not record or record.deleted or (u.role!="owner" and (record.created_by!=u.id or record.section in {"deposit","consignSale"})): raise HTTPException(404,"الفاتورة غير موجودة أو لا تملك صلاحية طباعتها")
    data=record.data if isinstance(record.data,dict) else {}
    if u.role!="owner" and data.get("outside_store_sale") and (data.get("owner_commission") or {}).get("status")!="paid":
        raise HTTPException(403,"لا يمكن طباعة فاتورة البيع خارج المتجر قبل أن يؤكد المالك تسديد عمولته البالغة 1.5٪")
    if u.role!="owner" and record.section=="directSale" and not data.get("outside_store_sale") and not bool(data.get("verified_payment")):
        raise HTTPException(403,"لا يمكن طباعة فاتورة البيع اليدوي قبل توثيق الدفع واعتماده من النظام")
    audit(s,u,"invoice_printed","record",record.id,{"record_id":record.id,"invoice_no":record.invoice_no or invoice_no,"section":record.section or section},request)
    s.commit()
    return {"ok":True}

@app.get("/audit-log")
def audit_log(s:Session=Depends(db),_:User=Depends(manager)):
    rows=s.execute(select(AuditEvent,User).outerjoin(User,AuditEvent.user_id==User.id).order_by(AuditEvent.id.desc()).limit(1000)).all()
    return [{"id":e.id,"user_id":e.user_id,"username":usr.username if usr else "—","user_name":usr.full_name if usr else "—","action":e.action,"entity":e.entity,"entity_id":e.entity_id,"details":e.details,"ip_address":e.ip_address,"created_at":e.created_at} for e,usr in rows]

# Manager-only direct changes. Employees must use the approval workflow above.
class RecordUpdate(BaseModel):
    data: dict
    invoice_no: Optional[str] = None
    currency: str = "USD"

@app.patch("/records/{record_id}")
def update_record(record_id:int, p:RecordUpdate, request:Request, s:Session=Depends(db), u:User=Depends(require_permission("invoices","edit"))):
    if u.role!="owner": raise HTTPException(403,"تعديل الفواتير مباشرة متاح للمالك فقط؛ أرسل طلب تعديل للموافقة")
    r=s.get(Record,record_id)
    if not r or r.deleted or (u.role!="owner" and (r.created_by!=u.id or r.section in {"deposit","consignSale"})): raise HTTPException(404,"السجل غير موجود")
    if p.currency not in ("USD","SYP"): raise HTTPException(400,"عملة غير مدعومة")
    if isinstance(r.data,dict) and r.data.get("outside_store_sale"):
        if (r.data.get("owner_commission") or {}).get("status")=="paid":
            raise HTTPException(409,"لا يمكن تعديل فاتورة بعد تسديد عمولة المالك وتسجيلها في محفظته")
        if u.role!="owner":
            raise HTTPException(403,"لا يمكن تعديل عملية البيع خارج المتجر بعد تسجيلها؛ راجع المالك")
    if p.currency!=r.currency and s.scalar(select(func.count(InvoicePayment.id)).where(InvoicePayment.record_id==r.id)):
        raise HTTPException(409,"لا يمكن تغيير عملة الفاتورة بعد تسجيل دفعات؛ احذف الدفعات أو سوّها أولاً")
    ensure_total_covers_payments(s,r.id,p.data)
    updated_data=prepare_record_inventory(s,r.section,p.data,allow_legacy=True,user=u)
    if isinstance(r.data,dict) and r.data.get("outside_store_sale"):
        old_commission=r.data.get("owner_commission") or {}
        items=updated_data.get("items") if isinstance(updated_data.get("items"),list) else []
        base=round(sum(max(0.0,float(x.get("quantity") or 0))*max(0.0,float(x.get("price") or 0)) for x in items if isinstance(x,dict)),2)
        updated_data["outside_store_sale"]=True
        updated_data["owner_commission"]={"rate":0.015,"base_amount":base,"amount":round(base*0.015,2),"currency":p.currency,"status":"pending","paid_at":None,"paid_by":None,"note":""}
    r.data=updated_data; r.invoice_no=p.invoice_no; r.currency=p.currency; r.updated_at=datetime.now(timezone.utc)
    recalculate_inventory(s)
    audit(s,u,"record_updated","record",r.id,{"section":r.section,"invoice_no":r.invoice_no},request); s.commit()
    if r.section in {"purchase","carPurchase","deposit","directSale","consignSale"}:
        _store_catalog_cache["value"]=None
        _store_catalog_cache["at"]=0
        _public_products_cache["value"].clear()
        _public_products_cache["at"].clear()
    return {"ok":True}

def sale_cash_moves_for_record(s:Session, record:Record):
    if record.section not in {"directSale","consignSale","carSale","purchase","carPurchase"}:
        return []
    invoice_no=record.invoice_no or str(record.id)
    return s.scalars(select(CashMove).where(or_(
        CashMove.record_id==record.id,
        CashMove.description.contains("فاتورة "+invoice_no)
    ))).all()

@app.delete("/records/{record_id}")
def delete_record(record_id:int, request:Request, s:Session=Depends(db), u:User=Depends(require_permission("invoices","delete"))):
    if u.role!="owner": raise HTTPException(403,"حذف الفواتير مباشرة متاح للمالك فقط؛ أرسل طلب حذف للموافقة")
    r=s.get(Record,record_id)
    if not r or r.deleted or (u.role!="owner" and (r.created_by!=u.id or r.section in {"deposit","consignSale"})): raise HTTPException(404,"السجل غير موجود")
    if (r.data or {}).get("outside_store_sale"):
        if ((r.data or {}).get("owner_commission") or {}).get("status")=="paid":
            raise HTTPException(409,"لا يمكن حذف فاتورة بعد تسديد عمولة المالك وإضافتها إلى محفظته")
        if u.role!="owner":
            raise HTTPException(403,"لا يمكن حذف بيع خارج المتجر؛ راجع المالك لتسوية العملية")
    related_cash_moves={m.id:m for m in (sale_cash_moves_for_record(s,r)+s.scalars(select(CashMove).where(CashMove.record_id==r.id)).all())}
    ensure_cash_reversal_safe(s,list(related_cash_moves.values()))
    r.deleted=True; r.updated_at=datetime.now(timezone.utc)
    recalculate_inventory(s)
    for payment in s.scalars(select(InvoicePayment).where(InvoicePayment.record_id==r.id)).all():
        s.delete(payment)
    for cash_move in sale_cash_moves_for_record(s,r):
        s.delete(cash_move)
    for cash_move in s.scalars(select(CashMove).where(CashMove.record_id==r.id)).all():
        s.delete(cash_move)
    audit(s,u,"record_deleted","record",r.id,{"section":r.section,"related_payments_and_cash_movements_deleted":True},request)
    s.commit()
    if r.section in {"purchase","carPurchase","deposit","directSale","consignSale"}:
        _store_catalog_cache["value"]=None
        _store_catalog_cache["at"]=0
        _public_products_cache["value"].clear()
        _public_products_cache["at"].clear()
    return {"ok":True}

@app.get("/my-change-requests")
def my_requests(s:Session=Depends(db),u:User=Depends(current_user)):
    rows=s.scalars(select(ChangeRequest).where(ChangeRequest.requested_by==u.id).order_by(ChangeRequest.id.desc()).limit(200)).all()
    out=[]
    for x in rows:
        rec=s.get(Record,x.record_id)
        if u.role!="owner" and rec and rec.section in {"deposit","consignSale"}:
            continue
        out.append({"id":x.id,"record_id":x.record_id,"section":rec.section if rec else None,"invoice_no":rec.invoice_no if rec else None,"action":x.action,"proposed_data":x.proposed_data,"reason":x.reason,"status":x.status,"created_at":x.created_at})
    return out


def ensure_user_wallets(s:Session,user_id:int):
    rows=s.scalars(select(UserWallet).where(UserWallet.user_id==user_id)).all()
    existing={x.currency for x in rows}
    for currency in ("USD","SYP"):
        if currency not in existing:
            s.add(UserWallet(user_id=user_id,currency=currency,balance=0))
    s.flush()

@app.get("/my-wallet")
def get_my_wallet(s:Session=Depends(db),u:User=Depends(current_user)):
    ensure_user_wallets(s,u.id)
    wallets=s.scalars(select(UserWallet).where(UserWallet.user_id==u.id).order_by(UserWallet.currency)).all()
    out=[]
    for w in wallets:
        tx=s.scalars(select(WalletTransaction).where(WalletTransaction.wallet_id==w.id).order_by(WalletTransaction.id.desc()).limit(100)).all()
        out.append({"id":w.id,"currency":w.currency,"balance":float(w.balance or 0),"transactions":[{"id":x.id,"amount":float(x.amount),"direction":x.direction,"reason":x.reason,"reference_type":x.reference_type,"reference_id":x.reference_id,"created_at":x.created_at} for x in tx]})
    s.commit()
    return out

@app.get("/wallets")
def list_user_wallets(s:Session=Depends(db),u:User=Depends(manager)):
    rows=s.scalars(select(User).where(User.deleted.is_(False),User.role!="owner").order_by(User.id)).all()
    result=[]
    for usr in rows:
        ensure_user_wallets(s,usr.id)
        wallets=s.scalars(select(UserWallet).where(UserWallet.user_id==usr.id).order_by(UserWallet.currency)).all()
        result.append({"user_id":usr.id,"username":usr.username,"name":usr.full_name,"wallets":[{"id":w.id,"currency":w.currency,"balance":float(w.balance or 0)} for w in wallets]})
    s.commit()
    return result

@app.get("/wallets/summary")
def wallet_totals(s:Session=Depends(db),u:User=Depends(manager)):
    rows=s.execute(select(UserWallet.currency,func.coalesce(func.sum(UserWallet.balance),0)).join(User,User.id==UserWallet.user_id).where(User.deleted.is_(False),User.role!="owner").group_by(UserWallet.currency)).all()
    totals={currency:float(balance or 0) for currency,balance in rows}
    return [{"currency":currency,"balance":totals.get(currency,0.0)} for currency in ("USD","SYP")]

@app.get("/users/{user_id}/wallet")
def get_user_wallet(user_id:int,s:Session=Depends(db),u:User=Depends(current_user)):
    if u.role!="owner" and u.id!=user_id: raise HTTPException(403,"لا يمكنك الوصول إلى محفظة مستخدم آخر")
    target=s.get(User,user_id)
    if not target or target.deleted: raise HTTPException(404,"المستخدم غير موجود")
    ensure_user_wallets(s,target.id)
    wallets=s.scalars(select(UserWallet).where(UserWallet.user_id==target.id).order_by(UserWallet.currency)).all()
    result=[]
    for w in wallets:
        tx=s.scalars(select(WalletTransaction).where(WalletTransaction.wallet_id==w.id).order_by(WalletTransaction.id.desc()).limit(100)).all()
        result.append({"id":w.id,"currency":w.currency,"balance":float(w.balance or 0),"transactions":[{"id":x.id,"amount":float(x.amount),"direction":x.direction,"reason":x.reason,"reference_type":x.reference_type,"reference_id":x.reference_id,"created_at":x.created_at} for x in tx]})
    s.commit()
    return {"user_id":target.id,"username":target.username,"name":target.full_name,"wallets":result}

class WalletRequestPayload(BaseModel):
    movement: str
    amount: float
    currency: str
    note: str = ""
    withdrawal_method: str = ""

class WalletRequestReviewPayload(BaseModel):
    decision: str
    note: str = ""

@app.get("/my-wallet/requests")
def list_my_wallet_requests(s:Session=Depends(db),u:User=Depends(current_user)):
    rows=s.scalars(select(WalletRequest).where(WalletRequest.user_id==u.id).order_by(WalletRequest.id.desc()).limit(100)).all()
    return [{"id":r.id,"movement":r.movement,"amount":float(r.amount),"currency":r.currency,"note":r.note,"withdrawal_method":r.withdrawal_method,"review_note":r.review_note,"status":r.status,"created_at":r.created_at.isoformat() if r.created_at else None,"reviewed_at":r.reviewed_at.isoformat() if r.reviewed_at else None} for r in rows]

@app.post("/my-wallet/requests")
def create_wallet_request(p:WalletRequestPayload,request:Request,s:Session=Depends(db),u:User=Depends(current_user)):
    movement=str(p.movement or "").strip()
    currency=str(p.currency or "").upper().strip()
    amount=round(float(p.amount),2)
    if movement not in {"deposit","withdrawal"}: raise HTTPException(400,"نوع الطلب غير صحيح")
    withdrawal_method=str(p.withdrawal_method or "").strip()
    allowed_withdrawal_methods={"cash","sham_cash","baraka_bank","syria_gulf","al_baraka"}
    if movement=="withdrawal" and withdrawal_method not in allowed_withdrawal_methods: raise HTTPException(400,"يرجى اختيار طريقة السحب")
    if movement=="deposit": withdrawal_method=""
    if currency not in {"USD","SYP"}: raise HTTPException(400,"العملة غير مدعومة")
    if amount<=0 or amount!=amount or amount==float("inf"): raise HTTPException(400,"أدخل مبلغاً صحيحاً أكبر من الصفر")
    ensure_user_wallets(s,u.id)
    if movement=="withdrawal":
        wallet=s.scalar(select(UserWallet).where(UserWallet.user_id==u.id,UserWallet.currency==currency).with_for_update())
        balance=round(float(wallet.balance or 0),2) if wallet else 0.0
        pending_withdrawals=float(s.scalar(select(func.coalesce(func.sum(WalletRequest.amount),0)).where(WalletRequest.user_id==u.id,WalletRequest.movement=="withdrawal",WalletRequest.currency==currency,WalletRequest.status=="pending")) or 0)
        available=round(balance-pending_withdrawals,2)
        if amount>available:
            raise HTTPException(409,f"لا يمكن طلب سحب أكثر من رصيدك المتاح. رصيد المحفظة: {balance:.2f} {currency}، والمبلغ المحجوز لطلبات معلّقة: {pending_withdrawals:.2f} {currency}، والمتاح للسحب: {max(0,available):.2f} {currency}")
    pending=s.scalar(select(func.count(WalletRequest.id)).where(WalletRequest.user_id==u.id,WalletRequest.status=="pending",WalletRequest.movement==movement))
    if pending: raise HTTPException(409,"لديك طلب من هذا النوع قيد المراجعة بالفعل")
    row=WalletRequest(user_id=u.id,movement=movement,amount=amount,currency=currency,note=(p.note or "").strip()[:500],withdrawal_method=withdrawal_method)
    s.add(row);s.flush()
    audit(s,u,"wallet_deposit_request" if movement=="deposit" else "wallet_withdrawal_request","wallet_request",row.id,{"amount":amount,"currency":currency,"note":row.note,"withdrawal_method":row.withdrawal_method},request)
    s.commit()
    return {"ok":True,"id":row.id,"status":row.status}

@app.get("/wallet-requests")
def list_wallet_requests(s:Session=Depends(db),u:User=Depends(manager)):
    rows=s.scalars(select(WalletRequest).order_by(WalletRequest.id.desc()).limit(300)).all()
    return [{"id":r.id,"user_id":r.user_id,"user_name":(s.get(User,r.user_id).full_name if s.get(User,r.user_id) else ""),"username":(s.get(User,r.user_id).username if s.get(User,r.user_id) else ""),"movement":r.movement,"amount":float(r.amount),"currency":r.currency,"note":r.note,"withdrawal_method":r.withdrawal_method,"review_note":r.review_note,"status":r.status,"created_at":r.created_at} for r in rows]

@app.post("/wallet-requests/{request_id}/review")
def review_wallet_request(request_id:int,p:WalletRequestReviewPayload,request:Request,s:Session=Depends(db),u:User=Depends(manager)):
    if u.role!="owner": raise HTTPException(403,"مراجعة طلبات المحافظ للمالك حصراً")
    row=s.scalar(select(WalletRequest).where(WalletRequest.id==request_id).with_for_update())
    if not row: raise HTTPException(404,"الطلب غير موجود")
    if row.status!="pending": raise HTTPException(409,"تمت معالجة هذا الطلب مسبقاً")
    decision=str(p.decision or "").strip()
    if decision not in {"approve","reject"}: raise HTTPException(400,"قرار المراجعة غير صحيح")
    target=s.get(User,row.user_id)
    if not target or target.deleted: raise HTTPException(404,"حساب المستخدم غير موجود")
    if decision=="approve":
        ensure_user_wallets(s,target.id)
        wallet=s.scalar(select(UserWallet).where(UserWallet.user_id==target.id,UserWallet.currency==row.currency).with_for_update())
        before=round(float(wallet.balance or 0),2)
        if row.movement=="withdrawal" and before<float(row.amount): raise HTTPException(409,"رصيد المحفظة لم يعد كافياً لتنفيذ السحب")
        wallet.balance=round(before+float(row.amount) if row.movement=="deposit" else before-float(row.amount),2)
        wallet.updated_at=datetime.now(timezone.utc)
        reason=("إيداع وافق عليه المالك بناءً على طلب المستخدم" if row.movement=="deposit" else "سحب نقدي نفذه المالك بناءً على طلب المستخدم")
        tx=WalletTransaction(wallet_id=wallet.id,user_id=target.id,amount=row.amount,currency=row.currency,direction="in" if row.movement=="deposit" else "out",reason=(p.note or "").strip()[:500] or reason,reference_type="wallet_request",reference_id=row.id,created_by=u.id)
        s.add(tx)
        # A cash payout is funded from the Sham Cash cashbox for online-sale
        # wallet balances. Keep the cashbox ledger in sync with the wallet debit.
        if row.movement=="withdrawal" and row.withdrawal_method=="cash":
            ensure_cash_balance(s,"شام كاش",row.currency,float(row.amount))
            s.add(CashMove(
                box_name="شام كاش",
                movement="withdrawal",
                amount=row.amount,
                currency=row.currency,
                description=f"صرف نقدي للمستخدم {target.full_name or target.username} · طلب سحب محفظة #{row.id}",
                created_by=u.id,
            ))
        row.status="approved"
    else:
        row.status="rejected"
    row.review_note=(p.note or "").strip()[:500];row.reviewed_by=u.id;row.reviewed_at=datetime.now(timezone.utc)
    audit(s,u,"wallet_request_"+row.status,"wallet_request",row.id,{"user_id":target.id,"movement":row.movement,"amount":float(row.amount),"currency":row.currency,"review_note":(p.note or "").strip()[:500]},request)
    s.commit()
    return {"ok":True,"status":row.status}

class WalletAdjustmentPayload(BaseModel):
    amount: float
    currency: str
    movement: str
    description: str = ""

class OwnerWalletTransferPayload(BaseModel):
    amount: float = Field(gt=0)
    currency: str
    description: str = ""
    verification_token: Optional[str] = None

@app.post("/owner-wallet/transfer-to-cashbox")
def transfer_owner_wallet_to_cashbox(p:OwnerWalletTransferPayload,request:Request,s:Session=Depends(db),u:User=Depends(manager)):
    if u.role!="owner": raise HTTPException(403,"تحويل محفظة المالك إلى الصندوق متاح للمالك فقط")
    currency=str(p.currency or "").upper().strip()
    amount=round(float(p.amount),2)
    if currency not in {"USD","SYP"}: raise HTTPException(400,"العملة غير مدعومة")
    if amount<=0 or amount!=amount or amount==float("inf"): raise HTTPException(400,"أدخل مبلغاً صحيحاً أكبر من الصفر")
    ensure_user_wallets(s,u.id)
    wallet=s.scalar(select(UserWallet).where(UserWallet.user_id==u.id,UserWallet.currency==currency).with_for_update())
    if not wallet: raise HTTPException(500,"تعذر العثور على محفظة المالك")
    before=round(float(wallet.balance or 0),2)
    if before<amount: raise HTTPException(409,f"رصيد محفظة المالك غير كافٍ. المتاح: {before:.2f} {currency}")
    consume_operation_verification(s,u,"cash_movement",p.verification_token)
    wallet.balance=round(before-amount,2)
    wallet.updated_at=datetime.now(timezone.utc)
    reason=(p.description or "").strip()[:500] or "تحويل من محفظة المالك إلى صندوق الإيداع"
    tx=WalletTransaction(wallet_id=wallet.id,user_id=u.id,amount=amount,currency=currency,direction="out",reason=reason,reference_type="owner_wallet_cashbox_transfer",created_by=u.id)
    move=CashMove(box_name="صندوق الإيداع",movement="deposit",amount=amount,currency=currency,description=reason,created_by=u.id)
    s.add_all([tx,move]);s.flush()
    audit(s,u,"owner_wallet_transferred_to_cashbox","owner_wallet",wallet.id,{"amount":amount,"currency":currency,"cash_move_id":move.id,"wallet_transaction_id":tx.id,"balance_before":before,"balance_after":float(wallet.balance)},request)
    s.commit()
    return {"ok":True,"amount":amount,"currency":currency,"cash_box":"صندوق الإيداع","wallet_balance":float(wallet.balance),"cash_move_id":move.id}

@app.post("/users/{user_id}/wallet/adjust")
def adjust_user_wallet(user_id:int,p:WalletAdjustmentPayload,request:Request,s:Session=Depends(db),u:User=Depends(manager)):
    if u.role!="owner":
        raise HTTPException(403,"الإيداع والسحب من صلاحيات المالك حصراً")
    target=s.get(User,user_id)
    if not target or target.deleted or target.role=="owner":
        raise HTTPException(404,"حساب المستخدم غير موجود")
    amount=round(float(p.amount),2)
    currency=str(p.currency or "").upper().strip()
    movement=str(p.movement or "").strip()
    if amount<=0 or amount!=amount or amount==float("inf"):
        raise HTTPException(400,"أدخل مبلغاً صحيحاً أكبر من الصفر")
    if currency not in {"USD","SYP"}:
        raise HTTPException(400,"العملة غير مدعومة")
    if movement not in {"deposit","withdrawal"}:
        raise HTTPException(400,"نوع الحركة غير صحيح")
    ensure_user_wallets(s,target.id)
    wallet=s.scalar(select(UserWallet).where(UserWallet.user_id==target.id,UserWallet.currency==currency).with_for_update())
    if not wallet:
        raise HTTPException(500,"تعذر العثور على محفظة المستخدم")
    before=round(float(wallet.balance or 0),2)
    if movement=="withdrawal" and before<amount:
        raise HTTPException(409,"رصيد المحفظة غير كافٍ لإتمام السحب")
    direction="in" if movement=="deposit" else "out"
    wallet.balance=round(before+amount if movement=="deposit" else before-amount,2)
    wallet.updated_at=datetime.now(timezone.utc)
    default_reason=("إيداع نقدي في محفظة المستخدم بواسطة المالك" if movement=="deposit" else "صرف نقدي للمستخدم مقابل خصم من رصيد محفظته بواسطة المالك")
    reason=(p.description or "").strip()[:500] or default_reason
    tx=WalletTransaction(wallet_id=wallet.id,user_id=target.id,amount=amount,currency=currency,direction=direction,reason=reason,reference_type="owner_wallet_adjustment",created_by=u.id)
    s.add(tx);s.flush()
    audit(s,u,"wallet_deposit" if movement=="deposit" else "wallet_cash_withdrawal","user_wallet",wallet.id,{"target_user_id":target.id,"amount":amount,"currency":currency,"balance_before":before,"balance_after":float(wallet.balance),"transaction_id":tx.id,"description":reason},request)
    s.commit()
    return {"ok":True,"user_id":target.id,"wallet_id":wallet.id,"amount":amount,"currency":currency,"movement":movement,"balance":float(wallet.balance),"transaction_id":tx.id}

@app.get("/cash-summary")
def cash_summary(s:Session=Depends(db),u:User=Depends(require_permission("cash","view"))):
    query=select(
            CashMove.box_name,
            CashMove.currency,
            func.sum(case(
                (CashMove.movement.in_(("deposit","transfer_in")),CashMove.amount),
                else_=-CashMove.amount
            )).label("balance")
        ).where(CashMove.voided.is_(False))
    if u.role!="owner":
        query=query.where(CashMove.box_name.not_in(["صندوق الأمانة","صندوق مبيع الأمانة","صندوق قل أمانة","صندوق قُل أمانة"]))
    rows=s.execute(query.group_by(CashMove.box_name,CashMove.currency)).all()
    return [{"box_name":box_name,"currency":currency,"balance":float(balance or 0)} for box_name,currency,balance in rows]


# Public storefront data: read-only aggregates from the live accounting database.
@app.get("/public/stats")
def public_stats(s:Session=Depends(db)):
    rows=s.scalars(select(Record).where(Record.deleted.is_(False))).all()
    profile=s.get(CompanyProfile,1)
    profile_data=profile.data if profile and isinstance(profile.data,dict) else {}
    customers=set()
    sales=0
    purchases=0
    for r in rows:
        data=r.data or {}
        customer=str(data.get("customer") or data.get("customer_name") or "").strip()
        if customer and customer not in {"—","-"}:
            customers.add(customer.casefold())
        if r.section in {"directSale","consignSale","carSale"}:
            sales+=1
        if r.section in {"purchase","carPurchase","deposit"}:
            purchases+=1
    return {"visible":profile_data.get("public_show_stats",True) is not False,"customers":len(customers),"sales":sales,"purchases":purchases,"records":len(rows)}

def is_strong_store_password(value:str)->bool:
    return len(value)>=8 and any(c.isupper() for c in value) and any(c.islower() for c in value) and any(c.isdigit() for c in value)

def require_strong_store_password(value:str):
    if not is_strong_store_password(value):
        raise HTTPException(400,"يجب أن تتكون كلمة المرور من 8 خانات على الأقل، وتتضمن حرفاً كبيراً وحرفاً صغيراً ورقماً")

class StoreRegisterPayload(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=256)
class StoreLoginPayload(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=256)
class StorePasswordResetRequestPayload(BaseModel):
    email: str = Field(min_length=5, max_length=254)
class StorePasswordResetConfirmPayload(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=256)

class StoreProfilePayload(BaseModel):
    full_name: str = Field(min_length=2,max_length=160)
    first_name: str = Field(default="",max_length=80)
    last_name: str = Field(default="",max_length=80)
    shipping_address: str = Field(default="",max_length=1000)
    phone_country_code: str = Field(default="",max_length=8)
    phone_number: str = Field(default="",max_length=32)
    avatar_data: Optional[str] = Field(default=None,max_length=5600000)
class StorePhoneCodePayload(BaseModel):
    phone_country_code: str = Field(default="",max_length=8)
    phone_number: str = Field(min_length=5,max_length=32)
class StorePhoneConfirmPayload(BaseModel):
    code: str = Field(min_length=6,max_length=6)

class StoreChangePasswordPayload(BaseModel):
    new_password: str = Field(min_length=8,max_length=256)
class StorePasswordChangeConfirmPayload(BaseModel):
    token: str = Field(min_length=32,max_length=256)

class StoreCartItemPayload(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=999)
class OnlineOrderPayload(BaseModel):
    first_name: str = Field(min_length=1,max_length=80)
    last_name: str = Field(min_length=1,max_length=80)
    shipping_address: str = Field(min_length=5,max_length=1000)
    phone_country_code: str = Field(min_length=2,max_length=8)
    phone_number: str = Field(min_length=5,max_length=32)
    payment_proof: str = Field(min_length=40,max_length=7000000)
    proof_type: str = Field(min_length=3,max_length=80)
    payment_method: str = Field(default="sham_cash",pattern="^(sham_cash|baraka_bank|syria_gulf)$")
    contract_identity: Optional[dict[str,str]] = None
    items: list[StoreCartItemPayload] = Field(min_length=1,max_length=100)

class StoreCartPayload(BaseModel):
    items: list[StoreCartItemPayload] = Field(default_factory=list, max_length=100)

def store_customer_token(customer:StoreCustomer):
    # Store sessions have a bounded lifetime and are held only in an HttpOnly cookie.
    now=datetime.now(timezone.utc)
    return jwt.encode({"sub":str(customer.id),"typ":"store_customer","iat":now,"exp":now+timedelta(days=30)},settings.jwt_secret,algorithm="HS256")

def set_store_session(response:Response, customer:StoreCustomer):
    response.set_cookie(key="aib_store_session",value=store_customer_token(customer),max_age=30*24*60*60,httponly=True,secure=True,samesite="lax",path="/")

def clear_store_session(response:Response):
    response.delete_cookie("aib_store_session",path="/",secure=True,httponly=True,samesite="lax")

@app.post("/store/auth/logout")
def logout_store_customer(request:Request, response:Response):
    require_store_same_origin(request)
    clear_store_session(response)
    return {"ok":True}

def store_product_category(name:str, model:str):
    value=(name+" "+(model or "")).lower()
    if any(x in value for x in ["مولد","generator","كمبريسر","compressor","ضاغط","مضخة","pump","تزفيت","asphalt","paver","roller","مدحلة","فرادة"]): return "special"
    if any(x in value for x in ["حفار","excavator","تركس","لودر","loader","كاتربلر","caterpillar","volvo ec","hyundai r"]): return "heavy"
    if any(x in value for x in ["شاحنة","truck","fh","scania","قاطر"]): return "trucks"
    if any(x in value for x in ["محرك","engine","gearbox","جير","دفرنس","ناقل"]): return "engines"
    if any(x in value for x in ["سيارة","sedan","bmw","mercedes","hyundai","kia","toyota","volkswagen"]): return "cars"
    return "parts"

def store_latest_prices(s:Session):
    prices={}
    # User-entered prices are final selling prices and must not receive the legacy 35% markup.
    for product in s.scalars(select(InventoryProduct).where(InventoryProduct.active.is_(True),InventoryProduct.sale_price.is_not(None))).all():
        prices[product.sku]={"sale_price":round(float(product.sale_price or 0),2),"currency":product.sale_currency or "USD"}
    records=s.scalars(select(Record).where(Record.section.in_(["purchase","carPurchase"]),Record.deleted.is_(False)).order_by(Record.created_at.desc(),Record.id.desc())).all()
    for record in records:
        for item in (record.data or {}).get("items",[]):
            if not isinstance(item,dict): continue
            sku=str(item.get("sku") or "").strip().upper()
            price=record_item_landed_unit_cost(record,item)
            if sku and price>0 and sku not in prices:
                prices[sku]={"sale_price":round(price*1.35,2),"currency":record.currency or "USD"}
    return prices

@app.post("/store/auth/register")
def store_register(p:StoreRegisterPayload, request:Request, s:Session=Depends(db)):
    require_strong_store_password(p.password)
    email=p.email.strip().lower()
    if "@" not in email or "." not in email.rsplit("@",1)[-1]:
        raise HTTPException(400,"يرجى إدخال بريد إلكتروني صحيح")
    customer=s.scalar(select(StoreCustomer).where(StoreCustomer.email==email))
    if customer and customer.active:
        raise HTTPException(409,"هذا البريد مسجل مسبقاً. سجّل الدخول بدلاً من إنشاء حساب جديد")
    now=datetime.now(timezone.utc)
    if not customer:
        customer=StoreCustomer(email=email,full_name=p.full_name.strip(),password_hash=password_hash.hash(p.password),cart=[],active=False)
        s.add(customer);s.flush()
    else:
        customer.full_name=p.full_name.strip()
        customer.password_hash=password_hash.hash(p.password)
        s.query(StoreEmailVerification).filter(StoreEmailVerification.customer_id==customer.id).delete(synchronize_session=False)
    latest=s.scalar(select(StoreEmailVerification).where(StoreEmailVerification.customer_id==customer.id).order_by(StoreEmailVerification.id.desc()))
    if latest and latest.created_at>now-timedelta(seconds=60):
        raise HTTPException(429,"يرجى الانتظار دقيقة قبل طلب رمز جديد")
    code=f"{secrets.randbelow(1000000):06d}"
    s.add(StoreEmailVerification(customer_id=customer.id,code_hash=password_hash.hash(code),expires_at=now+timedelta(minutes=10)))
    s.flush()
    try: send_verification_email(email,code)
    except Exception:
        s.rollback()
        raise
    s.commit()
    return {"ok":True,"verification_required":True,"message":"أرسلنا رمز تأكيد الحساب إلى بريدك الإلكتروني"}

class StoreEmailConfirmPayload(BaseModel):
    email: str = Field(min_length=5,max_length=254)
    code: str = Field(min_length=6,max_length=6)

@app.post("/store/auth/register/confirm")
def confirm_store_registration(p:StoreEmailConfirmPayload, request:Request, response:Response, s:Session=Depends(db)):
    email=p.email.strip().lower()
    customer=s.scalar(select(StoreCustomer).where(StoreCustomer.email==email,StoreCustomer.active.is_(False)))
    if not customer: raise HTTPException(400,"لا يوجد تسجيل معلّق لهذا البريد")
    row=s.scalar(select(StoreEmailVerification).where(StoreEmailVerification.customer_id==customer.id).order_by(StoreEmailVerification.id.desc()))
    now=datetime.now(timezone.utc)
    if not row or row.expires_at<now or row.attempts>=5:
        raise HTTPException(400,"رمز التأكيد منتهي أو غير صالح. أعد إنشاء الحساب")
    if not password_hash.verify(p.code,row.code_hash):
        row.attempts+=1;s.commit()
        raise HTTPException(400,"رمز التأكيد غير صحيح")
    customer.active=True
    s.query(StoreEmailVerification).filter(StoreEmailVerification.customer_id==customer.id).delete(synchronize_session=False)
    s.commit()
    set_store_session(response,customer)
    return {"ok":True,"customer":{"id":customer.id,"email":customer.email,"full_name":customer.full_name}}

@app.post("/store/auth/login")
def store_login(p:StoreLoginPayload, request:Request, s:Session=Depends(db)):
    email=p.email.strip().lower()
    customer=s.scalar(select(StoreCustomer).where(StoreCustomer.email==email))
    now=datetime.now(timezone.utc)
    if not customer or not customer.active:
        raise HTTPException(401,"البريد الإلكتروني أو كلمة المرور غير صحيحة")
    if customer.locked_until and customer.locked_until>now:
        raise HTTPException(423,"تم تعليق تسجيل الدخول مؤقتاً. حاول بعد قليل")
    if not password_hash.verify(p.password,customer.password_hash):
        customer.failed_logins+=1
        if customer.failed_logins>=5:
            customer.failed_logins=0
            customer.locked_until=now+timedelta(minutes=15)
        s.commit()
        raise HTTPException(401,"البريد الإلكتروني أو كلمة المرور غير صحيحة")
    customer.failed_logins=0;customer.locked_until=None
    latest=s.scalar(select(StoreLoginVerification).where(StoreLoginVerification.customer_id==customer.id).order_by(StoreLoginVerification.id.desc()))
    if latest and latest.created_at>now-timedelta(seconds=30):
        raise HTTPException(429,"أرسلنا رمزاً قبل قليل. افحص بريدك أو انتظر 30 ثانية")
    code=f"{secrets.randbelow(1000000):06d}"
    s.add(StoreLoginVerification(customer_id=customer.id,code_hash=password_hash.hash(code),expires_at=now+timedelta(minutes=10)))
    s.commit()
    try: send_verification_email(email,code)
    except Exception:
        s.rollback()
        raise
    return {"ok":True,"verification_required":True,"message":"أرسلنا رمز الدخول إلى بريدك الإلكتروني"}

@app.post("/store/auth/login/verify")
def verify_store_login(p:StoreEmailConfirmPayload, request:Request, response:Response, s:Session=Depends(db)):
    email=p.email.strip().lower()
    customer=s.scalar(select(StoreCustomer).where(StoreCustomer.email==email,StoreCustomer.active.is_(True)))
    if not customer: raise HTTPException(400,"بيانات التحقق غير صحيحة")
    row=s.scalar(select(StoreLoginVerification).where(StoreLoginVerification.customer_id==customer.id).order_by(StoreLoginVerification.id.desc()))
    now=datetime.now(timezone.utc)
    if not row or row.expires_at<now or row.attempts>=5:
        raise HTTPException(400,"رمز الدخول منتهي أو غير صالح. سجّل الدخول مجدداً")
    if not password_hash.verify(p.code,row.code_hash):
        row.attempts+=1;s.commit()
        raise HTTPException(400,"رمز الدخول غير صحيح")
    s.query(StoreLoginVerification).filter(StoreLoginVerification.customer_id==customer.id).delete(synchronize_session=False)
    s.commit()
    set_store_session(response,customer)
    return {"ok":True,"customer":{"id":customer.id,"email":customer.email,"full_name":customer.full_name}}

@app.post("/store/auth/password-reset/request")
def request_store_password_reset(p:StorePasswordResetRequestPayload, request:Request, s:Session=Depends(db)):
    email=p.email.strip().lower()
    customer=s.scalar(select(StoreCustomer).where(StoreCustomer.email==email,StoreCustomer.active.is_(True)))
    # Keep the response identical for known and unknown addresses.
    generic={"ok":True,"message":"إذا كان البريد مرتبطاً بحساب نشط، فستصلك رسالة تحتوي على رمز الاسترداد."}
    if not customer:
        return generic
    now=datetime.now(timezone.utc)
    latest=s.scalar(select(StorePasswordReset).where(StorePasswordReset.customer_id==customer.id).order_by(StorePasswordReset.id.desc()))
    if latest and latest.created_at>now-timedelta(seconds=60):
        raise HTTPException(429,"يرجى الانتظار دقيقة قبل طلب رمز جديد")
    code=f"{secrets.randbelow(1000000):06d}"
    row=StorePasswordReset(customer_id=customer.id,code_hash=password_hash.hash(code),expires_at=now+timedelta(minutes=10))
    s.add(row);s.flush()
    try:
        send_verification_email(email,code)
    except Exception:
        s.rollback()
        raise
    s.commit()
    return generic

@app.post("/store/auth/password-reset/confirm")
def confirm_store_password_reset(p:StorePasswordResetConfirmPayload, request:Request, s:Session=Depends(db)):
    require_strong_store_password(p.new_password)
    email=p.email.strip().lower()
    customer=s.scalar(select(StoreCustomer).where(StoreCustomer.email==email,StoreCustomer.active.is_(True)))
    if not customer:
        raise HTTPException(400,"بيانات الاسترداد غير صحيحة أو انتهت صلاحية الرمز")
    row=s.scalar(select(StorePasswordReset).where(StorePasswordReset.customer_id==customer.id).order_by(StorePasswordReset.id.desc()))
    now=datetime.now(timezone.utc)
    if not row or row.expires_at<now or row.attempts>=5:
        raise HTTPException(400,"رمز الاسترداد منتهي أو غير صالح. اطلب رمزاً جديداً")
    if not password_hash.verify(p.code,row.code_hash):
        row.attempts+=1;s.commit()
        raise HTTPException(400,"رمز الاسترداد غير صحيح")
    customer.password_hash=password_hash.hash(p.new_password)
    customer.failed_logins=0
    customer.locked_until=None
    s.query(StorePasswordReset).filter(StorePasswordReset.customer_id==customer.id).delete(synchronize_session=False)
    s.commit()
    notify_account_change(customer.email,"تم تغيير كلمة المرور الخاصة بحساب المتجر")
    return {"ok":True,"message":"تم تحديث كلمة المرور. يمكنك تسجيل الدخول الآن."}

@app.get("/store/auth/google/config")
def store_google_config():
    return {"configured":bool(settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri)}

@app.get("/store/auth/google/start")
def store_google_start(customer:StoreCustomer=Depends(current_store_customer)):
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(503,"ربط Google غير مهيأ بعد. أضف بيانات OAuth في إعدادات Render")
    nonce=secrets.token_urlsafe(32)
    state=jwt.encode({"sub":str(customer.id),"typ":"store_google_link","nonce":nonce,"exp":datetime.now(timezone.utc)+timedelta(minutes=10)},settings.jwt_secret,algorithm="HS256")
    params={"client_id":settings.google_client_id,"redirect_uri":settings.google_redirect_uri,"response_type":"code","scope":"openid email profile","state":state,"prompt":"select_account"}
    response=Response(content=json.dumps({"authorization_url":"https://accounts.google.com/o/oauth2/v2/auth?"+urlencode(params)}),media_type="application/json")
    response.set_cookie("aib_google_link_nonce",nonce,max_age=600,httponly=True,secure=True,samesite="lax",path="/store/auth/google")
    return response

@app.get("/store/auth/google/login/start")
def store_google_login_start():
    if not settings.google_client_id or not settings.google_client_secret or not settings.google_redirect_uri:
        raise HTTPException(503,"تسجيل Google غير مهيأ بعد. تحقق من إعدادات OAuth في Render")
    nonce=secrets.token_urlsafe(32)
    state=jwt.encode({"typ":"store_google_auth","nonce":nonce,"exp":datetime.now(timezone.utc)+timedelta(minutes=10)},settings.jwt_secret,algorithm="HS256")
    params={"client_id":settings.google_client_id,"redirect_uri":settings.google_redirect_uri,"response_type":"code","scope":"openid email profile","state":state,"prompt":"select_account"}
    response=Response(content=json.dumps({"authorization_url":"https://accounts.google.com/o/oauth2/v2/auth?"+urlencode(params)}),media_type="application/json")
    response.set_cookie("aib_google_auth_nonce",nonce,max_age=600,httponly=True,secure=True,samesite="lax",path="/store/auth/google")
    return response

@app.get("/store/auth/google/callback")
def store_google_callback(request:Request, code:str="", state:str="", error:str="", s:Session=Depends(db)):
    fail_url="/shop?google=error"
    if error or not code or not state:
        return RedirectResponse(fail_url,303)
    try:
        payload=jwt.decode(state,settings.jwt_secret,algorithms=["HS256"])
        flow=payload.get("typ")
        if flow=="store_google_auth":
            nonce_cookie=request.cookies.get("aib_google_auth_nonce","")
        elif flow=="store_google_link":
            nonce_cookie=request.cookies.get("aib_google_link_nonce","")
        else:
            raise ValueError("invalid oauth flow")
        if not secrets.compare_digest(str(payload.get("nonce","")),nonce_cookie):
            raise ValueError("invalid oauth state")
        token_data={"code":code,"client_id":settings.google_client_id,"client_secret":settings.google_client_secret,"redirect_uri":settings.google_redirect_uri,"grant_type":"authorization_code"}
        req=UrlRequest("https://oauth2.googleapis.com/token",data=urlencode(token_data).encode(),headers={"Content-Type":"application/x-www-form-urlencoded"},method="POST")
        with urlopen(req,timeout=20) as resp: token_response=json.loads(resp.read().decode())
        id_token=token_response.get("id_token")
        if not id_token: raise ValueError("Google did not return an ID token")
        verify_req=UrlRequest("https://oauth2.googleapis.com/tokeninfo?id_token="+id_token,headers={"Accept":"application/json"})
        with urlopen(verify_req,timeout=20) as resp: identity=json.loads(resp.read().decode())
        if identity.get("aud")!=settings.google_client_id or identity.get("iss") not in ("accounts.google.com","https://accounts.google.com") or identity.get("email_verified") not in (True,"true"):
            raise ValueError("Google identity verification failed")
        google_sub=str(identity.get("sub") or "")
        email=str(identity.get("email") or "").strip().lower()
        if not google_sub or not email: raise ValueError("Google identity is incomplete")
        linked=s.scalar(select(StoreCustomer).where(StoreCustomer.google_sub==google_sub))
        if flow=="store_google_link":
            customer=s.get(StoreCustomer,int(payload["sub"]))
            if not customer or not customer.active: raise ValueError("customer unavailable")
            if linked and linked.id!=customer.id: raise ValueError("حساب Google مرتبط بحساب متجر آخر")
            customer.google_sub=google_sub
            s.commit()
            return RedirectResponse("/shop?google=success",303)
        if linked:
            customer=linked
        else:
            customer=s.scalar(select(StoreCustomer).where(StoreCustomer.email==email))
            if customer:
                if customer.google_sub and customer.google_sub!=google_sub:
                    raise ValueError("هذا البريد مرتبط بحساب Google مختلف")
                customer.google_sub=google_sub
                customer.active=True
                s.query(StoreEmailVerification).filter(StoreEmailVerification.customer_id==customer.id).delete(synchronize_session=False)
            else:
                full_name=str(identity.get("name") or email.split("@",1)[0]).strip()[:160] or email.split("@",1)[0]
                customer=StoreCustomer(email=email,full_name=full_name,password_hash=password_hash.hash(secrets.token_urlsafe(48)),cart=[],active=True,google_sub=google_sub)
                s.add(customer)
                s.flush()
        customer.failed_logins=0
        customer.locked_until=None
        s.commit()
        response=RedirectResponse("/shop",303)
        set_store_session(response,customer)
        response.delete_cookie("aib_google_auth_nonce",path="/store/auth/google")
        return response
    except Exception as exc:
        s.rollback()
        print("Google OAuth failed: "+type(exc).__name__,flush=True)
        response=RedirectResponse(fail_url,303)
        response.delete_cookie("aib_google_auth_nonce",path="/store/auth/google")
        return response

@app.get("/store/auth/me")
def store_me(customer:StoreCustomer=Depends(current_store_customer)):
    return {"id":customer.id,"email":customer.email,"full_name":customer.full_name,"first_name":customer.first_name or "","last_name":customer.last_name or "","shipping_address":customer.shipping_address or "","phone_country_code":customer.phone_country_code or "+963","phone_number":customer.phone_number or "","phone_verified":bool(customer.phone_verified_at),"avatar_data":customer.avatar_data}

_store_phone_codes = {}
def _store_phone_e164(country_code: str, phone_number: str) -> str:
    raw = "".join(ch for ch in str(phone_number or "").strip() if ch.isdigit() or ch == "+")
    if raw.startswith("+"):
        number = "+" + "".join(ch for ch in raw[1:] if ch.isdigit())
    elif country_code:
        number = country_code.strip() + "".join(ch for ch in raw if ch.isdigit())
    else:
        raise HTTPException(400,"رمز الدولة اختياري، لكن عند تركه فارغاً أدخل الرقم بصيغته الدولية مع + ورمز الدولة")
    if not number.startswith("+") or not 8 <= len(number) <= 16:
        raise HTTPException(400,"رقم الهاتف غير صحيح. استخدم الصيغة الدولية")
    return number

@app.post("/store/auth/phone/send-code")
def send_store_phone_code(p:StorePhoneCodePayload, customer:StoreCustomer=Depends(current_store_customer)):
    sid=os.getenv("TWILIO_ACCOUNT_SID","").strip()
    token=os.getenv("TWILIO_AUTH_TOKEN","").strip()
    sender=os.getenv("TWILIO_PHONE_NUMBER","").strip()
    if not (sid and token and sender):
        raise HTTPException(503,"خدمة الرسائل النصية غير مهيأة بعد. أضف TWILIO_ACCOUNT_SID وTWILIO_AUTH_TOKEN وTWILIO_PHONE_NUMBER في Render")
    phone=_store_phone_e164(p.phone_country_code,p.phone_number)
    now=datetime.now(timezone.utc)
    previous=_store_phone_codes.get(customer.id)
    if previous and (now-previous["sent_at"]).total_seconds()<60:
        raise HTTPException(429,"انتظر دقيقة قبل طلب رمز جديد")
    code=f"{secrets.randbelow(1000000):06d}"
    body=urlencode({"To":phone,"From":sender,"Body":f"رمز التحقق لمجموعة AIB هو: {code}. صالح لمدة 5 دقائق."}).encode()
    req=UrlRequest(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",data=body,headers={"Authorization":"Basic "+base64.b64encode(f"{sid}:{token}".encode()).decode(),"Content-Type":"application/x-www-form-urlencoded"},method="POST")
    try:
        with urlopen(req,timeout=15) as response:
            result=json.loads(response.read().decode())
            if result.get("status") in ("failed","undelivered"):
                raise HTTPException(502,"تعذر تسليم رسالة التحقق إلى هذا الرقم")
    except HTTPError as exc:
        detail="تعذر إرسال رسالة التحقق. تحقق من إعدادات مزود الرسائل ودعم الدولة."
        try: detail=json.loads(exc.read().decode()).get("message") or detail
        except Exception: pass
        raise HTTPException(502,detail)
    except (URLError,TimeoutError):
        raise HTTPException(504,"انتهت مهلة إرسال رسالة التحقق. حاول مجدداً")
    _store_phone_codes[customer.id]={"hash":hashlib.sha256(code.encode()).hexdigest(),"sent_at":now,"expires_at":now+timedelta(minutes=5),"phone":phone,"attempts":0}
    return {"ok":True,"message":"تم إرسال رمز التحقق برسالة SMS، صالح لمدة 5 دقائق"}

@app.post("/store/auth/phone/confirm")
def confirm_store_phone(p:StorePhoneConfirmPayload,s:Session=Depends(db),customer:StoreCustomer=Depends(current_store_customer)):
    item=_store_phone_codes.get(customer.id)
    if not item or datetime.now(timezone.utc)>item["expires_at"]:
        _store_phone_codes.pop(customer.id,None)
        raise HTTPException(400,"انتهت صلاحية الرمز. اطلب رمزاً جديداً")
    item["attempts"]+=1
    if item["attempts"]>5:
        _store_phone_codes.pop(customer.id,None)
        raise HTTPException(429,"تم تجاوز محاولات التحقق. اطلب رمزاً جديداً")
    if not secrets.compare_digest(item["hash"],hashlib.sha256(p.code.encode()).hexdigest()):
        raise HTTPException(400,"رمز التحقق غير صحيح")
    customer.phone_country_code=""
    customer.phone_number=item["phone"]
    customer.phone_verified_at=datetime.now(timezone.utc)
    s.commit()
    _store_phone_codes.pop(customer.id,None)
    return {"ok":True,"phone_number":item["phone"],"message":"تم التحقق من رقم الهاتف بنجاح"}

@app.put("/store/auth/profile")
def update_store_profile(p:StoreProfilePayload, s:Session=Depends(db), customer:StoreCustomer=Depends(current_store_customer)):
    if p.avatar_data is not None and p.avatar_data and not (p.avatar_data.startswith("data:image/jpeg;base64,") or p.avatar_data.startswith("data:image/png;base64,") or p.avatar_data.startswith("data:image/webp;base64,")):
        raise HTTPException(400,"صيغة الصورة غير مدعومة. استخدم JPG أو PNG أو WEBP")
    customer.full_name=p.full_name.strip()
    customer.first_name=p.first_name.strip()
    customer.last_name=p.last_name.strip()
    customer.shipping_address=p.shipping_address.strip()
    new_phone_country_code=p.phone_country_code.strip()
    new_phone_number=p.phone_number.strip()
    if new_phone_number != customer.phone_number or new_phone_country_code != customer.phone_country_code:
        customer.phone_verified_at=None
    customer.phone_country_code=new_phone_country_code
    customer.phone_number=new_phone_number
    if p.avatar_data is not None: customer.avatar_data=p.avatar_data or None
    s.commit()
    return {"ok":True,"message":"تم حفظ بيانات حسابك","customer":{"id":customer.id,"email":customer.email,"full_name":customer.full_name,"first_name":customer.first_name,"last_name":customer.last_name,"shipping_address":customer.shipping_address,"phone_country_code":customer.phone_country_code,"phone_number":customer.phone_number,"phone_verified":bool(customer.phone_verified_at),"avatar_data":customer.avatar_data}}

@app.post("/store/auth/change-password")
def request_store_password_change(p:StoreChangePasswordPayload, request:Request, s:Session=Depends(db), customer:StoreCustomer=Depends(current_store_customer)):
    require_strong_store_password(p.new_password)
    if password_hash.verify(p.new_password,customer.password_hash):
        raise HTTPException(400,"اختر كلمة مرور جديدة مختلفة عن الحالية")
    now=datetime.now(timezone.utc)
    latest=s.scalar(select(StorePasswordReset).where(StorePasswordReset.customer_id==customer.id).order_by(StorePasswordReset.id.desc()))
    if latest and latest.pending_password_hash and latest.created_at>now-timedelta(seconds=60):
        raise HTTPException(429,"تم إرسال رابط تأكيد مؤخراً. تحقق من بريدك الإلكتروني قبل طلب رابط جديد")
    s.query(StorePasswordReset).filter(StorePasswordReset.customer_id==customer.id).delete(synchronize_session=False)
    token=secrets.token_urlsafe(36)
    row=StorePasswordReset(customer_id=customer.id,code_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),pending_password_hash=password_hash.hash(p.new_password),expires_at=now+timedelta(minutes=20))
    s.add(row);s.flush()
    link="https://aib-sy-global.onrender.com/shop#password_change_token="+token
    try:
        send_aib_email(customer.email,"تأكيد تغيير كلمة مرور حساب AIB",
            f"مرحباً {customer.full_name}، لتأكيد تغيير كلمة المرور افتح الرابط التالي خلال 20 دقيقة:\n{link}\nإذا لم تطلب هذا التغيير فتجاهل الرسالة.",
            f"<!doctype html><html lang='ar' dir='rtl'><meta charset='utf-8'><body style='font-family:Tahoma,Arial;background:#f2f5f7;padding:24px'><div style='max-width:520px;margin:auto;background:#fff;border:1px solid #e3e9ee;border-radius:16px;padding:28px;text-align:center;color:#243342'><h2>تأكيد تغيير كلمة المرور</h2><p>مرحباً {html.escape(customer.full_name)}، اضغط الزر أدناه لتأكيد كلمة المرور الجديدة.</p><a href='{html.escape(link,quote=True)}' style='display:inline-block;padding:14px 24px;border-radius:10px;background:#176b9b;color:#fff;text-decoration:none;font-weight:bold'>تأكيد تغيير كلمة المرور</a><p style='color:#718096;font-size:12px'>الرابط صالح لمدة 20 دقيقة ولمرة واحدة فقط.</p></div></body></html>")
    except Exception:
        s.rollback()
        raise
    s.commit()
    return {"ok":True,"message":"أرسلنا رابط تأكيد تغيير كلمة المرور إلى بريدك الإلكتروني. لن تتغير كلمة المرور قبل فتح الرابط."}

@app.post("/store/auth/change-password/confirm")
def confirm_store_password_change(p:StorePasswordChangeConfirmPayload, s:Session=Depends(db)):
    token_hash=hashlib.sha256(p.token.encode("utf-8")).hexdigest()
    row=s.scalar(select(StorePasswordReset).where(StorePasswordReset.code_hash==token_hash))
    now=datetime.now(timezone.utc)
    if not row or not row.pending_password_hash or row.expires_at<now or row.attempts>=5:
        raise HTTPException(400,"رابط التأكيد منتهي أو غير صالح. اطلب رابطاً جديداً")
    customer=s.get(StoreCustomer,row.customer_id)
    if not customer or not customer.active:
        raise HTTPException(400,"تعذر العثور على حساب نشط لهذا الرابط")
    customer.password_hash=row.pending_password_hash
    customer.failed_logins=0
    customer.locked_until=None
    s.query(StorePasswordReset).filter(StorePasswordReset.customer_id==customer.id).delete(synchronize_session=False)
    s.commit()
    send_notification_email(customer.email,"تنبيه أمان: تغيير كلمة مرور حساب AIB","تم تأكيد تغيير كلمة مرور حساب المتجر. إذا لم تكن أنت، تواصل مع إدارة AIB فوراً.")
    return {"ok":True,"message":"تم تأكيد الرابط وتغيير كلمة المرور بنجاح. يمكنك تسجيل الدخول بكلمة المرور الجديدة."}


def serialize_store_cart(s:Session, customer:StoreCustomer):
    prices=store_latest_prices(s)
    out=[]
    for item in customer.cart or []:
        if not isinstance(item,dict): continue
        product=s.get(InventoryProduct,int(item.get("product_id") or 0))
        if not product or not product.active or not product.is_store_visible: continue
        price=prices.get(product.sku,{})
        store_categories=latest_inventory_store_categories(s)
        explicit=store_categories.get(product.sku,{})
        out.append({"id":product.id,"sku":product.sku,"name":product.name,"model":product.model or "",
            "qty":int(item.get("quantity") or 1),"stock":float(product.owned_stock or 0)+float(product.consigned_stock or 0),
            "price":price.get("sale_price"),"currency":price.get("currency",""),
            "images":product.images or [],"category":store_product_category(product.name,product.model or ""),
            "store_family":explicit.get("store_family",""),"store_category":explicit.get("store_category",""),"vehicle_details":explicit.get("vehicle_details",{})})
    return out

@app.get("/store/cart")
def get_store_cart(s:Session=Depends(db), customer:StoreCustomer=Depends(current_store_customer)):
    return {"items":serialize_store_cart(s,customer)}

@app.put("/store/cart")
def save_store_cart(p:StoreCartPayload, request:Request, s:Session=Depends(db), customer:StoreCustomer=Depends(current_store_customer)):
    cleaned=[];seen=set()
    for item in p.items:
        if item.product_id in seen: continue
        seen.add(item.product_id)
        product=s.get(InventoryProduct,item.product_id)
        if not product or not product.active or not product.is_store_visible: raise HTTPException(404,"أحد المنتجات لم يعد متاحاً في المتجر")
        stock=float(product.owned_stock or 0)+float(product.consigned_stock or 0)
        if stock<=0: raise HTTPException(409,f"المنتج {product.name} غير متوفر حالياً")
        if item.quantity>stock: raise HTTPException(409,f"الكمية المطلوبة من {product.name} تتجاوز المخزون المتاح ({stock:g})")
        cleaned.append({"product_id":item.product_id,"quantity":item.quantity})
    customer.cart=cleaned
    s.commit()
    return {"ok":True,"items":serialize_store_cart(s,customer)}

@app.get("/store/customer-profile")
def get_store_customer_profile(customer:StoreCustomer=Depends(current_store_customer)):
    return {"first_name":customer.first_name,"last_name":customer.last_name,"shipping_address":customer.shipping_address,"phone_country_code":customer.phone_country_code,"phone_number":customer.phone_number}

@app.post("/store/orders")
def create_online_order(p:OnlineOrderPayload,s:Session=Depends(db),customer:StoreCustomer=Depends(current_store_customer)):
    try:
        header,encoded=p.payment_proof.split(",",1)
        if header not in ("data:image/jpeg;base64","data:image/png;base64","data:image/webp;base64","data:application/pdf;base64"):
            raise HTTPException(400,"صيغة إثبات الدفع غير مدعومة")
        raw=base64.b64decode(encoded,validate=True)
    except HTTPException: raise
    except Exception: raise HTTPException(400,"ملف إثبات الدفع غير صالح")
    if not raw or len(raw)>5*1024*1024: raise HTTPException(413,"الحد الأقصى لإثبات الدفع 5 ميغابايت")
    prices=store_latest_prices(s);store_categories=latest_inventory_store_categories(s);lines=[];currency=None;total=0;seen=set();has_full_vehicle=False
    for entry in p.items:
        if entry.product_id in seen: continue
        seen.add(entry.product_id);product=s.get(InventoryProduct,entry.product_id)
        if not product or not product.active or not product.is_store_visible: raise HTTPException(409,"أحد المنتجات غير متاح في المتجر")
        qty=int(entry.quantity);stock=float(product.owned_stock or 0)+float(product.consigned_stock or 0)
        if qty>stock: raise HTTPException(409,f"الكمية المطلوبة من {product.name} تتجاوز المخزون المتاح ({stock:g})")
        price=prices.get(product.sku)
        if not price or float(price.get("sale_price") or 0)<=0: raise HTTPException(409,"سعر أحد المنتجات غير محدد")
        if currency and currency!=price["currency"]: raise HTTPException(409,"لا يمكن جمع عملات مختلفة في طلب واحد")
        currency=price["currency"];unit=float(price["sale_price"]);total+=unit*qty
        catalog=store_categories.get(product.sku,{})
        if catalog.get("store_category") in {"cars","trucks","heavy","agri"}: has_full_vehicle=True
        lines.append({"product_id":product.id,"sku":product.sku,"description":product.name,"model":product.model or "","quantity":qty,"price":unit,"store_family":catalog.get("store_family",""),"store_category":catalog.get("store_category",""),"vehicle_details":catalog.get("vehicle_details",{})})
    if not lines: raise HTTPException(400,"السلة فارغة")
    if p.contract_identity and not has_full_vehicle: raise HTTPException(400,"بيانات العقد متاحة فقط عند شراء مركبة كاملة")
    if has_full_vehicle and not p.contract_identity: raise HTTPException(400,"لا يمكن إرسال طلب شراء مركبة كاملة دون معلومات عقد البيع وهوية العميل")
    contract_identity=None
    if p.contract_identity:
        allowed_identity=("first_name","last_name","father_name","mother_name","national_no","birth_place_date","id_type","id_no","id_issuer","registry","residence","address")
        contract_identity={k:str(p.contract_identity.get(k) or "").strip()[:500] for k in allowed_identity}
        if any(not contract_identity[k] for k in allowed_identity) or contract_identity["id_type"] not in {"هوية شخصية","جواز سفر"}:
            raise HTTPException(400,"يجب إكمال جميع بيانات هوية العميل والعقد قبل إرسال طلب الشراء")
    previous_profile={"full_name":customer.full_name,"shipping_address":customer.shipping_address,"phone_country_code":customer.phone_country_code,"phone_number":customer.phone_number}
    customer.first_name=p.first_name.strip();customer.last_name=p.last_name.strip();customer.full_name=(customer.first_name+" "+customer.last_name).strip()
    customer.shipping_address=p.shipping_address.strip();customer.phone_country_code=p.phone_country_code;customer.phone_number=p.phone_number.strip()
    data={"first_name":customer.first_name,"last_name":customer.last_name,"full_name":customer.full_name,"email":customer.email,"shipping_address":customer.shipping_address,"phone_country_code":customer.phone_country_code,"phone_number":customer.phone_number,"full_phone":customer.phone_country_code+customer.phone_number,"payment_method":p.payment_method,"include_contract_identity":bool(contract_identity),"contract_identity":contract_identity}
    order=OnlinePurchaseOrder(customer_id=customer.id,customer_data=data,items=lines,total=round(total,2),currency=currency or "USD",payment_proof=p.payment_proof,proof_type=p.proof_type,status="pending")
    s.add(order);s.commit();s.refresh(order)
    if any(previous_profile[k]!=(customer.full_name if k=="full_name" else customer.shipping_address if k=="shipping_address" else customer.phone_country_code if k=="phone_country_code" else customer.phone_number) for k in previous_profile):
        notify_account_change(customer.email,"تم تحديث بيانات الاسم أو عنوان الشحن أو رقم الهاتف أثناء إرسال طلب شراء")
    item_lines="\n".join(f"- {x['description']} ({x['sku']}) × {x['quantity']} = {x['price']*x['quantity']:.2f} {order.currency}" for x in lines)
    customer_message=(f"مرحباً {customer.full_name}،\nتم استلام طلب الشراء الإلكتروني رقم #{order.id} لدى مجموعة AIB.\n"
        f"المنتجات:\n{item_lines}\nالإجمالي: {float(order.total):.2f} {order.currency}\n"
        "الحالة: بانتظار مراجعة إثبات الدفع. سنرسل إليك تحديثاً عند اعتماد الطلب أو رفضه.")
    customer_html=aib_email_html("تم استلام طلبك بنجاح",f"مرحباً {customer.full_name}، استلمنا طلب الشراء الخاص بك، وسيقوم فريقنا بمراجعة إثبات الدفع وإبلاغك بالنتيجة.",[("رقم الطلب",f"#{order.id}"),("الإجمالي",f"{float(order.total):.2f} {html.escape(order.currency)}"),("حالة الطلب","بانتظار مراجعة إثبات الدفع")],note="احتفظ برقم الطلب لمتابعة حالته. لا يُعد الطلب معتمداً قبل مراجعة إثبات الدفع.")
    send_notification_email(customer.email,"تأكيد استلام طلب الشراء - مجموعة AIB",customer_message,customer_html)
    admin_email=settings.smtp_from or settings.smtp_user
    if admin_email:
        admin_body=(f"وصل طلب شراء جديد من {customer.full_name}\\nالبريد: {customer.email}\\nالهاتف: {data['full_phone']}\\n"
            f"الإجمالي: {float(order.total):.2f} {order.currency}\\nالمنتجات:\\n{item_lines}\\nيرجى مراجعة الطلب وإثبات الدفع من لوحة المحاسبة.")
        admin_html=aib_email_html(f"طلب شراء إلكتروني جديد #{order.id}","وصل طلب جديد من متجر AIB ويحتاج إلى مراجعة إثبات الدفع.",[("رقم الطلب",f"#{order.id}"),("العميل",html.escape(customer.full_name)),("البريد",html.escape(customer.email)),("الهاتف",html.escape(data["full_phone"])),("العنوان",html.escape(data["shipping_address"])),("بيانات العقد",html.escape((contract_identity or {}).get("first_name","") + " " + (contract_identity or {}).get("last_name","")) if contract_identity else "غير مضافة"),("الإجمالي",f"{float(order.total):.2f} {html.escape(order.currency)}")],accent="#168447",note="يرجى فتح بوابة المحاسبة لمراجعة الطلب والتحقق من إثبات الدفع.")
        send_notification_email(admin_email,f"طلب شراء إلكتروني جديد #{order.id} – AIB",admin_body,admin_html)
    return {"ok":True,"order_id":order.id,"customer":data,"items":lines,"total":float(order.total),"currency":order.currency,"status":order.status}


@app.get("/store/orders")
def list_customer_online_orders(s:Session=Depends(db),customer:StoreCustomer=Depends(current_store_customer)):
    rows=s.scalars(select(OnlinePurchaseOrder).where(OnlinePurchaseOrder.customer_id==customer.id).order_by(OnlinePurchaseOrder.created_at.desc(),OnlinePurchaseOrder.id.desc()).limit(100)).all()
    return [{"id":o.id,"items":o.items,"total":float(o.total),"currency":o.currency,"status":o.status,"review_note":o.review_note,"record_id":o.record_id,"created_at":o.created_at,"invoice_no":(s.get(Record,o.record_id).invoice_no if o.record_id and s.get(Record,o.record_id) else None)} for o in rows]

@app.get("/online-purchase-orders/count")
def count_online_purchase_orders(s:Session=Depends(db),u:User=Depends(manager)):
    pending=int(s.scalar(select(func.count(OnlinePurchaseOrder.id)).where(OnlinePurchaseOrder.status=="pending")) or 0)
    return {"pending":pending}

def _seller_confirmed_order_ids(s:Session,u:User):
    if u.role=="owner":
        return []
    rows=s.scalars(select(OnlinePurchaseOrder).where(
        OnlinePurchaseOrder.status.in_(("approved","shipping","delivered")),
        OnlinePurchaseOrder.record_id.is_not(None)
    )).all()
    ids=[]
    for order in rows:
        record=s.get(Record,order.record_id)
        if not record:
            continue
        lines=(record.data or {}).get("items",[])
        if any(
            item.get("owner_user_id")==u.id and float(item.get("user_owned_quantity") or 0)>0
            for item in lines
        ):
            ids.append(order.id)
    return ids

@app.get("/my-online-purchase-orders/count")
def count_my_online_purchase_orders(s:Session=Depends(db),u:User=Depends(current_user)):
    seen=set((u.profile_data or {}).get("online_order_seen_ids",[]))
    unread=sum(1 for order_id in _seller_confirmed_order_ids(s,u) if order_id not in seen)
    return {"total":unread}

@app.post("/my-online-purchase-orders/mark-viewed")
def mark_my_online_purchase_orders_viewed(s:Session=Depends(db),u:User=Depends(current_user)):
    if u.role=="owner":
        return {"ok":True,"marked":0}
    profile=dict(u.profile_data or {})
    seen=set(int(x) for x in profile.get("online_order_seen_ids",[]) if str(x).isdigit())
    current=set(_seller_confirmed_order_ids(s,u))
    new_ids=current-seen
    if new_ids:
        profile["online_order_seen_ids"]=sorted(seen|current)
        u.profile_data=profile
        s.commit()
    return {"ok":True,"marked":len(new_ids)}

@app.delete("/online-purchase-orders/{order_id}")
def delete_online_purchase_order(order_id:int,s:Session=Depends(db),u:User=Depends(manager)):
    order=s.get(OnlinePurchaseOrder,order_id)
    if not order: raise HTTPException(404,"الطلب غير موجود")
    if order.record_id is not None or order.status=="approved":
        raise HTTPException(409,"لا يمكن حذف طلب تم اعتماده وربطه بفاتورة؛ احتفظ بسجل الطلب والفاتورة")
    audit(s,u,"online_order_deleted","online_purchase_order",order.id,{"status":order.status,"record_id":order.record_id},request=None)
    s.delete(order)
    s.commit()
    return {"ok":True,"deleted_order_id":order_id}

@app.get("/online-purchase-orders")
def list_online_purchase_orders(s:Session=Depends(db),u:User=Depends(current_user)):
    owner_phone="+963 997 439 627"
    rows=s.scalars(select(OnlinePurchaseOrder).order_by(OnlinePurchaseOrder.id.desc())).all()
    result=[]
    for o in rows:
        customer=dict(o.customer_data or {})
        order_items=list(o.items or [])
        seller_total=float(o.total)
        if u.role!="owner":
            # Seller views are limited to their own inventory quantities on paid orders.
            record=s.get(Record,o.record_id) if o.record_id else None
            approved_lines=(record.data or {}).get("items",[]) if record else []
            seller_lines=[]
            for item in approved_lines:
                if item.get("owner_user_id")!=u.id:
                    continue
                owned_qty=float(item.get("user_owned_quantity") or 0)
                if owned_qty<=0:
                    continue
                seller_line=dict(item)
                seller_line["quantity"]=owned_qty
                seller_lines.append(seller_line)
            if not seller_lines or o.status not in {"approved","shipping","delivered"}:
                continue
            order_items=seller_lines
            seller_total=round(sum(float(x.get("quantity") or 0)*float(x.get("price") or 0) for x in seller_lines),2)
            customer={k:customer.get(k) for k in ("first_name","last_name","full_name","email","shipping_address","full_phone") if customer.get(k) is not None}
        result.append({"id":o.id,"customer":customer,"owner_phone":owner_phone,"items":order_items,"total":seller_total,"currency":o.currency,"payment_proof":o.payment_proof if u.role=="owner" else None,"proof_type":o.proof_type,"status":o.status,"record_id":o.record_id,"invoice_no":(s.get(Record,o.record_id).invoice_no if o.record_id and s.get(Record,o.record_id) else None),"review_note":o.review_note,"created_at":o.created_at})
    return result

class OnlineOrderReviewPayload(BaseModel):
    action: str
    note: str = ""

@app.post("/online-purchase-orders/{order_id}/review")
def review_online_purchase_order(order_id:int,p:OnlineOrderReviewPayload,s:Session=Depends(db),u:User=Depends(manager)):
    order=s.scalar(select(OnlinePurchaseOrder).where(OnlinePurchaseOrder.id==order_id).with_for_update())
    if not order: raise HTTPException(404,"الطلب غير موجود")
    if order.status!="pending": raise HTTPException(409,"تمت مراجعة الطلب")
    if p.action=="reject":
        order.status="rejected";order.review_note=p.note or "إثبات الدفع غير مقبول";order.reviewed_by=u.id;order.reviewed_at=datetime.now(timezone.utc);s.commit()
        customer_email=(order.customer_data or {}).get("email")
        rejection_body=f"تمت مراجعة طلب الشراء رقم #{order.id} ولم تتم الموافقة على إثبات الدفع.\\nملاحظة الإدارة: {order.review_note}"
        rejection_html=aib_email_html(f"تحديث حالة الطلب #{order.id}","نأسف لإبلاغك بأنه لم تتم الموافقة على إثبات الدفع المرفق. يرجى مراجعة الملاحظة أدناه والتواصل مع فريق AIB عند الحاجة.",[("رقم الطلب",f"#{order.id}"),("الحالة","لم تتم الموافقة على إثبات الدفع"),("ملاحظة الإدارة",html.escape(order.review_note))],accent="#b94a48",note="يمكنك التواصل مع فريقنا لتوضيح سبب الرفض قبل إعادة إرسال الطلب.")
        send_notification_email(customer_email,f"تحديث طلب الشراء #{order.id} - مجموعة AIB",rejection_body,rejection_html)
        return {"ok":True,"status":"rejected"}
    if p.action!="approve": raise HTTPException(400,"إجراء غير صالح")
    allocated_items=[]
    for x in order.items:
        product=s.scalar(select(InventoryProduct).where(InventoryProduct.sku==str(x["sku"]).strip().upper()).with_for_update())
        if not product or not product.active: raise HTTPException(409,f"المنتج {x.get('description') or x['sku']} لم يعد متاحاً")
        qty=float(x["quantity"])
        owned=float(product.owned_stock or 0)
        consigned=float(product.consigned_stock or 0)
        available=owned+consigned
        if qty>available+0.0001:
            raise HTTPException(409,f"المخزون تغيّر منذ إرسال الطلب. المتاح من {product.name} حالياً {available:g}")
        from_owned=min(qty,owned)
        from_consigned=qty-from_owned
        allocated_items.append({"sku":x["sku"],"description":x["description"],"model":x.get("model",""),"quantity":qty,"price":x["price"],"owned_quantity":from_owned,"consigned_quantity":from_consigned,"owner_user_id":product.owner_user_id if from_owned>0 else None,"user_owned_quantity":from_owned if product.owner_user_id else 0})
    data={"customer":order.customer_data["full_name"],"customer_phone":order.customer_data["full_phone"],"customer_address":order.customer_data["shipping_address"],"amount":float(order.total),"items":allocated_items,"notes":"طلب إلكتروني – تم التحقق من إثبات الدفع واعتماده"}
    identity=(order.customer_data or {}).get("contract_identity") or {}
    if identity:
        data.update({"include_buyer_identity":True,"buyer_first_name":identity.get("first_name",""),"buyer_last_name":identity.get("last_name",""),"buyer_father_name":identity.get("father_name",""),"buyer_mother_name":identity.get("mother_name",""),"buyer_national_no":identity.get("national_no",""),"buyer_birth_place_date":identity.get("birth_place_date",""),"buyer_id_type":identity.get("id_type",""),"buyer_id_no":identity.get("id_no",""),"buyer_id_issuer":identity.get("id_issuer",""),"buyer_registry":identity.get("registry",""),"buyer_residence":identity.get("residence",""),"buyer_address":identity.get("address","")})
    prepared=prepare_record_inventory(s,"directSale",data)
    s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"),{"key":"aib-invoice:directSale"})
    serial=int(s.scalar(select(func.count(Record.id)).where(Record.section=="directSale")) or 0)+1
    record=Record(section="directSale",invoice_no=f"A-{serial:05d}-B",currency=order.currency,data=prepared,created_by=u.id)
    s.add(record);s.flush();recalculate_inventory(s)
    payment=InvoicePayment(record_id=record.id,amount=order.total,method="sham_cash",cash_box="شام كاش",created_by=u.id)
    s.add(payment)
    s.add(CashMove(box_name="شام كاش",movement="deposit",amount=order.total,currency=order.currency,description="قبض فاتورة طلب شراء إلكتروني "+record.invoice_no,created_by=u.id,record_id=record.id))
    # Settle only the quantity drawn from a user's owned inventory. Owner stock and consigned stock do not earn an employee wallet credit.
    seller_totals={}
    for line in allocated_items:
        seller_id=line.get("owner_user_id")
        seller_qty=float(line.get("user_owned_quantity") or 0)
        if not seller_id or seller_qty<=0: continue
        gross=round(seller_qty*float(line.get("price") or 0),2)
        if gross<=0: continue
        bucket=seller_totals.setdefault(int(seller_id),{"gross":0.0,"items":[]})
        bucket["gross"]=round(bucket["gross"]+gross,2)
        bucket["items"].append({"sku":line["sku"],"quantity":seller_qty,"gross":gross})
    total_owner_commission=0.0
    for seller_id,amounts in seller_totals.items():
        seller=s.get(User,seller_id)
        if not seller or seller.deleted or seller.role=="owner":
            raise HTTPException(409,"تعذر تحديد صاحب أحد منتجات المستخدمين؛ لم يتم اعتماد الطلب")
        amounts["rate_percent"]=round(float(seller.owner_commission_rate if seller.owner_commission_rate is not None else 1.5),3)
        amounts["commission"]=round(amounts["gross"]*amounts["rate_percent"]/100,2)
        amounts["net"]=round(amounts["gross"]-amounts["commission"],2)
        ensure_user_wallets(s,seller.id)
        seller_wallet=s.scalar(select(UserWallet).where(UserWallet.user_id==seller.id,UserWallet.currency==order.currency).with_for_update())
        if not seller_wallet: raise HTTPException(500,"تعذر تجهيز محفظة صاحب المنتج")
        # Credit the full product value first, then record the store commission as a separate wallet deduction.
        seller_wallet.balance=round(float(seller_wallet.balance or 0)+amounts["gross"],2)
        seller_wallet.updated_at=datetime.now(timezone.utc)
        s.add(WalletTransaction(wallet_id=seller_wallet.id,user_id=seller.id,amount=amounts["gross"],currency=order.currency,direction="in",reason=f"إضافة كامل قيمة بيع منتجاتك عبر المتجر · طلب #{order.id} · فاتورة {record.invoice_no}",reference_type="store_order_seller_gross",reference_id=record.id,created_by=u.id))
        if amounts["commission"]>0:
            seller_wallet.balance=round(float(seller_wallet.balance or 0)-amounts["commission"],2)
            seller_wallet.updated_at=datetime.now(timezone.utc)
            s.add(WalletTransaction(wallet_id=seller_wallet.id,user_id=seller.id,amount=amounts["commission"],currency=order.currency,direction="out",reason=f"اقتطاع عمولة المتجر {amounts['rate_percent']:g}% · طلب #{order.id} · فاتورة {record.invoice_no}",reference_type="store_order_seller_commission",reference_id=record.id,created_by=u.id))
        total_owner_commission=round(total_owner_commission+amounts["commission"],2)
    if total_owner_commission>0:
        owner=s.scalar(select(User).where(User.role=="owner",User.deleted.is_(False)).order_by(User.id).limit(1))
        if not owner: raise HTTPException(500,"تعذر العثور على حساب المالك لإضافة عمولة المتجر")
        ensure_user_wallets(s,owner.id)
        owner_wallet=s.scalar(select(UserWallet).where(UserWallet.user_id==owner.id,UserWallet.currency==order.currency).with_for_update())
        if not owner_wallet: raise HTTPException(500,"تعذر تجهيز محفظة المالك")
        owner_wallet.balance=round(float(owner_wallet.balance or 0)+total_owner_commission,2)
        owner_wallet.updated_at=datetime.now(timezone.utc)
        s.add(WalletTransaction(wallet_id=owner_wallet.id,user_id=owner.id,amount=total_owner_commission,currency=order.currency,direction="in",reason=f"عمولة المستخدمين حسب النسب المحددة لكل حساب · طلب #{order.id} · فاتورة {record.invoice_no}",reference_type="store_order_owner_commission",reference_id=record.id,created_by=u.id))
    order.status="approved";order.record_id=record.id;order.reviewed_by=u.id;order.reviewed_at=datetime.now(timezone.utc);order.review_note=p.note
    audit(s,u,"online_order_approved","online_purchase_order",order.id,{"record_id":record.id,"invoice_no":record.invoice_no,"payment_method":"sham_cash"},request=None)
    s.commit()
    customer_email=(order.customer_data or {}).get("email")
    approval_body=f"تم اعتماد طلب الشراء رقم #{order.id} بعد مراجعة إثبات الدفع.\\nرقم فاتورة المبيع: {record.invoice_no}\\nالإجمالي: {float(order.total):.2f} {order.currency}"
    approval_html=aib_email_html("تم اعتماد طلبك بنجاح",f"مرحباً {(order.customer_data or {}).get('full_name','')}، تمت مراجعة إثبات الدفع واعتماد طلبك. شكراً لثقتك بمجموعة AIB.",[("رقم الطلب",f"#{order.id}"),("رقم الفاتورة",html.escape(record.invoice_no)),("الإجمالي",f"{float(order.total):.2f} {html.escape(order.currency)}"),("الحالة","تم اعتماد الطلب")],accent="#168447",note="احتفظ برقم الفاتورة لمتابعة طلبك. سيقوم فريقنا بالتواصل معك بشأن التسليم.")
    send_notification_email(customer_email,f"تم اعتماد طلب الشراء #{order.id} - مجموعة AIB",approval_body,approval_html)
    # Notify each actual product owner only after the payment approval and wallet settlement have committed.
    buyer=dict(order.customer_data or {})
    for seller_id,amounts in seller_totals.items():
        seller=s.get(User,seller_id)
        if not seller or not (seller.email or "").strip():
            continue
        seller_lines=[line for line in allocated_items if line.get("owner_user_id")==seller_id and float(line.get("user_owned_quantity") or 0)>0]
        seller_item_text="\n".join(f"- {line['description']} ({line['sku']}) × {float(line['user_owned_quantity']):g} = {float(line['user_owned_quantity'])*float(line['price']):.2f} {order.currency}" for line in seller_lines)
        buyer_name=str(buyer.get("full_name") or (str(buyer.get("first_name") or "")+" "+str(buyer.get("last_name") or "")).strip())
        buyer_phone=str(buyer.get("full_phone") or ((buyer.get("phone_country_code") or "")+(buyer.get("phone_number") or "")))
        seller_body=(f"تم تأكيد الدفع للطلب الإلكتروني رقم #{order.id}.\nرقم الفاتورة: {record.invoice_no}\n"
            f"اسم المستلم: {buyer_name}\nعنوان المستلم: {buyer.get('shipping_address') or 'غير متوفر'}\n"
            f"رقم هاتف المستلم: {buyer_phone or 'غير متوفر'}\nالمنتجات المباعة من مخزونك:\n{seller_item_text}\n"
            f"إجمالي قيمة منتجاتك: {amounts['gross']:.2f} {order.currency}\n"
            f"عمولة المالك {amounts['rate_percent']:g}%: {amounts['commission']:.2f} {order.currency}\n"
            f"صافي المبلغ المضاف إلى محفظتك: {amounts['net']:.2f} {order.currency}")
        seller_html=aib_email_html(f"تم بيع منتجاتك – الطلب #{order.id}",
            "تم تأكيد الدفع بنجاح، وهذه تفاصيل المستلم والمنتجات التي بيعت من مخزونك.",
            [("رقم الطلب",f"#{order.id}"),("رقم الفاتورة",html.escape(record.invoice_no)),
             ("اسم المستلم",html.escape(buyer_name)),("عنوان المستلم",html.escape(str(buyer.get("shipping_address") or "غير متوفر"))),
             ("هاتف المستلم",html.escape(buyer_phone or "غير متوفر")),("المنتجات المباعة",html.escape(seller_item_text).replace("\n","<br>")),
             ("إجمالي قيمة منتجاتك",f"{amounts['gross']:.2f} {html.escape(order.currency)}"),
             (f"عمولة المالك {amounts['rate_percent']:g}%",f"{amounts['commission']:.2f} {html.escape(order.currency)}"),
             ("صافي المبلغ المضاف لمحفظتك",f"{amounts['net']:.2f} {html.escape(order.currency)}")],
            accent="#168447",note="يمكنك مراجعة تفاصيل الطلب وطباعة فاتورة الطلب من صفحة طلبات الشراء عبر الإنترنت في تطبيق AIB.")
        send_notification_email(seller.email,f"تم بيع منتج من مخزونك – طلب #{order.id} | AIB",seller_body,seller_html)
    return {"ok":True,"status":"approved","record_id":record.id,"invoice_no":record.invoice_no,"customer":order.customer_data}


class OnlineOrderStatusPayload(BaseModel):
    status: str
    note: str = ""

@app.put("/online-purchase-orders/{order_id}/status")
def update_online_purchase_order_status(order_id:int,p:OnlineOrderStatusPayload,s:Session=Depends(db),u:User=Depends(manager)):
    if p.status not in {"shipping","delivered"}:
        raise HTTPException(400,"الحالة المطلوبة غير مدعومة")
    order=s.get(OnlinePurchaseOrder,order_id)
    if not order: raise HTTPException(404,"الطلب غير موجود")
    if order.status not in {"approved","shipping"}:
        raise HTTPException(409,"يجب اعتماد الطلب أولاً قبل تحديث حالة الشحن")
    if p.status=="delivered" and order.status!="shipping":
        raise HTTPException(409,"يجب تحويل الطلب إلى حالة الشحن أولاً")
    order.status=p.status
    if p.note.strip(): order.review_note=p.note.strip()
    s.commit()
    customer_email=(order.customer_data or {}).get("email")
    status_label="طلبك في الشحن" if p.status=="shipping" else "تم تسليم طلبك"
    status_html=aib_email_html(status_label,f"مرحباً {(order.customer_data or {}).get('full_name','')}، تم تحديث حالة طلبك لدى مجموعة AIB.",[("رقم الطلب",f"#{order.id}"),("الحالة","في الشحن" if p.status=="shipping" else "تم التسليم")],accent="#2476b9")
    send_notification_email(customer_email,f"تحديث حالة الطلب #{order.id} - مجموعة AIB",status_label,status_html)
    return {"ok":True,"status":order.status}

def _normalize_public_search_query(value: Optional[str]) -> str:
    """Unwrap list-shaped query strings emitted by callers; keep ordinary text unchanged."""
    raw = str(value or "").strip()
    if len(raw) >= 2 and raw.startswith("[") and raw.endswith("]"):
        try:
            parsed = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            parsed = None
        if isinstance(parsed, (list, tuple)):
            terms = [
                str(item).strip()
                for item in parsed
                if isinstance(item, (str, int, float)) and str(item).strip()
            ]
            return " ".join(terms)
    return raw


@app.get("/public/products")
def public_products(q:Optional[str]=None, category:Optional[str]=None, response:Response=None, s:Session=Depends(db)):
    import time
    started=time.perf_counter()
    q = _normalize_public_search_query(q)
    cache_key=((q or "").strip().casefold(),(category or "").strip().casefold())
    now=time.monotonic()
    cached=_public_products_cache["value"].get(cache_key)
    if cached is not None and now-_public_products_cache["at"].get(cache_key,0)<_PUBLIC_PRODUCTS_CACHE_TTL:
        elapsed_ms=(time.perf_counter()-started)*1000
        if response is not None:
            response.headers["X-AIB-Search-Cache"]="HIT"
            response.headers["Server-Timing"]=f"total;dur={elapsed_ms:.2f}"
        logging.getLogger("aib.search").info(
            "public_products_search cache=hit category=%s query_length=%d results=%d total_ms=%.2f",
            (category or "")[:60],len((q or "").strip()),len(cached),elapsed_ms,
        )
        return cached
    query_started=time.perf_counter()
    query=select(InventoryProduct).where(InventoryProduct.active.is_(True),InventoryProduct.is_store_visible.is_(True))
    if q:
        term=f"%{q.strip()}%"
        query=query.where(or_(InventoryProduct.sku.ilike(term),InventoryProduct.name.ilike(term),InventoryProduct.model.ilike(term)))
    rows=s.scalars(query.order_by(InventoryProduct.sku).limit(300)).all()
    query_ms=(time.perf_counter()-query_started)*1000
    # Match the inventory page's visibility rule exactly: employee-owned products
    # belong to that employee's inventory; legacy/owner products are visible only
    # when referenced by a non-deleted invoice. This prevents stale/orphaned
    # catalog rows from appearing in the public storefront.
    invoiced_skus={
        str(value).strip().upper()
        for value in s.execute(text("""
            SELECT DISTINCT UPPER(BTRIM(item->>'sku'))
            FROM records AS r
            CROSS JOIN LATERAL jsonb_array_elements(
                CASE
                    WHEN jsonb_typeof(CAST(r.data AS JSONB)->'items')='array'
                    THEN CAST(r.data AS JSONB)->'items'
                    ELSE '[]'::jsonb
                END
            ) AS item
            WHERE r.deleted IS FALSE
              AND NULLIF(BTRIM(item->>'sku'),'') IS NOT NULL
        """)).scalars().all()
    }
    rows=[
        p for p in rows
        if p.owner_user_id is not None
        or str(p.sku or "").strip().upper() in invoiced_skus
    ]
    visibility_ms=(time.perf_counter()-query_started)*1000-query_ms
    catalog_started=time.perf_counter()
    store_categories,latest_purchase=latest_store_catalog_data(s)
    catalog_ms=(time.perf_counter()-catalog_started)*1000
    out=[]
    for p in rows:
        name=(p.name+" "+(p.model or "")).lower()
        heavy_terms=["حفار","حفارة","excavator","تركس","لودر","loader","كاتربلر","caterpillar","volvo ec","hyundai r","بلدوزر","جرافة"]
        agri_terms=["زراعي","زراعية","جرار","تركتور","tractor","combine","حصادة","حصادات","harvester"]
        truck_terms=["شاحنة","truck","fh","scania","قاطر","رأس قاطر","مرسيدس اكتروس","actros","volvo fh"]
        car_terms=["سيارة","سياحية","sedan","bmw","mercedes","hyundai","kia","toyota","volkswagen","audi","škoda","skoda","نيسان","هوندا"]
        engine_terms=["محرك","مكينة","engine","motor"]
        engine_part_terms=["قطع محركات","قطع المحرك","قطع محرك","بستم","مكبس","شنبر","رنج","صباب","بلوف","راس محرك","رأس محرك","وش سلندر","جوان","كرتير","عمود كرنك","كرنك","طرمبة زيت","طرمبة ماء","oil pump","piston","liner","valve","gasket","crankshaft","cylinder head"]
        part_terms=["قطع","قطعة","فلتر","فلتر","حساس","بخاخ","انجكتر","injector","طرمبة","مضخة","رمان","bearing","سير","belt","كلتش","clutch","فرامل","brake","ديسك","جلدة","خرطوم","hose","gearbox","جير","دفرنس","ناقل"]
        is_engine=any(x in name for x in engine_terms)
        is_engine_part=is_engine and any(x in name for x in engine_part_terms)
        is_part=any(x in name for x in part_terms)
        car_engine_model_prefixes=("N20","N47","N57","N63","B47","B48","B57","B58","M47","M54","M57","M62","S63")
        is_known_car_engine=any((p.model or "").strip().upper().startswith(prefix) for prefix in car_engine_model_prefixes)
        if any(x in name for x in agri_terms): family="agri"
        elif any(x in name for x in heavy_terms): family="heavy"
        elif any(x in name for x in truck_terms): family="truck"
        elif any(x in name for x in car_terms) or is_known_car_engine: family="car"
        else: family="other"
        if family=="other":
            if is_engine: cat="engines"
            elif is_part: cat="parts"
            else: cat="parts"
        elif is_engine_part: cat=family+"_engine_parts"
        elif is_engine: cat=family+"_engines"
        elif is_part: cat=family+"_parts"
        elif family=="car": cat="cars"
        elif family=="truck": cat="trucks"
        elif family=="heavy": cat="heavy"
        else: cat="agri"
        explicit_category=store_categories.get(p.sku,{})
        if p.store_family and p.store_category:
            family=p.store_family
            cat=p.store_category
        elif explicit_category:
            family=explicit_category["store_family"]
            cat=explicit_category["store_category"]
        if category:
            # Preserve legacy landing-page filters while supporting exact shop subcategories.
            legacy_groups = {
                "parts": {"car_parts", "car_engine_parts", "truck_parts", "truck_engine_parts", "heavy_parts", "heavy_engine_parts", "agri_parts", "agri_engine_parts"},
                "engines": {"car_engines", "car_engine_parts", "truck_engines", "truck_engine_parts", "heavy_engines", "heavy_engine_parts", "agri_engines", "agri_engine_parts"},
                "heavy": {"heavy", "heavy_parts", "heavy_engines", "heavy_engine_parts"},
            }
            if category in legacy_groups:
                if cat not in legacy_groups[category]: continue
            elif cat != category:
                # Exact shop subcategories do not duplicate their products into parent categories.
                continue
        stock=float(p.owned_stock or 0)+float(p.consigned_stock or 0)
        price=latest_purchase.get(p.sku,{})
        product_details={**(store_categories.get(p.sku,{}).get("vehicle_details") or {}),**(p.vehicle_details or {})}
        out.append({"id":p.id,"sku":p.sku,"name":p.name,"model":p.model,"description":p.description or "","category":cat,"stock":stock,"condition":p.condition or "new","manufacturer":product_details.get("manufacturer") or product_details.get("vehicle_make") or "","fuel_type":product_details.get("vehicle_fuel") or product_details.get("fuel_type") or "","images":[f"/public/products/{p.id}/image/{i}?v={int(now*1000)}" for i in range(len(p.images or []))],"video_url":p.video_url or "","shipping_included":bool(p.shipping_included),"vehicle_details":product_details,"sale_price":float(p.sale_price) if p.sale_price is not None else price.get("sale_price"),"currency":p.sale_currency if p.sale_price is not None else price.get("currency","")})
    # Bound memory and retain only a short freshness window so stock/price edits appear quickly.
    if len(_public_products_cache["value"])>=_PUBLIC_PRODUCTS_CACHE_MAX:
        _public_products_cache["value"].clear();_public_products_cache["at"].clear()
    _public_products_cache["value"][cache_key]=out
    _public_products_cache["at"][cache_key]=now
    total_ms=(time.perf_counter()-started)*1000
    if response is not None:
        response.headers["X-AIB-Search-Cache"]="MISS"
        response.headers["Server-Timing"]=(
            f"products_db;dur={query_ms:.2f}, "
            f"visibility;dur={visibility_ms:.2f}, "
            f"catalog;dur={catalog_ms:.2f}, total;dur={total_ms:.2f}"
        )
    logging.getLogger("aib.search").info(
        "public_products_search cache=miss category=%s query_length=%d results=%d "
        "products_db_ms=%.2f visibility_ms=%.2f catalog_ms=%.2f total_ms=%.2f",
        (category or "")[:60],len((q or "").strip()),len(out),
        query_ms,visibility_ms,catalog_ms,total_ms,
    )
    return out

# Serve the connected responsive web app from the same origin as the API.
from pathlib import Path
from fastapi.responses import FileResponse, Response
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

@app.get("/customer-i18n.js", include_in_schema=False)
def customer_i18n_script():
    return FileResponse(
        FRONTEND_DIR / "customer-i18n.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"},
    )

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(FRONTEND_DIR / "store.html")

@app.get("/shop", include_in_schema=False)
def shop_page():
    return FileResponse(
        FRONTEND_DIR / "shop.html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"},
    )

@app.get("/data/{filename}", include_in_schema=False)
def public_reference_data(filename: str):
    # Only expose the two curated public reference catalogues; never serve arbitrary files.
    allowed = {"vehiclesdb-catalog.json", "tractor-brands.json", "heavy-equipment-brands.json", "manufacturers.json"}
    if filename not in allowed:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Reference data not found")
    path = (FRONTEND_DIR / "data" / filename).resolve()
    if path.parent != (FRONTEND_DIR / "data").resolve() or not path.is_file():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Reference data not found")
    return FileResponse(
        path,
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=86400"},
    )

@app.get("/accounting", include_in_schema=False)
def accounting_app():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/sham_cash_qr.png", include_in_schema=False)
def sham_cash_qr():
    return FileResponse(FRONTEND_DIR / "sham_cash_qr.png", media_type="image/png")

@app.get("/aib-logo.png", include_in_schema=False)
@app.get("/aib-logo.webp", include_in_schema=False)
def aib_original_logo():
    # Serve the original transparent AIB WebP asset directly from the same
    # frontend directory copied into the production Docker image.
    # The latest user-uploaded original AIB logo is a transparent PNG.
    logo_path = FRONTEND_DIR / "file_00000000d68c81f490ddf34ada4cb0b8.png"
    if not logo_path.is_file():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="AIB logo asset not found")
    return FileResponse(
        logo_path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300"},
    )

@app.get("/logos/{filename}", include_in_schema=False)
def brand_logo(filename: str):
    allowed_logos = {
        "aib-group-logo.webp",
        "ibrahim-trucks-logo.webp",
        "mohamed-alshaibani-home-appliances-logo.webp",
    }
    if filename not in allowed_logos:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(
        FRONTEND_DIR / "logos" / filename,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/logo.jpg", include_in_schema=False)
def logo_jpg():
    return FileResponse(FRONTEND_DIR / "logo.jpg", media_type="image/jpeg", headers={"Cache-Control": "public, max-age=3600"})

@app.get("/logo.png", include_in_schema=False)
def logo_png():
    return FileResponse(FRONTEND_DIR / "logo.png", media_type="image/png")

@app.get("/logo.svg", include_in_schema=False)
def logo_svg():
    return FileResponse(FRONTEND_DIR / "logo.svg", media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})


@app.get("/accounting-portal", include_in_schema=False)
def accounting_portal():
    return FileResponse(FRONTEND_DIR / "accounting-portal.html")


# Google Gemini assistant endpoints. API credentials remain server-side only.
class GeminiChatPayload(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)

class GeminiImageSearchPayload(BaseModel):
    image_base64: str = Field(min_length=1, max_length=12000000)
    mime_type: str = Field(default="image/jpeg", max_length=100)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)

class GeminiVoicePayload(BaseModel):
    audio_base64: str = Field(min_length=1, max_length=12000000)
    mime_type: str = Field(default="audio/webm", max_length=100)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)

_gemini_rate_limits = {}

def _gemini_reply(message: str, history: list[dict[str, str]], system_prompt: str) -> str:
    if not settings.gemini_api_key:
        raise HTTPException(503, "مساعد Gemini غير مفعّل بعد. أضف GEMINI_API_KEY في إعدادات Render.")
    now = datetime.now(timezone.utc).timestamp()
    # A lightweight per-process guard against accidental repeated requests.
    key = "global"
    recent = [stamp for stamp in _gemini_rate_limits.get(key, []) if now - stamp < 60]
    if len(recent) >= 50:
        raise HTTPException(429, "تم تجاوز عدد الطلبات مؤقتاً. حاول بعد دقيقة.")
    recent.append(now)
    _gemini_rate_limits[key] = recent
    contents = []
    for item in history[-12:]:
        role = item.get("role", "")
        text_value = str(item.get("text", ""))[:4000]
        if role in ("user", "model") and text_value.strip():
            contents.append({"role": role, "parts": [{"text": text_value}]})
    contents.append({"role": "user", "parts": [{"text": message.strip()}]})
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 900}
    }
    req = UrlRequest(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": settings.gemini_api_key},
        method="POST"
    )
    try:
        with urlopen(req, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 429:
            raise HTTPException(429, "وصلنا إلى حد الاستخدام المؤقت لدى Google. حاول لاحقاً.")
        if exc.code in (401, 403):
            raise HTTPException(502, "تعذر التحقق من مفتاح Gemini. راجع قيمة GEMINI_API_KEY في Render.")
        if exc.code >= 500:
            raise HTTPException(503, "خدمة Gemini مشغولة حالياً. حاول بعد قليل.")
        raise HTTPException(502, "تعذر إكمال طلب Gemini. تحقق من إعدادات المفتاح والطراز.")
    except (URLError, TimeoutError):
        raise HTTPException(504, "انتهت مهلة الاتصال بخدمة Gemini. حاول مجدداً.")
    except Exception:
        raise HTTPException(502, "حدث خطأ أثناء الاتصال بمساعد Gemini.")
    candidates = result.get("candidates") or []
    parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
    answer = "\n".join(str(part.get("text", "")) for part in parts if part.get("text"))
    if not answer.strip():
        raise HTTPException(502, "لم يُرجع Gemini إجابة نصية. أعد صياغة السؤال.")
    return answer.strip()

def _store_inventory_search(s: Session, message: str) -> list[dict]:
    """Search the full active store catalogue using short Arabic/English keywords."""
    normalized = _normalize_order_search(message)
    stop_words = {
        "اريد","ابغي","ابحث","بحث","عن","لي","من","في","متجر","المتجر","قسم",
        "رجاء","لو","سمحت","هل","يوجد","موجود","متوفر","شراء","طلب","السعر",
        "كم","تفاصيل","اعرض","وريني","اظهر","هات","جيب","عندي","عندكم",
        "please","find","search","show","get","want","need","the","for","me"
    }
    raw_tokens = [x for x in normalized.split() if len(x) > 1 and x not in stop_words]
    if not raw_tokens:
        return []

    # Expand everyday customer wording to the terms used in inventory records/categories.
    synonym_groups = [
        ("محرك","محركات","مكينة","مكينه","موتور","engine","motor"),
        ("جير","قير","فتيس","علبة","علب","سرعة","gearbox","transmission"),
        ("سيارة","سيارات","مركبة","مركبات","سياحية","car","cars","vehicle"),
        ("شاحنة","شاحنات","تريلا","قاطرة","رأس","truck","trucks","lorry"),
        ("حفارة","حفارات","حفار","بوكلين","تركس","لودر","بلدوزر","excavator","loader"),
        ("جرار","جرارات","تركتور","زراعي","زراعية","tractor","agricultural"),
        ("مولد","مولدة","مولدات","كهرباء","generator","generators"),
        ("مضخة","مضخات","طرمبة","طلمبة","pump","pumps"),
        ("قطع","قطعة","غيار","سبير","spare","parts"),
        ("بستم","مكبس","piston"),("بخاخ","انجكتر","injector"),
        ("فلتر","مرشح","filter"),("فرامل","بريك","brake"),
        ("باب","ابواب","أبواب","door"),("كشاف","مصباح","ضوء","headlight"),
    ]
    expanded = set(raw_tokens)
    for group in synonym_groups:
        normalized_group = {_normalize_order_search(x) for x in group}
        if expanded.intersection(normalized_group):
            expanded.update(normalized_group)
    tokens = list(expanded)

    rows = s.scalars(select(InventoryProduct).where(
        InventoryProduct.active.is_(True)
    ).order_by(InventoryProduct.sku).limit(500)).all()
    store_categories, latest_purchase = latest_store_catalog_data(s)

    category_labels = {
        "cars":"سيارات مركبات سياحية","trucks":"شاحنات","heavy":"معدات ثقيلة حفارات",
        "agri":"معدات زراعية جرارات","car_parts":"قطع غيار سيارات",
        "car_engines":"محركات سيارات","car_engine_parts":"قطع محركات سيارات",
        "truck_parts":"قطع غيار شاحنات","truck_engines":"محركات شاحنات",
        "truck_engine_parts":"قطع محركات شاحنات","heavy_parts":"قطع غيار معدات ثقيلة",
        "heavy_engines":"محركات معدات ثقيلة","heavy_engine_parts":"قطع محركات معدات ثقيلة",
        "agri_parts":"قطع غيار جرارات معدات زراعية","agri_engines":"محركات جرارات",
        "agri_engine_parts":"قطع محركات جرارات","generators":"مولدات كهربائية",
        "water_pumps":"مضخات مياه","hydraulic_compressors":"ضواغط هيدروليك",
        "road_equipment":"معدات طرق","special_parts":"قطع غيار متنوعة",
        "special_engines":"محركات متنوعة","parts":"قطع غيار","engines":"محركات"
    }
    scored = []
    for p in rows:
        stock = float(p.owned_stock or 0) + float(p.consigned_stock or 0)
        catalog = store_categories.get(p.sku, {})
        category = catalog.get("store_category", "")
        vehicle = catalog.get("vehicle_details", {}) or {}
        vehicle_text = " ".join(str(v) for v in vehicle.values() if v not in (None, ""))
        category_text = category_labels.get(category, category.replace("_"," "))
        searchable = _normalize_order_search(" ".join([
            p.sku or "", p.name or "", p.model or "", vehicle_text,
            category_text, catalog.get("store_family", "")
        ]))
        matched = [token for token in tokens if token in searchable]
        if not matched:
            continue
        # Exact SKU/model hits rank above broad category/description matches.
        sku_model = _normalize_order_search((p.sku or "") + " " + (p.model or ""))
        score = len(matched) * 3
        score += sum(8 for token in matched if token in sku_model)
        if len(tokens) > 1 and len(matched) == len(tokens):
            score += 5
        scored.append((score, p, stock, catalog, category))

    scored.sort(key=lambda item: (item[0], item[1].sku), reverse=True)
    results = []
    for _, p, stock, catalog, category in scored[:12]:
        pricing = latest_purchase.get(p.sku, {})
        results.append({
            "id":p.id, "sku":p.sku, "name":p.name, "model":p.model or "",
            "category":category or "parts", "store_family":catalog.get("store_family",""),
            "vehicle_details":catalog.get("vehicle_details",{}),
            "stock":stock, "sale_price":pricing.get("sale_price"),
            "currency":pricing.get("currency",""), "images":(p.images or [])[:5],
            "shipping_included":bool(p.shipping_included)
        })
    return results

def _gemini_transcribe_audio(audio_base64: str, mime_type: str) -> dict:
    if not settings.gemini_api_key:
        raise HTTPException(503, "مساعد Gemini غير مفعّل. تحقق من إعداد GEMINI_API_KEY.")
    try:
        audio_bytes = base64.b64decode(audio_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "ملف التسجيل الصوتي غير صالح.")
    if not audio_bytes or len(audio_bytes) > 8 * 1024 * 1024:
        raise HTTPException(413, "حجم التسجيل الصوتي غير مناسب. اختصر التسجيل وحاول مجدداً.")
    if not mime_type.startswith("audio/"):
        raise HTTPException(400, "صيغة التسجيل الصوتي غير مدعومة.")
    now = datetime.now(timezone.utc).timestamp()
    recent = [stamp for stamp in _gemini_rate_limits.get("global", []) if now - stamp < 60]
    if len(recent) >= 50:
        raise HTTPException(429, "تم تجاوز عدد الطلبات مؤقتاً. حاول بعد دقيقة.")
    recent.append(now)
    _gemini_rate_limits["global"] = recent
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": "استمع إلى التسجيل الصوتي واكتشف لغة المتحدث بنفسك دون الاعتماد على لغة الجهاز أو المتجر. اللغات المتوقعة هي العربية أو الإنجليزية أو التركية أو الألمانية أو الفرنسية أو الروسية، لكن لا تفترض أياً منها. أعد كائن JSON صحيحاً بمفتاحين فقط: language لاسم اللغة بالعربية، و transcript للكلام كما نطق به المتحدث وبنفس لغته. لا تترجم الكلام ولا تضف شرحاً. إذا لم يوجد كلام مفهوم أعد transcript فارغاً."},
                {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(audio_bytes).decode("ascii")}}
            ]
        }],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 500, "responseMimeType": "application/json"}
    }
    req = UrlRequest(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": settings.gemini_api_key},
        method="POST"
    )
    try:
        with urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 429:
            raise HTTPException(429, "وصلنا إلى حد الاستخدام المؤقت لدى Google. حاول لاحقاً.")
        if exc.code in (401, 403):
            raise HTTPException(502, "تعذر التحقق من مفتاح Gemini.")
        if exc.code >= 500:
            raise HTTPException(503, "خدمة Gemini مشغولة حالياً. حاول بعد قليل.")
        raise HTTPException(502, "تعذر تحليل التسجيل الصوتي.")
    except (URLError, TimeoutError):
        raise HTTPException(504, "انتهت مهلة تحليل التسجيل الصوتي.")
    except Exception:
        raise HTTPException(502, "حدث خطأ أثناء تحليل التسجيل الصوتي.")
    candidates = result.get("candidates") or []
    parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
    raw = "\n".join(str(part.get("text", "")) for part in parts if part.get("text")).strip()
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        raise HTTPException(502, "لم يتمكن Gemini من تحديد الكلام في التسجيل. حاول مرة أخرى.")
    transcript = str(parsed.get("transcript", "")).strip()[:4000]
    language = str(parsed.get("language", "لغة غير محددة")).strip()[:40]
    if not transcript:
        raise HTTPException(422, "لم أسمع كلاماً واضحاً. تحدث بوضوح وحاول مرة أخرى.")
    return {"transcript": transcript, "language": language}


@app.post("/ai/store-voice")
def gemini_store_voice(payload: GeminiVoicePayload, s: Session = Depends(db)):
    detected = _gemini_transcribe_audio(payload.audio_base64, payload.mime_type)
    transcript = detected["transcript"]
    products = _store_inventory_search(s, transcript)
    product_context = json.dumps(products, ensure_ascii=False)
    system_prompt = (
        "أنت مساعد خدمة العملاء لمتجر مجموعة AIB التجارية. أجب بنفس لغة العميل المكتشفة في رسالته، وهي " + detected["language"] + ". "
        "افهم المقصود من البحث الصوتي والكلمات المنطوقة كما هي. نتائج البحث المباشر من مخزون المتجر: " + product_context + ". "
        "إذا وجدت منتجات فاعرضها ووجّه العميل إلى البطاقات الظاهرة أسفل الرد. اذكر السعر والكمية فقط إذا كانت متاحة. "
        "إذا لم توجد نتائج فاطلب معلومة إضافية قصيرة. لا تخترع سعراً أو كمية أو مواصفة، ولا تكشف بيانات العملاء."
    )
    try:
        reply = _gemini_reply(transcript, payload.history, system_prompt)
    except HTTPException as exc:
        if products:
            reply = "تم التعرف على كلامك والبحث في مخزون AIB. أدرجت المنتجات المطابقة أدناه."
        elif exc.status_code in (429, 502, 503, 504):
            reply = "تم التعرف على كلامك، لكن تعذر رد Gemini مؤقتاً ولم تظهر نتائج مطابقة في المخزون."
        else:
            raise
    return {"transcript": transcript, "language": detected["language"], "reply": reply, "products": products}


@app.post("/ai/store-image-search")
def gemini_store_image_search(payload: GeminiImageSearchPayload, s: Session = Depends(db)):
    if not settings.gemini_api_key:
        raise HTTPException(503, "مساعد Gemini غير مفعّل. تحقق من إعداد GEMINI_API_KEY.")
    try:
        image_bytes = base64.b64decode(payload.image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "ملف الصورة غير صالح.")
    if not image_bytes or len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(413, "حجم الصورة كبير. اختر صورة أصغر من 8 ميغابايت.")
    mime_type = payload.mime_type.split(";")[0].strip().lower()
    if mime_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        raise HTTPException(415, "صيغة الصورة غير مدعومة. استخدم JPG أو PNG أو WEBP.")
    now = datetime.now(timezone.utc).timestamp()
    recent = [stamp for stamp in _gemini_rate_limits.get("global", []) if now - stamp < 60]
    if len(recent) >= 50:
        raise HTTPException(429, "تم تجاوز عدد الطلبات مؤقتاً. حاول بعد دقيقة.")
    recent.append(now)
    _gemini_rate_limits["global"] = recent
    request_payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": "أنت خبير تعرف بصري على قطع غيار السيارات والشاحنات والمحركات والمعدات الثقيلة والمقطورات والمنتجات في متجر AIB. افحص الصورة بعناية: حدد نوع القطعة أو المنتج وشكله ووظيفته الظاهرة، واقرأ أي كتابة أو رقم صنف أو شعار أو موديل ظاهر بالصورة (OCR). أعد JSON صالحاً فقط بالمفتاحين search_terms وdescription. اجعل search_terms عبارة بحث غنية لا تتجاوز 500 حرف، تتضمن الاسم الدقيق بالعربية والإنجليزية إن أمكن، المرادفات الشائعة، نوع القطعة، الشركة أو الموديل ورقم القطعة المقروء حرفياً؛ أدرج عدة كلمات بديلة مفصولة بمسافات حتى يعثر البحث على سجلات المخزون حتى لو اختلفت التسمية. لا تضف رقماً أو ماركة أو موديل غير مقروء بوضوح ولا تخمن. description وصف عربي واضح لما تراه مع بيان درجة عدم اليقين عند الحاجة. إذا كانت الصورة لا تعرض منتجاً أو قطعة بوضوح فاذكر ذلك ولا تختلق تحديداً."},
                {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode("ascii")}}
            ]
        }],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300, "responseMimeType": "application/json"}
    }
    req = UrlRequest(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent",
        data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": settings.gemini_api_key},
        method="POST"
    )
    try:
        with urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 429:
            raise HTTPException(429, "وصلنا إلى حد الاستخدام المؤقت لدى Google. حاول لاحقاً.")
        if exc.code in (401, 403):
            raise HTTPException(502, "تعذر التحقق من مفتاح Gemini.")
        if exc.code >= 500:
            raise HTTPException(503, "خدمة Gemini مشغولة حالياً. حاول بعد قليل.")
        raise HTTPException(502, "تعذر تحليل الصورة.")
    except (URLError, TimeoutError):
        raise HTTPException(504, "انتهت مهلة تحليل الصورة.")
    except Exception:
        raise HTTPException(502, "حدث خطأ أثناء تحليل الصورة.")
    candidates = result.get("candidates") or []
    parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
    raw = "\n".join(str(part.get("text", "")) for part in parts if part.get("text")).strip()
    try:
        identified = json.loads(raw)
    except (ValueError, TypeError):
        raise HTTPException(502, "لم يتمكن Gemini من تحديد المنتج في الصورة. جرّب صورة أوضح.")
    description = str(identified.get("description", "")).strip()[:500]
    search_terms = str(identified.get("search_terms", "")).strip()[:500] or description
    if not search_terms:
        raise HTTPException(422, "لم يظهر منتج واضح في الصورة. التقط صورة أقرب وأكثر وضوحاً.")
    products = _store_inventory_search(s, search_terms)
    context = json.dumps(products, ensure_ascii=False)
    prompt = (
        "أنت مساعد متجر مجموعة AIB التجارية. حللنا صورة العميل ووصفها: " + description +
        ". كلمات البحث المستخلصة: " + search_terms +
        ". نتائج البحث الفعلية من المخزون: " + context +
        ". أجب بالعربية، اشرح باختصار ما تم التعرف عليه، واعرض المنتجات المطابقة إن وجدت. لا تخترع أسعاراً أو مواصفات."
    )
    try:
        reply = _gemini_reply(search_terms, payload.history, prompt)
    except HTTPException as exc:
        if products:
            reply = "تم تحليل الصورة والبحث في مخزون AIB. أدرجت المنتجات المطابقة أدناه."
        elif exc.status_code in (429, 502, 503, 504):
            reply = "تم تحليل الصورة، لكن تعذر رد Gemini مؤقتاً ولم تظهر نتائج مطابقة في المخزون."
        else:
            raise
    return {"description": description, "search_terms": search_terms, "reply": reply, "products": products}


@app.post("/ai/store-chat")
def gemini_store_chat(payload: GeminiChatPayload, s: Session = Depends(db)):
    products = _store_inventory_search(s, payload.message)
    product_context = json.dumps(products, ensure_ascii=False)
    system_prompt = (
        "أنت مساعد خدمة العملاء لمتجر مجموعة AIB التجارية. أجب بالعربية الواضحة. "
        "افهم كلمات العملاء البسيطة واللهجات والأسماء المختصرة بالعربية والإنجليزية، مثل مكينة/محرك، جير/علبة سرعة، بوكلين/حفارة، تركتور/جرار، طرمبة/مضخة، وقطع/سبير. "
        "نتائج البحث المباشر من كامل كتالوج المتجر الفعلي، وتشمل الاسم والطراز ورقم الصنف والتصنيف ومواصفات المركبة والكمية والسعر والصور، موجودة هنا بصيغة JSON: " + product_context + ". "
        "إذا وجدت منتجات فاعرضها للعميل ووجّهه إلى بطاقات المنتجات الظاهرة أسفل ردك لفتح التفاصيل أو الشراء؛ لا تطلب منه إعادة البحث يدوياً. "
        "اذكر السعر والكمية فقط إذا كانت متاحة في البيانات. إذا لم توجد نتائج فاطلب كلمة واحدة إضافية مثل الماركة أو رقم الطراز. "
        "لا تخترع سعراً أو كمية أو مواصفة، ولا تدّع توفر منتج غير موجود في النتائج. لا تكشف بيانات العملاء أو الطلبات. لا تطلب كلمات مرور أو رموز تحقق أو بيانات بطاقات."
    )
    try:
        reply = _gemini_reply(payload.message, payload.history, system_prompt)
    except HTTPException as exc:
        # Inventory search must remain usable even when Google's Gemini quota
        # or service is temporarily unavailable.
        if products:
            reply = "عثرت على نتائج في مخزون مجموعة AIB. أدرجت تفاصيل المحركات والمنتجات المتاحة أدناه. قد يتأخر الرد الذكي مؤقتاً، لكن نتائج المخزون مباشرة."
        elif exc.status_code in (429, 502, 503, 504):
            reply = "تعذر الاتصال بمساعد Gemini مؤقتاً، ولم يعثر البحث الحالي على منتج مطابق في المخزون. جرّب رقم الطراز أو اسم المحرك مرة أخرى."
        else:
            raise
    return {"reply": reply, "products": products}

def _normalize_order_search(value: Any) -> str:
    value = str(value or "").casefold()
    for old_char, new_char in (("أ","ا"),("إ","ا"),("آ","ا"),("ى","ي"),("ة","ه")):
        value = value.replace(old_char, new_char)
    return "".join(ch if ch.isalnum() else " " for ch in value)

def _online_order_search_context(s: Session, message: str) -> list[dict]:
    normalized = _normalize_order_search(message)
    stop_words = {"طلب","طلبات","الطلب","الطلبات","زبون","زبائن","الزبون","الزبائن","عميل","عملاء","العميل","العملاء","ابحث","بحث","اعرض","عرض","تفاصيل","تفصيل","عن","من","في","حالة","الشراء","شراء","الكتروني","الالكتروني","الجديد","الجديدة","كل","اخر","احدث","رقم","order","orders","customer","customers","show","find","search","details","the","for"}
    tokens = [x for x in normalized.split() if len(x) > 1 and x not in stop_words]
    # Search the complete order history (newest first); do not limit the candidate
    # set before matching because an older customer order may otherwise be missed.
    rows = s.scalars(select(OnlinePurchaseOrder).order_by(OnlinePurchaseOrder.id.desc())).all()
    scored = []
    for order in rows:
        customer = order.customer_data or {}
        items = order.items or []
        item_terms = " ".join(str(x.get(k,"")) for x in items if isinstance(x,dict) for k in ("description","sku","model","product_name","name"))
        searchable = _normalize_order_search(" ".join([
            str(order.id), str(customer.get("full_name","")), str(customer.get("first_name","")),
            str(customer.get("last_name","")), str(customer.get("email","")),
            str(customer.get("full_phone","")), str(customer.get("phone_number","")),
            str(customer.get("shipping_address","")), item_terms
        ]))
        if not tokens:
            score = 1
        else:
            matched = sum(1 for token in tokens if token in searchable)
            # Require a meaningful match rather than returning unrelated orders.
            score = matched if matched == len(tokens) else 0
        if score:
            scored.append((score, order))
    scored.sort(key=lambda pair: (pair[0], pair[1].id), reverse=True)
    results = []
    for _, order in scored[:10]:
        customer = order.customer_data or {}
        item_results = []
        for line in (order.items or []):
            if not isinstance(line,dict):
                continue
            sku = str(line.get("sku","")).strip().upper()
            product = s.scalar(select(InventoryProduct).where(InventoryProduct.sku == sku)) if sku else None
            available = float((product.owned_stock or 0) + (product.consigned_stock or 0)) if product and product.active else 0
            item_results.append({
                "name": line.get("description") or line.get("product_name") or line.get("name",""),
                "sku": sku,
                "model": line.get("model",""),
                "quantity": line.get("quantity",0),
                "unit_price": line.get("price",0),
                "inventory_found": bool(product and product.active),
                "inventory_available": available,
                "inventory_status": ("متوفر" if available >= float(line.get("quantity") or 0) else "المخزون أقل من كمية الطلب") if product and product.active else "المنتج غير موجود حالياً في المخزون"
            })
        results.append({
            "id": order.id,
            "customer_name": customer.get("full_name",""),
            "phone": customer.get("full_phone") or (str(customer.get("phone_country_code","")) + str(customer.get("phone_number",""))),
            "email": customer.get("email",""),
            "shipping_address": customer.get("shipping_address",""),
            "items": item_results,
            "total": float(order.total or 0),
            "currency": order.currency,
            "status": order.status,
            "invoice_record_id": order.record_id,
            "review_note": order.review_note or "",
            "payment_proof_available": bool(order.payment_proof),
            "created_at": order.created_at.isoformat() if order.created_at else None
        })
    return results

@app.post("/ai/accounting-chat")
def gemini_accounting_chat(payload: GeminiChatPayload, s: Session = Depends(db), u: User = Depends(current_user)):
    normalized_message = _normalize_order_search(payload.message)
    order_intent = any(term in normalized_message for term in ("طلب","طلبات","زبون","زبائن","عميل","عملاء","order","orders","customer"))
    orders = _online_order_search_context(s, payload.message) if order_intent and u.role == "owner" else []
    if order_intent and u.role != "owner":
        return {"reply":"البحث في طلبات الزبائن وتفاصيلهم متاح للمالك فقط حفاظاً على خصوصية بيانات العملاء. يمكنك طلب الصلاحية من المالك.","orders":[]}
    order_context = json.dumps(orders, ensure_ascii=False)
    system_prompt = (
        "أنت مساعد ذكي داخلي لبرنامج المحاسبة والإدارة في مجموعة AIB التجارية. أجب بالعربية الواضحة، واشرح الإجراءات المحاسبية وتنظيم الفواتير والصناديق والمخزون والتقارير. "
        "يمكنك البحث في طلبات الشراء الإلكتروني عندما يسأل المستخدم عنها. بيانات الطلبات الفعلية المصرح بها لهذا السؤال موجودة في سياق النظام التالي بصيغة JSON: " + order_context + ". "
        "اعتمد على هذه البيانات فقط، ولا تخترع أي طلب أو معلومة. إذا كانت القائمة فارغة فقل إنه لم يتم العثور على طلب مطابق. اذكر رقم الطلب والاسم والهاتف والمنتجات والكميات والإجمالي والحالة وتاريخ الطلب عند توفرها. "
        "لا تعرض إثبات الدفع نفسه أو بياناته المشفرة؛ اكتف بذكر هل الإثبات مرفق. المستخدم الحالي دوره " + str(u.role) + ". "
        "لا تكشف أو تطلب كلمات المرور أو مفاتيح API أو رموز التحقق. لا تنفذ موافقة أو رفضاً أو تعديلاً مالياً؛ اشرح أن هذه الإجراءات تتم من شاشة مراجعة الطلبات وبصلاحيات التطبيق."
    )
    reply = _gemini_reply(payload.message, payload.history, system_prompt)
    return {"reply": reply, "orders": orders}
