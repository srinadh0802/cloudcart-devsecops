from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column
from shared.database import Base, database
from shared.security import hash_password, verify_password, token, current_user

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(240), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(250))
    role: Mapped[str] = mapped_column(String(20))

Session = database('auth')
app = FastAPI(title='CloudCart Auth Service')

class Credentials(BaseModel):
    email: str = Field(min_length=5, max_length=240)
    password: str = Field(min_length=8, max_length=128)

class Registration(Credentials):
    name: str = Field(min_length=2, max_length=120)
    role: str = Field(pattern='^(customer|owner)$')

@app.get('/health')
def health(): return {'status': 'ok', 'service': 'auth'}

@app.post('/register', status_code=201)
def register(data: Registration):
    email = data.email.lower().strip()
    with Session() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise HTTPException(409, 'Email already registered')
        u = User(name=data.name.strip(), email=email, password_hash=hash_password(data.password), role=data.role)
        db.add(u); db.commit(); db.refresh(u)
        return {'id': u.id, 'name': u.name, 'email': u.email, 'role': u.role, 'access_token': token(u.id, u.role)}

@app.post('/login')
def login(data: Credentials):
    with Session() as db:
        u = db.scalar(select(User).where(User.email == data.email.lower().strip()))
        if not u or not verify_password(data.password, u.password_hash):
            raise HTTPException(401, 'Incorrect email or password')
        return {'id':u.id, 'name':u.name, 'email':u.email, 'role':u.role, 'access_token':token(u.id,u.role)}

@app.get('/me')
def me(user: dict = Depends(current_user)):
    with Session() as db:
        u = db.get(User, user['id'])
        if not u: raise HTTPException(404, 'User not found')
        return {'id':u.id, 'name':u.name,'email':u.email,'role':u.role}
