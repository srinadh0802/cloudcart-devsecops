import json
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, Text, ForeignKey, select
from sqlalchemy.orm import Mapped, mapped_column
from shared.database import Base, database
from shared.security import current_user, require_owner
from shared.network import fetch

class Order(Base):
    __tablename__='orders'
    id:Mapped[int]=mapped_column(primary_key=True)
    customer_id:Mapped[int]=mapped_column(Integer,index=True)
    store_id:Mapped[int]=mapped_column(Integer,index=True)
    listing_id:Mapped[int]=mapped_column(Integer)
    product_id:Mapped[int]=mapped_column(Integer)
    product_name:Mapped[str]=mapped_column(String(180))
    quantity:Mapped[int]=mapped_column(Integer)
    unit_price_pence:Mapped[int]=mapped_column(Integer)
    delivery_pence:Mapped[int]=mapped_column(Integer)
    total_pence:Mapped[int]=mapped_column(Integer)
    postcode:Mapped[str]=mapped_column(String(12))
    status:Mapped[str]=mapped_column(String(30),default='placed')
    created_at:Mapped[str]=mapped_column(String(40))

class Outbox(Base):
    __tablename__='outbox'
    id:Mapped[int]=mapped_column(primary_key=True)
    order_id:Mapped[int]=mapped_column(ForeignKey('orders.id'))
    event_type:Mapped[str]=mapped_column(String(60))
    payload:Mapped[str]=mapped_column(Text)
    published:Mapped[bool]=mapped_column(default=False)

Session=database('orders')
app=FastAPI(title='CloudCart Order Service')

class Checkout(BaseModel):
    listing_id:int=Field(gt=0)
    quantity:int=Field(gt=0,le=10)
    postcode:str=Field(min_length=5,max_length=12)

class StatusChange(BaseModel):
    status:str=Field(pattern='^(confirmed|dispatched|delivered|cancelled)$')

def present(o):
    return {'id':o.id,'customer_id':o.customer_id,'store_id':o.store_id,'listing_id':o.listing_id,'product_id':o.product_id,'product_name':o.product_name,'quantity':o.quantity,'unit_price_pence':o.unit_price_pence,'delivery_pence':o.delivery_pence,'total_pence':o.total_pence,'postcode':o.postcode,'status':o.status,'created_at':o.created_at}

def emit(db,order,event_type):
    payload={'event_id':f'{event_type}:{order.id}:{order.status}', 'type':event_type,'order_id':order.id,'customer_id':order.customer_id,'store_id':order.store_id,'status':order.status,'total_pence':order.total_pence}
    db.add(Outbox(order_id=order.id,event_type=event_type,payload=json.dumps(payload)))

@app.get('/health')
def health():return {'status':'ok','service':'orders'}

@app.post('/orders',status_code=201)
def checkout(data:Checkout,user:dict=Depends(current_user)):
    # V1: one seller's listing per checkout; no real payments yet.
    listing=fetch('catalog','GET',f'/listings/{data.listing_id}')
    fetch('stores','GET',f'/stores/{listing["store_id"]}')
    shipping=fetch('delivery','POST','/quote',payload={'store_id':listing['store_id'],'postcode':data.postcode})
    stock_request={'store_id':listing['store_id'],'product_id':listing['product_id'],'quantity':data.quantity}
    fetch('inventory','POST','/internal/reserve',payload=stock_request,internal=True)
    try:
        with Session() as db:
            price=listing['price_pence'];delivery=shipping['delivery_pence']
            row=Order(customer_id=user['id'],store_id=listing['store_id'],listing_id=listing['id'],product_id=listing['product_id'],product_name=listing['product']['name'],quantity=data.quantity,unit_price_pence=price,delivery_pence=delivery,total_pence=price*data.quantity+delivery,postcode=shipping['postcode'],status='placed',created_at=datetime.now(timezone.utc).isoformat())
            db.add(row);db.flush();emit(db,row,'order.created');db.commit();db.refresh(row)
            return present(row)
    except Exception:
        # Best-effort compensation; full production recovery is a later reliability milestone.
        try:fetch('inventory','POST','/internal/release',payload=stock_request,internal=True)
        except Exception:pass
        raise

@app.get('/orders/mine')
def my_orders(user:dict=Depends(current_user)):
    with Session() as db:return [present(o) for o in db.scalars(select(Order).where(Order.customer_id==user['id']).order_by(Order.id.desc())).all()]

@app.get('/orders/store/{store_id}')
def store_orders(store_id:int,user:dict=Depends(require_owner)):
    check=fetch('stores','GET',f'/internal/stores/{store_id}/owned-by/{user["id"]}',internal=True)
    if not check['valid']:raise HTTPException(403,'Not your store')
    with Session() as db:return [present(o) for o in db.scalars(select(Order).where(Order.store_id==store_id).order_by(Order.id.desc())).all()]

@app.patch('/orders/{order_id}/status')
def change_status(order_id:int,data:StatusChange,user:dict=Depends(require_owner)):
    with Session() as db:
        row=db.get(Order,order_id)
        if not row:raise HTTPException(404,'Order not found')
        check=fetch('stores','GET',f'/internal/stores/{row.store_id}/owned-by/{user["id"]}',internal=True)
        if not check['valid']:raise HTTPException(403,'Not your order')
        transitions={'placed':{'confirmed','cancelled'},'confirmed':{'dispatched','cancelled'},'dispatched':{'delivered'},'delivered':set(),'cancelled':set()}
        if data.status not in transitions[row.status]:raise HTTPException(409,'Invalid status transition')
        # Cancellation inventory compensation is outside V1; prevent cancellation rather than misstate stock.
        if data.status == 'cancelled':
            fetch('inventory','POST','/internal/release',payload={'store_id':row.store_id,'product_id':row.product_id,'quantity':row.quantity},internal=True)
        row.status=data.status;emit(db,row,'order.updated');db.commit()
        return present(row)
