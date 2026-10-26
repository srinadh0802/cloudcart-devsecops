"""Create example listings from three UK stores using public APIs."""
import httpx

AUTH='http://127.0.0.1:8001';STORES='http://127.0.0.1:8002';CATALOG='http://127.0.0.1:8003';INVENTORY='http://127.0.0.1:8004'
PASS='DemoPassword123!'

def call(url, method='GET', body=None, jwt=None):
    r=httpx.request(method,url,json=body,headers={'Authorization':f'Bearer {jwt}'} if jwt else {},timeout=8)
    if r.status_code>=400:raise RuntimeError(f'{url}: {r.status_code} {r.text}')
    return r.json()

def ensure_user(email,name,role):
    r=httpx.post(AUTH+'/register',json={'email':email,'name':name,'password':PASS,'role':role},timeout=8)
    if r.status_code==409:return call(AUTH+'/login','POST',{'email':email,'password':PASS})
    r.raise_for_status();return r.json()

def main():
    owner=ensure_user('demo.owner@cloudcart.local','Demo Seller','owner')
    ensure_user('demo.customer@cloudcart.local','Demo Customer','customer')
    jwt=owner['access_token']
    stores=call(STORES+'/stores')
    for name,city in [('Northern Tech','Manchester'),('Capital Electronics','London'),('Midlands Gadgets','Birmingham')]:
        if not any(s['name']==name for s in stores):
            stores.append(call(STORES+'/stores','POST',{'name':name,'city':city,'description':'UK nationwide electronics store'},jwt))
    products=call(CATALOG+'/products')
    demo=[('NovaBook Pro 14 Laptop','Nova','Electronics','Nova Manufacturing','China'),('Studio Wireless Headphones','Sonic','Electronics','Sonic Audio','Vietnam'),('PixelView Smartphone','PixelView','Electronics','PixelView Electronics','South Korea')]
    for name,brand,category,manufacturer,origin in demo:
        if not any(p['name']==name for p in products):
            products.append(call(CATALOG+'/products','POST',{'name':name,'brand':brand,'category':category,'manufacturer':manufacturer,'origin_country':origin},jwt))
    prices=[[79999,78999,80999],[11999,11499,12499],[54999,53999,55999]]
    listings=call(CATALOG+'/listings')
    for pi,product in enumerate([next(p for p in products if p['name']==d[0]) for d in demo]):
        for si,store in enumerate([next(s for s in stores if s['name']==n) for n in ('Northern Tech','Capital Electronics','Midlands Gadgets')]):
            if not any(l['store_id']==store['id'] and l['product_id']==product['id'] for l in listings):
                listings.append(call(CATALOG+'/listings','POST',{'store_id':store['id'],'product_id':product['id'],'price_gbp':str(prices[pi][si]/100)},jwt))
            call(INVENTORY+'/stock','POST',{'store_id':store['id'],'product_id':product['id'],'quantity':10+si*5},jwt)
    print('Sample data loaded: 3 UK stores, 3 products, 9 store listings.')
    print('Seller:   demo.owner@cloudcart.local / '+PASS)
    print('Customer: demo.customer@cloudcart.local / '+PASS)

if __name__=='__main__':main()
