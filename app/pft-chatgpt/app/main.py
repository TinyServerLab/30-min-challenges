import csv
import io
import os
import secrets
import hashlib
import base64
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import jwt
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, DateTime, Numeric, ForeignKey, Text, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

DATABASE_URL = os.environ["DATABASE_URL"]
SECRET = os.environ["APP_SECRET"]
ALGO = "HS256"
TOKEN_DAYS = 7

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(320), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    password_hash = Column(String(300), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    type = Column(String(10), nullable=False)  # income / expense
    icon = Column(String(20), default="•")
    color = Column(String(20), default="#6366f1")

class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    kind = Column(String(40), default="Other")
    opening_balance = Column(Numeric(14,2), default=0)
    current_balance = Column(Numeric(14,2), default=0)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    amount = Column(Numeric(14,2), nullable=False)
    txn_date = Column(Date, nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    type = Column(String(10), nullable=False)  # income / expense
    note = Column(Text, default="")
    recurring = Column(Boolean, default=False, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    category = relationship("Category")
    source = relationship("Source")

class Investment(Base):
    __tablename__ = "investments"
    id = Column(Integer, primary_key=True)
    name = Column(String(160), nullable=False)
    kind = Column(String(40), nullable=False)
    contribution = Column(Numeric(14,2), nullable=False)
    current_value = Column(Numeric(14,2), nullable=False)
    entry_date = Column(Date, nullable=False)
    note = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

Base.metadata.create_all(engine)

def db():
    return SessionLocal()

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**15, r=8, p=1)
    return "scrypt$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()

def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, digest_b64 = stored.split("$")
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**15, r=8, p=1)
        return secrets.compare_digest(actual, expected)
    except Exception:
        return False

def create_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user.id), "iat": now, "exp": now + timedelta(days=TOKEN_DAYS)}, SECRET, algorithm=ALGO)

def current_user(request: Request, dbs: Session) -> Optional[User]:
    token = request.cookies.get("finance_session")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGO])
        uid = int(payload["sub"])
        return dbs.get(User, uid)
    except Exception:
        return None

def require_user(request: Request, dbs: Session) -> User:
    user = current_user(request, dbs)
    if not user:
        raise HTTPException(401, "Authentication required")
    return user

def seed():
    dbs = db()
    try:
        if dbs.query(User).count() == 0:
            email = os.environ.get("ADMIN_EMAIL", "admin@example.com").strip().lower()
            password = os.environ.get("ADMIN_PASSWORD", "change-me")
            name = os.environ.get("ADMIN_NAME", "Household Admin")
            dbs.add(User(email=email, name=name, password_hash=hash_password(password), is_admin=True))
        if os.environ.get("SEED_DEFAULTS", "true").lower() == "true":
            if dbs.query(Category).count() == 0:
                cats = [
                    ("Salary", "income", "₹", "#16a34a"), ("Other Income", "income", "+", "#22c55e"),
                    ("Food", "expense", "🍴", "#f97316"), ("Groceries", "expense", "🛒", "#eab308"),
                    ("Transport", "expense", "🚗", "#3b82f6"), ("Bills", "expense", "▣", "#8b5cf6"),
                    ("Shopping", "expense", "🛍", "#ec4899"), ("Health", "expense", "♥", "#ef4444"),
                    ("Education", "expense", "E", "#06b6d4"), ("Entertainment", "expense", "★", "#a855f7"),
                    ("Home", "expense", "⌂", "#64748b"), ("Other Expense", "expense", "•", "#475569"),
                ]
                dbs.add_all([Category(name=n, type=t, icon=i, color=c) for n,t,i,c in cats])
            if dbs.query(Source).count() == 0:
                srcs = ["Cash", "Bank Account", "Credit Card", "UPI", "Wallet"]
                dbs.add_all([Source(name=s, kind=s) for s in srcs])
        dbs.commit()
    finally:
        dbs.close()

seed()

app = FastAPI(title="Household Finance Tracker", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

def money(v):
    return float(Decimal(v or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def date_range(request: Request):
    start = request.query_params.get("start")
    end = request.query_params.get("end")
    today = date.today()
    if not start:
        start = today.replace(day=1).isoformat()
    if not end:
        end = today.isoformat()
    return date.fromisoformat(start), date.fromisoformat(end)

@app.get("/health")
def health():
    dbs = db()
    try:
        dbs.execute(func.count(User.id))
        return {"status": "ok"}
    finally:
        dbs.close()

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    dbs = db()
    try:
        user = current_user(request, dbs)
        if not user:
            return RedirectResponse("/login", status_code=303)
        return templates.TemplateResponse("index.html", {"request": request, "user": user})
    finally:
        dbs.close()

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    dbs = db()
    try:
        if current_user(request, dbs):
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse("index.html", {"request": request, "login_only": True})
    finally:
        dbs.close()

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...)):
    dbs = db()
    try:
        user = dbs.query(User).filter(func.lower(User.email) == email.strip().lower()).first()
        if not user or not verify_password(password, user.password_hash):
            return RedirectResponse("/login?error=1", status_code=303)
        r = RedirectResponse("/", status_code=303)
        r.set_cookie("finance_session", create_token(user), httponly=True, secure=False, samesite="lax", max_age=TOKEN_DAYS*86400, path="/")
        return r
    finally:
        dbs.close()

@app.post("/logout")
def logout():
    r = RedirectResponse("/login", status_code=303)
    r.delete_cookie("finance_session", path="/")
    return r

@app.get("/api/bootstrap")
def bootstrap(request: Request):
    dbs = db(); user = require_user(request, dbs)
    try:
        cats = [{"id":c.id,"name":c.name,"type":c.type,"icon":c.icon,"color":c.color} for c in dbs.query(Category).order_by(Category.type, Category.name).all()]
        srcs = [{"id":s.id,"name":s.name,"kind":s.kind,"opening_balance":money(s.opening_balance),"current_balance":money(s.current_balance)} for s in dbs.query(Source).order_by(Source.name).all()]
        users = [{"id":u.id,"name":u.name,"email":u.email,"is_admin":u.is_admin} for u in dbs.query(User).order_by(User.name).all()] if user.is_admin else []
        return {"user":{"id":user.id,"name":user.name,"email":user.email,"is_admin":user.is_admin},"categories":cats,"sources":srcs,"users":users}
    finally: dbs.close()

@app.get("/api/dashboard")
def dashboard(request: Request):
    dbs = db(); require_user(request, dbs)
    try:
        start, end = date_range(request)
        rows = dbs.query(Transaction).filter(Transaction.txn_date.between(start,end)).all()
        income = sum(money(t.amount) for t in rows if t.type=="income")
        expense = sum(money(t.amount) for t in rows if t.type=="expense")
        bycat = {}
        for t in rows:
            if t.type == "expense":
                key = t.category.name
                bycat.setdefault(key, {"name":key,"value":0,"color":t.category.color})
                bycat[key]["value"] += money(t.amount)
        sources = dbs.query(Source).all()
        source_total = sum(money(s.current_balance) for s in sources)
        investments = dbs.query(Investment).all()
        invest_total = sum(money(i.current_value) for i in investments)
        networth = source_total + invest_total
        trend = []
        cursor = start
        while cursor <= end:
            val = sum(money(t.amount) * (1 if t.type=="income" else -1) for t in rows if t.txn_date == cursor)
            trend.append({"date":cursor.isoformat(),"net":val})
            cursor += timedelta(days=1)
        return {"start":start.isoformat(),"end":end.isoformat(),"income":income,"expense":expense,"savings":income-expense,
                "source_total":source_total,"investment_total":invest_total,"networth":networth,
                "categories":list(bycat.values()),"trend":trend}
    finally: dbs.close()

@app.get("/api/transactions")
def transactions(request: Request):
    dbs = db(); require_user(request, dbs)
    try:
        start,end=date_range(request)
        rows=dbs.query(Transaction).filter(Transaction.txn_date.between(start,end)).order_by(Transaction.txn_date.desc(),Transaction.id.desc()).limit(500).all()
        return [{"id":t.id,"amount":money(t.amount),"date":t.txn_date.isoformat(),"category_id":t.category_id,"category":t.category.name,
                 "source_id":t.source_id,"source":t.source.name,"type":t.type,"note":t.note or "","recurring":t.recurring} for t in rows]
    finally: dbs.close()

@app.post("/api/transactions")
async def add_transaction(request: Request):
    dbs=db(); user=require_user(request,dbs)
    try:
        p=await request.json()
        t=Transaction(amount=Decimal(str(p["amount"])),txn_date=date.fromisoformat(p["date"]),category_id=int(p["category_id"]),
                      source_id=int(p["source_id"]),type=p["type"],note=p.get("note",""),recurring=bool(p.get("recurring",False)),created_by=user.id)
        dbs.add(t); dbs.commit()
        recalc_source(dbs, t.source_id)
        dbs.commit()
        return {"ok":True,"id":t.id}
    finally: dbs.close()

@app.put("/api/transactions/{tid}")
async def edit_transaction(tid:int, request:Request):
    dbs=db(); require_user(request,dbs)
    try:
        t=dbs.get(Transaction,tid)
        if not t: raise HTTPException(404,"Not found")
        old_source=t.source_id
        p=await request.json()
        t.amount=Decimal(str(p["amount"])); t.txn_date=date.fromisoformat(p["date"]); t.category_id=int(p["category_id"])
        t.source_id=int(p["source_id"]); t.type=p["type"]; t.note=p.get("note",""); t.recurring=bool(p.get("recurring",False))
        dbs.commit(); recalc_source(dbs,old_source); recalc_source(dbs,t.source_id); dbs.commit()
        return {"ok":True}
    finally: dbs.close()

@app.delete("/api/transactions/{tid}")
def delete_transaction(tid:int,request:Request):
    dbs=db(); require_user(request,dbs)
    try:
        t=dbs.get(Transaction,tid)
        if not t: raise HTTPException(404,"Not found")
        sid=t.source_id; dbs.delete(t); dbs.commit(); recalc_source(dbs,sid); dbs.commit()
        return {"ok":True}
    finally: dbs.close()

def recalc_source(dbs,sid):
    s=dbs.get(Source,sid)
    if not s:return
    inc=dbs.query(func.coalesce(func.sum(Transaction.amount),0)).filter(Transaction.source_id==sid,Transaction.type=="income").scalar()
    exp=dbs.query(func.coalesce(func.sum(Transaction.amount),0)).filter(Transaction.source_id==sid,Transaction.type=="expense").scalar()
    s.current_balance=Decimal(s.opening_balance or 0)+Decimal(inc or 0)-Decimal(exp or 0)

@app.get("/api/categories")
def categories(request:Request):
    dbs=db(); require_user(request,dbs)
    try:return [{"id":c.id,"name":c.name,"type":c.type,"icon":c.icon,"color":c.color} for c in dbs.query(Category).order_by(Category.type,Category.name).all()]
    finally:dbs.close()

@app.post("/api/categories")
async def add_category(request:Request):
    dbs=db(); require_user(request,dbs)
    try:
        p=await request.json(); c=Category(name=p["name"].strip(),type=p["type"],icon=p.get("icon","•"),color=p.get("color","#6366f1"))
        dbs.add(c);dbs.commit();return {"ok":True,"id":c.id}
    finally:dbs.close()

@app.put("/api/categories/{cid}")
async def edit_category(cid:int,request:Request):
    dbs=db(); require_user(request,dbs)
    try:
        c=dbs.get(Category,cid)
        if not c: raise HTTPException(404,"Not found")
        p=await request.json(); c.name=p["name"].strip(); c.type=p["type"]; c.icon=p.get("icon","•"); c.color=p.get("color","#6366f1"); dbs.commit()
        return {"ok":True}
    finally:dbs.close()

@app.delete("/api/categories/{cid}")
def del_category(cid:int,request:Request):
    dbs=db(); require_user(request,dbs)
    try:
        if dbs.query(Transaction).filter(Transaction.category_id==cid).first(): raise HTTPException(409,"Category is used by transactions")
        c=dbs.get(Category,cid)
        if c: dbs.delete(c);dbs.commit()
        return {"ok":True}
    finally:dbs.close()

@app.get("/api/sources")
def sources(request:Request):
    dbs=db(); require_user(request,dbs)
    try:return [{"id":s.id,"name":s.name,"kind":s.kind,"opening_balance":money(s.opening_balance),"current_balance":money(s.current_balance)} for s in dbs.query(Source).order_by(Source.name).all()]
    finally:dbs.close()

@app.post("/api/sources")
async def add_source(request:Request):
    dbs=db(); require_user(request,dbs)
    try:
        p=await request.json(); s=Source(name=p["name"].strip(),kind=p.get("kind","Other"),opening_balance=Decimal(str(p.get("opening_balance",0))),current_balance=Decimal(str(p.get("opening_balance",0))))
        dbs.add(s);dbs.commit();return {"ok":True,"id":s.id}
    finally:dbs.close()

@app.put("/api/sources/{sid}")
async def edit_source(sid:int,request:Request):
    dbs=db(); require_user(request,dbs)
    try:
        s=dbs.get(Source,sid)
        if not s: raise HTTPException(404,"Not found")
        p=await request.json(); s.name=p["name"].strip();s.kind=p.get("kind","Other");s.opening_balance=Decimal(str(p.get("opening_balance",0)));dbs.commit();recalc_source(dbs,sid);dbs.commit()
        return {"ok":True}
    finally:dbs.close()

@app.delete("/api/sources/{sid}")
def del_source(sid:int,request:Request):
    dbs=db(); require_user(request,dbs)
    try:
        if dbs.query(Transaction).filter(Transaction.source_id==sid).first(): raise HTTPException(409,"Source is used by transactions")
        s=dbs.get(Source,sid)
        if s:dbs.delete(s);dbs.commit()
        return {"ok":True}
    finally:dbs.close()

@app.get("/api/investments")
def investments(request:Request):
    dbs=db(); require_user(request,dbs)
    try:
        return [{"id":i.id,"name":i.name,"kind":i.kind,"contribution":money(i.contribution),"current_value":money(i.current_value),"date":i.entry_date.isoformat(),"note":i.note or ""} for i in dbs.query(Investment).order_by(Investment.entry_date.desc()).all()]
    finally:dbs.close()

@app.post("/api/investments")
async def add_investment(request:Request):
    dbs=db(); user=require_user(request,dbs)
    try:
        p=await request.json(); i=Investment(name=p["name"],kind=p["kind"],contribution=Decimal(str(p["contribution"])),current_value=Decimal(str(p["current_value"])),entry_date=date.fromisoformat(p["date"]),note=p.get("note",""),created_by=user.id)
        dbs.add(i);dbs.commit();return {"ok":True,"id":i.id}
    finally:dbs.close()

@app.put("/api/investments/{iid}")
async def edit_investment(iid:int,request:Request):
    dbs=db(); require_user(request,dbs)
    try:
        i=dbs.get(Investment,iid)
        if not i: raise HTTPException(404,"Not found")
        p=await request.json();i.name=p["name"];i.kind=p["kind"];i.contribution=Decimal(str(p["contribution"]));i.current_value=Decimal(str(p["current_value"]));i.entry_date=date.fromisoformat(p["date"]);i.note=p.get("note","");dbs.commit();return {"ok":True}
    finally:dbs.close()

@app.delete("/api/investments/{iid}")
def del_investment(iid:int,request:Request):
    dbs=db();require_user(request,dbs)
    try:
        i=dbs.get(Investment,iid)
        if i:dbs.delete(i);dbs.commit()
        return {"ok":True}
    finally:dbs.close()

@app.post("/api/users")
async def add_user(request:Request):
    dbs=db(); user=require_user(request,dbs)
    if not user.is_admin: raise HTTPException(403,"Admin only")
    try:
        p=await request.json(); email=p["email"].strip().lower()
        if dbs.query(User).filter(func.lower(User.email)==email).first(): raise HTTPException(409,"Email already exists")
        u=User(email=email,name=p["name"].strip(),password_hash=hash_password(p["password"]),is_admin=bool(p.get("is_admin",False)))
        dbs.add(u);dbs.commit();return {"ok":True,"id":u.id}
    finally:dbs.close()

@app.delete("/api/users/{uid}")
def del_user(uid:int,request:Request):
    dbs=db(); user=require_user(request,dbs)
    if not user.is_admin: raise HTTPException(403,"Admin only")
    if uid==user.id: raise HTTPException(400,"Cannot delete yourself")
    try:
        u=dbs.get(User,uid)
        if u:dbs.delete(u);dbs.commit()
        return {"ok":True}
    finally:dbs.close()

def make_pdf(title, start, end, rows, income, expense):
    # Minimal dependency-free PDF writer: text-only report, suitable for household export.
    lines=[title, f"Period: {start} to {end}", "", f"Income: {income:,.2f}", f"Expense: {expense:,.2f}", f"Net: {income-expense:,.2f}", "", "Date | Type | Category | Source | Amount | Note"]
    for t in rows[:120]:
        note=(t.note or "").replace("|","/").replace("\n"," ")[:45]
        lines.append(f"{t.txn_date} | {t.type} | {t.category.name[:18]} | {t.source.name[:18]} | {money(t.amount):,.2f} | {note}")
    # PDF content stream using Helvetica; escape PDF special chars.
    esc=lambda s:s.replace("\\","\\\\").replace("(","\\(").replace(")","\\)")
    content=["BT","/F1 8 Tf","40 800 Td"]
    for idx,line in enumerate(lines):
        if idx>0: content.append("0 -12 Td")
        content.append(f"({esc(line)}) Tj")
    content.append("ET")
    stream="\n".join(content).encode()
    objs=[]
    def obj(n,s): objs.append(f"{n} 0 obj\n{s}\nendobj\n")
    obj(1,"<< /Type /Catalog /Pages 2 0 R >>")
    obj(2,"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    obj(3,"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>")
    obj(4,"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    obj(5,f"<< /Length {len(stream)} >>\nstream\n{stream.decode()}\nendstream")
    pdf=b"%PDF-1.4\n"; offsets=[0]
    for o in objs:
        offsets.append(len(pdf)); pdf+=o.encode()
    xref=len(pdf); pdf+=f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode()
    for off in offsets[1:]: pdf+=f"{off:010d} 00000 n \n".encode()
    pdf+=f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return pdf

@app.get("/api/report.csv")
def report_csv(request:Request):
    dbs=db();require_user(request,dbs)
    try:
        start,end=date_range(request);rows=dbs.query(Transaction).filter(Transaction.txn_date.between(start,end)).order_by(Transaction.txn_date).all()
        out=io.StringIO();w=csv.writer(out);w.writerow(["Date","Type","Category","Source","Amount","Recurring","Note"])
        for t in rows:w.writerow([t.txn_date,t.type,t.category.name,t.source.name,money(t.amount),t.recurring,t.note or ""])
        return StreamingResponse(iter([out.getvalue()]),media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="finance-{start}-{end}.csv"'})
    finally:dbs.close()

@app.get("/api/report.pdf")
def report_pdf(request:Request):
    dbs=db();require_user(request,dbs)
    try:
        start,end=date_range(request);rows=dbs.query(Transaction).filter(Transaction.txn_date.between(start,end)).order_by(Transaction.txn_date).all()
        income=sum(money(t.amount) for t in rows if t.type=="income");expense=sum(money(t.amount) for t in rows if t.type=="expense")
        pdf=make_pdf("Household Finance Report",start,end,rows,income,expense)
        return Response(pdf,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="finance-{start}-{end}.pdf"'})
    finally:dbs.close()
