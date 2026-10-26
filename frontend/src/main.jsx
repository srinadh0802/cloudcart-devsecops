import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

const money = pennies => `£${((pennies || 0) / 100).toFixed(2)}`
async function api(path, method='GET', body, token) {
  const headers = { ...(body ? {'Content-Type':'application/json'} : {}), ...(token ? {Authorization: `Bearer ${token}`} : {}) }
  const response = await fetch(`/api/${path}`, {method, headers, ...(body ? {body: JSON.stringify(body)} : {})})
  const result = await response.json().catch(() => ({}))
  if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : `Request failed (${response.status})`)
  return result
}

const icons = {'Laptop':'💻','Headphones':'🎧','Phone':'📱','Tablet':'📲','Camera':'📸'}
const emojiFor = name => Object.entries(icons).find(([key])=>name?.toLowerCase().includes(key.toLowerCase()))?.[1] || '📦'

function App() {
  const [session, setSession] = useState(() => { try {return JSON.parse(localStorage.getItem('cloudcart-session') || 'null')} catch {return null} })
  const [view, setView] = useState('shop')
  const [listings, setListings] = useState([])
  const [stores, setStores] = useState([])
  const [stock, setStock] = useState({})
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [selected, setSelected] = useState(null)
  const [postcode, setPostcode] = useState('SW1A 1AA')
  const [quantity, setQuantity] = useState(1)
  const [authMode, setAuthMode] = useState('login')
  const [role, setRole] = useState('customer')
  const [authForm, setAuthForm] = useState({name:'', email:'', password:''})
  const [myStores, setMyStores] = useState([])
  const [orders, setOrders] = useState([])
  const [myOrders, setMyOrders] = useState([])
  const [products, setProducts] = useState([])
  const [newStore, setNewStore] = useState({name:'',city:'',description:''})
  const [newProduct, setNewProduct] = useState({name:'',brand:'',category:'Electronics',manufacturer:'',origin_country:'Not specified'})
  const [newListing, setNewListing] = useState({store_id:'',product_id:'',price_gbp:'',quantity:10})

  const storeById = useMemo(() => Object.fromEntries(stores.map(s => [s.id,s])), [stores])
  const filtered = useMemo(() => listings.filter(l =>
    (filter === 'all' || (filter === 'electronics' && l.product.category.toLowerCase() === 'electronics')) &&
    `${l.product.name} ${l.product.brand} ${storeById[l.store_id]?.name || ''}`.toLowerCase().includes(search.toLowerCase())
  ), [listings, filter, search, storeById])

  async function loadMarketplace() {
    const [ls,ss] = await Promise.all([api('catalog/listings'),api('stores/stores')])
    setListings(ls);setStores(ss)
    const result = await Promise.all(ls.map(l => api(`inventory/stock?store_id=${l.store_id}&product_id=${l.product_id}`).catch(()=>null)))
    setStock(Object.fromEntries(ls.map((l,i)=>[l.id,result[i]?.quantity ?? '?'])))
  }
  async function loadOwner() {
    if (session?.role !== 'owner') return
    const [my, ps] = await Promise.all([api('stores/stores/mine','GET',null,session.access_token),api('catalog/products')])
    setMyStores(my);setProducts(ps)
    setNewListing(v => ({...v,store_id:v.store_id || String(my[0]?.id || ''),product_id:v.product_id || String(ps[0]?.id || '')}))
    const all = await Promise.all(my.map(s=>api(`orders/orders/store/${s.id}`,'GET',null,session.access_token)))
    setOrders(all.flat())
  }
  async function loadMyOrders() {
    if (session) setMyOrders(await api('orders/orders/mine','GET',null,session.access_token))
  }
  useEffect(()=>{ loadMarketplace().catch(e =>setError(`Backend unavailable: ${e.message}. Start the six API services.`)) }, [])
  useEffect(()=>{ if(session) {loadMyOrders().catch(()=>{});loadOwner().catch(()=>{})} }, [session])

  async function action(run, success) {
    setBusy(true);setError('');setNotice('')
    try {await run();setNotice(success);await loadMarketplace();if(session){await loadMyOrders();if(session.role==='owner')await loadOwner()}}
    catch(e){setError(e.message)} finally {setBusy(false)}
  }
  async function authenticate(e) {
    e.preventDefault()
    await action(async()=>{
      const data = authMode==='register' ? await api('auth/register','POST',{...authForm,role}) : await api('auth/login','POST',{email:authForm.email,password:authForm.password})
      setSession(data);localStorage.setItem('cloudcart-session',JSON.stringify(data));setView(data.role==='owner'?'owner':'shop')
    },'Signed in successfully!')
  }
  function signOut() {localStorage.removeItem('cloudcart-session');setSession(null);setMyStores([]);setOrders([]);setMyOrders([]);setView('shop');setNotice('Signed out')}
  async function checkout(e) {
    e.preventDefault()
    if (!session) {setView('login');setNotice('Sign in to place an order');return}
    await action(async()=>{
      await api('orders/orders','POST',{listing_id:selected.id,quantity:Number(quantity),postcode},session.access_token)
      setSelected(null);setView('orders')
    },'Order placed! Your chosen store has received the order.')
  }
  const NavButton = ({to,children}) => <button className={view===to?'nav-active':''} onClick={()=>{setView(to);setError('');setNotice('')}}>{children}</button>

  return <>
    <header className="topbar"><div className="container bar-inner"><button className="brand" onClick={()=>setView('shop')}><span className="brand-mark">☁</span> Cloud<span>Cart</span><small>UK</small></button>
      <nav><NavButton to="shop">Marketplace</NavButton>{session&&<NavButton to="orders">My orders</NavButton>}{session?.role==='owner'&&<NavButton to="owner">Seller dashboard</NavButton>}</nav>
      <div className="account">{session?<><span className="welcome">Hi, {session.name.split(' ')[0]}</span><button className="btn secondary tiny" onClick={signOut}>Sign out</button></>:<button className="btn primary tiny" onClick={()=>setView('login')}>Sign in / Join</button>}</div>
    </div></header>
    {(notice||error) && <div className={`flash ${error?'danger':''}`} role="status"><div className="container">{error || notice}<button onClick={()=>{setNotice('');setError('')}}>×</button></div></div>}
    {view==='shop'&&<main>
      <section className="hero"><div className="container hero-grid"><div><div className="eyebrow">🇬🇧 THE UK-WIDE INDEPENDENT MARKETPLACE</div><h1>One product.<br/><em>Your choice</em> of store.</h1><p>Compare real store listings, discover where products come from, and choose the UK retailer you trust.</p><button className="btn primary" onClick={()=>document.getElementById('products')?.scrollIntoView({behavior:'smooth'})}>Explore products <span>→</span></button><div className="hero-features"><span>✓ UK-wide delivery</span><span>✓ Compare store prices</span><span>✓ Choose your seller</span></div></div><div className="hero-art"><div className="art-circle"><span>🛍️</span></div><div className="float-card c1">🏬 &nbsp; Choose your store</div><div className="float-card c2">📦 &nbsp; Order direct</div><div className="float-card c3">🇬🇧 &nbsp; Across the UK</div></div></div></section>
      <section className="container marketplace" id="products"><div className="section-head"><div><div className="eyebrow blue">SHOP BY YOUR PREFERENCES</div><h2>Find your next favourite</h2><p>Transparent prices from independent UK retailers.</p></div><span className="counter">{filtered.length} store offers</span></div>
        <div className="search-row"><div className="searchbox">🔎 <input aria-label="Search products or stores" placeholder="Search laptops, phones, stores..." value={search} onChange={e=>setSearch(e.target.value)}/></div><div className="chips"><button onClick={()=>setFilter('all')} className={filter==='all'?'active':''}>All products</button><button onClick={()=>setFilter('electronics')} className={filter==='electronics'?'active':''}>Electronics</button></div></div>
        <div className="products">{filtered.map(l=><article className="product" key={l.id}><div className="product-art"><span>{emojiFor(l.product.name)}</span><div className="product-tag">{l.product.category}</div></div><div className="product-content"><div className="muted">{l.product.brand}</div><h3>{l.product.name}</h3><div className="muted">Manufacturer: {l.product.manufacturer}</div><div className="muted">Origin: {l.product.origin_country} <small>(seller-provided)</small></div><div className="store-line">🏪 {storeById[l.store_id]?.name || `Store #${l.store_id}`} · {storeById[l.store_id]?.city || 'UK'}</div><div className="product-bottom"><div><div className="price">{money(l.price_pence)}</div><div className={Number(stock[l.id])>0?'stock-good':'stock-bad'}>{Number(stock[l.id])>0?`${stock[l.id]} in stock`:'Out of stock'}</div></div><button className="btn primary tiny" disabled={!(Number(stock[l.id])>0)} onClick={()=>{setSelected(l);setQuantity(1)}}>Choose store →</button></div></div></article>)}</div>
        {!filtered.length&&<div className="empty">No matching offers yet. Start the APIs and run the sample data script, or list a product as a store owner.</div>}
      </section></main>}
    {view==='login'&&<main className="container form-page"><div className="panel auth-card"><div className="eyebrow blue">WELCOME TO CLOUDCART</div><h2>{authMode==='login'?'Sign in to continue':'Create your account'}</h2><p>{authMode==='login'?'Choose your store, shop with confidence.':'Customers and independent stores are both welcome.'}</p><div className="tab-row"><button className={authMode==='login'?'active':''} onClick={()=>setAuthMode('login')}>Sign in</button><button className={authMode==='register'?'active':''} onClick={()=>setAuthMode('register')}>Register</button></div><form onSubmit={authenticate} className="form-stack">{authMode==='register'&&<><label>Full name<input required value={authForm.name} onChange={e=>setAuthForm({...authForm,name:e.target.value})} placeholder="Your name"/></label><label>Account type<select value={role} onChange={e=>setRole(e.target.value)}><option value="customer">Customer</option><option value="owner">Store owner</option></select></label></>}<label>Email<input type="email" required value={authForm.email} onChange={e=>setAuthForm({...authForm,email:e.target.value})} placeholder="you@example.com"/></label><label>Password<input type="password" minLength={8} required value={authForm.password} onChange={e=>setAuthForm({...authForm,password:e.target.value})} placeholder="At least 8 characters"/></label><button className="btn primary" disabled={busy}>{busy?'Working...':authMode==='login'?'Sign in':'Create account'} →</button></form></div></main>}
    {view==='orders'&&<main className="container interior"><div className="section-head"><div><div className="eyebrow blue">YOUR ACCOUNT</div><h2>Order history</h2></div></div>{!session?<div className="empty">Please sign in to see your orders.</div>:myOrders.length?<div className="order-list">{myOrders.map(o=><div className="order-line" key={o.id}><div><b>Order #{o.id} · {o.product_name}</b><p>{o.quantity} item(s) · Store: {storeById[o.store_id]?.name||`#${o.store_id}`} · {o.postcode}</p></div><div><span className="status">{o.status}</span><strong>{money(o.total_pence)}</strong></div></div>)}</div>:<div className="empty">No orders yet. Find your first product in the marketplace.</div>}</main>}
    {view==='owner'&&<main className="container interior"><div className="section-head"><div><div className="eyebrow blue">SELLER CENTRAL</div><h2>Your store dashboard</h2><p>Manage UK stores, product listings, stock and customer orders.</p></div></div>{session?.role!=='owner'?<div className="empty">Sign in with a store-owner account to access the dashboard.</div>:<><div className="stats"><div>🏪 <strong>{myStores.length}</strong><span>Your stores</span></div><div>🏷️ <strong>{listings.filter(l=>myStores.some(s=>s.id===l.store_id)).length}</strong><span>Live listings</span></div><div>🛒 <strong>{orders.length}</strong><span>Customer orders</span></div></div><div className="owner-grid"><div className="panel"><h3>① Register a store</h3><form className="form-stack" onSubmit={e=>{e.preventDefault();action(()=>api('stores/stores','POST',newStore,session.access_token),'Store registered successfully')}}><label>Store name<input required value={newStore.name} onChange={e=>setNewStore({...newStore,name:e.target.value})} placeholder="Manchester Tech Hub"/></label><label>City<input required value={newStore.city} onChange={e=>setNewStore({...newStore,city:e.target.value})} placeholder="Manchester"/></label><label>Description<input value={newStore.description} onChange={e=>setNewStore({...newStore,description:e.target.value})}/></label><button className="btn primary tiny" disabled={busy}>Add store</button></form></div><div className="panel"><h3>② Create a product</h3><form className="form-stack" onSubmit={e=>{e.preventDefault();action(()=>api('catalog/products','POST',newProduct,session.access_token),'Product created successfully')}}>{['name','brand','category','manufacturer','origin_country'].map(key=><label key={key}>{key.replaceAll('_',' ')}<input required value={newProduct[key]} onChange={e=>setNewProduct({...newProduct,[key]:e.target.value})}/></label>)}<button className="btn primary tiny" disabled={busy}>Add product</button></form></div><div className="panel"><h3>③ List product & set stock</h3><form className="form-stack" onSubmit={e=>{e.preventDefault();action(async()=>{const payload={store_id:Number(newListing.store_id),product_id:Number(newListing.product_id),price_gbp:newListing.price_gbp};await api('catalog/listings','POST',payload,session.access_token);await api('inventory/stock','POST',{store_id:payload.store_id,product_id:payload.product_id,quantity:Number(newListing.quantity)},session.access_token)},'Product listed with inventory')}}><label>Store<select required value={newListing.store_id} onChange={e=>setNewListing({...newListing,store_id:e.target.value})}><option value="">Select a store</option>{myStores.map(s=><option value={s.id} key={s.id}>{s.name}</option>)}</select></label><label>Product<select required value={newListing.product_id} onChange={e=>setNewListing({...newListing,product_id:e.target.value})}><option value="">Select a product</option>{products.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select></label><label>Price (£)<input required type="number" min="0.01" step="0.01" value={newListing.price_gbp} onChange={e=>setNewListing({...newListing,price_gbp:e.target.value})} placeholder="649.99"/></label><label>Available quantity<input required type="number" min="0" value={newListing.quantity} onChange={e=>setNewListing({...newListing,quantity:e.target.value})}/></label><button className="btn primary tiny" disabled={busy||!myStores.length||!products.length}>Publish listing</button></form></div></div><div className="panel owner-orders"><h3>Orders from your stores</h3>{orders.length?orders.map(o=><div className="order-line" key={o.id}><div><b>#{o.id} · {o.product_name}</b><p>Qty {o.quantity} · {o.postcode} · {money(o.total_pence)}</p></div><div><span className="status">{o.status}</span>{(['placed','confirmed','dispatched'].includes(o.status))&&<button className="btn secondary tiny" onClick={()=>action(()=>api(`orders/orders/${o.id}/status`,'PATCH',{status:{placed:'confirmed',confirmed:'dispatched',dispatched:'delivered'}[o.status]},session.access_token),'Order status updated')}>{ {placed:'Confirm',confirmed:'Dispatch',dispatched:'Mark delivered'}[o.status]}</button>}</div></div>):<p className="muted">No orders yet.</p>}</div></>}</main>}
    <footer><div className="container footer-inner"><div className="brand">☁ Cloud<span>Cart</span> <small>UK</small></div><span>Made for local choice. Built as a DevSecOps learning project.</span><span>UK marketplace demo · No real payments</span></div></footer>
    {selected&&<div className="modal-backdrop" onClick={()=>setSelected(null)}><div className="modal panel" onClick={e=>e.stopPropagation()}><button className="close" onClick={()=>setSelected(null)}>✕</button><div className="eyebrow blue">CHECKOUT · DEMO ONLY</div><h2>{selected.product.name}</h2><p>Buying from <b>{storeById[selected.store_id]?.name}</b> in {storeById[selected.store_id]?.city}.</p><form className="form-stack" onSubmit={checkout}><label>UK delivery postcode<input required value={postcode} onChange={e=>setPostcode(e.target.value)} placeholder="SW1A 1AA"/></label><label>Quantity<input type="number" min="1" max="10" required value={quantity} onChange={e=>setQuantity(e.target.value)}/></label><div className="price-breakdown"><div>Items <b>{money(selected.price_pence*Number(quantity))}</b></div><div>UK delivery (estimate) <b>£4.99</b></div><div className="total">Total <b>{money(selected.price_pence*Number(quantity)+499)}</b></div></div><button className="btn primary" disabled={busy}>{busy?'Processing...':'Place demo order →'}</button></form><small className="muted">No card details collected. Orders and stock are stored locally.</small></div></div>}
  </>
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>)
