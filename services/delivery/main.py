import re
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from shared.database import Base, database
from shared.security import internal_auth
from shared.network import fetch

# Simplified UK postcode validation: format check, not Royal Mail address verification.
UK_POSTCODE=re.compile(r'^(GIR\s?0AA|(?:[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}))$',re.I)

class Delivery(Base):
    __tablename__='deliveries'
    id:Mapped[int]=mapped_column(primary_key=True)
    order_id:Mapped[int]=mapped_column(Integer,unique=True,index=True)
    store_id:Mapped[int]=mapped_column(Integer)
    postcode:Mapped[str]=mapped_column(String(12))
    status:Mapped[str]=mapped_column(String(30),default='awaiting_dispatch')

Session=database('delivery')
app=FastAPI(title='CloudCart UK Delivery Service')

class Quote(BaseModel):
    store_id:int=Field(gt=0)
    postcode:str=Field(min_length=5,max_length=12)

class ShippingRecord(Quote):
    order_id:int=Field(gt=0)

@app.get('/health')
def health():return {'status':'ok','service':'delivery'}

@app.post('/quote')
def quote(data:Quote):
    postcode=' '.join(data.postcode.upper().split())
    if not UK_POSTCODE.fullmatch(postcode):raise HTTPException(422,'Enter a valid UK postcode')
    store=fetch('stores','GET',f'/stores/{data.store_id}')
    if not store['nationwide_delivery']:raise HTTPException(422,'Store does not offer nationwide delivery')
    return {'eligible':True,'postcode':postcode,'delivery_pence':499,'delivery_gbp':'4.99','eta_business_days':'3-5','carrier':'To be assigned'}

@app.post('/internal/shipments',dependencies=[Depends(internal_auth)],status_code=201)
def shipment(data:ShippingRecord):
    # Demo-only: real fulfilment integrates with carriers asynchronously.
    with Session() as db:
        row=db.query(Delivery).filter_by(order_id=data.order_id).first()
        if row:return {'id':row.id,'status':row.status}
        row=Delivery(order_id=data.order_id,store_id=data.store_id,postcode=data.postcode.upper())
        db.add(row);db.commit();db.refresh(row)
        return {'id':row.id,'status':row.status}
