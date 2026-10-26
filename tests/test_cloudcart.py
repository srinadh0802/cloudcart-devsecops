"""Core phase-2 tests. End-to-end HTTP tests will grow in the Test stage."""
from uuid import uuid4
from fastapi.testclient import TestClient
from shared.security import token
from services.auth.main import app as auth_app
from services.stores.main import app as stores_app
from services.catalog.main import app as catalog_app
from services.inventory.main import app as inventory_app
from services.orders.main import app as orders_app
from services.delivery.main import app as delivery_app

AUTH = TestClient(auth_app)
STORES = TestClient(stores_app)
CATALOG = TestClient(catalog_app)
INVENTORY = TestClient(inventory_app)
ORDERS = TestClient(orders_app)
DELIVERY = TestClient(delivery_app)

def headers(role='owner', user_id=90213):return {'Authorization':f'Bearer {token(user_id,role)}'}

def test_register_login_and_user_role():
    email=f'test-{uuid4().hex}@cloudcart.local'
    body={'name':'Test Shopper','email':email,'password':'A-long-password-123','role':'customer'}
    r=AUTH.post('/register',json=body)
    assert r.status_code==201, r.text
    assert AUTH.post('/register',json=body).status_code==409
    login=AUTH.post('/login',json={'email':email,'password':body['password']})
    assert login.status_code==200
    me=AUTH.get('/me',headers={'Authorization':f'Bearer {login.json()["access_token"]}'})
    assert me.json()['role']=='customer'
    assert AUTH.post('/login',json={'email':email,'password':'wrong123'}).status_code==401

def test_owner_can_create_store_customer_cannot():
    payload={'name':'Test Tech','city':'Leicester','description':'A store'}
    assert STORES.post('/stores',json=payload,headers=headers('customer')).status_code==403
    r=STORES.post('/stores',json=payload,headers=headers('owner'))
    assert r.status_code==201,r.text
    assert r.json()['city']=='Leicester'

def test_product_creation_and_search():
    name=f'Test Laptop {uuid4().hex[:8]}'
    body={'name':name,'brand':'CloudTech','category':'Electronics','manufacturer':'Example Maker','origin_country':'UK'}
    assert CATALOG.post('/products',json=body,headers=headers('customer')).status_code==403
    r=CATALOG.post('/products',json=body,headers=headers())
    assert r.status_code==201,r.text
    assert any(p['name']==name for p in CATALOG.get(f'/products?q={name}').json())

def test_stock_atomic_reservation_and_internal_auth(monkeypatch):
    from services.inventory import main as inventory_module
    monkeypatch.setattr(inventory_module,'fetch',lambda *args,**kwargs: {'valid':True} if '/owned-by/' in args[2] else [{'id':1}])
    store=600000+int(uuid4().hex[:4],16)
    product=600000+int(uuid4().hex[:4],16)
    payload={'store_id':store,'product_id':product,'quantity':2}
    assert INVENTORY.post('/stock',json=payload,headers=headers()).status_code==200
    assert INVENTORY.post('/internal/reserve',json={'store_id':store,'product_id':product,'quantity':1}).status_code==403
    secret={'X-Internal-Key':'local-internal-dev-secret-change-before-deploying-2026'}
    assert INVENTORY.post('/internal/reserve',json={'store_id':store,'product_id':product,'quantity':2},headers=secret).status_code==200
    assert INVENTORY.post('/internal/reserve',json={'store_id':store,'product_id':product,'quantity':1},headers=secret).status_code==409
    assert INVENTORY.get(f'/stock?store_id={store}&product_id={product}').json()['quantity']==0

def test_uk_postcode_and_store_coverage(monkeypatch):
    from services.delivery import main as delivery_module
    monkeypatch.setattr(delivery_module,'fetch',lambda *args,**kwargs: {'nationwide_delivery':True})
    assert DELIVERY.post('/quote',json={'store_id':1,'postcode':'SW1A 1AA'}).json()['delivery_pence']==499
    assert DELIVERY.post('/quote',json={'store_id':1,'postcode':'90210'}).status_code==422

def test_checkout_outbox_and_order_history(monkeypatch):
    from services.orders import main as order_module
    calls=[]
    def fake_fetch(name,method,path,*,payload=None,internal=False):
        calls.append((name,path,payload))
        if name=='catalog':return {'id':234,'store_id':88,'product_id':34,'price_pence':65000,'product':{'name':'Cloud Laptop'}}
        if name=='stores':return {'id':88}
        if name=='delivery':return {'postcode':'SW1A 1AA','delivery_pence':499}
        if name=='inventory':return {'reserved':True}
        raise AssertionError(name)
    monkeypatch.setattr(order_module,'fetch',fake_fetch)
    response=ORDERS.post('/orders',json={'listing_id':234,'quantity':2,'postcode':'SW1A 1AA'},headers=headers('customer',user_id=800012))
    assert response.status_code==201,response.text
    created=response.json()
    assert created['total_pence']==130499
    assert created['store_id']==88
    mine=ORDERS.get('/orders/mine',headers=headers('customer',user_id=800012))
    assert any(o['id']==created['id'] for o in mine.json())
    with order_module.Session() as db:
        outbox=db.query(order_module.Outbox).filter_by(order_id=created['id']).one()
        assert outbox.published is False
        assert outbox.event_type=='order.created'
