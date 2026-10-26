from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column
from shared.database import Base, database
from shared.security import current_user, require_owner, internal_auth

class Store(Base):
    __tablename__ = 'stores'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(350), default='')
    nationwide_delivery: Mapped[bool] = mapped_column(default=True)

Session = database('stores')
app = FastAPI(title='CloudCart Stores Service')

class CreateStore(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    city: str = Field(min_length=2, max_length=100)
    description: str = Field(default='', max_length=350)
    nationwide_delivery: bool = True

def present(s):
    return {'id': s.id, 'name': s.name, 'city': s.city, 'owner_id': s.owner_id, 'description': s.description, 'nationwide_delivery': s.nationwide_delivery}

@app.get('/health')
def health(): return {'status':'ok','service':'stores'}

@app.get('/stores')
def stores():
    with Session() as db: return [present(s) for s in db.scalars(select(Store).order_by(Store.id)).all()]

@app.get('/stores/mine')
def mine(owner: dict = Depends(require_owner)):
    with Session() as db: return [present(s) for s in db.scalars(select(Store).where(Store.owner_id == owner['id'])).all()]

@app.get('/stores/{store_id}')
def get_store(store_id: int):
    with Session() as db:
        s = db.get(Store, store_id)
        if not s: raise HTTPException(404, 'Store not found')
        return present(s)

@app.post('/stores', status_code=201)
def create(data: CreateStore, owner: dict = Depends(require_owner)):
    with Session() as db:
        s = Store(**data.model_dump(), owner_id=owner['id']); db.add(s); db.commit(); db.refresh(s)
        return present(s)

@app.get('/internal/stores/{store_id}/owned-by/{owner_id}', dependencies=[Depends(internal_auth)])
def belongs(store_id: int, owner_id: int):
    with Session() as db:
        s = db.get(Store, store_id)
        return {'valid': bool(s and s.owner_id == owner_id)}
