import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
import jwt
from passlib.context import CryptContext

app = FastAPI(title="CRUD Board API", root_path="/api")

# --- Config ---
MONGODB_URI = "mongodb+srv://yos_db_user:00kJUBG53vLFZIqH@cluster0.jivkpdj.mongodb.net/?appName=Cluster0"
DATABASE_NAME = "CRUD_Board"
SECRET_KEY = "supersecretkey123"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password123"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

client = AsyncIOMotorClient(MONGODB_URI)
db = client[DATABASE_NAME]
packages_collection = db["packages"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models (อัปเดตใหม่ ตามความต้องการ) ---
class LanguageContent(BaseModel):
    title: str = ""
    excerpt: str = ""
    package_detail: str = "" # เก็บเป็น HTML จาก Text Editor
    cover_image: str = ""    # ย้ายรูปภาพมาอยู่ที่นี่ (แต่ละภาษารูปไม่เหมือนกันได้)

class PackageModel(BaseModel):
    package_id: str
    package_name: str
    full_price: float = 0    # ราคาเต็ม
    sale_price: float = 0    # ราคาขายจริง
    start_date: datetime
    end_date: datetime
    languages: Dict[str, LanguageContent] = {}

class Token(BaseModel):
    access_token: str
    token_type: str

# --- Helpers & Auth ---
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_admin(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("sub") != ADMIN_USERNAME:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return payload.get("sub")
    except:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

# --- Routes ---
@app.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != ADMIN_USERNAME or form_data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    return {"access_token": create_access_token(data={"sub": form_data.username}), "token_type": "bearer"}

@app.get("/packages", response_model=List[dict])
async def get_packages(current_user: str = Depends(get_current_admin)):
    packages = []
    async for doc in packages_collection.find():
        doc["_id"] = str(doc["_id"])
        doc["status"] = "Expired" if datetime.now() > doc["end_date"] else "Published"
        packages.append(doc)
    return packages

@app.post("/packages")
async def create_package(package: PackageModel, current_user: str = Depends(get_current_admin)):
    if await packages_collection.find_one({"package_id": package.package_id}):
        raise HTTPException(status_code=400, detail="Package ID already exists")
    await packages_collection.insert_one(package.dict())
    return {"message": "Created"}

@app.put("/packages/{package_id}")
async def update_package(package_id: str, package: PackageModel, current_user: str = Depends(get_current_admin)):
    result = await packages_collection.replace_one({"package_id": package_id}, package.dict())
    if result.matched_count == 0: raise HTTPException(status_code=404, detail="Not found")
    return {"message": "Updated"}

@app.delete("/packages/{package_id}")
async def delete_package(package_id: str, current_user: str = Depends(get_current_admin)):
    result = await packages_collection.delete_one({"package_id": package_id})
    if result.deleted_count == 0: raise HTTPException(status_code=404, detail="Not found")
    return {"message": "Deleted"}

@app.get("/packages/{package_id}")
async def get_package_detail(package_id: str):
    doc = await packages_collection.find_one({"package_id": package_id})
    if not doc: raise HTTPException(status_code=404, detail="Not found")
    doc["_id"] = str(doc["_id"])
    return doc