from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, UniqueConstraint, update, select
from sqlalchemy.orm import Mapped, mapped_column
from shared.database import Base, database
from shared.security import require_owner, internal_auth
from shared.network import fetch

class Stock(Base):
    __tablename__='stock'
    __table_args__=(UniqueConstraint('store_id','product_id',name='uq_stock_store_product'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    store_id:Mapped[int]=mapped_column(Integer,index=True)
    product_id:Mapped[int]=mapped_column(Integer)
    quantity:Mapped[int]=mapped_column(Integer,default=0)

Session=database('inventory')
app=FastAPI(title='CloudCart Inventory Service')

class SetStock(BaseModel):
    store_id:int=Field(gt=0)
    product_id:int=Field(gt=0)
    quantity:int=Field(ge=0,le=1000000)

class ChangeStock(BaseModel):
    store_id:int=Field(gt=0)
    product_id:int=Field(gt=0)
    quantity:int=Field(gt=0,le=1000)

def present(row): return {'store_id':row.store_id,'product_id':row.product_id,'quantity':row.quantity}

@app.get('/health')
def health(): return {'status':'ok','service':'inventory'}

@app.get('/stock')
def get_stock(store_id:int,product_id:int):
    with Session() as db:
        row=db.scalar(select(Stock).where(Stock.store_id==store_id,Stock.product_id==product_id))
        return present(row) if row else {'store_id':store_id,'product_id':product_id,'quantity':0}

@app.post('/stock')
def set_stock(data:SetStock,user:dict=Depends(require_owner)):
    owned=fetch('stores','GET',f'/internal/stores/{data.store_id}/owned-by/{user["id"]}',internal=True)
    if not owned['valid']:raise HTTPException(403,'You do not own this store')
    listings=fetch('catalog','GET',f'/listings?store_id={data.store_id}&product_id={data.product_id}')
    if not listings:raise HTTPException(400,'Create a store listing first')
    with Session() as db:
        row=db.scalar(select(Stock).where(Stock.store_id==data.store_id,Stock.product_id==data.product_id))
        if row:row.quantity=data.quantity
        else:row=Stock(**data.model_dump());db.add(row)
        db.commit();return present(row)

@app.post('/internal/reserve',dependencies=[Depends(internal_auth)])
def reserve(data:ChangeStock):
    # Atomic UPDATE protects against two customers reserving the last item.
    with Session() as db:
        result=db.execute(update(Stock).where(Stock.store_id==data.store_id,Stock.product_id==data.product_id,Stock.quantity>=data.quantity).values(quantity=Stock.quantity-data.quantity))
        if result.rowcount!=1:db.rollback();raise HTTPException(409,'Insufficient stock')
        db.commit();return {'reserved':True,'quantity':data.quantity}

@app.post('/internal/release',dependencies=[Depends(internal_auth)])
def release(data:ChangeStock):
    with Session() as db:
        result=db.execute(update(Stock).where(Stock.store_id==data.store_id,Stock.product_id==data.product_id).values(quantity=Stock.quantity+data.quantity))
        if result.rowcount!=1:db.rollback();raise HTTPException(404,'Stock row not found')
        db.commit();return {'released':True}
