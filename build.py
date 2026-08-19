#!/usr/bin/env python3
"""Pegasus Depot static site generator.
Reads data/*.json, writes HTML pages, optimised images, catalog.js and Shopify import CSVs.
Run:  python3 build.py
"""
import json, os, re, csv, shutil, html as H
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).parent
DATA = json.load(open(ROOT / 'data/catalog.json'))
BUNDLES = json.load(open(ROOT / 'data/bundles.json'))['bundles']
VEHICLES = json.load(open(ROOT / 'data/vehicles.json'))['vehicles']
BRAND = DATA['brand']
CATS = DATA['categories']
PRODUCTS = DATA['products']
P = {p['id']: p for p in PRODUCTS}
CAT = {c['id']: c for c in CATS}
VEH = {v['id']: v for v in VEHICLES}
SKU = {}
for p in PRODUCTS:
    for v in p['variants']:
        SKU[v['sku']] = (p, v)
B = {b['id']: b for b in BUNDLES}
SITE_URL = 'https://' + BRAND['domain']
IMG_OUT = ROOT / 'assets/img'
IMG_OUT.mkdir(parents=True, exist_ok=True)
(ROOT / 'assets/css').mkdir(parents=True, exist_ok=True)
(ROOT / 'assets/js').mkdir(parents=True, exist_ok=True)
for d in ['products', 'bundles', 'vehicles']:
    (ROOT / d).mkdir(exist_ok=True)
VERSION = '3'

# ---------------------------------------------------------------- images
_img_cache = {}
def opt(path, maxpx=1100, quality=82):
    """Resize + convert to webp into assets/img/. Returns site-relative path."""
    if not path:
        return None
    key = (path, maxpx)
    if key in _img_cache:
        return _img_cache[key]
    src = ROOT / path
    stem = re.sub(r'[^A-Za-z0-9_-]+', '-', Path(path).stem).strip('-').lower()
    name = f'{stem}-{maxpx}.webp'
    dst = IMG_OUT / name
    rel = f'assets/img/{name}'
    if not src.exists():
        if dst.exists():
            _img_cache[key] = rel; return rel
        # fall back to any already-optimised size of the same image
        cands = sorted(IMG_OUT.glob(f'{stem}-*.webp'), key=lambda c: int(c.stem.rsplit('-', 1)[1]))
        if cands:
            pick = next((c for c in reversed(cands) if int(c.stem.rsplit('-', 1)[1]) <= maxpx), cands[-1])
            _img_cache[key] = f'assets/img/{pick.name}'; return _img_cache[key]
        print('MISSING IMAGE', path); return path
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        try:
            im = Image.open(src)
            im = im.convert('RGBA') if im.mode in ('P', 'LA') else im.convert('RGB') if im.mode != 'RGBA' else im
            im.thumbnail((maxpx, maxpx), Image.LANCZOS)
            if im.mode == 'RGBA':
                bg = Image.new('RGB', im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[3]); im = bg
            im.save(dst, 'WEBP', quality=quality, method=6)
        except Exception as e:
            print('IMG ERR', path, e); return path
    _img_cache[key] = rel
    return rel

def sq(path, maxpx=900):
    return opt(path, maxpx)
def scene(path, maxpx=1800):
    return opt(path, maxpx, 80)
SCENE_KEYS = ['vehicle', 'ventilator-1', 'ventilator-2', 'ventilator-3', '2021', 'PMH', 'Jozef', 'DSC', 'Ceilingflow-at', 'Project1', 'krismar', 'Horse', 'SANY', 'mercedes', 'vanhool', 'Transfer', 'c294', '/51.', 'IMG_', 'b1b68', 'Magazijn', 'magazijn', 'assembly', 'group-photo', 'building', 'le-mans-warehouse', 'MAN-LE4', 'Splash', 'Residence', 'VDL', 'bus-me', 'School', 'kdv']
def is_scene(path):
    return any(k in path for k in SCENE_KEYS)

# ---------------------------------------------------------------- helpers
def money(n):
    if n is None: return 'Quote'
    s = f'{n:,.2f}'
    if s.endswith('.00'): s = s[:-3]
    return '€' + s

def esc(s): return H.escape(str(s), quote=True)

def price_from(p):
    """Default (first priced) variant price."""
    v = next((v for v in p['variants'] if v.get('price') is not None), None)
    return v['price'] if v else None

def price_min(p):
    prices = [v['price'] for v in p['variants'] if v.get('price') is not None]
    return min(prices) if prices else None

def compare_from(p):
    v = next((v for v in p['variants'] if v.get('price') is not None), None)
    return v.get('compare_at') if v else None

def bundle_calc(b, choice=None):
    full = 0
    for i, it in enumerate(b['items']):
        sku = it.get('sku') or (choice[i] if choice else it['choices'][0])
        full += SKU[sku][1]['price'] * it['qty']
    return full, round(full * (1 - b['discount']))

def voltages(p):
    vs = set()
    for v in p['variants']:
        for k, val in (v.get('options') or {}).items():
            if k.lower() == 'voltage':
                if '12' in val: vs.add('12V')
                if '24' in val: vs.add('24V')
                if 'Motorless' in val: vs.add('Motorless')
            if k in ('Operation', 'Light', 'LED version') and ('12' in val):
                vs.add('12V'); vs.add('24V')
    for sp in (p.get('specs') or {}).values():
        if '12V' in sp and '24V' in sp: vs.update(['12V', '24V'])
    if not vs and p['category'] in ('rooftop-ventilators', 'floor-ventilation', 'interior-valves'):
        vs.add('No power')
    return sorted(vs)

def colours(p):
    cols = []
    for v in p['variants']:
        c = (v.get('options') or {}).get('Colour')
        if c and c not in cols: cols.append(c)
    return cols
SWATCH = {'white': '#FFFFFF', 'black': '#111111', 'grey': '#9A9A9A', 'light grey': '#CFCFCF', 'dark grey': '#55585C', 'light grey / dark grey': 'linear-gradient(90deg,#CFCFCF 50%,#55585C 50%)'}

ICON = {
 'arrow': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 5l7 7-7 7"/></svg>',
 'plus': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
 'bag': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8h12l1 13H5L6 8z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/></svg>',
 'search': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
 'menu': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
 'close': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
 'check': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 4.5-5"/></svg>',
 'truck': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7h11v9H3zM14 10h4l3 3v3h-7z"/><circle cx="7" cy="18" r="1.6"/><circle cx="17" cy="18" r="1.6"/></svg>',
 'shield': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/><path d="m9 12 2 2 4-4"/></svg>',
 'box': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M3 8l9-4 9 4-9 4z"/><path d="M3 8v8l9 4 9-4V8"/><path d="M12 12v8"/></svg>',
 'chat': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M4 5h16v11H8l-4 4z"/></svg>',
 'chev': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>',
 'doc': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 13h6M9 17h6"/></svg>',
 'bolt': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M13 2 4 14h7l-1 8 9-12h-7z"/></svg>',
 'euro': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M17 6.5A6 6 0 0 0 7.5 9M17 17.5A6 6 0 0 1 7.5 15M4 10.5h9M4 13.5h9"/></svg>',
 'ruler': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="m3 17 14-14 4 4L7 21z"/><path d="m13 7 2 2M10 10l2 2M7 13l2 2"/></svg>',
}

LOGO_SVG = '''<svg viewBox="0 0 48 48" fill="none" aria-hidden="true"><defs><linearGradient id="pg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#E3C990"/><stop offset=".55" stop-color="#C9A96A"/><stop offset="1" stop-color="#9C7B3E"/></linearGradient></defs><circle cx="24" cy="24" r="23" stroke="url(#pg)" stroke-width="1.4"/><path d="M14 33c2.5-9 8-14 20-15-3 3.5-7 5-9.5 5.5 2 0 5-.5 7.5-2-2 3.5-5.5 5-8.5 5.2 1.5.3 4 .2 6-.8-2.5 3.6-6.3 4.6-9 4.2 1.2.6 2.7.9 4 .8-3 2.6-7 2.8-10.5 2.1z" fill="url(#pg)"/><path d="M14 33l-1.5 3.2" stroke="url(#pg)" stroke-width="1.6" stroke-linecap="round"/></svg>'''
FAVICON = "data:image/svg+xml," + LOGO_SVG.replace('#', '%23').replace('"', "'").replace('<', '%3C').replace('>', '%3E')

def rel(depth):
    return '../' * depth

def jsonld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace('</', '<\\/') + '</script>'

def product_ld(p):
    offers = [{"@type": "Offer", "sku": v['sku'], "name": v['label'], "price": f"{v['price']:.2f}", "priceCurrency": "EUR", "availability": "https://schema.org/InStock", "itemCondition": "https://schema.org/NewCondition", "url": f"{SITE_URL}/products/{p['id']}.html", "shippingDetails": {"@type": "OfferShippingDetails", "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "NL"}}} for v in p['variants'] if v.get('price') is not None]
    d = {"@context": "https://schema.org", "@type": "Product", "name": p['name'], "sku": p['variants'][0]['sku'], "description": p['summary'], "brand": {"@type": "Brand", "name": "Pegasus Depot"}, "image": [f"{SITE_URL}/{sq(p['images'][0], 1400)}"], "category": CAT[p['category']]['name'], "url": f"{SITE_URL}/products/{p['id']}.html"}
    if offers:
        prices = [float(o['price']) for o in offers]
        d["offers"] = {"@type": "AggregateOffer", "lowPrice": f"{min(prices):.2f}", "highPrice": f"{max(prices):.2f}", "priceCurrency": "EUR", "offerCount": len(offers), "offers": offers}
    ld = [d, {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL + "/"}, {"@type": "ListItem", "position": 2, "name": "Shop", "item": SITE_URL + "/shop.html"}, {"@type": "ListItem", "position": 3, "name": CAT[p['category']]['name'], "item": f"{SITE_URL}/shop.html?cat={p['category']}"}, {"@type": "ListItem", "position": 4, "name": p['name']}]}]
    if p.get('faq'):
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q['q'], "acceptedAnswer": {"@type": "Answer", "text": q['a']}} for q in p['faq']]})
    return ''.join(jsonld(x) for x in ld)

ORG_LD = {"@context": "https://schema.org", "@type": "OnlineStore", "name": "Pegasus Depot", "url": SITE_URL, "logo": SITE_URL + "/assets/img/og-default.webp", "email": BRAND['email'], "telephone": BRAND['phone'], "address": {"@type": "PostalAddress", "addressCountry": "NL"}, "areaServed": "EU", "description": "Premium vehicle ventilation, roof hatches and interior LED lighting for vans, campers, horse trailers, buses and ambulances."}

# ---------------------------------------------------------------- layout
def head(title, desc, depth=0, og_image=None, canonical=None):
    r = rel(depth)
    og = scene(og_image) if og_image else 'assets/img/og-default.webp'
    return f'''<!DOCTYPE html>
<html lang="en" data-root="{r}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE_URL}/{canonical or ''}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:type" content="website"><meta property="og:image" content="{SITE_URL}/{og}"><meta property="og:site_name" content="Pegasus Depot">
<meta name="theme-color" content="#0B0C0E">
<link rel="icon" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{r}assets/css/site.css?v={VERSION}">
</head>
<body>'''

def header(depth=0):
    r = rel(depth)
    cat_items = ''.join(f'<a class="m-item" href="{r}shop.html?cat={c["id"]}"><img src="{r}{sq(c["image"],200)}" alt=""><div><b>{esc(c["name"])}</b><span>{esc(c["short"])}</span></div></a>' for c in CATS)
    veh_items = ''.join(f'<a class="m-item" href="{r}vehicles/{v["id"]}.html"><img src="{r}{scene(v["hero"],200)}" alt="" style="object-fit:cover;padding:0"><div><b>{esc(v["name"])}</b><span>{esc(v["eyebrow"])}</span></div></a>' for v in VEHICLES)
    best = [P['le-mans'], P['v12-valve'], P['turbo-ii'], P['winglet']]
    hero_b = [b for b in BUNDLES if b.get('hero')][:4]
    bundle_items = ''.join(f'<a class="m-item" href="{r}bundles/{b["id"]}.html"><img src="{r}{sq(b["images"][0],200)}" alt=""><div><b>{esc(b["name"])}</b><span>{esc(b["tagline"])}</span></div></a>' for b in hero_b)
    kit_items = ''.join(f'<a class="m-item" href="{r}bundles/{b["id"]}.html"><img src="{r}{sq(b["images"][0],200)}" alt=""><div><b>{esc(b["name"])}</b><span>Save {int(b["discount"]*100)}%</span></div></a>' for b in hero_b[:2])
    best_items = ''.join(f'<a class="m-item" href="{r}products/{p["id"]}.html"><img src="{r}{sq(p["images"][0],200)}" alt=""><div><b>{esc(p["short_name"])}</b><span>from {money(price_from(p))}</span></div></a>' for p in best)
    return f'''
<div class="announce"><span>Free EU shipping from €{BRAND["free_shipping_from"]}</span><span>Ships within 24h from stock</span><span>Trade &amp; fleet accounts welcome</span><span>EMC approved · Dutch engineered</span></div>
<header class="header"><div class="wrap header-in">
  <a class="logo" href="{r}index.html" aria-label="Pegasus Depot home">{LOGO_SVG}<span>PEGASUS<small>DEPOT</small></span></a>
  <ul class="nav">
    <li><a href="{r}shop.html">Shop {ICON['chev']}</a>
      <div class="mega mega--wide">
        <div><h5>By category</h5>{cat_items}</div>
        <div><h5>Bestsellers</h5>{best_items}<h5 style="margin-top:16px">Popular kits</h5>{kit_items}</div>
        <a class="m-feature" href="{r}products/le-mans.html" style="background-image:url('{r}{scene(P['le-mans']['images'][2],900)}')"><b>Le Mans 850 m³/h</b><span>The roof fan Europe's bodybuilders specify. From {money(price_from(P['le-mans']))}.</span></a>
      </div></li>
    <li><a href="{r}bundles.html">Kits &amp; Bundles {ICON['chev']}</a>
      <div class="mega mega--cols">
        <div><h5>Complete kits, save up to 12%</h5>{bundle_items}<a class="link" style="margin:12px 10px 0" href="{r}bundles.html">All {len(BUNDLES)} kits {ICON['arrow']}</a></div>
        <a class="m-feature" href="{r}bundles/le-mans-complete-kit.html" style="background-image:url('{r}{scene(B['le-mans-complete-kit']['scene'],900)}')"><b>Le Mans Complete Kit</b><span>Fan + switch + V12 valve. One hole, one afternoon.</span></a>
      </div></li>
    <li><a href="{r}vehicles/commercial-vans.html">Shop by vehicle {ICON['chev']}</a>
      <div class="mega mega--cols"><div>{veh_items}</div>
        <a class="m-feature" href="{r}vehicles/horse-trailers.html" style="background-image:url('{r}{scene(VEH['horse-trailers']['hero'],900)}')"><b>Horse trailers</b><span>Calm horses arrive ready to perform.</span></a>
      </div></li>
    <li><a href="{r}trade.html">Trade</a></li>
    <li><a href="{r}about.html">About</a></li>
  </ul>
  <div class="hdr-actions">
    <a href="#" class="icon-btn" data-open-search aria-label="Search">{ICON['search']}</a>
    <a href="#" class="icon-btn" data-open-cart aria-label="Cart">{ICON['bag']}<span class="cart-count"></span></a>
    <button class="icon-btn burger" id="burger" aria-label="Menu">{ICON['menu']}</button>
  </div>
</div></header>
<nav class="mnav" id="mnav" aria-label="Mobile">
  <div class="top"><a class="logo" href="{r}index.html">{LOGO_SVG}<span>PEGASUS<small>DEPOT</small></span></a><button class="icon-btn" id="mnav-close" aria-label="Close">{ICON['close']}</button></div>
  <a class="row" href="{r}shop.html">Shop all products</a><a class="row" href="{r}bundles.html">Kits &amp; bundles</a>
  <h5>Categories</h5>{''.join(f'<a class="row" href="{r}shop.html?cat={c["id"]}">{esc(c["name"])}</a>' for c in CATS)}
  <h5>By vehicle</h5>{''.join(f'<a class="row" href="{r}vehicles/{v["id"]}.html">{esc(v["name"])}</a>' for v in VEHICLES)}
  <h5>Company</h5><a class="row" href="{r}trade.html">Trade &amp; fleet accounts</a><a class="row" href="{r}about.html">About Pegasus Depot</a><a class="row" href="{r}contact.html">Contact</a><a class="row" href="{r}shipping-returns.html">Shipping &amp; returns</a>
</nav>
<div class="search" id="search"><button class="icon-btn search-close" id="search-close" aria-label="Close">{ICON['close']}</button><div class="search-in"><input id="search-input" type="search" placeholder="Search products, kits or article numbers…" autocomplete="off"><div class="search-res" id="search-res"></div></div></div>
<div class="overlay" id="overlay"></div>
<aside class="drawer" id="drawer" aria-label="Cart">
  <div class="drawer-head"><b>Your cart</b><button class="icon-btn" data-close-cart aria-label="Close" style="color:var(--text)">{ICON['close']}</button></div>
  <div class="ship-bar"><span id="ship-txt"></span><div class="bar"><i id="ship-bar"></i></div></div>
  <div class="drawer-body" id="cart-body"></div>
  <div class="drawer-foot"><div class="row"><span>Subtotal</span><span id="cart-sub">€0</span></div><div class="row"><span>Shipping (EU)</span><span id="cart-ship">–</span></div><div class="row total"><span>Total incl. VAT</span><span id="cart-total">€0</span></div>
  <a class="btn btn-gold btn-block" id="checkout-btn" href="{r}checkout.html" style="margin-top:14px">Secure checkout {ICON['arrow']}</a><p class="muted" style="font-size:12px;text-align:center;margin-top:10px">iDEAL · Visa · Mastercard · PayPal · Bancontact · Invoice for trade</p></div>
</aside>
<div class="toast" id="toast">{ICON['check']}<span></span></div>
'''

def footer(depth=0):
    r = rel(depth)
    return f'''
<footer class="footer"><div class="wrap">
  <div class="footer-grid">
    <div><a class="logo" href="{r}index.html">{LOGO_SVG}<span>PEGASUS<small>DEPOT</small></span></a>
      <p style="margin-top:16px;max-width:34ch">Premium ventilation, roof hatches and interior lighting for vehicles that work harder. Engineered in the Netherlands, shipped across Europe from stock.</p>
      <p style="margin-top:14px;color:var(--text-inv)">{esc(BRAND['email'])}<br>{esc(BRAND['phone'])}<br>{esc(BRAND['address'])}</p></div>
    <div><h5>Shop</h5>{''.join(f'<a href="{r}shop.html?cat={c["id"]}">{esc(c["name"])}</a>' for c in CATS)}<a href="{r}bundles.html">Kits &amp; bundles</a></div>
    <div><h5>By vehicle</h5>{''.join(f'<a href="{r}vehicles/{v["id"]}.html">{esc(v["nav"])}</a>' for v in VEHICLES)}</div>
    <div><h5>Company</h5><a href="{r}about.html">About us</a><a href="{r}trade.html">Trade &amp; fleet accounts</a><a href="{r}contact.html">Contact</a><a href="{r}shipping-returns.html">Shipping &amp; returns</a><a href="{r}terms.html">Terms &amp; warranty</a><a href="{r}privacy.html">Privacy</a></div>
    <div><h5>Why Pegasus Depot</h5><p>✓ Manufacturer-direct quality<br>✓ EMC approved motors<br>✓ Ships within 24h from NL<br>✓ 2-year warranty<br>✓ Trade pricing for fleets and bodybuilders</p>
      <div class="pay" style="margin-top:16px"><span>iDEAL</span><span>VISA</span><span>MASTERCARD</span><span>PAYPAL</span><span>BANCONTACT</span><span>SEPA</span></div></div>
  </div>
  <div class="footer-bottom"><span>© 2026 Pegasus Depot · {esc(BRAND['domain'])} · All prices incl. 21% VAT</span><span>Pegasus Depot is an independent online retailer. Product names and article numbers refer to the original manufacturer's specifications.</span></div>
</div></footer>
<script src="{r}assets/js/catalog.js?v={VERSION}"></script>
<script src="{r}assets/js/site.js?v={VERSION}"></script>
</body></html>'''

# ---------------------------------------------------------------- components
def card(p, depth=0, dark=False):
    r = rel(depth)
    pf = price_from(p); cf = compare_from(p)
    badges = ''.join(f'<span class="badge {"gold" if b in ("Bestseller","Most popular","New") else ""}">{esc(b)}</span>' for b in p.get('badges', [])[:2])
    cols = colours(p)
    sw = ''.join(f'<i class="swatch" style="background:{SWATCH.get(c.lower(),"#ddd")}" title="{esc(c)}"></i>' for c in cols[:4])
    first = next((v for v in p['variants'] if v.get('price') is not None), p['variants'][0])
    prices = sorted(set(v['price'] for v in p['variants'] if v.get('price') is not None))
    multi = len([v for v in p['variants'] if v.get('price') is not None]) > 1
    show_from = len(prices) > 1 and pf == prices[0]
    pr = ('<span class="from">from</span>' if show_from else '') + (money(pf) if pf is not None else 'On request')
    was = f'<span class="was">{money(cf)}</span>' if cf and pf and cf > pf and not show_from else ''
    add = (f'<a class="add" href="{r}products/{p["id"]}.html" aria-label="Choose options">{ICON["arrow"]}</a>' if multi or p.get('quote_only')
           else f'<button class="add" data-add-sku="{first["sku"]}" data-product="{p["id"]}" aria-label="Add to cart">{ICON["plus"]}</button>')
    return f'''<article class="card {'card--dark' if dark else ''}" data-card data-cat="{p['category']}" data-veh="{','.join(p.get('applications',[]))}" data-volt="{','.join(voltages(p))}" data-price="{pf or 99999}" data-name="{esc(p['name'])}" data-order="{PRODUCTS.index(p)}" data-txt="{esc((p['name']+' '+p['tagline']+' '+' '.join(v['sku'] for v in p['variants'])).lower())}">
  <div class="card-media"><div class="card-badges">{badges}</div><img src="{r}{sq(p['images'][0])}" alt="{esc(p['name'])}" loading="lazy"></div>
  <div class="card-body"><div class="card-cat">{esc(CAT[p['category']]['name'])}</div><h3 class="card-title"><a href="{r}products/{p['id']}.html">{esc(p['name'])}</a></h3><p class="card-sub">{esc(p['tagline'])}</p>
  <div class="card-foot"><div><div class="price">{was}{pr}</div>{f'<div class="swatches" style="margin-top:6px">{sw}</div>' if sw else ''}</div>{add}</div></div>
</article>'''

def bundle_card(b, depth=0):
    r = rel(depth)
    full, price = bundle_calc(b)
    imgs = ''.join(f'<img src="{r}{sq(i,500)}" alt="" loading="lazy">' for i in b['images'][:3])
    parts = [f'{it["qty"]}× ' * (it['qty'] > 1) + P[it['product']]['short_name'] for it in b['items']]
    return f'''<article class="bundle-card">
  <div class="bundle-media"><div class="stack">{imgs}</div><div class="plus">{''.join(f'<span>{esc(x)}</span>' for x in parts[:4])}{'<span>…</span>' if len(parts)>4 else ''}</div></div>
  <div class="bundle-body"><div class="pill-row">{''.join(f'<span class="save-pill">{esc(x)}</span>' for x in b.get('badges',[])[:2])}</div>
  <h3 class="card-title"><a href="{r}bundles/{b['id']}.html">{esc(b['name'])}</a></h3><p class="card-sub">{esc(b['tagline'])}</p>
  <div class="card-foot"><div class="price"><span class="was">{money(full)}</span>{money(price)}<small>incl. VAT</small></div><a class="btn btn-gold btn-sm" href="{r}bundles/{b['id']}.html">Build kit {ICON['arrow']}</a></div></div>
</article>'''

def vehicle_tile(v, depth=0):
    r = rel(depth)
    return f'<a class="veh-tile" href="{r}vehicles/{v["id"]}.html"><img src="{r}{scene(v["hero"],900)}" alt="{esc(v["name"])}" loading="lazy"><span class="arrow">{ICON["arrow"]}</span><div><b>{esc(v["name"])}</b><span>{esc(v["headline"])}</span></div></a>'

def faq_block(items):
    if not items: return ''
    return '<div class="faq">' + ''.join(f'<details><summary>{esc(q["q"])}</summary><p>{esc(q["a"])}</p></details>' for q in items) + '</div>'

def newsletter(depth=0):
    r = rel(depth)
    return f'''<section class="section ivory"><div class="wrap"><div class="band reveal">
  <div><div class="eyebrow">Trade &amp; fleet</div><h2 class="h2" style="margin:12px 0 14px">Bodybuilder, converter or fleet manager?</h2><p class="lead">Open a trade account for volume pricing, ex-VAT invoicing and a dedicated contact who answers within 24 hours.</p></div>
  <div><form data-demo><input type="email" placeholder="Your work email" required><button class="btn btn-gold">Request trade pricing</button></form><p class="muted" style="font-size:12.5px;margin-top:12px">Or call {esc(BRAND['phone'])}. No spam, no newsletters you did not ask for.</p></div>
</div></div></section>'''

def trust_strip():
    return f'''<div class="trust"><div class="wrap trust-in">
  <div class="trust-item">{ICON['truck']}<div><b>Ships within 24h</b><span>From our Dutch warehouse, across the EU</span></div></div>
  <div class="trust-item">{ICON['shield']}<div><b>EMC approved motors</b><span>No interference with vehicle electronics</span></div></div>
  <div class="trust-item">{ICON['box']}<div><b>Complete kits</b><span>Fan, switch, valve and filter in one box</span></div></div>
  <div class="trust-item">{ICON['chat']}<div><b>Engineers on the phone</b><span>Real advice on cut-outs, voltage and airflow</span></div></div>
</div></div>'''

# ---------------------------------------------------------------- pages
def page_index():
    lm = P['le-mans']
    best_ids = ['le-mans', 'v12-valve', 'turbo-ii', 'winglet', 'speedcontrol', 'switch-fan', 'floor-ventilator-129', 'roof-hatch-electric-large']
    hero_bundles = [b for b in BUNDLES if b.get('hero')]
    reviews = [
        ('Excellent products for a fair price, lightning-fast reply to my email and shipping usually the same day.', 'Rick de K.', 'Van conversion, NL'),
        ('Very satisfied with the products and the team. Customer care and assistance are excellent.', 'Stefania D.', 'Coach builder, IT'),
        ('Reliable and of excellent quality. Our horse trucks have run these roof fans for years.', 'Tommy S.', 'Horsebox builder'),
    ]
    compare_rows = [('le-mans', '850 m³/h', '12V / 24V', '80 W', '52 dB(A)', 'Ø 230 mm', 'Blow &amp; suck'),
                    ('le-mans-ll', '515 to 565 m³/h', '12V / 24V', '34 W', '65 dB(A)', 'Ø 230 mm', 'Suck, brushless'),
                    ('rooftop-round', '850 m³/h', '12V / 24V', '80 W', '52 dB(A)', 'Ø 230 mm', 'Blow &amp; suck'),
                    ('winglet', '65 m³/h', '12V', '3 W', '32 dB(A)', 'Ø 80 mm', 'Suck'),
                    ('turbo-ii', '~245 m³/h at 100 km/h', 'None', '0 W', 'Silent', 'Ø 128 mm', 'Suck while driving'),
                    ('turbo-iii', '~120 m³/h at 100 km/h', 'None', '0 W', 'Silent', 'Ø 80 mm', 'Suck while driving'),
                    ('exhaust-ventilator', 'Venturi', 'None', '0 W', 'Silent', 'max. Ø 140 mm', 'Suck while driving')]
    h = head('Pegasus Depot · Premium Vehicle Ventilation, Roof Hatches & LED Lighting', 'Rooftop ventilators, interior valves, switches, roof hatches and LED lighting for vans, campers, horse trailers, buses and ambulances. Dutch engineered, EMC approved, shipped within 24h across Europe.', 0, lm['images'][2], '')
    h += jsonld(ORG_LD) + jsonld({"@context": "https://schema.org", "@type": "WebSite", "name": "Pegasus Depot", "url": SITE_URL})
    h += header(0)
    h += f'''
<section class="hero"><div class="hero-bg" style="background-image:url('{scene(lm['images'][2],2000)}')"></div>
<div class="wrap hero-in">
  <div><div class="eyebrow">Dutch engineered · EMC approved · Ships in 24h</div>
    <h1 class="h-display">Engineered airflow for vehicles that <em>work harder.</em></h1>
    <p class="lead">Rooftop ventilators, closable valves, roof hatches and LED lighting for vans, campers, horse trailers, coaches and ambulances. Bought direct, delivered fast, backed by engineers who answer the phone.</p>
    <div class="hero-cta"><a class="btn btn-gold btn-lg" href="shop.html?cat=rooftop-ventilators">Shop rooftop ventilators {ICON['arrow']}</a><a class="btn btn-ghost btn-lg" href="bundles.html">Build a complete kit</a></div></div>
  <div class="hero-stats"><div class="stat"><b>850</b><span>m³/h airflow from the Le Mans, our bestseller</span></div><div class="stat"><b>24h</b><span>dispatch from stock in the Netherlands</span></div><div class="stat"><b>42</b><span>countries served through dealers and direct</span></div><div class="stat"><b>20+</b><span>years of vehicle ventilation manufacturing</span></div></div>
</div></section>
{trust_strip()}

<section class="section dark"><div class="wrap">
  <div class="sec-head reveal"><div><div class="eyebrow">Shop by category</div><h2 class="h2">Everything between the roof and the floor.</h2></div><a class="link" href="shop.html">View all {len(PRODUCTS)} products {ICON['arrow']}</a></div>
  <div class="cat-grid reveal">{''.join(f'<a class="cat-tile" href="shop.html?cat={c["id"]}"><span class="count">{sum(1 for p in PRODUCTS if p["category"]==c["id"])} products</span><img src="{sq(c["image"],700)}" alt="" loading="lazy"><b>{esc(c["name"])}</b><span>{esc(c["short"])}</span></a>' for c in CATS)}</div>
</div></section>

<section class="section ivory"><div class="wrap">
  <div class="sec-head reveal"><div><div class="eyebrow">Bestsellers</div><h2 class="h2">What Europe's bodybuilders order every week.</h2></div><a class="link" href="shop.html">Shop all {ICON['arrow']}</a></div>
  <div class="grid reveal">{''.join(card(P[i]) for i in best_ids)}</div>
</div></section>

<section class="section dark-2"><div class="wrap">
  <div class="sec-head reveal"><div><div class="eyebrow">Kits &amp; bundles</div><h2 class="h2">One hole. One box. Everything inside.</h2><p class="lead">We pre-match fan, switch, valve and filter so nothing is missing on installation day. Kits save 8 to 12% versus buying the parts separately.</p></div><a class="link" href="bundles.html">All {len(BUNDLES)} kits {ICON['arrow']}</a></div>
  <div class="grid grid-3 reveal">{''.join(bundle_card(b) for b in hero_bundles[:3])}</div>
</div></section>

<section class="section ivory-2"><div class="wrap">
  <div class="split reveal"><div class="media"><img src="{scene(P['le-mans']['images'][3],1400)}" alt="Le Mans rooftop ventilator installed on a van roof" loading="lazy"><span class="tag">Le Mans · 850 m³/h</span></div>
  <div><div class="eyebrow">The Le Mans system</div><h2 class="h2" style="margin:12px 0 16px">The roof fan that became the standard.</h2><p class="lead">Ambulance converters, horsebox builders and bus manufacturers specify the Le Mans for one reason: it moves 850 m³/h in either direction, year after year, without drama. Build it into a complete system in four steps.</p>
  <ul class="checks"><li>{ICON['check']}<div><b>1. Choose your fan</b>12V or 24V, white or black, or motorless.</div></li><li>{ICON['check']}<div><b>2. Add a switch</b>Round, square or illuminated with ventilation symbol: blow / off / suck.</div></li><li>{ICON['check']}<div><b>3. Finish the ceiling</b>V12 closable valve (manual or electric), Flower Power LED valve or honeycomb grille.</div></li><li>{ICON['check']}<div><b>4. Control and protect</b>Speedcontrol for silent nights, snow filter and a floor vent for a full airflow loop.</div></li></ul>
  <div class="hero-cta"><a class="btn btn-dark" href="bundles/le-mans-complete-kit.html">Le Mans Complete Kit {ICON['arrow']}</a><a class="btn btn-ghost" href="products/le-mans.html">Le Mans product page</a></div></div></div>
</div></section>

<section class="section ivory"><div class="wrap">
  <div class="sec-head reveal"><div><div class="eyebrow">Shop by vehicle</div><h2 class="h2">Built for the way your vehicle works.</h2></div></div>
  <div class="veh-grid reveal">{''.join(vehicle_tile(v) for v in VEHICLES)}</div>
</div></section>

<section class="section white"><div class="wrap">
  <div class="sec-head reveal"><div><div class="eyebrow">Which roof fan?</div><h2 class="h2">Seven ventilators, one honest comparison.</h2></div><a class="link" href="shop.html?cat=rooftop-ventilators">Shop rooftop ventilators {ICON['arrow']}</a></div>
  <div class="table-wrap reveal"><table class="compare"><thead><tr><th>Model</th><th></th><th>Airflow</th><th>Voltage</th><th>Power</th><th>Noise</th><th>Roof cut-out</th><th>Function</th><th>From</th></tr></thead><tbody>
  {''.join(f'<tr><td><a href="products/{i}.html">{esc(P[i]["short_name"])}</a></td><td><img src="{sq(P[i]["images"][0],200)}" alt=""></td><td>{a}</td><td>{v}</td><td>{w}</td><td>{n}</td><td>{c}</td><td>{f}</td><td><b>{money(price_from(P[i]))}</b></td></tr>' for i,a,v,w,n,c,f in compare_rows)}
  </tbody></table></div>
</div></section>

<section class="section dark"><div class="wrap">
  <div class="sec-head reveal"><div><div class="eyebrow">Why buy direct from Pegasus Depot</div><h2 class="h2">Manufacturer quality. Webshop convenience.</h2></div></div>
  <div class="usp-grid reveal">
    <div class="usp">{ICON['bolt']}<b>EMC approved, every motor</b><p>Our ventilators carry EMC approval so they never disturb radios, telematics or medical equipment. Test reports available on request.</p></div>
    <div class="usp">{ICON['box']}<b>From stock, within 24h</b><p>Thousands of units on the shelf in the Netherlands. Order before 15:00 and we ship the same working day across the EU.</p></div>
    <div class="usp">{ICON['ruler']}<b>Made to fit</b><p>Standard 230 mm, 128 mm and 80 mm cut-outs, roof thickness ranges up to 70 mm, and technical drawings for every product.</p></div>
    <div class="usp">{ICON['euro']}<b>Kits that save</b><p>Complete kits save 8 to 12%. Trade accounts get volume pricing and ex-VAT invoicing. No hidden surcharges.</p></div>
  </div>
</div></section>

<section class="section ivory"><div class="wrap">
  <div class="sec-head reveal"><div><div class="eyebrow">Customer reviews</div><h2 class="h2">Rated excellent by the people who install it.</h2></div></div>
  <div class="rev-grid reveal">{''.join(f'<div class="rev"><div class="stars">★★★★★</div><p>“{esc(t)}”</p><small>{esc(n)} · {esc(w)}</small></div>' for t,n,w in reviews)}</div>
</div></section>

<section class="section white"><div class="wrap">
  <div class="sec-head reveal"><div><div class="eyebrow">FAQ</div><h2 class="h2">Straight answers before you drill.</h2></div></div>
  <div class="reveal">{faq_block([
    {"q":"How big a hole do I need to cut?","a":"Le Mans, Le Mans LL and Round rooftop ventilators need Ø 230 mm. Turbo II needs Ø 128 mm. Winglet and Turbo III need Ø 80 mm. Floor ventilators are Ø 129 mm or Ø 80 mm. Every product page has the drawing."},
    {"q":"12V or 24V?","a":"Cars, vans, campers and trailers towed by them are 12V. Trucks, coaches, buses and most horse trucks on a truck chassis are 24V. Roof hatches and the control unit are 24V; for 12V vehicles we supply a converter."},
    {"q":"Do I need a switch and a speed controller?","a":"Electric roof fans need a 3-way switch to select blow / off / suck. The Speedcontrol is optional but recommended: it lets the fan run quietly at reduced speed and draws no current at zero."},
    {"q":"Can I close the vent in winter?","a":"Yes. Choose a closable interior valve: V12 (manual or electric), Flower Power or the rotating valve. The honeycomb grille is fixed and cannot be closed."},
    {"q":"How fast do you ship?","a":"Orders placed before 15:00 CET ship the same working day from our warehouse in the Netherlands. Free EU shipping from €150."},
    {"q":"Do you offer trade pricing?","a":"Yes. Bodybuilders, converters, fleets and dealers can request a trade account for volume pricing and ex-VAT invoicing."},
  ])}</div>
</div></section>
{newsletter()}
'''
    h += footer(0)
    return h

def page_shop():
    h = head('Shop all vehicle ventilation products · Pegasus Depot', 'All rooftop ventilators, interior valves, switches, roof hatches, floor vents and LED lighting. Filter by category, vehicle type and voltage.', 0, P['le-mans']['images'][2], 'shop.html')
    h += header(0)
    cat_f = ''.join(f'<label><input type="checkbox" data-f="cat:{c["id"]}"> {esc(c["name"])}</label>' for c in CATS)
    veh_f = ''.join(f'<label><input type="checkbox" data-f="veh:{v["id"]}"> {esc(v["nav"])}</label>' for v in VEHICLES)
    volt_f = ''.join(f'<label><input type="checkbox" data-f="volt:{x}"> {x}</label>' for x in ['12V', '24V', 'Motorless', 'No power'])
    h += f'''
<section class="page-hero" style="min-height:360px"><img class="bg" src="{scene(P['le-mans']['images'][4],1800)}" alt=""><div class="wrap"><div class="crumbs"><a href="index.html">Home</a> / <span>Shop</span></div><div class="eyebrow">All products</div><h1 class="h1">The complete range, <em class="serif" style="color:var(--gold-2);font-style:italic;font-weight:400">in stock.</em></h1><p class="lead">{len(PRODUCTS)} products across {len(CATS)} categories. Filter by what you drive and what voltage you run.</p></div></section>
<section class="section--tight ivory"><div class="wrap shop" data-shop>
  <aside class="filters">
    <div><h5>Search</h5><input id="shop-q" type="search" placeholder="Name or article number" style="width:100%;padding:11px 14px;border:1px solid var(--line);border-radius:10px;font:inherit;background:#fff"></div>
    <div><h5>Category</h5>{cat_f}</div>
    <div><h5>Vehicle</h5>{veh_f}</div>
    <div><h5>Power</h5>{volt_f}</div>
    <button class="btn btn-ghost btn-sm" id="clear-f">Clear filters</button>
  </aside>
  <div>
    <div class="shop-top"><div><span id="shop-count" style="font-weight:700"></span> <span class="muted">· prices incl. VAT</span></div><div style="display:flex;gap:10px"><button class="btn btn-ghost btn-sm mob-filter" id="mob-filter">Filters</button><select id="sort"><option value="featured">Sort: Featured</option><option value="price-asc">Price: low to high</option><option value="price-desc">Price: high to low</option><option value="name">Name A to Z</option></select></div></div>
    <div class="grid grid-3" id="shop-grid">{''.join(card(p) for p in PRODUCTS)}</div>
  </div>
</div></section>
{newsletter()}'''
    h += footer(0)
    return h

def page_bundles():
    h = head('Kits & bundles · save up to 12% · Pegasus Depot', 'Complete ventilation kits: roof fan + switch + valve + filter, pre-matched and discounted. For vans, campers, horse trailers, buses and ambulances.', 0, B['le-mans-complete-kit']['scene'], 'bundles.html')
    h += header(0)
    h += f'''
<section class="page-hero"><img class="bg" src="{scene(B['le-mans-complete-kit']['scene'],1800)}" alt=""><div class="wrap"><div class="crumbs"><a href="index.html">Home</a> / <span>Kits &amp; bundles</span></div><div class="eyebrow">Kits &amp; bundles</div><h1 class="h1">Everything in one box, <em class="serif" style="color:var(--gold-2);font-style:italic;font-weight:400">8 to 12% cheaper.</em></h1><p class="lead">We pre-match fan, switch, valve, filter and floor vent so nothing is missing when the hole saw comes out. Choose your voltage and colours on each kit page.</p></div></section>
<section class="section dark-2"><div class="wrap"><div class="grid grid-3">{''.join(bundle_card(b) for b in BUNDLES)}</div></div></section>
<section class="section ivory"><div class="wrap"><div class="sec-head"><div><div class="eyebrow">How kits work</div><h2 class="h2">Pick the kit, pick the options, done.</h2></div></div>
<div class="pain-grid"><div class="pain"><div class="num">01</div><b>Pre-matched by engineers</b><p>Every kit combines parts that share the same cut-out, voltage and connectors. No surprises on the roof.</p></div><div class="pain"><div class="num">02</div><b>Choose colour and voltage</b><p>Select 12V or 24V, white or black covers and the interior valve colour on the kit page. The price updates live.</p></div><div class="pain"><div class="num">03</div><b>One parcel, one invoice</b><p>Ships within 24h as a single consignment. Trade customers get the bundle price on top of their account terms.</p></div></div></div></section>
{newsletter()}'''
    h += footer(0)
    return h

def page_product(p):
    depth = 1; r = rel(depth)
    c = CAT[p['category']]
    pf = price_from(p); cf = compare_from(p)
    first = next((v for v in p['variants'] if v.get('price') is not None), p['variants'][0])
    opt_names = list((p['variants'][0].get('options') or {}).keys())
    gal = []
    for img in p['images']:
        sc = is_scene(img)
        gal.append((scene(img, 1400) if sc else sq(img, 1400), sc))
    if p.get('drawing'):
        gal.append((opt(p['drawing'], 1400), False))
    thumbs = ''.join(f'<button class="{"on" if i==0 else ""}" data-src="{r}{src}" {"data-scene=1" if sc else ""} aria-label="Image {i+1}"><img src="{r}{src}" alt="" class="{"scene" if sc else ""}" loading="lazy"></button>' for i, (src, sc) in enumerate(gal))
    badges = ''.join(f'<span class="badge {"gold" if b in ("Bestseller","New") else ""}">{esc(b)}</span>' for b in p.get('badges', []))
    opts_html = ''
    for k in opt_names:
        opts_html += f'<div class="opt-group"><h6>{esc(k)} <span data-opt-label="{esc(k)}"></span></h6><div class="opts" data-opt="{esc(k)}"></div></div>'
    addon_ids = [a for a in p.get('accessories', []) if a in P and not P[a].get('quote_only')][:4]
    addons = ''
    for a in addon_ids:
        ap = P[a]; av = next(v for v in ap['variants'] if v.get('price') is not None)
        addons += f'<label class="addon"><input type="checkbox" data-sku="{av["sku"]}" data-price="{av["price"]}"><img src="{r}{sq(ap["images"][0],200)}" alt=""><div><b>{esc(ap["short_name"])}</b><span>{esc(av["label"])} · {av["sku"]}</span></div><span class="p">+ {money(av["price"])}</span></label>'
    in_bundles = [b for b in BUNDLES if any(it['product'] == p['id'] for it in b['items'])]
    upsell = ''
    if in_bundles:
        b = in_bundles[0]; full, price = bundle_calc(b)
        upsell = f'<div class="upsell"><h6>Complete the set and save {int(b["discount"]*100)}%</h6><div class="up-row"><img src="{r}{sq(b["images"][0],200)}" alt=""><div><b>{esc(b["name"])}</b><span>{esc(b["tagline"])} <b style="display:inline;color:var(--gold-deep)">{money(price)}</b> <s class="muted">{money(full)}</s></span></div><a class="btn btn-dark btn-sm" href="{r}bundles/{b["id"]}.html">View kit</a></div></div>'
    specs = ''.join(f'<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>' for k, v in (p.get('specs') or {}).items())
    variants_table = '<table class="spec-table"><thead><tr><th>Article no.</th><th>Variant</th><th>Price incl. VAT</th></tr></thead><tbody>' + ''.join(f'<tr><td style="font-weight:700;color:var(--text)">{v["sku"]}</td><td>{esc(v["label"])}</td><td>{money(v["price"]) if v.get("price") is not None else "On request"}</td></tr>' for v in p['variants']) + '</tbody></table>'
    dls = ''
    dls += f'<a href="{r}contact.html?datasheet={first["sku"]}">{ICON["doc"]} Request technical datasheet (PDF)</a>'
    if p.get('drawing'): dls += f'<a href="{r}{opt(p["drawing"],2000)}" target="_blank" rel="noopener">{ICON["ruler"]} Dimensional drawing</a>'
    related = [P[a] for a in p.get('accessories', []) if a in P][:4]
    if len(related) < 4:
        related += [x for x in PRODUCTS if x['category'] == p['category'] and x['id'] != p['id'] and x not in related][:4 - len(related)]
    vehicles = [VEH[a] for a in p.get('applications', []) if a in VEH]
    quote = p.get('quote_only')
    ideal = ('<div class="pill-row" style="margin-top:10px"><span class="muted" style="font-size:13px;align-self:center">Ideal for:</span>' + ''.join(f'<a class="pill" href="{r}vehicles/{v["id"]}.html">{esc(v["nav"])}</a>' for v in vehicles) + '</div>') if vehicles else ''
    buy_btn = (f'<a class="btn btn-gold btn-lg" href="{r}contact.html?product={p["id"]}">Request a quote {ICON["arrow"]}</a>' if quote
               else f'<button class="btn btn-gold btn-lg" id="add-btn">Add to cart {ICON["bag"]}</button>')
    addons_html = f'<div class="addons"><h6 class="eyebrow" style="margin-bottom:4px">Frequently added</h6>{addons}<div style="display:flex;justify-content:space-between;font-size:13px;color:var(--text-2);padding:4px 2px"><span>Total with selected add-ons</span><b id="addon-total"></b></div></div>' if addons and not quote else ''
    drawing_html = f'<div class="drawing-box"><img src="{r}{opt(p["drawing"],1400)}" alt="Dimensional drawing {esc(p["name"])}" loading="lazy"></div>' if p.get('drawing') else ''
    faq_tab_btn = '<button data-tab="t-faq">FAQ</button>' if p.get('faq') else ''
    faq_tab = f'<div class="tab-panel" id="t-faq">{faq_block(p["faq"])}</div>' if p.get('faq') else ''
    kits_html = ('<section class="section dark-2"><div class="wrap"><div class="sec-head"><div><div class="eyebrow">Kits with this product</div><h2 class="h2">Save up to 12% in a kit.</h2></div></div><div class="grid grid-3">' + ''.join(bundle_card(b, depth) for b in in_bundles[:3]) + '</div></div></section>') if in_bundles else ''
    qty_html = '' if quote else '<div class="qty"><button id="qty-minus" aria-label="Less">−</button><input id="qty" value="1" inputmode="numeric"><button id="qty-plus" aria-label="More">+</button></div>'
    sticky_btn = f'<a class="btn btn-gold" href="{r}contact.html">Request a quote</a>' if quote else '<button class="btn btn-gold" id="sticky-add">Add to cart</button>'
    h = head(f'{p["name"]} · {p["tagline"]} · Pegasus Depot', p['summary'], depth, p['images'][0], f'products/{p["id"]}.html')
    h += product_ld(p)
    h += header(depth)
    h += f'''
<div class="wrap"><div class="crumbs light-crumbs"><a href="{r}index.html">Home</a> / <a href="{r}shop.html">Shop</a> / <a href="{r}shop.html?cat={c['id']}">{esc(c['name'])}</a> / <span>{esc(p['short_name'])}</span></div></div>
<section class="wrap pdp" data-pdp="{p['id']}">
  <div class="gallery"><div class="gallery-main"><div class="badge-wrap">{badges}</div><img id="gallery-img" src="{r}{gal[0][0]}" alt="{esc(p['name'])}" class="{'scene' if gal[0][1] else ''}"></div><div class="thumbs">{thumbs}</div></div>
  <div class="buy">
    <div class="eyebrow">{esc(c['name'])}</div>
    <h1 class="h1">{esc(p['name'])}</h1>
    <p class="tagline">{esc(p['tagline'])}</p>
    <div class="rating">★★★★★ <span>4.9 · trusted by bodybuilders across Europe</span></div>
    <div class="buy-price"><span class="now" id="pdp-price">{money(pf) if pf is not None else 'On request'}</span><span class="was" id="pdp-was">{money(cf) if cf else ''}</span><span class="save" id="pdp-save"></span></div>
    <div class="vat">{'Price on request, configured per application.' if quote else 'Incl. 21% VAT · ex-VAT for trade accounts · free EU shipping from €150'}</div>
    <div class="sku" id="pdp-sku">Article no. {first['sku']}</div>
    {opts_html}
    <div class="buy-row">{qty_html}{buy_btn}</div>
    {upsell}
    {addons_html}
    <ul class="buy-meta"><li>{ICON['truck']}<span><b>Ships within 24h</b> from stock in the Netherlands</span></li><li>{ICON['shield']}<span><b>2-year warranty</b> and 30-day returns on unused items</span></li><li>{ICON['chat']}<span><b>Installation advice</b> by phone or email, same day</span></li></ul>
    <p style="margin-top:18px;font-size:15px;color:var(--text-2);line-height:1.65">{esc(p['summary'])}</p>
  </div>
</section>
<div class="wrap"><div class="tabs">
  <div class="tab-nav"><button class="on" data-tab="t-desc">Description</button><button data-tab="t-spec">Specifications</button><button data-tab="t-var">Variants &amp; article numbers</button><button data-tab="t-dl">Downloads &amp; drawing</button>{faq_tab_btn}</div>
  <div class="tab-panel on" id="t-desc">{''.join(f'<p>{esc(x)}</p>' for x in p['description'])}<h4 class="h4" style="margin:18px 0 10px">Key features</h4><ul class="feat">{''.join(f'<li>{esc(f)}</li>' for f in p['features'])}</ul>{ideal}</div>
  <div class="tab-panel" id="t-spec"><table class="spec-table">{specs}</table></div>
  <div class="tab-panel" id="t-var">{variants_table}</div>
  <div class="tab-panel" id="t-dl"><div class="dl">{dls}</div>{drawing_html}</div>
  {faq_tab}
</div></div>
<section class="section ivory"><div class="wrap"><div class="sec-head"><div><div class="eyebrow">Complete the system</div><h2 class="h2">Goes well with the {esc(p['short_name'])}.</h2></div><a class="link" href="{r}shop.html">Shop all {ICON['arrow']}</a></div><div class="grid">{''.join(card(x, depth) for x in related)}</div></div></section>
{kits_html}
{newsletter(depth)}
<div class="sticky-buy"><div class="price" id="sticky-price">{money(pf) if pf is not None else 'Quote'}</div>{sticky_btn}</div>
'''
    h += footer(depth)
    return h

def page_bundle(b):
    depth = 1; r = rel(depth)
    full, price = bundle_calc(b)
    items = ''
    for i, it in enumerate(b['items']):
        p = P[it['product']]
        sku = it.get('sku') or it['choices'][0]
        v = SKU[sku][1]
        opts = '<div class="b-opts"></div>' if it.get('choices') else f'<div class="qtyb">{esc(v["label"])}</div>'
        vg = f'<span class="qtyb">{esc(it.get("variant_group",""))}</span>' if it.get('variant_group') else ''
        items += f'<div class="b-item" data-bitem="{i}"><img src="{r}{sq(p["images"][0],200)}" alt=""><div><b>{it["qty"]}× {esc(p["name"])}</b>{vg}{opts}<a class="link" style="font-size:12px;margin-top:8px" href="{r}products/{p["id"]}.html">Product details {ICON["arrow"]}</a></div><div class="b-price"></div></div>'
    gal = [(scene(b['scene'], 1400), True)] + [(sq(i, 1200), False) for i in b['images']]
    thumbs = ''.join(f'<button class="{"on" if i==0 else ""}" data-src="{r}{src}" {"data-scene=1" if sc else ""} aria-label="Image {i+1}"><img src="{r}{src}" alt="" class="{"scene" if sc else ""}" loading="lazy"></button>' for i, (src, sc) in enumerate(gal))
    included = ''.join(f'<li>{ICON["check"]}<div><b>{it["qty"]}× {esc(P[it["product"]]["name"])}</b>{esc(P[it["product"]]["tagline"])}</div></li>' for it in b['items'])
    vehicles = [VEH[a] for a in b.get('for', []) if a in VEH]
    other = [x for x in BUNDLES if x['id'] != b['id'] and set(x.get('for', [])) & set(b.get('for', []))][:3] or [x for x in BUNDLES if x['id'] != b['id']][:3]
    ideal = ('<div class="pill-row" style="margin-top:10px"><span class="muted" style="font-size:13px;align-self:center">Ideal for:</span>' + ''.join(f'<a class="pill" href="{r}vehicles/{v["id"]}.html">{esc(v["nav"])}</a>' for v in vehicles) + '</div>') if vehicles else ''
    h = head(f'{b["name"]} · save {int(b["discount"]*100)}% · Pegasus Depot', b['summary'], depth, b['scene'], f'bundles/{b["id"]}.html')
    h += jsonld({"@context": "https://schema.org", "@type": "Product", "name": b['name'], "description": b['summary'], "brand": {"@type": "Brand", "name": "Pegasus Depot"}, "image": [f"{SITE_URL}/{scene(b['scene'], 1400)}"], "url": f"{SITE_URL}/bundles/{b['id']}.html", "offers": {"@type": "Offer", "price": f"{price:.2f}", "priceCurrency": "EUR", "availability": "https://schema.org/InStock", "url": f"{SITE_URL}/bundles/{b['id']}.html"}})
    h += header(depth)
    h += f'''
<div class="wrap"><div class="crumbs light-crumbs"><a href="{r}index.html">Home</a> / <a href="{r}bundles.html">Kits &amp; bundles</a> / <span>{esc(b['name'])}</span></div></div>
<section class="wrap pdp" data-bundle="{b['id']}">
  <div class="gallery"><div class="gallery-main"><div class="badge-wrap">{''.join(f'<span class="badge gold">{esc(x)}</span>' for x in b.get('badges',[]))}</div><img id="gallery-img" class="scene" src="{r}{gal[0][0]}" alt="{esc(b['name'])}"></div><div class="thumbs">{thumbs}</div></div>
  <div class="buy">
    <div class="eyebrow">Complete kit · {len(b['items'])} components</div>
    <h1 class="h1">{esc(b['name'])}</h1>
    <p class="tagline">{esc(b['tagline'])}</p>
    <p style="margin-top:16px;font-size:15.5px;color:var(--text-2);line-height:1.65">{esc(b['summary'])}</p>
    <h6 class="eyebrow" style="margin-top:26px">Configure your kit</h6>
    <div class="bundle-items">{items}</div>
    <div class="b-total"><div><div class="lbl">Kit price incl. VAT</div><div class="sum"><span class="was" id="b-full">{money(full)}</span><span id="b-price">{money(price)}</span></div><div class="saving" id="b-save"></div></div><button class="btn btn-gold btn-lg" id="add-btn">Add kit to cart {ICON['bag']}</button></div>
    <ul class="buy-meta"><li>{ICON['truck']}<span><b>Ships within 24h</b> as one parcel, from stock in the Netherlands</span></li><li>{ICON['shield']}<span><b>2-year warranty</b> on every component</span></li><li>{ICON['chat']}<span><b>Installation advice</b> included: call or email our engineers</span></li></ul>
  </div>
</section>
<div class="wrap"><div class="tabs">
  <div class="tab-nav"><button class="on" data-tab="t-desc">Why this kit</button><button data-tab="t-inc">What's included</button></div>
  <div class="tab-panel on" id="t-desc">{''.join(f'<p>{esc(x)}</p>' for x in b['description'])}{ideal}</div>
  <div class="tab-panel" id="t-inc"><ul class="checks">{included}</ul></div>
</div></div>
<section class="section dark-2"><div class="wrap"><div class="sec-head"><div><div class="eyebrow">More kits</div><h2 class="h2">Other kits for the same job.</h2></div><a class="link" href="{r}bundles.html">All kits {ICON['arrow']}</a></div><div class="grid grid-3">{''.join(bundle_card(x, depth) for x in other)}</div></div></section>
{newsletter(depth)}
<div class="sticky-buy"><div class="price" id="sticky-price">{money(price)}</div><button class="btn btn-gold" id="sticky-add">Add kit to cart</button></div>
'''
    h += footer(depth)
    return h

def page_vehicle(v):
    depth = 1; r = rel(depth)
    prods = [P[i] for i in v['products'] if i in P]
    bundles = [B[i] for i in v['bundles'] if i in B]
    faq_html = ('<section class="section white"><div class="wrap"><div class="sec-head"><div><div class="eyebrow">FAQ</div><h2 class="h2">Questions from ' + esc(v['nav'].lower()) + ' owners.</h2></div></div>' + faq_block(v['faq']) + '</div></section>') if v.get('faq') else ''
    h = head(f'Ventilation for {v["name"]} · Pegasus Depot', v['intro'], depth, v['hero'], f'vehicles/{v["id"]}.html')
    h += header(depth)
    h += f'''
<section class="page-hero"><img class="bg" src="{r}{scene(v['hero'],1800)}" alt="{esc(v['name'])}"><div class="wrap"><div class="crumbs"><a href="{r}index.html">Home</a> / <span>Shop by vehicle</span> / <span>{esc(v['name'])}</span></div><div class="eyebrow">{esc(v['eyebrow'])}</div><h1 class="h1">{esc(v['headline'])}</h1><p class="lead">{esc(v['intro'])}</p><div class="hero-cta"><a class="btn btn-gold" href="#kits">Recommended kits {ICON['arrow']}</a><a class="btn btn-ghost" href="#products">All products for {esc(v['nav'].lower())}</a></div></div></section>
<section class="section ivory"><div class="wrap"><div class="sec-head"><div><div class="eyebrow">The challenge</div><h2 class="h2">What goes wrong without proper airflow.</h2></div></div>
<div class="pain-grid">{''.join(f'<div class="pain"><div class="num">0{i+1}</div><b>{esc(x["title"])}</b><p>{esc(x["text"])}</p></div>' for i,x in enumerate(v['pains']))}</div></div></section>
<section class="section dark-2" id="kits"><div class="wrap"><div class="sec-head"><div><div class="eyebrow">Recommended kits</div><h2 class="h2">Pre-matched for {esc(v['nav'].lower())}.</h2></div><a class="link" href="{r}bundles.html">All kits {ICON['arrow']}</a></div><div class="grid grid-3">{''.join(bundle_card(b, depth) for b in bundles)}</div></div></section>
<section class="section ivory" id="products"><div class="wrap"><div class="sec-head"><div><div class="eyebrow">Products</div><h2 class="h2">Everything we recommend for {esc(v['nav'].lower())}.</h2></div><a class="link" href="{r}shop.html?veh={v['id']}">Filter the shop {ICON['arrow']}</a></div><div class="grid">{''.join(card(p, depth) for p in prods)}</div></div></section>
{faq_html}
<section class="section ivory-2"><div class="wrap"><div class="sec-head"><div><div class="eyebrow">Other vehicles</div><h2 class="h2">Also built for.</h2></div></div><div class="veh-grid">{''.join(vehicle_tile(x, depth) for x in VEHICLES if x['id']!=v['id'])}</div></div></section>
{newsletter(depth)}'''
    h += footer(depth)
    return h

def simple_page(slug, title, desc, body, og=None):
    h = head(f'{title} · Pegasus Depot', desc, 0, og, slug)
    h += header(0) + body + footer(0)
    return h

def page_about():
    body = f'''
<section class="page-hero"><img class="bg" src="{scene('assets/media/assembly-line.webp',1800)}" alt=""><div class="wrap"><div class="crumbs"><a href="index.html">Home</a> / <span>About</span></div><div class="eyebrow">About Pegasus Depot</div><h1 class="h1">Direct from the people who make it.</h1><p class="lead">Pegasus Depot is the direct-to-customer store for a Dutch vehicle ventilation manufacturer with more than twenty years of history, a dealer network in 42 countries and a warehouse full of stock in the Netherlands.</p></div></section>
<section class="section ivory"><div class="wrap"><div class="split"><div><div class="eyebrow">Our story</div><h2 class="h2" style="margin:12px 0 16px">Built for bodybuilders. Now open to everyone.</h2><p class="lead">For two decades our ventilators, valves, hatches and lights were sold through dealers and fitted by bus builders, ambulance converters, horsebox manufacturers and van outfitters across Europe. Pegasus Depot opens that same catalogue, at the same quality, to every workshop, fleet and owner who wants to buy direct.</p>
<ul class="checks"><li>{ICON['check']}<div><b>Manufacturer quality</b>Every product comes from the same production line our OEM customers rely on.</div></li><li>{ICON['check']}<div><b>Real stock, real speed</b>Thousands of units on the shelf. Order before 15:00 and it ships today.</div></li><li>{ICON['check']}<div><b>Engineers, not call centres</b>Questions about cut-outs, airflow or voltage are answered by people who design the products.</div></li></ul></div>
<div class="story-grid"><img src="{scene('assets/media/le-mans-warehouse.webp',1200)}" alt="Le Mans ventilators in the warehouse"><img src="{scene('assets/media/magazijn-6.webp',800)}" alt="Assembly of rooftop ventilators"><img src="{scene('assets/media/Magazijn-1.webp',800)}" alt="Stock shelves"></div></div></div></section>
<section class="section dark"><div class="wrap"><div class="sec-head"><div><div class="eyebrow">In numbers</div><h2 class="h2">Small company. Serious footprint.</h2></div></div><div class="hero-stats stats-4"><div class="stat"><b>20+</b><span>years manufacturing vehicle ventilation</span></div><div class="stat"><b>42</b><span>countries served</span></div><div class="stat"><b>{len(PRODUCTS)}</b><span>products, {sum(len(p['variants']) for p in PRODUCTS)} article numbers</span></div><div class="stat"><b>24h</b><span>dispatch from stock</span></div></div></div></section>
<section class="section ivory"><div class="wrap"><div class="story-grid"><img src="{scene('assets/media/magazijn5.webp',1400)}" alt="Warehouse logistics"><img src="{scene('assets/media/magazijn-6.webp',800)}" alt="Stock shelves"><img src="{scene('assets/media/assembly-line.webp',800)}" alt="Assembly of rooftop ventilators"></div></div></section>
{newsletter()}'''
    return simple_page('about.html', 'About us', 'Pegasus Depot is the direct-to-customer store of a Dutch vehicle ventilation manufacturer: 20+ years, 42 countries, stock in the Netherlands.', body, 'assets/media/le-mans-warehouse.webp')

def page_trade():
    body = f'''
<section class="page-hero"><img class="bg" src="{scene('assets/media/IMG_010422.webp',1800)}" alt=""><div class="wrap"><div class="crumbs"><a href="index.html">Home</a> / <span>Trade</span></div><div class="eyebrow">Trade &amp; fleet accounts</div><h1 class="h1">Volume pricing for the people who fit it for a living.</h1><p class="lead">Bodybuilders, van converters, horsebox manufacturers, ambulance outfitters, fleet workshops and dealers: open a trade account and buy at trade prices, ex-VAT, with a dedicated contact.</p></div></section>
<section class="section ivory"><div class="wrap contact-grid"><div><div class="eyebrow">What you get</div><h2 class="h2" style="margin:12px 0 18px">Built around your workshop, not our webshop.</h2>
<ul class="checks"><li>{ICON['check']}<div><b>Tiered volume pricing</b>Discounts from the first 10 units, better at 50 and project pricing above.</div></li><li>{ICON['check']}<div><b>Ex-VAT invoicing and 30-day terms</b>For approved EU businesses with a valid VAT number.</div></li><li>{ICON['check']}<div><b>Project support</b>Drawings, EMC reports, cut-out templates and airflow advice for new vehicle designs.</div></li><li>{ICON['check']}<div><b>Custom colours and OEM options</b>Grilles and valves in your fleet colour, motorless versions, private label on request.</div></li><li>{ICON['check']}<div><b>Call-off stock</b>Reserve quantities for a build programme and call them off as you need them.</div></li></ul></div>
<div class="info-card"><form class="form" data-demo><div class="form-row"><div class="field"><label>Company</label><input required></div><div class="field"><label>VAT number</label><input></div></div><div class="form-row"><div class="field"><label>Name</label><input required></div><div class="field"><label>Email</label><input type="email" required></div></div><div class="field"><label>What do you build or run?</label><select><option>Van conversions / bodybuilding</option><option>Horseboxes / animal transport</option><option>Buses / coaches</option><option>Ambulances / emergency vehicles</option><option>Campers / leisure</option><option>Marine</option><option>Fleet workshop</option><option>Dealer / reseller</option></select></div><div class="field"><label>Expected annual volume</label><select><option>10 to 50 units</option><option>50 to 250 units</option><option>250+ units</option></select></div><div class="field"><label>Message</label><textarea rows="4" placeholder="Which products, which vehicles, which timeline?"></textarea></div><button class="btn btn-gold btn-block">Request a trade account {ICON['arrow']}</button><p class="note">We reply within one working day. Existing dealers keep their current terms.</p></form></div></div></section>
{newsletter()}'''
    return simple_page('trade.html', 'Trade & fleet accounts', 'Trade pricing, ex-VAT invoicing and project support for bodybuilders, converters, fleets and dealers.', body)

def page_contact():
    body = f'''
<section class="page-hero" style="min-height:340px"><img class="bg" src="{scene('assets/media/Magazijn-1.webp',1800)}" alt=""><div class="wrap"><div class="crumbs"><a href="index.html">Home</a> / <span>Contact</span></div><div class="eyebrow">Contact</div><h1 class="h1">Talk to an engineer, not a bot.</h1><p class="lead">Cut-out sizes, 12V or 24V, how many fans for a 7-metre body: ask us. We answer within 24 hours on working days, usually much faster.</p></div></section>
<section class="section ivory"><div class="wrap contact-grid"><div class="info-card"><form class="form" data-demo><div class="form-row"><div class="field"><label>Name</label><input required></div><div class="field"><label>Email</label><input type="email" required></div></div><div class="form-row"><div class="field"><label>Phone</label><input></div><div class="field"><label>Vehicle type</label><select>{''.join(f'<option>{esc(v["name"])}</option>' for v in VEHICLES)}<option>Other</option></select></div></div><div class="field"><label>Message</label><textarea rows="6" placeholder="Tell us about the vehicle, the products you have in mind and any article numbers."></textarea></div><button class="btn btn-gold btn-block">Send message {ICON['arrow']}</button></form></div>
<div style="display:grid;gap:16px"><div class="info-card"><b>Email</b><span>{esc(BRAND['email'])}</span><b>Phone</b><span>{esc(BRAND['phone'])} · Mon to Fri 08:30 to 17:00 CET</span><b>Warehouse &amp; office</b><span>{esc(BRAND['address'])}</span></div><div class="info-card"><b>Technical documents</b><span>Every product page has a downloadable datasheet and dimensional drawing. EMC test reports are available on request for trade customers.</span></div><div class="info-card"><b>Returns</b><span>Unused items in original packaging can be returned within 30 days. See <a href="shipping-returns.html" style="text-decoration:underline">shipping &amp; returns</a>.</span></div></div></div></section>'''
    return simple_page('contact.html', 'Contact', 'Contact Pegasus Depot for technical advice, quotes and trade accounts.', body)

def page_shipping():
    body = f'''
<section class="section ivory"><div class="wrap" style="max-width:860px"><div class="crumbs light-crumbs" style="padding:0 0 20px"><a href="index.html">Home</a> / <span>Shipping &amp; returns</span></div><div class="eyebrow">Shipping &amp; returns</div><h1 class="h1" style="margin:12px 0 24px">Fast out, easy back.</h1>
<h3 class="h3">Shipping</h3><p class="lead" style="margin:10px 0 22px">Orders placed before 15:00 CET on working days ship the same day from our warehouse in the Netherlands. Netherlands and Belgium: next working day. Germany, France, Austria, Denmark: 2 to 3 working days. Rest of EU: 3 to 5 working days. UK, Switzerland, Norway: 4 to 7 working days, duties may apply.</p>
<table class="spec-table" style="margin-bottom:30px"><tr><th>Netherlands &amp; Belgium</th><td>€6.95 · free from €{BRAND['free_shipping_from']}</td></tr><tr><th>Germany, France, Luxembourg, Austria, Denmark</th><td>€9.95 · free from €{BRAND['free_shipping_from']}</td></tr><tr><th>Rest of EU</th><td>€14.95 · free from €250</td></tr><tr><th>Roof hatches (oversize)</th><td>€29 flat, pallet shipping quoted for 3+ hatches</td></tr><tr><th>UK, CH, NO and non-EU</th><td>Quoted at checkout</td></tr></table>
<h3 class="h3">Returns &amp; warranty</h3><p class="lead" style="margin:10px 0 22px">Unused products in original packaging can be returned within 30 days for a full refund. Products that have been installed or cut to size cannot be returned unless defective. All products carry a 2-year manufacturer warranty against defects in materials and workmanship. Electric motors are EMC approved and tested before dispatch.</p>
<p class="note">Trade customers: returns and warranty claims are handled through your account contact. Keep the article number and the batch label from the box.</p></div></section>'''
    return simple_page('shipping-returns.html', 'Shipping & returns', 'Same-day dispatch before 15:00 CET, free EU shipping from €150, 30-day returns and 2-year warranty.', body)

def page_terms():
    body = '''<section class="section ivory"><div class="wrap" style="max-width:860px"><div class="eyebrow">Terms &amp; warranty</div><h1 class="h1" style="margin:12px 0 24px">Terms of sale</h1>
<p class="lead" style="margin-bottom:18px">These terms apply to all orders placed on pegasusdepot.com. By placing an order you agree to them.</p>
<h3 class="h3">Prices and payment</h3><p class="lead" style="margin:8px 0 18px">All prices are in euro and include 21% Dutch VAT unless stated otherwise. Trade accounts are invoiced ex-VAT where a valid EU VAT number is provided. Payment by iDEAL, credit card, PayPal, Bancontact or SEPA transfer; approved trade accounts may pay on 30-day terms.</p>
<h3 class="h3">Delivery</h3><p class="lead" style="margin:8px 0 18px">Delivery times are estimates. Risk passes to you on delivery. Check the parcel on receipt and report transport damage within 48 hours.</p>
<h3 class="h3">Warranty</h3><p class="lead" style="margin:8px 0 18px">Two years against defects in materials and workmanship from the date of delivery. Excluded: wear, incorrect installation, incorrect voltage, mechanical damage and modifications. Warranty is repair or replacement at our discretion.</p>
<h3 class="h3">Specifications</h3><p class="lead" style="margin:8px 0 18px">Technical data is taken from the manufacturer's datasheets and may be updated without notice. Always check the current drawing before cutting a roof.</p>
<h3 class="h3">Governing law</h3><p class="lead" style="margin:8px 0 18px">Dutch law applies. Disputes are submitted to the competent court in the Netherlands.</p></div></section>'''
    return simple_page('terms.html', 'Terms & warranty', 'Terms of sale and warranty conditions of Pegasus Depot.', body)

def page_privacy():
    body = '''<section class="section ivory"><div class="wrap" style="max-width:860px"><div class="eyebrow">Privacy</div><h1 class="h1" style="margin:12px 0 24px">Privacy policy</h1>
<p class="lead" style="margin-bottom:18px">We only collect the data needed to process your order, answer your questions and, if you opt in, send you occasional product updates. We never sell your data.</p>
<h3 class="h3">What we store</h3><p class="lead" style="margin:8px 0 18px">Name, company, address, email, phone, order history and, for trade accounts, VAT number. Payment details are processed by our payment provider and never stored on our servers.</p>
<h3 class="h3">Cookies</h3><p class="lead" style="margin:8px 0 18px">Your cart is stored in your browser's local storage. We use privacy-friendly analytics without cross-site tracking.</p>
<h3 class="h3">Your rights</h3><p class="lead" style="margin:8px 0 18px">You can request, correct or delete your data at any time by emailing hello@pegasusdepot.com.</p></div></section>'''
    return simple_page('privacy.html', 'Privacy', 'Privacy policy of Pegasus Depot.', body)

def page_checkout():
    body = f'''
<section class="section ivory"><div class="wrap checkout"><div><div class="eyebrow">Checkout</div><h1 class="h1" style="margin:12px 0 8px">Almost there.</h1><p class="muted" style="margin-bottom:26px">Secure checkout · iDEAL, cards, PayPal, Bancontact · Invoice for approved trade accounts</p>
<form class="form" id="checkout-form"><h3 class="h4">Contact</h3><div class="form-row"><div class="field"><label>Email</label><input type="email" required></div><div class="field"><label>Phone</label><input></div></div>
<h3 class="h4" style="margin-top:10px">Delivery address</h3><div class="form-row"><div class="field"><label>First name</label><input required></div><div class="field"><label>Last name</label><input required></div></div><div class="field"><label>Company (optional)</label><input></div><div class="field"><label>Address</label><input required></div><div class="form-row"><div class="field"><label>Postcode</label><input required></div><div class="field"><label>City</label><input required></div></div><div class="field"><label>Country</label><select><option>Netherlands</option><option>Belgium</option><option>Germany</option><option>France</option><option>Austria</option><option>Denmark</option><option>Luxembourg</option><option>Italy</option><option>Spain</option><option>Sweden</option><option>Ireland</option><option>Poland</option><option>Other EU</option><option>United Kingdom</option><option>Switzerland</option><option>Norway</option></select></div>
<h3 class="h4" style="margin-top:10px">Business details (optional)</h3><div class="field"><label>EU VAT number for ex-VAT invoicing</label><input placeholder="NL123456789B01"></div>
<h3 class="h4" style="margin-top:10px">Payment</h3><div class="pill-row"><span class="pill">iDEAL</span><span class="pill">Visa / Mastercard</span><span class="pill">PayPal</span><span class="pill">Bancontact</span><span class="pill">SEPA transfer</span><span class="pill">Invoice (trade)</span></div>
<button class="btn btn-gold btn-lg btn-block" style="margin-top:18px">Place order {ICON['arrow']}</button><p class="note">Prototype checkout: no payment is taken. The live store will hand over to Shopify Checkout with the same cart.</p></form></div>
<aside class="summary"><h3 class="h4" style="margin-bottom:14px">Order summary</h3><div id="co-lines"></div><div class="hr" style="margin:16px 0"></div><div class="row" style="display:flex;justify-content:space-between"><span>Subtotal</span><b id="co-sub">€0</b></div><div class="row" style="display:flex;justify-content:space-between;margin-top:6px"><span>Shipping</span><b id="co-ship">–</b></div><div class="row" style="display:flex;justify-content:space-between;margin-top:12px;font-size:20px"><span>Total incl. VAT</span><b id="co-total">€0</b></div><p class="muted" style="font-size:12.5px;margin-top:14px">Ships within 24h · 30-day returns · 2-year warranty</p></aside></div></section>'''
    return simple_page('checkout.html', 'Checkout', 'Secure checkout.', body)

def page_thanks():
    body = f'''<section class="section ivory"><div class="wrap center" style="max-width:680px"><div class="eyebrow">Order received</div><h1 class="h1" style="margin:12px 0 14px">Thank you.</h1><p class="lead" style="margin:0 auto 10px">Your order <b id="order-id"></b> is being prepared in our Dutch warehouse. You will receive a confirmation email and a tracking link as soon as the parcel leaves our warehouse.</p><p class="muted">Questions? {esc(BRAND['email'])} · {esc(BRAND['phone'])}</p><div class="hero-cta" style="justify-content:center"><a class="btn btn-dark" href="shop.html">Continue shopping</a></div></div></section>'''
    return simple_page('thank-you.html', 'Thank you', 'Order confirmation.', body)

def page_404():
    body = f'''<section class="section ivory"><div class="wrap center" style="max-width:680px"><div class="eyebrow">404</div><h1 class="h1" style="margin:12px 0 14px">That page drove off.</h1><p class="lead" style="margin:0 auto 24px">The page you are looking for does not exist or has moved. Try the shop or search for an article number.</p><div class="hero-cta" style="justify-content:center"><a class="btn btn-gold" href="shop.html">Go to the shop</a><a class="btn btn-ghost" href="index.html">Home</a></div></div></section>'''
    return simple_page('404.html', 'Page not found', 'Page not found.', body)

# ---------------------------------------------------------------- catalog.js + csv + sitemap
def write_catalog_js():
    slim = {
        'brand': BRAND,
        'products': [{**{k: p[k] for k in ['id', 'name', 'short_name', 'category', 'tagline', 'summary', 'variants']}, 'images': [sq(i, 400) for i in p['images'][:1]], 'quote_only': p.get('quote_only', False)} for p in PRODUCTS],
        'bundles': [{**{k: b[k] for k in ['id', 'name', 'tagline', 'summary', 'discount', 'items']}, 'images': [sq(b['images'][0], 400)]} for b in BUNDLES],
    }
    (ROOT / 'assets/js/catalog.js').write_text('window.CATALOG=' + json.dumps(slim, ensure_ascii=False) + ';')

def write_shopify_csv():
    cols = ['Handle', 'Title', 'Body (HTML)', 'Vendor', 'Product Category', 'Type', 'Tags', 'Published', 'Option1 Name', 'Option1 Value', 'Option2 Name', 'Option2 Value', 'Option3 Name', 'Option3 Value', 'Variant SKU', 'Variant Grams', 'Variant Inventory Tracker', 'Variant Inventory Qty', 'Variant Inventory Policy', 'Variant Fulfillment Service', 'Variant Price', 'Variant Compare At Price', 'Variant Requires Shipping', 'Variant Taxable', 'Variant Barcode', 'Image Src', 'Image Position', 'Image Alt Text', 'Gift Card', 'SEO Title', 'SEO Description', 'Variant Weight Unit', 'Status']
    rows = []
    for p in PRODUCTS:
        body = ''.join(f'<p>{H.escape(x)}</p>' for x in p['description']) + '<h3>Key features</h3><ul>' + ''.join(f'<li>{H.escape(f)}</li>' for f in p['features']) + '</ul><h3>Specifications</h3><table>' + ''.join(f'<tr><th>{H.escape(k)}</th><td>{H.escape(v)}</td></tr>' for k, v in (p.get('specs') or {}).items()) + '</table>'
        opt_names = list((p['variants'][0].get('options') or {}).keys())[:3]
        tags = ','.join([CAT[p['category']]['name']] + [VEH[a]['name'] for a in p.get('applications', []) if a in VEH] + p.get('badges', []))
        imgs = [sq(i, 1400) if not is_scene(i) else scene(i, 1400) for i in p['images']]
        for i, v in enumerate(p['variants']):
            row = {c: '' for c in cols}
            if i == 0:
                row.update({'Title': p['name'], 'Body (HTML)': body, 'Vendor': 'Pegasus Depot', 'Type': CAT[p['category']]['name'], 'Tags': tags, 'Published': 'TRUE', 'SEO Title': f'{p["name"]} · {p["tagline"]}', 'SEO Description': p['summary'][:320], 'Status': 'active'})
            row['Handle'] = p['id']
            for n, on in enumerate(opt_names):
                row[f'Option{n+1} Name'] = on if i == 0 else ''
                row[f'Option{n+1} Value'] = v['options'].get(on, '')
            if not opt_names:
                row['Option1 Name'] = 'Title' if i == 0 else ''; row['Option1 Value'] = 'Default Title'
            row.update({'Variant SKU': v['sku'], 'Variant Inventory Tracker': 'shopify', 'Variant Inventory Qty': '25', 'Variant Inventory Policy': 'continue', 'Variant Fulfillment Service': 'manual', 'Variant Price': v['price'] if v.get('price') is not None else '', 'Variant Compare At Price': v.get('compare_at') or '', 'Variant Requires Shipping': 'TRUE', 'Variant Taxable': 'TRUE', 'Variant Weight Unit': 'kg'})
            if i < len(imgs):
                row['Image Src'] = f'{SITE_URL}/{imgs[i]}'; row['Image Position'] = i + 1; row['Image Alt Text'] = p['name']
            rows.append(row)
        for j in range(len(p['variants']), len(imgs)):
            row = {c: '' for c in cols}; row['Handle'] = p['id']; row['Image Src'] = f'{SITE_URL}/{imgs[j]}'; row['Image Position'] = j + 1; row['Image Alt Text'] = p['name']; rows.append(row)
    with open(ROOT / 'shopify-products.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    with open(ROOT / 'shopify-bundles.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['Bundle handle', 'Bundle title', 'Discount', 'Component product', 'Component SKU options', 'Qty', 'Bundle price (default options)', 'Compare at'])
        for b in BUNDLES:
            full, price = bundle_calc(b)
            for it in b['items']:
                w.writerow([b['id'], b['name'], f'{int(b["discount"]*100)}%', P[it['product']]['name'], it.get('sku') or ' | '.join(it['choices']), it['qty'], price, full])

def write_sitemap(urls):
    (ROOT / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(f'  <url><loc>{SITE_URL}/{u}</loc></url>\n' for u in urls) + '</urlset>\n')
    (ROOT / 'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n')
    (ROOT / 'CNAME').write_text(BRAND['domain'] + '\n')

# ---------------------------------------------------------------- main
def main():
    shutil.copy(ROOT / 'src/site.css', ROOT / 'assets/css/site.css')
    shutil.copy(ROOT / 'src/site.js', ROOT / 'assets/js/site.js')
    og = scene(P['le-mans']['images'][2], 1200)
    shutil.copy(ROOT / og, IMG_OUT / 'og-default.webp')
    urls = []
    def w(path, html):
        (ROOT / path).write_text(html, encoding='utf-8'); urls.append(path)
    w('index.html', page_index())
    w('shop.html', page_shop())
    w('bundles.html', page_bundles())
    for p in PRODUCTS: w(f'products/{p["id"]}.html', page_product(p))
    for b in BUNDLES: w(f'bundles/{b["id"]}.html', page_bundle(b))
    for v in VEHICLES: w(f'vehicles/{v["id"]}.html', page_vehicle(v))
    w('about.html', page_about()); w('trade.html', page_trade()); w('contact.html', page_contact())
    w('shipping-returns.html', page_shipping()); w('terms.html', page_terms()); w('privacy.html', page_privacy())
    w('checkout.html', page_checkout()); w('thank-you.html', page_thanks()); (ROOT / '404.html').write_text(page_404(), encoding='utf-8')
    write_catalog_js(); write_shopify_csv(); write_sitemap([u for u in urls if u not in ('checkout.html', 'thank-you.html')])
    print(f'Built {len(urls)} pages, {len(PRODUCTS)} products, {len(BUNDLES)} bundles, {len(VEHICLES)} vehicle pages.')

if __name__ == '__main__':
    main()
