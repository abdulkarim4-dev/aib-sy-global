from datetime import datetime, timedelta, timezone
from typing import Optional, Any
import os, secrets, json, base64, binascii, smtplib, hashlib, html
from email.message import EmailMessage
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import HTTPError, URLError
import jwt
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from pwdlib import PasswordHash
from sqlalchemy import create_engine, String, Boolean, DateTime, Integer, ForeignKey, JSON, Text, Numeric, select, func, text, or_, case
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
    brevo_sender_email: str = ""
    brevo_sender_name: str = "مجموعة AIB التجارية"
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
    permissions: Mapped[dict]=mapped_column(JSON, default=dict, nullable=False)
    active: Mapped[bool]=mapped_column(Boolean, default=True)
    deleted: Mapped[bool]=mapped_column(Boolean, default=False, nullable=False)
    failed_logins: Mapped[int]=mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True), nullable=True)
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
    phone_number: Mapped[str]=mapped_column(String(32),default="")

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
    owned_stock: Mapped[Any]=mapped_column(Numeric(18,3), default=0)
    consigned_stock: Mapped[Any]=mapped_column(Numeric(18,3), default=0)
    active: Mapped[bool]=mapped_column(Boolean, default=True)
    images: Mapped[list]=mapped_column(JSON, default=list, nullable=False)
    shipping_included: Mapped[bool]=mapped_column(Boolean, default=False, nullable=False)
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
oauth=OAuth2PasswordBearer(tokenUrl="/auth/login")
app=FastAPI(title="AIB Accounting API", version="1.0.0")
app.add_middleware(GZipMiddleware, minimum_size=900, compresslevel=5)

def db():
    s=SessionLocal()
    try: yield s
    finally: s.close()
def audit(s:Session, user:Optional[User], action:str, entity:str, entity_id:Optional[int], details:dict, request:Optional[Request]=None):
    s.add(AuditEvent(user_id=user.id if user else None, action=action, entity=entity, entity_id=entity_id, details=details, ip_address=request.client.host if request and request.client else ""))
def token_for(user:User,email_otp_verified:bool=False):
    now=datetime.now(timezone.utc)
    claims={"sub":str(user.id),"iat":now,"exp":now+timedelta(minutes=settings.jwt_minutes),"email_otp_verified":bool(email_otp_verified)}
    return jwt.encode(claims,settings.jwt_secret,algorithm="HS256")
def current_user(token:str=Depends(oauth), s:Session=Depends(db)):
    try:
        payload=jwt.decode(token,settings.jwt_secret,algorithms=["HS256"])
        if payload.get("typ")=="store_customer": raise ValueError("store token")
        uid=int(payload["sub"])
    except Exception: raise HTTPException(401,"جلسة الدخول غير صالحة أو انتهت")
    u=s.get(User,uid)
    if not u or not u.active: raise HTTPException(401,"الحساب غير فعال")
    if not payload.get("email_otp_verified"): raise HTTPException(401,"يجب تسجيل الدخول مجدداً وتأكيد رمز البريد الإلكتروني")
    return u
def current_store_customer(token:str=Depends(oauth), s:Session=Depends(db)):
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

PERMISSION_SCHEMA={"inventory":{"view"},"invoices":{"view","create","edit","delete","print"},"cash":{"view","create","edit","delete","print"}}
def has_permission(user:User,module:str,action:str)->bool:
    if user.role=="owner": return True
    return bool(((user.permissions or {}).get(module) or {}).get(action,False))
def require_permission(module:str,action:str):
    def checker(u:User=Depends(current_user)):
        if not has_permission(u,module,action):
            raise HTTPException(403,"ليست لديك صلاحية تنفيذ هذا الإجراء. راجع المالك لمنحك الإذن.")
        return u
    return checker

@app.on_event("startup")
def startup():
    if settings.jwt_secret.startswith("CHANGE_THIS") and os.getenv("ENVIRONMENT")=="production":
        raise RuntimeError("Set a strong JWT_SECRET before production")
    Base.metadata.create_all(engine)
    # Migrate existing cash_moves before any ORM query selects the new columns.
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS permissions JSONB NOT NULL DEFAULT '{}'::jsonb"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(254)"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email_unique ON users (email) WHERE email IS NOT NULL"))
        conn.execute(text("ALTER TABLE inventory_products ADD COLUMN IF NOT EXISTS images JSONB NOT NULL DEFAULT '[]'::jsonb"))
        conn.execute(text("ALTER TABLE inventory_products ADD COLUMN IF NOT EXISTS shipping_included BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE store_customers ADD COLUMN IF NOT EXISTS first_name VARCHAR(80) NOT NULL DEFAULT ''"))
        conn.execute(text("ALTER TABLE store_customers ADD COLUMN IF NOT EXISTS last_name VARCHAR(80) NOT NULL DEFAULT ''"))
        conn.execute(text("ALTER TABLE store_customers ADD COLUMN IF NOT EXISTS shipping_address TEXT NOT NULL DEFAULT ''"))
        conn.execute(text("ALTER TABLE store_customers ADD COLUMN IF NOT EXISTS phone_country_code VARCHAR(8) NOT NULL DEFAULT '+963'"))
        conn.execute(text("ALTER TABLE store_customers ADD COLUMN IF NOT EXISTS phone_number VARCHAR(32) NOT NULL DEFAULT ''"))

        conn.execute(text("ALTER TABLE cash_moves ADD COLUMN IF NOT EXISTS voided BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE cash_moves ADD COLUMN IF NOT EXISTS record_id INTEGER REFERENCES records(id)"))
        conn.execute(text("ALTER TABLE cash_moves ADD COLUMN IF NOT EXISTS voided_by INTEGER REFERENCES users(id)"))
        conn.execute(text("ALTER TABLE cash_moves ADD COLUMN IF NOT EXISTS voided_at TIMESTAMP WITH TIME ZONE"))
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
def health(): return {"status":"ok","service":"AIB Accounting API"}
class AccountingLoginConfirmPayload(BaseModel):
    challenge_id:int
    code:str=Field(min_length=6,max_length=6)

class AccountingLoginResendPayload(BaseModel):
    challenge_id:int

def accounting_login_user_payload(u:User):
    return {"id":u.id,"username":u.username,"name":u.full_name,"email":u.email,"role":u.role,"permissions":u.permissions or {}}

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
    if u.role=="owner" and not u.email:
        owner_email=(settings.smtp_from or settings.smtp_user or "").strip().lower()
        if not owner_email:
            raise HTTPException(503,"لم يتم تحديد بريد المالك. أضف بريد المالك في إعدادات البريد على Render أولاً.")
        duplicate=s.scalar(select(User).where(User.email==owner_email,User.id!=u.id))
        if duplicate: raise HTTPException(409,"بريد المالك مستخدم لحساب آخر. حدّث بريد المالك من قاعدة البيانات.")
        u.email=owner_email
        u.email_verified=False
        s.flush()
    if not u.email:
        audit(s,u,"login_blocked_no_email","user",u.id,{},request);s.commit()
        raise HTTPException(403,"لا يوجد بريد إلكتروني مسجل لهذا الحساب. تواصل مع المالك.")
    if u.role!="owner" and not u.email_verified:
        audit(s,u,"login_blocked_unverified_email","user",u.id,{},request);s.commit()
        raise HTTPException(403,"البريد الإلكتروني لهذا الموظف غير موثق. اطلب من المالك تحديث بيانات الحساب.")
    latest=s.scalar(select(AccountingLoginVerification).where(AccountingLoginVerification.user_id==u.id).order_by(AccountingLoginVerification.id.desc()))
    if latest and latest.used_at is None and latest.created_at>now-timedelta(seconds=30):
        raise HTTPException(429,"تم إرسال رمز قبل قليل. انتظر 30 ثانية قبل طلب رمز جديد.")
    code=f"{secrets.randbelow(1000000):06d}"
    challenge=AccountingLoginVerification(user_id=u.id,code_hash=password_hash.hash(code),expires_at=now+timedelta(minutes=10))
    s.add(challenge); s.flush()
    try:
        send_aib_email(u.email,"رمز الدخول إلى المحاسبة – مجموعة AIB",
            f"مرحباً {u.full_name}، رمز الدخول لمرة واحدة هو: {code}\\nتنتهي صلاحيته خلال 10 دقائق. لا تشارك هذا الرمز مع أي شخص.",
            f"""<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><body style="margin:0;background:#f2f5f7;padding:24px;font-family:Tahoma,Arial"><div style="max-width:520px;margin:auto;background:#fff;border-radius:16px;overflow:hidden;border:1px solid #e4eaf0"><div style="background:#172b3b;padding:22px;text-align:center;color:#fff"><b style="font-size:27px">AIB</b><div>مجموعة AIB التجارية</div></div><div style="padding:28px;text-align:center;color:#243342"><h2>تأكيد الدخول إلى برنامج المحاسبة</h2><p>مرحباً {html.escape(u.full_name)}، استخدم رمز التحقق التالي لإكمال تسجيل الدخول.</p><div style="font-size:32px;letter-spacing:8px;font-weight:900;color:#168447;background:#f1f7f3;border:1px dashed #168447;border-radius:12px;padding:18px">{code}</div><p style="color:#697887">الرمز صالح لمدة 10 دقائق ولمرة واحدة فقط.</p><small>إذا لم تطلب تسجيل الدخول، تجاهل هذه الرسالة.</small></div></div></body></html>""")
    except Exception:
        s.rollback()
        raise HTTPException(503,"تعذر إرسال رمز الدخول إلى البريد المسجل. تحقق من إعدادات البريد أو تواصل مع المالك.")
    audit(s,u,"accounting_login_code_sent","user",u.id,{"challenge_id":challenge.id},request); s.commit()
    return {"requires_email_code":True,"challenge_id":challenge.id,"masked_email":masked_email(u.email),"expires_in":600}
    audit(s,u,"login","user",u.id,{"method":"password"},request); s.commit()
    return {"access_token":token_for(u,email_otp_verified=True),"token_type":"bearer","user":accounting_login_user_payload(u)}

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
def me(u:User=Depends(current_user)): return {"id":u.id,"username":u.username,"name":u.full_name,"email":u.email,"role":u.role,"permissions":u.permissions or {}}

class AccountSettingsPayload(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
class PasswordChangePayload(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)
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
    if action in {"cash_movement","cash_transfer"}:
        return True
    return u.role!="owner" and action in {"invoice_create","invoice_payment"}

def masked_email(email:str)->str:
    local,_,domain=email.partition("@")
    visible=local[:2] if len(local)>2 else local[:1]
    return visible+"***@"+domain

class OperationVerificationStartPayload(BaseModel):
    action: str
class OperationVerificationConfirmPayload(BaseModel):
    challenge_id: int
    code: str = Field(min_length=6,max_length=6)

@app.post("/operation-verifications/start")
def start_operation_verification(p:OperationVerificationStartPayload,request:Request,s:Session=Depends(db),u:User=Depends(current_user)):
    if p.action not in {"invoice_create","invoice_payment","cash_movement","cash_transfer"}:
        raise HTTPException(400,"نوع العملية غير مدعوم للتحقق")
    if not operation_verification_required(u,p.action):
        return {"required":False}
    email=(u.email or "").strip().lower()
    if not email or not u.email_verified:
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
@app.post("/auth/change-password")
def change_owner_password(p:PasswordChangePayload, request:Request, s:Session=Depends(db), u:User=Depends(current_user)):
    if u.role != "owner":
        raise HTTPException(403,"تغيير كلمة المرور مباشرة متاح لحساب المالك فقط")
    if not password_hash.verify(p.current_password,u.password_hash):
        raise HTTPException(401,"كلمة المرور الحالية غير صحيحة")
    u.password_hash=password_hash.hash(p.new_password)
    u.failed_logins=0
    u.locked_until=None
    audit(s,u,"owner_password_changed","user",u.id,{"method":"self_service"},request)
    s.commit()
    notify_account_change(u.email,"تم تغيير كلمة المرور")
    return {"ok":True,"message":"تم تغيير كلمة المرور بنجاح"}

@app.post("/password-change-requests")
def create_password_change_request(p:PasswordChangePayload, request:Request, s:Session=Depends(db), u:User=Depends(current_user)):
    if not password_hash.verify(p.current_password,u.password_hash): raise HTTPException(401,"كلمة المرور الحالية غير صحيحة")
    pending=s.scalar(select(PasswordChangeRequest).where(PasswordChangeRequest.user_id==u.id,PasswordChangeRequest.status=="pending"))
    if pending: raise HTTPException(409,"لديك طلب تغيير كلمة مرور قيد انتظار موافقة المالك")
    row=PasswordChangeRequest(user_id=u.id,requested_by=u.id,new_password_hash=password_hash.hash(p.new_password))
    s.add(row); s.flush()
    audit(s,u,"password_change_requested","user",u.id,{"request_id":row.id},request)
    s.commit()
    return {"id":row.id,"status":"pending"}
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

class UserCreate(BaseModel): username:str=Field(min_length=3,max_length=80); full_name:str=Field(min_length=2,max_length=160); email:str=Field(min_length=5,max_length=254); email_confirm:str|None=None; password:str=Field(min_length=12); role:str="employee"
class CompanyProfilePayload(BaseModel):
    data: dict

@app.get("/company-profile")
def get_company_profile(s:Session=Depends(db), u:User=Depends(current_user)):
    profile=s.get(CompanyProfile,1)
    return profile.data if profile else {}

@app.put("/company-profile")
def update_company_profile(p:CompanyProfilePayload, request:Request, s:Session=Depends(db), u:User=Depends(manager)):
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
    return [{"id":u.id,"username":u.username,"name":u.full_name,"email":u.email,"role":u.role,"active":u.active,"permissions":u.permissions or {}} for u in s.scalars(select(User).where(User.deleted.is_(False))).all()]
@app.post("/users")
def add_user(payload:UserCreate, request:Request, s:Session=Depends(db), u:User=Depends(manager)):
    if payload.role not in ("employee","owner"): raise HTTPException(400,"دور غير صالح")
    if s.scalar(select(User).where(User.username==payload.username)): raise HTTPException(409,"اسم المستخدم مستخدم")
    email=(payload.email or "").strip().lower()
    if (not email) or ("@" not in email) or ("." not in email.rsplit("@",1)[-1]) or len(email)>254: raise HTTPException(400,"البريد الإلكتروني مطلوب ويجب أن يكون صالحاً")
    if s.scalar(select(User).where(User.email==email,User.deleted.is_(False))): raise HTTPException(409,"البريد الإلكتروني مستخدم لحساب نشط")
    # Older soft-deleted accounts may still hold the unique email value.
    for archived in s.scalars(select(User).where(User.email==email,User.deleted.is_(True))).all():
        archived.email=None
        archived.email_verified=False
    nu=User(username=payload.username,full_name=payload.full_name,email=email,email_verified=False,password_hash=password_hash.hash(payload.password),role="employee")
    nu.permissions={}; s.add(nu); s.flush()
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
    return {"id":nu.id,"username":nu.username,"email":email,"email_verified":False,"approval_required":True}
class EmployeeEmailApprovalPayload(BaseModel):
    code:str=Field(min_length=6,max_length=6)

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
    normalized_code=str(p.code).strip().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹","01234567890123456789"))
    if len(normalized_code)!=6 or not normalized_code.isdigit() or not password_hash.verify(normalized_code,row.code_hash):
        row.attempts+=1;s.commit();raise HTTPException(400,"رمز تأكيد البريد غير صحيح. أدخل الأرقام الستة كما ظهرت في الرسالة.")
    row.used_at=now;target.email_verified=True
    audit(s,u,"employee_email_confirmed_by_owner","user",target.id,{"email":target.email},request);s.commit()
    return {"ok":True,"email_verified":True,"username":target.username}

class UserPermissionsPayload(BaseModel):
    permissions: dict
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
    if any(clean["invoices"][k] for k in ("create","edit","delete","print")):
        clean["invoices"]["view"]=True
    if any(clean["cash"][k] for k in ("create","edit","delete","print")):
        clean["cash"]["view"]=True
    target.permissions=clean
    audit(s,u,"user_permissions_updated","user",user_id,{"permissions":clean},request)
    s.commit()
    return {"ok":True,"permissions":clean}
class UserPasswordResetPayload(BaseModel):
    password: str = Field(min_length=12, max_length=256)

@app.patch("/users/{user_id}/password")
def reset_user_password(user_id:int, p:UserPasswordResetPayload, request:Request, s:Session=Depends(db), u:User=Depends(manager)):
    target=s.get(User,user_id)
    if not target: raise HTTPException(404,"المستخدم غير موجود")
    if target.role=="owner": raise HTTPException(400,"لا يمكن إصدار بطاقة دخول لحساب المالك من هذه الصفحة")
    target.password_hash=password_hash.hash(p.password)
    target.failed_logins=0
    target.locked_until=None
    audit(s,u,"user_credentials_reissued","user",user_id,{"username":target.username},request)
    s.commit()
    return {"ok":True,"username":target.username,"full_name":target.full_name,"email":target.email}

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

def prepare_record_inventory(s:Session, section:str, raw_data:dict, allow_legacy:bool=False)->dict:
    data=dict(raw_data or {})
    items=data.get("items") if isinstance(data.get("items"),list) else []
    prepared=[]
    stock_sections={"purchase","directSale","deposit","consignSale"}
    for raw in items:
        if not isinstance(raw,dict): continue
        item=dict(raw)
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
            product=InventoryProduct(sku=sku,name=name or sku,model=model)
            s.add(product)
            try: s.flush()
            except Exception:
                s.rollback()
                raise HTTPException(409,f"رقم القطعة {sku} مستخدم مسبقاً. ابحث عنها واخترها.")
        else:
            if not product.active: raise HTTPException(400,f"القطعة {sku} غير مفعلة")
            if not name: item["description"]=product.name
            if not model: item["model"]=product.model
        item["sku"]=sku
        family=str(item.get("store_family") or "").strip()
        category=str(item.get("store_category") or "").strip()
        allowed={"car":{"cars","car_parts","car_engines","car_engine_parts"},"truck":{"trucks","truck_parts","truck_engines","truck_engine_parts"},"heavy":{"heavy","heavy_parts","heavy_engines","heavy_engine_parts"},"agri":{"agri","agri_parts","agri_engines","agri_engine_parts"}}
        if section in {"purchase","deposit"} and name and (not family or not category):
            raise HTTPException(400,"يجب اختيار القسم الرئيسي والقسم الفرعي للمنتج عند الشراء أو وضع الأمانة")
        if family or category:
            if category not in allowed.get(family,set()):
                raise HTTPException(400,"اختر القسم الرئيسي والفرعي للمنتج بشكل صحيح قبل الحفظ")
        prepared.append(item)
    data["items"]=prepared
    return data

def recalculate_inventory(s:Session):
    totals={p.id:{"owned":0.0,"consigned":0.0} for p in s.scalars(select(InventoryProduct)).all()}
    for record in s.scalars(select(Record).where(Record.deleted.is_(False))).all():
        if record.section not in {"purchase","directSale","deposit","consignSale"}: continue
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
                bucket="owned" if record.section in {"purchase","directSale"} else "consigned"
                sign=-1 if record.section in {"directSale","consignSale"} else 1
                totals[product.id][bucket]+=sign*qty
    for product in s.scalars(select(InventoryProduct)).all():
        owned=round(totals[product.id]["owned"],3)
        consigned=round(totals[product.id]["consigned"],3)
        if owned < -0.0001: raise HTTPException(400,f"الرصيد المملوك للقطعة {product.sku} غير كافٍ. الرصيد الحالي لا يسمح بهذه الكمية.")
        if consigned < -0.0001: raise HTTPException(400,f"رصيد الأمانة للقطعة {product.sku} غير كافٍ. تحقق من إيداعات الأمانة السابقة.")
        product.owned_stock=max(0,owned)
        product.consigned_stock=max(0,consigned)

_store_catalog_cache={"at":0.0,"value":None}

def latest_store_catalog_data(s:Session)->tuple[dict,dict]:
    """Reuse the recent catalog snapshot instead of rescanning all invoice history on every request."""
    import time
    now=time.monotonic()
    cached=_store_catalog_cache["value"]
    if cached is not None and now-_store_catalog_cache["at"]<45:
        return cached
    latest_categories={}
    latest_prices={}
    allowed={"car":{"cars","car_parts","car_engines","car_engine_parts"},"truck":{"trucks","truck_parts","truck_engines","truck_engine_parts"},"heavy":{"heavy","heavy_parts","heavy_engines","heavy_engine_parts"},"agri":{"agri","agri_parts","agri_engines","agri_engine_parts"}}
    rows=s.scalars(select(Record).where(
        Record.deleted.is_(False),
        Record.section.in_(["purchase","deposit"])
    ).order_by(Record.created_at.desc(),Record.id.desc())).all()
    for record in rows:
        for item in (record.data or {}).get("items",[]):
            if not isinstance(item,dict): continue
            sku=str(item.get("sku") or "").strip().upper()
            if not sku: continue
            if record.section=="purchase" and sku not in latest_prices:
                price=float(item.get("price") or 0)
                if price>0:
                    latest_prices[sku]={"purchase_price":round(price,2),"sale_price":round(price*1.35,2),"currency":record.currency or "USD"}
            if sku not in latest_categories:
                family=str(item.get("store_family") or "").strip()
                category=str(item.get("store_category") or "").strip()
                if category in allowed.get(family,set()):
                    latest_categories[sku]={"store_family":family,"store_category":category}
    result=(latest_categories,latest_prices)
    _store_catalog_cache["value"]=result
    _store_catalog_cache["at"]=now
    return result

def latest_inventory_store_categories(s:Session)->dict:
    return latest_store_catalog_data(s)[0]

@app.get("/inventory/products")
def list_inventory_products(q:Optional[str]=None, s:Session=Depends(db), u:User=Depends(require_permission("inventory","view"))):
    query=select(InventoryProduct).where(InventoryProduct.active.is_(True))
    if q:
        term=f"%{q.strip()}%"
        query=query.where(or_(InventoryProduct.sku.ilike(term),InventoryProduct.name.ilike(term),InventoryProduct.model.ilike(term)))
    rows=s.scalars(query.order_by(InventoryProduct.sku).limit(300)).all()
    store_categories,latest_purchase=latest_store_catalog_data(s)
    return [{"id":p.id,"sku":p.sku,"name":p.name,"model":p.model,"owned_stock":float(p.owned_stock or 0),"consigned_stock":float(p.consigned_stock or 0),"images":p.images or [],"shipping_included":bool(p.shipping_included),**store_categories.get(p.sku,{}),**latest_purchase.get(p.sku,{"purchase_price":0,"sale_price":0,"currency":"—"})} for p in rows]

class InventoryImagesPayload(BaseModel):
    images: list[str] = Field(default_factory=list, max_length=20)

class InventoryShippingPayload(BaseModel):
    included: bool = False

@app.put("/inventory/products/{product_id}/shipping")
def update_inventory_product_shipping(product_id:int, p:InventoryShippingPayload, request:Request, s:Session=Depends(db), u:User=Depends(require_permission("inventory","edit"))):
    product=s.get(InventoryProduct,product_id)
    if not product or not product.active: raise HTTPException(404,"القطعة غير موجودة في المخزون")
    product.shipping_included=bool(p.included)
    audit(s,u,"inventory_shipping_updated","inventory_product",product.id,{"sku":product.sku,"shipping_included":product.shipping_included},request)
    s.commit()
    return {"ok":True,"shipping_included":product.shipping_included}

@app.put("/inventory/products/{product_id}/images")
def update_inventory_product_images(product_id:int, p:InventoryImagesPayload, request:Request, s:Session=Depends(db), u:User=Depends(require_permission("inventory","edit"))):
    product=s.get(InventoryProduct,product_id)
    if not product or not product.active: raise HTTPException(404,"القطعة غير موجودة في المخزون")
    total_bytes=0
    for image_data in p.images:
        if not isinstance(image_data,str) or "," not in image_data: raise HTTPException(400,"صيغة إحدى الصور غير صالحة")
        header,encoded=image_data.split(",",1)
        if header not in ("data:image/jpeg;base64","data:image/png;base64","data:image/webp;base64"): raise HTTPException(400,"يسمح فقط بصور JPG أو PNG أو WEBP")
        try: raw=base64.b64decode(encoded,validate=True)
        except (binascii.Error,ValueError): raise HTTPException(400,"بيانات إحدى الصور غير صالحة")
        if not raw or len(raw)>1024*1024: raise HTTPException(413,"يجب ألا يتجاوز حجم الصورة الواحدة 1 ميغابايت بعد الضغط")
        total_bytes+=len(raw)
    if total_bytes>8*1024*1024: raise HTTPException(413,"الحجم الإجمالي للصور يتجاوز 8 ميغابايت")
    product.images=p.images
    audit(s,u,"inventory_images_updated","inventory_product",product.id,{"sku":product.sku,"image_count":len(p.images)},request)
    s.commit()
    return {"ok":True,"images":product.images,"count":len(product.images)}

class RecordCreate(BaseModel): section:str; invoice_no:Optional[str]=None; currency:str="USD"; data:dict; verification_token:Optional[str]=None
@app.post("/records")
def create_record(p:RecordCreate, request:Request, s:Session=Depends(db), u:User=Depends(require_permission("invoices","create"))):
    if p.section not in {"deposit","purchase","consignSale","directSale","repair","carPurchase","carSale"}: raise HTTPException(400,"قسم غير معروف")
    if p.currency not in {"USD","SYP"}: raise HTTPException(400,"عملة غير مدعومة")
    section_codes={"directSale":"A","purchase":"B","consignSale":"C","deposit":"D","repair":"E","carPurchase":"F","carSale":"G"}
    # Serialize numbering per section so simultaneous users cannot receive the same sequence.
    s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key":"aib-invoice:"+p.section})
    serial=int(s.scalar(select(func.count(Record.id)).where(Record.section==p.section)) or 0)+1
    invoice_no=f"{section_codes[p.section]}-{serial:05d}-B"
    prepared_data=prepare_record_inventory(s,p.section,p.data)
    consume_operation_verification(s,u,"invoice_create",p.verification_token)
    r=Record(section=p.section,invoice_no=invoice_no,currency=p.currency,data=prepared_data,created_by=u.id)
    s.add(r); s.flush(); recalculate_inventory(s); audit(s,u,"record_created","record",r.id,{"section":r.section,"invoice_no":r.invoice_no},request); s.commit(); return {"id":r.id,"invoice_no":r.invoice_no,"created_at":r.created_at}
@app.get("/records")
def list_records(section:Optional[str]=None, s:Session=Depends(db), u:User=Depends(require_permission("invoices","view"))):
    q=select(Record).where(Record.deleted==False)
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
        out.append({"id":r.id,"section":r.section,"invoice_no":r.invoice_no,"currency":r.currency,"data":r.data,"created_by":r.created_by,"created_at":r.created_at,"updated_at":r.updated_at,"payments":[{"id":x.id,"amount":float(x.amount),"method":x.method,"cash_box":x.cash_box,"paid_at":x.paid_at} for x in pays],"paid_total":round(paid,2),"remaining":round(max(total-paid,0),2),"payment_status":"paid" if total>0 and paid>=total else "partial" if paid>0 else "unpaid"})
    return out
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
    if not r or r.deleted: raise HTTPException(404,"الفاتورة غير موجودة")
    if p.method not in {"cash","baraka_bank","sham_cash","syriatel_cash"}: raise HTTPException(400,"طريقة الدفع غير صالحة")
    total=float(r.data.get("amount",r.data.get("price",r.data.get("sale",0))) or 0)
    paid=float(s.scalar(select(func.coalesce(func.sum(InvoicePayment.amount),0)).where(InvoicePayment.record_id==record_id)) or 0)
    if round(paid+p.amount,2)>round(total,2): raise HTTPException(400,"مجموع الدفعات يتجاوز إجمالي الفاتورة")
    if not p.cash_box.strip(): raise HTTPException(400,"اختر الصندوق الذي ستدخل إليه الدفعة")
    consume_operation_verification(s,u,"invoice_payment",p.verification_token)
    x=InvoicePayment(record_id=record_id,amount=p.amount,method=p.method,cash_box=p.cash_box,paid_at=p.paid_at or datetime.now(timezone.utc),created_by=u.id)
    s.add(x); s.flush()
    movement="withdrawal" if r.section in {"purchase","carPurchase"} else "deposit"
    if movement=="withdrawal": ensure_cash_balance(s,p.cash_box,r.currency,p.amount)
    s.add(CashMove(box_name=p.cash_box,movement=movement,amount=p.amount,currency=r.currency,description=invoice_cash_description(r,"قبض" if movement=="deposit" else "صرف"),created_by=u.id,record_id=r.id))
    audit(s,u,"invoice_payment_created","invoice_payment",x.id,{"record_id":record_id,"amount":p.amount,"method":p.method,"cash_box":p.cash_box,"cash_movement":movement},request); s.commit()
    return {"id":x.id,"record_id":record_id,"amount":float(x.amount),"method":x.method,"cash_box":x.cash_box,"paid_at":x.paid_at}

@app.get("/records/{record_id}/payments")
def list_invoice_payments(record_id:int,s:Session=Depends(db),u:User=Depends(require_permission("invoices","view"))):
    r=s.get(Record,record_id)
    if not r or r.deleted: raise HTTPException(404,"الفاتورة غير موجودة")
    return [{"id":x.id,"amount":float(x.amount),"method":x.method,"cash_box":x.cash_box,"paid_at":x.paid_at} for x in s.scalars(select(InvoicePayment).where(InvoicePayment.record_id==record_id).order_by(InvoicePayment.id)).all()]

class PaymentUpdatePayload(BaseModel):
    amount: float = Field(gt=0)
    method: str
    paid_at: Optional[datetime] = None
    cash_box: str

def reverse_payment_cash_move(s:Session, r:Record, payment:InvoicePayment, u:User, reason:str):
    movement="withdrawal" if r.section in {"purchase","carPurchase"} else "deposit"
    reverse="deposit" if movement=="withdrawal" else "withdrawal"
    if reverse=="withdrawal": ensure_cash_balance(s,payment.cash_box,r.currency,float(payment.amount))
    s.add(CashMove(box_name=payment.cash_box,movement=reverse,amount=payment.amount,currency=r.currency,description=invoice_cash_description(r,f"تسوية عكسية للدفعة {payment.id} ({reason})"),created_by=u.id,record_id=r.id))

@app.put("/records/{record_id}/payments/{payment_id}")
def update_invoice_payment(record_id:int,payment_id:int,p:PaymentUpdatePayload,request:Request,s:Session=Depends(db),u:User=Depends(require_permission("invoices","edit"))):
    r=s.get(Record,record_id); x=s.get(InvoicePayment,payment_id)
    if not r or r.deleted or not x or x.record_id!=record_id: raise HTTPException(404,"الدفعة غير موجودة")
    if p.method not in {"cash","baraka_bank","sham_cash","syriatel_cash"}: raise HTTPException(400,"طريقة الدفع غير صالحة")
    if not p.cash_box.strip(): raise HTTPException(400,"اختر الصندوق")
    paid=float(s.scalar(select(func.coalesce(func.sum(InvoicePayment.amount),0)).where(InvoicePayment.record_id==record_id)) or 0)
    total=float(r.data.get("amount",r.data.get("price",r.data.get("sale",0))) or 0)
    if round(paid-float(x.amount)+p.amount,2)>round(total,2): raise HTTPException(400,"مجموع الدفعات بعد التعديل يتجاوز إجمالي الفاتورة")
    changed=(round(float(x.amount),2)!=round(p.amount,2) or x.method!=p.method or x.cash_box!=p.cash_box or (p.paid_at and x.paid_at!=p.paid_at))
    if not changed: return {"ok":True,"unchanged":True}
    reverse_payment_cash_move(s,r,x,u,"تعديل")
    movement="withdrawal" if r.section in {"purchase","carPurchase"} else "deposit"
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
    r=s.get(Record,record_id); x=s.get(InvoicePayment,payment_id)
    if not r or r.deleted or not x or x.record_id!=record_id: raise HTTPException(404,"الدفعة غير موجودة")
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
    if not s.get(Record,record_id): raise HTTPException(404,"السجل غير موجود")
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
        ensure_total_covers_payments(s,rec.id,p.data)
        rec.data=prepare_record_inventory(s,rec.section,p.data,allow_legacy=True); rec.currency=currency; rec.updated_at=datetime.now(timezone.utc)
        recalculate_inventory(s)
    elif cr.action=="delete":
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
    if p.movement not in ("deposit","withdrawal"): raise HTTPException(400,"اختر إيداعاً أو سحباً؛ التحويل بين الصناديق له عملية مستقلة")
    if p.currency not in ("USD","SYP"): raise HTTPException(400,"عملة غير مدعومة")
    if p.movement=="withdrawal": ensure_cash_balance(s,p.box_name,p.currency,p.amount)
    consume_operation_verification(s,u,"cash_movement",p.verification_token)
    m=CashMove(**p.model_dump(exclude={"verification_token"}),created_by=u.id); s.add(m); s.flush(); audit(s,u,"cash_movement_created","cash",m.id,{"box":p.box_name,"movement":p.movement,"amount":p.amount,"currency":p.currency},request); s.commit(); return {"id":m.id}
@app.post("/cash-transfers")
def cash_transfer(p:CashTransferPayload,request:Request,s:Session=Depends(db),u:User=Depends(require_permission("cash","create"))):
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
    rows=s.scalars(select(CashMove).where(CashMove.box_name==box_name).order_by(CashMove.id.desc())).all()
    return [{"id":m.id,"box_name":m.box_name,"movement":m.movement,"amount":float(m.amount),"currency":m.currency,"description":cash_move_display_description(s,m),"created_by":m.created_by,"created_at":m.created_at,"transfer_group":m.transfer_group,"voided":m.voided,"voided_by":m.voided_by,"voided_at":m.voided_at,"sale_locked":is_sale_cash_move(s,m),"purchase_locked":is_purchase_cash_move(s,m)} for m in rows]

@app.get("/cash-movements")
def cash_list(s:Session=Depends(db),u:User=Depends(require_permission("cash","view"))):
    rows=s.scalars(select(CashMove).order_by(CashMove.id.desc())).all()
    return [{"id":m.id,"box_name":m.box_name,"movement":m.movement,"amount":float(m.amount),"currency":m.currency,"description":cash_move_display_description(s,m),"created_by":m.created_by,"created_at":m.created_at,"transfer_group":m.transfer_group,"voided":m.voided,"voided_by":m.voided_by,"voided_at":m.voided_at,"sale_locked":is_sale_cash_move(s,m),"purchase_locked":is_purchase_cash_move(s,m)} for m in rows]

@app.patch("/cash-movements/{move_id}/void")
def void_cash_movement(move_id:int,request:Request,s:Session=Depends(db),u:User=Depends(require_permission("cash","edit"))):
    move=s.get(CashMove,move_id)
    if not move: raise HTTPException(404,"حركة الصندوق غير موجودة")
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
    move=s.get(CashMove,move_id)
    if not move: raise HTTPException(404,"حركة الصندوق غير موجودة")
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
@app.post("/audit-log/print")
def audit_invoice_print(request:Request, record_id:int, invoice_no:str="", section:str="", s:Session=Depends(db), u:User=Depends(require_permission("invoices","print"))):
    record=s.get(Record,record_id)
    if not record or record.deleted: raise HTTPException(404,"الفاتورة غير موجودة")
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
    r=s.get(Record,record_id)
    if not r or r.deleted: raise HTTPException(404,"السجل غير موجود")
    if p.currency not in ("USD","SYP"): raise HTTPException(400,"عملة غير مدعومة")
    ensure_total_covers_payments(s,r.id,p.data)
    r.data=prepare_record_inventory(s,r.section,p.data,allow_legacy=True); r.invoice_no=p.invoice_no; r.currency=p.currency; r.updated_at=datetime.now(timezone.utc)
    recalculate_inventory(s)
    audit(s,u,"record_updated","record",r.id,{"section":r.section,"invoice_no":r.invoice_no},request); s.commit(); return {"ok":True}

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
    r=s.get(Record,record_id)
    if not r or r.deleted: raise HTTPException(404,"السجل غير موجود")
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
    return {"ok":True}

@app.get("/my-change-requests")
def my_requests(s:Session=Depends(db),u:User=Depends(current_user)):
    rows=s.scalars(select(ChangeRequest).where(ChangeRequest.requested_by==u.id).order_by(ChangeRequest.id.desc()).limit(200)).all()
    out=[]
    for x in rows:
        rec=s.get(Record,x.record_id)
        out.append({"id":x.id,"record_id":x.record_id,"section":rec.section if rec else None,"invoice_no":rec.invoice_no if rec else None,"action":x.action,"proposed_data":x.proposed_data,"reason":x.reason,"status":x.status,"created_at":x.created_at})
    return out

@app.get("/cash-summary")
def cash_summary(s:Session=Depends(db),u:User=Depends(require_permission("cash","view"))):
    rows=s.execute(
        select(
            CashMove.box_name,
            CashMove.currency,
            func.sum(case(
                (CashMove.movement.in_(("deposit","transfer_in")),CashMove.amount),
                else_=-CashMove.amount
            )).label("balance")
        ).where(CashMove.voided.is_(False)).group_by(CashMove.box_name,CashMove.currency)
    ).all()
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

class StoreRegisterPayload(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=256)
class StoreLoginPayload(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=256)
class StorePasswordResetRequestPayload(BaseModel):
    email: str = Field(min_length=5, max_length=254)
class StorePasswordResetConfirmPayload(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=10, max_length=256)

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
    items: list[StoreCartItemPayload] = Field(min_length=1,max_length=100)

class StoreCartPayload(BaseModel):
    items: list[StoreCartItemPayload] = Field(default_factory=list, max_length=100)

def store_customer_token(customer:StoreCustomer):
    now=datetime.now(timezone.utc)
    return jwt.encode({"sub":str(customer.id),"typ":"store_customer","iat":now,"exp":now+timedelta(days=30)},settings.jwt_secret,algorithm="HS256")

def store_product_category(name:str, model:str):
    value=(name+" "+(model or "")).lower()
    if any(x in value for x in ["حفار","excavator","تركس","لودر","loader","كاتربلر","caterpillar","volvo ec","hyundai r"]): return "heavy"
    if any(x in value for x in ["شاحنة","truck","fh","scania","قاطر"]): return "trucks"
    if any(x in value for x in ["محرك","engine","gearbox","جير","دفرنس","ناقل"]): return "engines"
    if any(x in value for x in ["سيارة","sedan","bmw","mercedes","hyundai","kia","toyota","volkswagen"]): return "cars"
    return "parts"

def store_latest_prices(s:Session):
    prices={}
    records=s.scalars(select(Record).where(Record.section=="purchase",Record.deleted.is_(False)).order_by(Record.created_at.desc(),Record.id.desc())).all()
    for record in records:
        for item in (record.data or {}).get("items",[]):
            if not isinstance(item,dict): continue
            sku=str(item.get("sku") or "").strip().upper()
            price=float(item.get("price") or 0)
            if sku and price>0 and sku not in prices:
                prices[sku]={"sale_price":round(price*1.35,2),"currency":record.currency or "USD"}
    return prices

@app.post("/store/auth/register")
def store_register(p:StoreRegisterPayload, request:Request, s:Session=Depends(db)):
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
def confirm_store_registration(p:StoreEmailConfirmPayload, request:Request, s:Session=Depends(db)):
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
    return {"access_token":store_customer_token(customer),"token_type":"bearer","customer":{"id":customer.id,"email":customer.email,"full_name":customer.full_name}}

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
def verify_store_login(p:StoreEmailConfirmPayload, request:Request, s:Session=Depends(db)):
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
    return {"access_token":store_customer_token(customer),"token_type":"bearer","customer":{"id":customer.id,"email":customer.email,"full_name":customer.full_name}}

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

@app.get("/store/auth/me")
def store_me(customer:StoreCustomer=Depends(current_store_customer)):
    return {"id":customer.id,"email":customer.email,"full_name":customer.full_name}

def serialize_store_cart(s:Session, customer:StoreCustomer):
    prices=store_latest_prices(s)
    out=[]
    for item in customer.cart or []:
        if not isinstance(item,dict): continue
        product=s.get(InventoryProduct,int(item.get("product_id") or 0))
        if not product or not product.active: continue
        price=prices.get(product.sku,{})
        out.append({"id":product.id,"sku":product.sku,"name":product.name,"model":product.model or "",
            "qty":int(item.get("quantity") or 1),"stock":float(product.owned_stock or 0)+float(product.consigned_stock or 0),
            "price":price.get("sale_price"),"currency":price.get("currency",""),
            "images":product.images or [],"category":store_product_category(product.name,product.model or "")})
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
        if not product or not product.active: raise HTTPException(404,"أحد المنتجات لم يعد متاحاً")
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
    prices=store_latest_prices(s);lines=[];currency=None;total=0;seen=set()
    for entry in p.items:
        if entry.product_id in seen: continue
        seen.add(entry.product_id);product=s.get(InventoryProduct,entry.product_id)
        if not product or not product.active: raise HTTPException(409,"أحد المنتجات غير متاح")
        qty=int(entry.quantity);stock=float(product.owned_stock or 0)+float(product.consigned_stock or 0)
        if qty>stock: raise HTTPException(409,f"الكمية المطلوبة من {product.name} تتجاوز المخزون المتاح ({stock:g})")
        price=prices.get(product.sku)
        if not price or float(price.get("sale_price") or 0)<=0: raise HTTPException(409,"سعر أحد المنتجات غير محدد")
        if currency and currency!=price["currency"]: raise HTTPException(409,"لا يمكن جمع عملات مختلفة في طلب واحد")
        currency=price["currency"];unit=float(price["sale_price"]);total+=unit*qty
        lines.append({"product_id":product.id,"sku":product.sku,"description":product.name,"model":product.model or "","quantity":qty,"price":unit})
    if not lines: raise HTTPException(400,"السلة فارغة")
    previous_profile={"full_name":customer.full_name,"shipping_address":customer.shipping_address,"phone_country_code":customer.phone_country_code,"phone_number":customer.phone_number}
    customer.first_name=p.first_name.strip();customer.last_name=p.last_name.strip();customer.full_name=(customer.first_name+" "+customer.last_name).strip()
    customer.shipping_address=p.shipping_address.strip();customer.phone_country_code=p.phone_country_code;customer.phone_number=p.phone_number.strip()
    data={"first_name":customer.first_name,"last_name":customer.last_name,"full_name":customer.full_name,"email":customer.email,"shipping_address":customer.shipping_address,"phone_country_code":customer.phone_country_code,"phone_number":customer.phone_number,"full_phone":customer.phone_country_code+customer.phone_number}
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
        admin_html=aib_email_html(f"طلب شراء إلكتروني جديد #{order.id}","وصل طلب جديد من متجر AIB ويحتاج إلى مراجعة إثبات الدفع.",[("رقم الطلب",f"#{order.id}"),("العميل",html.escape(customer.full_name)),("البريد",html.escape(customer.email)),("الهاتف",html.escape(data["full_phone"])),("العنوان",html.escape(data["shipping_address"])),("الإجمالي",f"{float(order.total):.2f} {html.escape(order.currency)}")],accent="#168447",note="يرجى فتح بوابة المحاسبة لمراجعة الطلب والتحقق من إثبات الدفع.")
        send_notification_email(admin_email,f"طلب شراء إلكتروني جديد #{order.id} – AIB",admin_body,admin_html)
    return {"ok":True,"order_id":order.id,"customer":data,"items":lines,"total":float(order.total),"currency":order.currency,"status":order.status}

@app.get("/online-purchase-orders/count")
def count_online_purchase_orders(s:Session=Depends(db),u:User=Depends(manager)):
    pending=int(s.scalar(select(func.count(OnlinePurchaseOrder.id)).where(OnlinePurchaseOrder.status=="pending")) or 0)
    return {"pending":pending}

@app.get("/online-purchase-orders")
def list_online_purchase_orders(s:Session=Depends(db),u:User=Depends(manager)):
    return [{"id":o.id,"customer":o.customer_data,"items":o.items,"total":float(o.total),"currency":o.currency,"payment_proof":o.payment_proof,"proof_type":o.proof_type,"status":o.status,"record_id":o.record_id,"review_note":o.review_note,"created_at":o.created_at} for o in s.scalars(select(OnlinePurchaseOrder).order_by(OnlinePurchaseOrder.id.desc())).all()]

class OnlineOrderReviewPayload(BaseModel):
    action: str
    note: str = ""

@app.post("/online-purchase-orders/{order_id}/review")
def review_online_purchase_order(order_id:int,p:OnlineOrderReviewPayload,s:Session=Depends(db),u:User=Depends(manager)):
    order=s.get(OnlinePurchaseOrder,order_id)
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
        product=s.scalar(select(InventoryProduct).where(InventoryProduct.sku==str(x["sku"]).strip().upper()))
        if not product or not product.active: raise HTTPException(409,f"المنتج {x.get('description') or x['sku']} لم يعد متاحاً")
        qty=float(x["quantity"])
        owned=float(product.owned_stock or 0)
        consigned=float(product.consigned_stock or 0)
        available=owned+consigned
        if qty>available+0.0001:
            raise HTTPException(409,f"المخزون تغيّر منذ إرسال الطلب. المتاح من {product.name} حالياً {available:g}")
        from_owned=min(qty,owned)
        from_consigned=qty-from_owned
        allocated_items.append({"sku":x["sku"],"description":x["description"],"model":x.get("model",""),"quantity":qty,"price":x["price"],"owned_quantity":from_owned,"consigned_quantity":from_consigned})
    data={"customer":order.customer_data["full_name"],"customer_phone":order.customer_data["full_phone"],"customer_address":order.customer_data["shipping_address"],"amount":float(order.total),"items":allocated_items,"notes":"طلب إلكتروني – تم التحقق من إثبات الدفع واعتماده"}
    prepared=prepare_record_inventory(s,"directSale",data)
    s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"),{"key":"aib-invoice:directSale"})
    serial=int(s.scalar(select(func.count(Record.id)).where(Record.section=="directSale")) or 0)+1
    record=Record(section="directSale",invoice_no=f"A-{serial:05d}-B",currency=order.currency,data=prepared,created_by=u.id)
    s.add(record);s.flush();recalculate_inventory(s)
    payment=InvoicePayment(record_id=record.id,amount=order.total,method="sham_cash",cash_box="شام كاش",created_by=u.id)
    s.add(payment)
    s.add(CashMove(box_name="شام كاش",movement="deposit",amount=order.total,currency=order.currency,description="قبض فاتورة طلب شراء إلكتروني "+record.invoice_no,created_by=u.id,record_id=record.id))
    order.status="approved";order.record_id=record.id;order.reviewed_by=u.id;order.reviewed_at=datetime.now(timezone.utc);order.review_note=p.note
    audit(s,u,"online_order_approved","online_purchase_order",order.id,{"record_id":record.id,"invoice_no":record.invoice_no,"payment_method":"sham_cash"},request=None)
    s.commit()
    customer_email=(order.customer_data or {}).get("email")
    approval_body=f"تم اعتماد طلب الشراء رقم #{order.id} بعد مراجعة إثبات الدفع.\\nرقم فاتورة المبيع: {record.invoice_no}\\nالإجمالي: {float(order.total):.2f} {order.currency}"
    approval_html=aib_email_html("تم اعتماد طلبك بنجاح",f"مرحباً {(order.customer_data or {}).get('full_name','')}، تمت مراجعة إثبات الدفع واعتماد طلبك. شكراً لثقتك بمجموعة AIB.",[("رقم الطلب",f"#{order.id}"),("رقم الفاتورة",html.escape(record.invoice_no)),("الإجمالي",f"{float(order.total):.2f} {html.escape(order.currency)}"),("الحالة","تم اعتماد الطلب")],accent="#168447",note="احتفظ برقم الفاتورة لمتابعة طلبك. سيقوم فريقنا بالتواصل معك بشأن التسليم.")
    send_notification_email(customer_email,f"تم اعتماد طلب الشراء #{order.id} - مجموعة AIB",approval_body,approval_html)
    return {"ok":True,"status":"approved","record_id":record.id,"invoice_no":record.invoice_no,"customer":order.customer_data}

@app.get("/public/products")
def public_products(q:Optional[str]=None, category:Optional[str]=None, s:Session=Depends(db)):
    query=select(InventoryProduct).where(InventoryProduct.active.is_(True))
    if q:
        term=f"%{q.strip()}%"
        query=query.where(or_(InventoryProduct.sku.ilike(term),InventoryProduct.name.ilike(term),InventoryProduct.model.ilike(term)))
    rows=s.scalars(query.order_by(InventoryProduct.sku).limit(300)).all()
    store_categories,latest_purchase=latest_store_catalog_data(s)
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
        if explicit_category:
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
        # Keep the N20 engine visible as an out-of-stock catalog item; do not expose other zero-stock items.
        if stock <= 0 and (p.model or "").strip().upper() != "N20B20B": continue
        price=latest_purchase.get(p.sku,{})
        out.append({"id":p.id,"sku":p.sku,"name":p.name,"model":p.model,"category":cat,"stock":stock,"images":p.images or [],"shipping_included":bool(p.shipping_included),"sale_price":price.get("sale_price"),"currency":price.get("currency","")})
    return out

# Serve the connected responsive web app from the same origin as the API.
from pathlib import Path
from fastapi.responses import FileResponse, Response
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
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
    allowed = {"vehiclesdb-catalog.json", "tractor-brands.json"}
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

@app.get("/aib-logo.webp", include_in_schema=False)
def aib_original_logo():
    logo_data = base64.b64decode((FRONTEND_DIR / "aib-logo.webp.b64").read_text(encoding="ascii").strip())
    return Response(content=logo_data, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})

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
