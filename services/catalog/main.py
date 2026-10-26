from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, ForeignKey, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column
from shared.database import Base, database
from shared.security import require_owner
from shared.network import fetch
from shared.money import pennies

class Product(Base):
    __tablename__='products'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    brand: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(80))
    manufacturer: Mapped[str] = mapped_column(String(150))
    origin_country: Mapped[str] = mapped_column(String(80), default='Not specified')
    image_url: Mapped[str] = mapped_column(String(600), default='')

class Listing(Base):
    __tablename__='listings'
    __table_args__=(UniqueConstraint('store_id','product_id',name='uq_store_product'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'))
    store_id: Mapped[int] = mapped_column(Integer, index=True)
    price_pence: Mapped[int] = mapped_column(Integer)

Session=database('catalog')
app=FastAPI(title='CloudCart Catalog Service')

class NewProduct(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    brand: str = Field(min_length=2, max_length=100)
    category: str = Field(min_length=2, max_length=80)
    manufacturer: str = Field(min_length=2, max_length=150)
    origin_country: str = Field(default='Not specified', max_length=80)
    image_url: str = Field(default='', max_length=600)

class NewListing(BaseModel):
    product_id: int = Field(gt=0)
    store_id: int = Field(gt=0)
    price_gbp: str

def product_view(p): return {'id':p.id,'name':p.name,'brand':p.brand,'category':p.category,'manufacturer':p.manufacturer,'origin_country':p.origin_country,'image_url':p.image_url}

def listing_view(db,l):
    p=db.get(Product,l.product_id)
    return {'id':l.id,'store_id':l.store_id,'product_id':l.product_id,'price_pence':l.price_pence, 'price_gbp':f'{l.price_pence/100:.2f}', 'product':product_view(p)}

def check_owner(store_id, user):
    result=fetch('stores','GET',f'/internal/stores/{store_id}/owned-by/{user["id"]}',internal=True)
    if not result['valid']: raise HTTPException(403,'You do not own this store')

@app.get('/health')
def health(): return {'status':'ok','service':'catalog'}

@app.get('/products')
def products(q: str = '', category: str = ''):
    with Session() as db:
        stmt=select(Product)
        if q: stmt=stmt.where(Product.name.ilike(f'%{q[:100]}%'))
        if category: stmt=stmt.where(Product.category == category)
        return [product_view(p) for p in db.scalars(stmt.order_by(Product.id)).all()]

@app.post('/products', status_code=201)
def create_product(data:NewProduct, user:dict=Depends(require_owner)):
    with Session() as db:
        p=Product(**data.model_dump()); db.add(p); db.commit(); db.refresh(p)
        return product_view(p)

@app.get('/listings')
def listings(q:str='', store_id:int|None=None, product_id:int|None=None):
    with Session() as db:
        stmt=select(Listing).join(Product)
        if q: stmt=stmt.where(Product.name.ilike(f'%{q[:100]}%'))
        if store_id is not None: stmt=stmt.where(Listing.store_id==store_id)
        if product_id is not None: stmt=stmt.where(Listing.product_id==product_id)
        return [listing_view(db,l) for l in db.scalars(stmt.order_by(Listing.id)).all()]

@app.get('/listings/{listing_id}')
def get_listing(listing_id:int):
    with Session() as db:
        l=db.get(Listing,listing_id)
        if not l: raise HTTPException(404,'Listing not found')
        return listing_view(db,l)

@app.post('/listings', status_code=201)
def create_listing(data:NewListing, user:dict=Depends(require_owner)):
    check_owner(data.store_id,user)
    price=pennies(data.price_gbp)
    with Session() as db:
        if not db.get(Product,data.product_id): raise HTTPException(404,'Product not found')
        existing=db.scalar(select(Listing).where(Listing.store_id==data.store_id,Listing.product_id==data.product_id))
        if existing: raise HTTPException(409,'Product already listed at this store')
        l=Listing(product_id=data.product_id,store_id=data.store_id,price_pence=price)
        db.add(l);db.commit();db.refresh(l);return listing_view(db,l)
