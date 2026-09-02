import os
import uuid
import urllib.request
import urllib.parse
import json
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from typing import Optional, Any
from datetime import datetime
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import UploadFile
from wtforms import FileField
from pydantic import BaseModel
from fastapi import APIRouter

# ЗАМЕНИ ЭТУ СТРОКУ на свои данные из Supabase (Settings -> Database -> Connection string -> URI)
# Пример: postgresql+psycopg2://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
DATABASE_URL = "postgresql+psycopg2://postgres:blaserfeed31@db.yfidjtjkvdroknxtezwq.supabase.co:5432/postgres"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Property(Base):
    __tablename__ = "properties"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, index=True)
    deal_type = Column(String)
    property_type = Column(String)
    building_class = Column(String, nullable=True)
    area_min = Column(Integer)
    area_max = Column(Integer)
    price = Column(Float)
    price_unit = Column(String)
    no_commission = Column(Boolean, default=False)
    image_url = Column(String, nullable=True)
    image_url_2 = Column(String, nullable=True)
    image_url_3 = Column(String, nullable=True)
    image_url_4 = Column(String, nullable=True)
    image_url_5 = Column(String, nullable=True)
    image_url_6 = Column(String, nullable=True)
    image_url_7 = Column(String, nullable=True)
    image_url_8 = Column(String, nullable=True)
    image_url_9 = Column(String, nullable=True)
    image_url_10 = Column(String, nullable=True)
    is_exclusive = Column(Boolean, default=False)
    show_on_landing = Column(Boolean, default=False)
    broker_id = Column(Integer, nullable=True)
    address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    role = Column(String, default="broker")

    full_name = Column(String, nullable=True)
    position = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    whatsapp = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)

class ManagementLeadDB(Base):
    __tablename__ = "management_leads"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    property_type = Column(String, nullable=False)
    area = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Так как таблицы мы уже перенесли через SQL Editor, блок миграций ниже просто подстрахует структуру
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE properties ADD COLUMN IF NOT EXISTS image_url_2 VARCHAR;"))
        conn.execute(text("ALTER TABLE properties ADD COLUMN IF NOT EXISTS image_url_3 VARCHAR;"))
        conn.execute(text("ALTER TABLE properties ADD COLUMN IF NOT EXISTS image_url_4 VARCHAR;"))
        for i in range(5, 11):
            conn.execute(text(f"ALTER TABLE properties ADD COLUMN IF NOT EXISTS image_url_{i} VARCHAR;"))     
        conn.execute(text("ALTER TABLE properties ADD COLUMN IF NOT EXISTS show_on_landing BOOLEAN DEFAULT FALSE;"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR;"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS position VARCHAR;"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR;"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp VARCHAR;"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS photo_url VARCHAR;"))
        conn.commit()
except Exception:
    pass

with SessionLocal() as db:
    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        admin_user = User(username="admin", password="123456", role="admin", full_name="Главный Администратор")
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

    if admin_user:
        db.execute(text(f"UPDATE properties SET broker_id = {admin_user.id} WHERE broker_id IS NULL"))
        db.commit()

os.makedirs("static/uploads", exist_ok=True)

app = FastAPI()
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

class IframeCookieMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for i, (key, value) in enumerate(response.headers.raw):
            if key.lower() == b'set-cookie':
                cookie_str = value.decode('latin-1')
                if 'SameSite=None' not in cookie_str:
                    new_cookie = f"{cookie_str}; SameSite=None; Secure".encode('latin-1')
                    response.headers.raw[i] = (key, new_cookie)
        return response

app.add_middleware(IframeCookieMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        recaptcha_token = form.get("recaptcha_token")

        if recaptcha_token:
            url = 'https://www.google.com/recaptcha/api/siteverify'
            data = urllib.parse.urlencode({
                'secret': '6LeE9ZstAAAAAMLA2CbP9eTfk2ic7KKV79QvM7eI',
                'response': recaptcha_token
            }).encode()
            
            req = urllib.request.Request(url, data=data)
            response = urllib.request.urlopen(req)
            result = json.loads(response.read().decode())
            
            if not result.get('success') or result.get('score', 0) < 0.5:
                return False 

        with SessionLocal() as db:
            user = db.query(User).filter(User.username == username, User.password == password).first()
            if user:
                request.session.update({"token": user.username, "role": user.role, "user_id": user.id})
                return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return "token" in request.session

authentication_backend = AdminAuth(secret_key="topbroker_super_secret_key_2026")
admin = Admin(app, engine, authentication_backend=authentication_backend, title="TOP Broker | Управление", templates_dir="templates")

class PropertyAdmin(ModelView, model=Property):
    name = "Объект"
    name_plural = "Объекты недвижимости"
    icon = "fa-solid fa-building"
    
    column_list = [Property.id, Property.title, Property.deal_type, Property.price, Property.address, Property.is_exclusive]
    column_searchable_list = [Property.title, Property.address]

    column_labels = {
        Property.id: "ID",
        Property.title: "Название (Например: БЦ Esentai)",
        Property.deal_type: "Тип сделки (Аренда/Продажа)",
        Property.property_type: "Категория",
        Property.building_class: "Класс (A/B/C)",
        Property.area_min: "Мин. площадь (м²)",
        Property.area_max: "Макс. площадь (м²)",
        Property.price: "Ставка / Цена",
        Property.price_unit: "За что (тг/м² в месяц)",
        Property.no_commission: "Без комиссии",
        Property.image_url: "Главная фотография",
        Property.image_url_2: "Дополнительная фотография 1",
        Property.image_url_3: "Дополнительная фотография 2",
        Property.image_url_4: "Дополнительная фотография 3",
        Property.image_url_5: "Дополнительная фотография 4",
        Property.image_url_6: "Дополнительная фотография 5",
        Property.image_url_7: "Дополнительная фотография 6",
        Property.image_url_8: "Дополнительная фотография 7",
        Property.image_url_9: "Дополнительная фотография 8",
        Property.image_url_10: "Дополнительная фотография 9",
        Property.is_exclusive: "Эксклюзивный объект",
        Property.show_on_landing: "Показывать на главной странице",
        Property.address: "Адрес (для Яндекс Карт)",
        Property.broker_id: "ID Брокера"
    }

    form_overrides = {
        "image_url": FileField,
        "image_url_2": FileField,
        "image_url_3": FileField,
        "image_url_4": FileField,
        "image_url_5": FileField,
        "image_url_6": FileField,
        "image_url_7": FileField,
        "image_url_8": FileField,
        "image_url_9": FileField,
        "image_url_10": FileField
    }

    def list_query(self, request: Request):
        stmt = super().list_query(request)
        if request.session.get("role") == "broker":
            stmt = stmt.where(Property.broker_id == request.session.get("user_id"))
        return stmt

    def count_query(self, request: Request):
        stmt = super().count_query(request)
        if request.session.get("role") == "broker":
            stmt = stmt.where(Property.broker_id == request.session.get("user_id"))
        return stmt

    async def on_model_change(self, data: dict, model: Any, is_created: bool, request: Request):
        user_id = request.session.get("user_id")
        if request.session.get("role") == "broker":
            if is_created:
                data["broker_id"] = user_id
            elif getattr(model, "broker_id", None) != user_id:
                raise Exception("Ошибка: Вы не можете редактировать чужой объект!")

        img_fields = [
            "image_url", "image_url_2", "image_url_3", "image_url_4",
            "image_url_5", "image_url_6", "image_url_7", "image_url_8",
            "image_url_9", "image_url_10"
        ]
        
        for img_field in img_fields:
            image_file = data.get(img_field)
            if isinstance(image_file, UploadFile) and image_file.filename:
                ext = image_file.filename.split('.')[-1]
                filename = f"{uuid.uuid4()}.{ext}"
                filepath = f"static/uploads/{filename}"
                content = await image_file.read()
                with open(filepath, "wb") as f:
                    f.write(content)
                data[img_field] = f"/static/uploads/{filename}"
            else:
                data.pop(img_field, None)

class UserAdmin(ModelView, model=User):
    name = "Профиль"
    name_plural = "Мой Профиль / Брокеры"
    icon = "fa-solid fa-user-tie"
    
    column_list = [User.username, User.full_name, User.role]
    
    column_labels = {
        User.username: "Логин для входа",
        User.password: "Пароль",
        User.role: "Роль (admin или broker)",
        User.full_name: "Имя Фамилия (для сайта)",
        User.position: "Должность",
        User.phone: "Телефон (с кодом)",
        User.whatsapp: "Ссылка на WhatsApp",
        User.photo_url: "Фотография брокера"
    }
    
    form_overrides = {"photo_url": FileField}

    def list_query(self, request: Request):
        stmt = super().list_query(request)
        if request.session.get("role") == "broker":
            stmt = stmt.where(User.id == request.session.get("user_id"))
        return stmt

    async def on_model_change(self, data: dict, model: Any, is_created: bool, request: Request):
        image_file = data.get("photo_url")
        if isinstance(image_file, UploadFile) and image_file.filename:
            ext = image_file.filename.split('.')[-1]
            filename = f"broker_{uuid.uuid4()}.{ext}"
            filepath = f"static/uploads/{filename}"
            content = await image_file.read()
            with open(filepath, "wb") as f:
                f.write(content)
            data["photo_url"] = f"/static/uploads/{filename}"
        else:
            data.pop("photo_url", None)

class ManagementLeadAdmin(ModelView, model=ManagementLeadDB):
    name = "Заявка на управление"
    name_plural = "Заявки на управление"
    icon = "fa-solid fa-envelope"
    
    column_list = [
        ManagementLeadDB.id, 
        ManagementLeadDB.property_type, 
        ManagementLeadDB.area, 
        ManagementLeadDB.phone, 
        ManagementLeadDB.created_at
    ]
    column_searchable_list = [ManagementLeadDB.phone, ManagementLeadDB.property_type]
    column_sortable_list = [ManagementLeadDB.created_at]
    column_default_sort = [("created_at", True)]

admin.add_view(PropertyAdmin)
admin.add_view(UserAdmin)
admin.add_view(ManagementLeadAdmin)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/api/properties")
def get_properties(
    deal_type: Optional[str] = None,
    property_type: Optional[str] = None,
    building_class: Optional[str] = None,
    area_min: Optional[int] = None,
    area_max: Optional[int] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    db: Session = Depends(get_db)
):
    try:
        query = db.query(Property)
        if deal_type: query = query.filter(Property.deal_type == deal_type)
        if property_type: query = query.filter(Property.property_type == property_type)
        if building_class: query = query.filter(Property.building_class == building_class)
        if area_min is not None: query = query.filter(Property.area_max >= area_min)
        if area_max is not None: query = query.filter(Property.area_min <= area_max)
        if price_min is not None: query = query.filter(Property.price >= price_min)
        if price_max is not None: query = query.filter(Property.price <= price_max)
            
        query = query.order_by(Property.is_exclusive.desc(), Property.id.asc())
        properties = query.all()
        
        result = [{
            "id": p.id,
            "title": p.title,
            "deal_type": p.deal_type,
            "property_type": p.property_type,
            "building_class": p.building_class,
            "area_min": p.area_min,
            "area_max": p.area_max,
            "price": p.price,
            "price_unit": p.price_unit,
            "no_commission": p.no_commission,
            "image_url": p.image_url,
            "is_exclusive": p.is_exclusive,
            "address": p.address 
        } for p in properties]
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/properties/{prop_id}")
def get_property(prop_id: int, db: Session = Depends(get_db)):
    try:
        prop = db.query(Property).filter(Property.id == prop_id).first()
        if not prop: return {"status": "error", "message": "Объект не найден"}
            
        result = {
            "id": prop.id,
            "title": prop.title,
            "deal_type": prop.deal_type,
            "property_type": prop.property_type,
            "building_class": prop.building_class,
            "area_min": prop.area_min,
            "area_max": prop.area_max,
            "price": prop.price,
            "price_unit": prop.price_unit,
            "no_commission": prop.no_commission,
            "image_url": prop.image_url,
            "image_url_2": prop.image_url_2,
            "image_url_3": prop.image_url_3,
            "image_url_4": prop.image_url_4,
            "image_url_5": prop.image_url_5,
            "image_url_6": prop.image_url_6,
            "image_url_7": prop.image_url_7,
            "image_url_8": prop.image_url_8,
            "image_url_9": prop.image_url_9,
            "image_url_10": prop.image_url_10,
            "is_exclusive": prop.is_exclusive,
            "address": prop.address
        }
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/brokers")
def get_brokers(db: Session = Depends(get_db)):
    try:
        brokers = db.query(User).filter(User.full_name != None).all()
        result = [{"id": b.id, "name": b.full_name, "position": b.position, "phone": b.phone, "whatsapp": b.whatsapp, "photo_url": b.photo_url} for b in brokers]
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
class ManagementLeadCreate(BaseModel):
    property_type: str
    area: str
    phone: str

@app.post("/api/management/lead")
async def create_management_lead(lead: ManagementLeadCreate, db: Session = Depends(get_db)):
    new_lead = ManagementLeadDB(
        property_type=lead.property_type,
        area=lead.area,
        phone=lead.phone
    )
    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)
    
    return {"status": "success", "message": "Заявка сохранена"}