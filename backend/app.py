from datetime import datetime, timedelta, timezone
from typing import Optional, Any
import os, secrets
import jwt
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from pwdlib import PasswordHash
from sqlalchemy import create_engine, String, Boolean, DateTime, Integer, ForeignKey, JSON, Text, Numeric, select, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://aib:aib_change_me@db:5432/aib"
    jwt_secret: str = "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET_BEFORE_DEPLOYMENT"
    jwt_minutes: int = 30
    owner_username: str = "abdulkarim"
    owner_password: str = ""
    owner_name: str = "عبد الكريم محمد بن خيرو"
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
    password_hash: Mapped[str]=mapped_column(String(300))
    role: Mapped[str]=mapped_column(String(20), default="employee")
    active: Mapped[bool]=mapped_column(Boolean, default=True)
    failed_logins: Mapped[int]=mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
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

def db():
    s=SessionLocal()
    try: yield s
    finally: s.close()
def audit(s:Session, user:Optional[User], action:str, entity:str, entity_id:Optional[int], details:dict, request:Optional[Request]=None):
    s.add(AuditEvent(user_id=user.id if user else None, action=action, entity=entity, entity_id=entity_id, details=details, ip_address=request.client.host if request and request.client else ""))
def token_for(user:User):
    now=datetime.now(timezone.utc)
    return jwt.encode({"sub":str(user.id),"iat":now,"exp":now+timedelta(minutes=settings.jwt_minutes)},settings.jwt_secret,algorithm="HS256")
def current_user(token:str=Depends(oauth), s:Session=Depends(db)):
    try: uid=int(jwt.decode(token,settings.jwt_secret,algorithms=["HS256"])["sub"])
    except Exception: raise HTTPException(401,"جلسة الدخول غير صالحة أو انتهت")
    u=s.get(User,uid)
    if not u or not u.active: raise HTTPException(401,"الحساب غير فعال")
    return u
def manager(u:User=Depends(current_user)):
    if u.role!="owner": raise HTTPException(403,"هذا الإجراء متاح للمدير فقط")
    return u
def can_add(u:User=Depends(current_user)): return u

@app.on_event("startup")
def startup():
    if settings.jwt_secret.startswith("CHANGE_THIS") and os.getenv("ENVIRONMENT")=="production":
        raise RuntimeError("Set a strong JWT_SECRET before production")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE cash_moves ADD COLUMN IF NOT EXISTS transfer_group VARCHAR(36)"))
        conn.execute(text("ALTER TABLE invoice_payments ADD COLUMN IF NOT EXISTS cash_box VARCHAR(100) NOT NULL DEFAULT 'صندوق المبيع'"))
    if settings.owner_password:
        with SessionLocal() as s:
            if not s.scalar(select(User).where(User.username==settings.owner_username)):
                s.add(User(username=settings.owner_username,full_name=settings.owner_name,password_hash=password_hash.hash(settings.owner_password),role="owner")); s.commit()

@app.get("/health")
def health(): return {"status":"ok","service":"AIB Accounting API"}
@app.post("/auth/login")
def login(form:OAuth2PasswordRequestForm=Depends(), request:Request=None, s:Session=Depends(db)):
    u=s.scalar(select(User).where(User.username==form.username))
    now=datetime.now(timezone.utc)
    if not u:
        audit(s,None,"login_failed","user",None,{"username":form.username},request); s.commit(); raise HTTPException(401,"اسم المستخدم أو كلمة المرور غير صحيحة")
    if u.locked_until and u.locked_until>now: raise HTTPException(423,"الحساب مقفل مؤقتاً، حاول لاحقاً")
    if not password_hash.verify(form.password,u.password_hash):
        u.failed_logins+=1
        if u.failed_logins>=3: u.locked_until=now+timedelta(minutes=5); u.failed_logins=0
        audit(s,u,"login_failed","user",u.id,{},request); s.commit(); raise HTTPException(401,"اسم المستخدم أو كلمة المرور غير صحيحة")
    if not u.active: raise HTTPException(403,"الحساب غير فعال")
    u.failed_logins=0; u.locked_until=None; audit(s,u,"login","user",u.id,{},request); s.commit()
    return {"access_token":token_for(u),"token_type":"bearer","user":{"id":u.id,"username":u.username,"name":u.full_name,"role":u.role}}
@app.get("/auth/me")
def me(u:User=Depends(current_user)): return {"id":u.id,"username":u.username,"name":u.full_name,"role":u.role}

class UserCreate(BaseModel): username:str=Field(min_length=3,max_length=80); full_name:str; password:str=Field(min_length=12); role:str="employee"
@app.get("/users")
def list_users(s:Session=Depends(db), _:User=Depends(manager)):
    return [{"id":u.id,"username":u.username,"name":u.full_name,"role":u.role,"active":u.active} for u in s.scalars(select(User)).all()]
@app.post("/users")
def add_user(payload:UserCreate, request:Request, s:Session=Depends(db), u:User=Depends(manager)):
    if payload.role not in ("employee","owner"): raise HTTPException(400,"دور غير صالح")
    if s.scalar(select(User).where(User.username==payload.username)): raise HTTPException(409,"اسم المستخدم مستخدم")
    nu=User(username=payload.username,full_name=payload.full_name,password_hash=password_hash.hash(payload.password),role="employee")
    s.add(nu); s.flush(); audit(s,u,"user_created","user",nu.id,{"username":nu.username},request); s.commit(); return {"id":nu.id,"username":nu.username}
@app.patch("/users/{user_id}/active")
def set_user_active(user_id:int, active:bool, request:Request, s:Session=Depends(db), u:User=Depends(manager)):
    target=s.get(User,user_id)
    if not target: raise HTTPException(404,"المستخدم غير موجود")
    if target.role=="owner": raise HTTPException(400,"لا يمكن تعطيل حساب المالك")
    target.active=active; audit(s,u,"user_status_changed","user",user_id,{"active":active},request); s.commit(); return {"ok":True}

class RecordCreate(BaseModel): section:str; invoice_no:Optional[str]=None; currency:str="USD"; data:dict
@app.post("/records")
def create_record(p:RecordCreate, request:Request, s:Session=Depends(db), u:User=Depends(can_add)):
    if p.section not in {"deposit","purchase","consignSale","directSale","repair","carPurchase","carSale"}: raise HTTPException(400,"قسم غير معروف")
    if p.currency not in {"USD","SYP"}: raise HTTPException(400,"عملة غير مدعومة")
    r=Record(section=p.section,invoice_no=p.invoice_no,currency=p.currency,data=p.data,created_by=u.id)
    s.add(r); s.flush(); audit(s,u,"record_created","record",r.id,{"section":r.section,"invoice_no":r.invoice_no},request); s.commit(); return {"id":r.id,"created_at":r.created_at}
@app.get("/records")
def list_records(section:Optional[str]=None, s:Session=Depends(db), u:User=Depends(current_user)):
    q=select(Record).where(Record.deleted==False)
    if section: q=q.where(Record.section==section)
    out=[]
    for r in s.scalars(q.order_by(Record.id.desc())).all():
        pays=s.scalars(select(InvoicePayment).where(InvoicePayment.record_id==r.id).order_by(InvoicePayment.id)).all()
        total=float(r.data.get("amount",r.data.get("price",r.data.get("sale",0))) or 0)
        paid=sum(float(x.amount) for x in pays)
        out.append({"id":r.id,"section":r.section,"invoice_no":r.invoice_no,"currency":r.currency,"data":r.data,"created_by":r.created_by,"created_at":r.created_at,"updated_at":r.updated_at,"payments":[{"id":x.id,"amount":float(x.amount),"method":x.method,"cash_box":x.cash_box,"paid_at":x.paid_at} for x in pays],"paid_total":round(paid,2),"remaining":round(max(total-paid,0),2),"payment_status":"paid" if total>0 and paid>=total else "partial" if paid>0 else "unpaid"})
    return out
class PaymentPayload(BaseModel):
    amount: float = Field(gt=0)
    method: str
    paid_at: Optional[datetime] = None
    cash_box: str = "صندوق المبيع"

@app.post("/records/{record_id}/payments")
def add_invoice_payment(record_id:int,p:PaymentPayload,request:Request,s:Session=Depends(db),u:User=Depends(can_add)):
    r=s.get(Record,record_id)
    if not r or r.deleted: raise HTTPException(404,"الفاتورة غير موجودة")
    if p.method not in {"cash","baraka_bank","sham_cash","syriatel_cash"}: raise HTTPException(400,"طريقة الدفع غير صالحة")
    total=float(r.data.get("amount",r.data.get("price",r.data.get("sale",0))) or 0)
    paid=float(s.scalar(select(func.coalesce(func.sum(InvoicePayment.amount),0)).where(InvoicePayment.record_id==record_id)) or 0)
    if round(paid+p.amount,2)>round(total,2): raise HTTPException(400,"مجموع الدفعات يتجاوز إجمالي الفاتورة")
    if not p.cash_box.strip(): raise HTTPException(400,"اختر الصندوق الذي ستدخل إليه الدفعة")
    x=InvoicePayment(record_id=record_id,amount=p.amount,method=p.method,cash_box=p.cash_box,paid_at=p.paid_at or datetime.now(timezone.utc),created_by=u.id)
    s.add(x); s.flush()
    movement="withdrawal" if r.section in {"purchase","carPurchase"} else "deposit"
    s.add(CashMove(box_name=p.cash_box,movement=movement,amount=p.amount,currency=r.currency,description=("دفعة فاتورة "+(r.invoice_no or str(r.id))),created_by=u.id))
    audit(s,u,"invoice_payment_created","invoice_payment",x.id,{"record_id":record_id,"amount":p.amount,"method":p.method,"cash_box":p.cash_box,"cash_movement":movement},request); s.commit()
    return {"id":x.id,"record_id":record_id,"amount":float(x.amount),"method":x.method,"cash_box":x.cash_box,"paid_at":x.paid_at}

@app.get("/records/{record_id}/payments")
def list_invoice_payments(record_id:int,s:Session=Depends(db),u:User=Depends(current_user)):
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
    s.add(CashMove(box_name=payment.cash_box,movement=reverse,amount=payment.amount,currency=r.currency,description=f"تسوية عكسية للدفعة رقم {payment.id} - فاتورة {r.invoice_no or r.id} ({reason})",created_by=u.id))

@app.put("/records/{record_id}/payments/{payment_id}")
def update_invoice_payment(record_id:int,payment_id:int,p:PaymentUpdatePayload,request:Request,s:Session=Depends(db),u:User=Depends(manager)):
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
    movement="withdrawal" if r.section=="purchase" else "deposit"
    s.add(CashMove(box_name=p.cash_box,movement=movement,amount=p.amount,currency=r.currency,description=f"تسجيل بديل للدفعة رقم {x.id} - فاتورة {r.invoice_no or r.id}",created_by=u.id))
    old={"amount":float(x.amount),"method":x.method,"cash_box":x.cash_box,"paid_at":str(x.paid_at)}
    x.amount=p.amount; x.method=p.method; x.cash_box=p.cash_box
    if p.paid_at: x.paid_at=p.paid_at
    audit(s,u,"invoice_payment_updated","invoice_payment",x.id,{"record_id":record_id,"old":old,"new":{"amount":p.amount,"method":p.method,"cash_box":p.cash_box,"paid_at":str(x.paid_at)},"cash_adjustment":"automatic_reversal_and_replacement"},request)
    s.commit()
    return {"ok":True,"id":x.id}

@app.delete("/records/{record_id}/payments/{payment_id}")
def delete_invoice_payment(record_id:int,payment_id:int,request:Request,s:Session=Depends(db),u:User=Depends(manager)):
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
    if not s.get(Record,record_id): raise HTTPException(404,"السجل غير موجود")
    if p.action=="update" and p.proposed_data is None: raise HTTPException(400,"البيانات المقترحة مطلوبة")
    cr=ChangeRequest(record_id=record_id,requested_by=u.id,action=p.action,proposed_data=p.proposed_data,reason=p.reason)
    s.add(cr); s.flush(); audit(s,u,"change_requested","record",record_id,{"request_id":cr.id,"action":p.action},request); s.commit(); return {"request_id":cr.id,"status":"pending"}
@app.get("/change-requests")
def requests(s:Session=Depends(db),_:User=Depends(manager)):
    return [{"id":x.id,"record_id":x.record_id,"requested_by":x.requested_by,"action":x.action,"proposed_data":x.proposed_data,"reason":x.reason,"status":x.status,"created_at":x.created_at} for x in s.scalars(select(ChangeRequest).where(ChangeRequest.status=="pending")).all()]
def ensure_total_covers_payments(s:Session, record_id:int, new_data:dict):
    total=float(new_data.get("amount",new_data.get("price",new_data.get("sale",0))) or 0)
    paid=float(s.scalar(select(func.coalesce(func.sum(InvoicePayment.amount),0)).where(InvoicePayment.record_id==record_id)) or 0)
    if round(total,2)<round(paid,2):
        raise HTTPException(400,"لا يمكن تخفيض إجمالي الفاتورة إلى أقل من مجموع الدفعات المسجلة")

@app.post("/change-requests/{request_id}/approve")
def approve(request_id:int,approve:bool,request:Request,s:Session=Depends(db),u:User=Depends(manager)):
    cr=s.get(ChangeRequest,request_id)
    if not cr or cr.status!="pending": raise HTTPException(404,"الطلب غير موجود أو تمت معالجته")
    rec=s.get(Record,cr.record_id)
    if approve:
        if cr.action=="delete": rec.deleted=True
        else:
            ensure_total_covers_payments(s,rec.id,cr.proposed_data)
            rec.data=cr.proposed_data; rec.updated_at=datetime.now(timezone.utc)
    cr.status="approved" if approve else "rejected"; cr.reviewed_by=u.id; cr.reviewed_at=datetime.now(timezone.utc)
    audit(s,u,"change_request_"+cr.status,"record",cr.record_id,{"request_id":cr.id},request); s.commit(); return {"status":cr.status}
class CashPayload(BaseModel): box_name:str; movement:str; amount:float=Field(gt=0); currency:str="USD"; description:str=""
class CashTransferPayload(BaseModel):
    source_box:str
    destination_box:str
    amount:float=Field(gt=0)
    currency:str="USD"
    description:str=""
@app.post("/cash-movements")
def cash_move(p:CashPayload,request:Request,s:Session=Depends(db),u:User=Depends(can_add)):
    if p.movement not in ("deposit","withdrawal"): raise HTTPException(400,"اختر إيداعاً أو سحباً؛ التحويل بين الصناديق له عملية مستقلة")
    if p.currency not in ("USD","SYP"): raise HTTPException(400,"عملة غير مدعومة")
    m=CashMove(**p.model_dump(),created_by=u.id); s.add(m); s.flush(); audit(s,u,"cash_movement_created","cash",m.id,{"box":p.box_name,"movement":p.movement,"amount":p.amount,"currency":p.currency},request); s.commit(); return {"id":m.id}
@app.post("/cash-transfers")
def cash_transfer(p:CashTransferPayload,request:Request,s:Session=Depends(db),u:User=Depends(can_add)):
    if p.source_box==p.destination_box: raise HTTPException(400,"يجب اختيار صندوقين مختلفين")
    if p.currency not in ("USD","SYP"): raise HTTPException(400,"عملة غير مدعومة")
    rows=s.scalars(select(CashMove).where(CashMove.box_name==p.source_box,CashMove.currency==p.currency).with_for_update()).all()
    balance=sum((1 if x.movement in ("deposit","transfer_in") else -1)*float(x.amount) for x in rows)
    if round(balance,2)<round(p.amount,2): raise HTTPException(400,"رصيد الصندوق المصدر غير كافٍ")
    import uuid
    group=str(uuid.uuid4())
    source=CashMove(box_name=p.source_box,movement="withdrawal",amount=p.amount,currency=p.currency,description=("تحويل إلى "+p.destination_box+" · "+p.description).strip(" ·"),created_by=u.id,transfer_group=group)
    dest=CashMove(box_name=p.destination_box,movement="deposit",amount=p.amount,currency=p.currency,description=("تحويل من "+p.source_box+" · "+p.description).strip(" ·"),created_by=u.id,transfer_group=group)
    s.add_all([source,dest]); s.flush()
    audit(s,u,"cash_transfer_created","cash_transfer",source.id,{"transfer_group":group,"from":p.source_box,"to":p.destination_box,"amount":p.amount,"currency":p.currency},request)
    s.commit()
    return {"ok":True,"transfer_group":group,"source_movement_id":source.id,"destination_movement_id":dest.id}

@app.get("/cash-boxes/{box_name}/movements")
def cash_box_movements(box_name:str,s:Session=Depends(db),u:User=Depends(current_user)):
    rows=s.scalars(select(CashMove).where(CashMove.box_name==box_name).order_by(CashMove.id.desc())).all()
    return [{"id":m.id,"box_name":m.box_name,"movement":m.movement,"amount":float(m.amount),"currency":m.currency,"description":m.description,"created_by":m.created_by,"created_at":m.created_at,"transfer_group":m.transfer_group} for m in rows]

@app.get("/cash-movements")
def cash_list(s:Session=Depends(db),u:User=Depends(current_user)):
    return [{"id":m.id,"box_name":m.box_name,"movement":m.movement,"amount":float(m.amount),"currency":m.currency,"description":m.description,"created_by":m.created_by,"created_at":m.created_at,"transfer_group":m.transfer_group} for m in s.scalars(select(CashMove).order_by(CashMove.id.desc())).all()]
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
def update_record(record_id:int, p:RecordUpdate, request:Request, s:Session=Depends(db), u:User=Depends(manager)):
    r=s.get(Record,record_id)
    if not r or r.deleted: raise HTTPException(404,"السجل غير موجود")
    if p.currency not in ("USD","SYP"): raise HTTPException(400,"عملة غير مدعومة")
    ensure_total_covers_payments(s,r.id,p.data)
    r.data=p.data; r.invoice_no=p.invoice_no; r.currency=p.currency; r.updated_at=datetime.now(timezone.utc)
    audit(s,u,"record_updated","record",r.id,{"section":r.section,"invoice_no":r.invoice_no},request); s.commit(); return {"ok":True}

@app.delete("/records/{record_id}")
def delete_record(record_id:int, request:Request, s:Session=Depends(db), u:User=Depends(manager)):
    r=s.get(Record,record_id)
    if not r or r.deleted: raise HTTPException(404,"السجل غير موجود")
    r.deleted=True; r.updated_at=datetime.now(timezone.utc)
    audit(s,u,"record_deleted","record",r.id,{"section":r.section},request); s.commit(); return {"ok":True}

@app.get("/my-change-requests")
def my_requests(s:Session=Depends(db),u:User=Depends(current_user)):
    rows=s.scalars(select(ChangeRequest).where(ChangeRequest.requested_by==u.id).order_by(ChangeRequest.id.desc()).limit(200)).all()
    return [{"id":x.id,"record_id":x.record_id,"action":x.action,"reason":x.reason,"status":x.status,"created_at":x.created_at} for x in rows]

@app.get("/cash-summary")
def cash_summary(s:Session=Depends(db),u:User=Depends(current_user)):
    rows=s.scalars(select(CashMove)).all(); out={}
    for m in rows:
        key=f"{m.box_name}|{m.currency}"
        sign=1 if m.movement in ("deposit","transfer_in") else -1
        out[key]=out.get(key,0)+sign*float(m.amount)
    return [{"box_name":k.rsplit("|",1)[0],"currency":k.rsplit("|",1)[1],"balance":v} for k,v in out.items()]

# Serve the connected responsive web app from the same origin as the API.
from pathlib import Path
from fastapi.responses import FileResponse
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
@app.get("/", include_in_schema=False)
def home():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/sham_cash_qr.png", include_in_schema=False)
def sham_cash_qr():
    return FileResponse(FRONTEND_DIR / "sham_cash_qr.png", media_type="image/png")

@app.get("/logo.png", include_in_schema=False)
def logo():
    return FileResponse(FRONTEND_DIR / "logo.png", media_type="image/png")
