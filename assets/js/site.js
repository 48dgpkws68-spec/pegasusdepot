/* Pegasus Depot · storefront logic (static prototype, Shopify-ready data model) */
(function () {
  if (location.search.includes('capture')) document.documentElement.classList.add('capture');
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  /* reveal on scroll (works without catalog) */
  const io = 'IntersectionObserver' in window ? new IntersectionObserver((es) => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }), { threshold: .08 }) : null;
  $$('.reveal').forEach(el => io ? io.observe(el) : el.classList.add('in'));
  /* header: mega menu (hover + keyboard), mobile nav */
  $$('.nav > li').forEach(li => {
    let t; li.addEventListener('mouseenter', () => { clearTimeout(t); $$('.nav > li').forEach(x => x.classList.remove('open')); li.classList.add('open'); });
    li.addEventListener('mouseleave', () => { t = setTimeout(() => li.classList.remove('open'), 120); });
    li.addEventListener('focusin', () => { $$('.nav > li').forEach(x => x.classList.remove('open')); li.classList.add('open'); });
    li.addEventListener('focusout', (e) => { if (!li.contains(e.relatedTarget)) li.classList.remove('open'); });
  });
  $('#burger')?.addEventListener('click', () => $('#mnav').classList.add('open'));
  $('#mnav-close')?.addEventListener('click', () => $('#mnav').classList.remove('open'));
  const C = window.CATALOG;
  if (!C) return;
  const ROOT = document.documentElement.getAttribute('data-root') || '';
  const money = (n) => '€' + (Math.round(n * 100) / 100).toLocaleString('en-IE', { minimumFractionDigits: n % 1 ? 2 : 0, maximumFractionDigits: 2 });
  const byId = {}; C.products.forEach(p => byId[p.id] = p);
  const bySku = {}; C.products.forEach(p => p.variants.forEach(v => bySku[v.sku] = { p, v }));
  const bundleById = {}; (C.bundles || []).forEach(b => bundleById[b.id] = b);

  /* ---------- cart ---------- */
  const KEY = 'pegasus_cart_v1';
  let cart = [];
  try { const c = JSON.parse(localStorage.getItem(KEY) || '[]'); cart = Array.isArray(c) ? c.filter(l => l && Number.isFinite(+l.price) && Number.isInteger(+l.qty) && +l.qty > 0) : []; } catch (e) { cart = []; }
  const save = () => { localStorage.setItem(KEY, JSON.stringify(cart)); renderCart(); };
  const lineKey = (l) => l.type + ':' + l.id + ':' + (l.skus || []).join('+');
  function addLine(line) {
    const k = lineKey(line);
    const ex = cart.find(l => lineKey(l) === k);
    if (ex) ex.qty += line.qty; else cart.push(line);
    save(); openCart(); toast('Added to your cart');
  }
  function setQty(i, q) { if (q <= 0) cart.splice(i, 1); else cart[i].qty = q; save(); }
  const subtotal = () => cart.reduce((s, l) => s + l.price * l.qty, 0);
  const SHIP = C.brand.shipping || { zones: [], oversize_categories: [], oversize_price: 0 };
  const ISO = { 'Netherlands': 'NL', 'Belgium': 'BE', 'Germany': 'DE', 'France': 'FR', 'Luxembourg': 'LU', 'Austria': 'AT', 'Denmark': 'DK', 'United Kingdom': 'UK', 'Switzerland': 'CH', 'Norway': 'NO' };
  function shipping(st, country) {
    const zone = SHIP.zones.find(z => z.countries.includes(country)) || SHIP.zones.find(z => z.id === 'eu') || { price: 0, free_from: 0 };
    const short = ISO[country] || 'EU';
    if (zone.price == null) return { price: 0, quote: true, short };
    let base = (zone.free_from != null && st >= zone.free_from) || st === 0 ? 0 : zone.price;
    const hatches = cart.reduce((n, l) => n + ((l.type === 'product' && (byId[l.id] || {}).category && SHIP.oversize_categories.includes(byId[l.id].category)) ? l.qty : 0) + ((l.type === 'bundle' && (bundleById[l.id] || { items: [] }).items.some(it => SHIP.oversize_categories.includes((byId[it.product] || {}).category))) ? l.qty * (bundleById[l.id].items.filter(it => SHIP.oversize_categories.includes((byId[it.product] || {}).category)).reduce((a, it) => a + it.qty, 0)) : 0), 0);
    return { price: base + (hatches ? SHIP.oversize_price : 0), quote: false, short, hatches };
  }
  const count = () => cart.reduce((s, l) => s + l.qty, 0);

  function renderCart() {
    $$('.cart-count').forEach(el => el.textContent = count() || '');
    const body = $('#cart-body'); if (!body) return;
    if (!cart.length) {
      let restore = '';
      try { const h = JSON.parse(localStorage.getItem('pegasus_handoff') || 'null'); if (h && h.lines && h.lines.length && Date.now() - h.t < 2 * 3600 * 1000) restore = '<br><br><button class="btn btn-sm" data-restore>Restore previous cart</button>'; } catch (e) {}
      body.innerHTML = '<div class="empty"><b>Your cart is empty</b>Add a rooftop ventilator, a kit or an accessory to get started.<br><br><a class="btn btn-dark btn-sm" href="' + ROOT + 'shop.html">Browse the shop</a>' + restore + '</div>';
    } else {
      body.innerHTML = cart.map((l, i) => `
        <div class="ci">
          <img src="${ROOT + l.image}" alt="">
          <div><b>${l.title}</b><span>${l.sub || ''}</span>
            <div class="ci-qty"><button data-q="${i}:-1" aria-label="Decrease">−</button><i>${l.qty}</i><button data-q="${i}:1" aria-label="Increase">+</button></div>
          </div>
          <div class="ci-price">${money(l.price * l.qty)}<br><a class="rm" data-rm="${i}" href="#">Remove</a></div>
        </div>`).join('');
    }
    const st = subtotal();
    const free = C.brand.free_shipping_from;
    const country = localStorage.getItem('pegasus_country') || 'Netherlands';
    const sh = shipping(st, country);
    const ship = sh.price || 0;
    $('#cart-sub').textContent = money(st);
    const lbl = $('#cart-ship-lbl'); if (lbl) lbl.textContent = 'Shipping (' + sh.short + ')';
    $('#cart-ship').textContent = st === 0 ? '–' : sh.quote ? 'Quoted' : (ship ? money(ship) : 'Free');
    $('#cart-total').textContent = money(st + ship);
    const bar = $('#ship-bar'); const txt = $('#ship-txt');
    if (bar) { bar.style.width = Math.min(100, st / free * 100) + '%'; }
    if (txt) { txt.innerHTML = sh.quote ? 'Shipping to the UK, Switzerland and Norway is quoted before you order.' : st >= free ? (sh.hatches ? '<b>Free EU shipping unlocked.</b> Orders with roof hatches carry a flat €' + SHIP.oversize_price + ' oversize fee.' : '<b>You have unlocked free EU shipping.</b>') : 'Add <b>' + money(free - st) + '</b> for free EU shipping' + (sh.hatches ? ' (plus a flat €' + SHIP.oversize_price + ' oversize fee for roof hatches)' : ''); }
    if (bar) bar.parentElement.style.display = sh.quote ? 'none' : '';
    const dn = $('#drawer-note'); if (dn) dn.textContent = 'Shipping calculated for ' + country + '; change your country at checkout.';
    const co = $('#checkout-btn'); if (co) co.classList.toggle('disabled', !cart.length);
    body.onclick = (e) => {
      const q = e.target.closest('[data-q]'); if (q) { const [i, d] = q.dataset.q.split(':').map(Number); setQty(i, cart[i].qty + d); }
      const r = e.target.closest('[data-rm]'); if (r) { e.preventDefault(); setQty(+r.dataset.rm, 0); }
      if (e.target.closest('[data-restore]')) { try { const h = JSON.parse(localStorage.getItem('pegasus_handoff') || 'null'); if (h && h.lines) { cart = h.lines; localStorage.removeItem('pegasus_handoff'); save(); toast('Cart restored'); } } catch (x) {} }
    };
    // checkout page summary
    const sum = $('#co-lines');
    if (sum) {
      sum.innerHTML = cart.length ? cart.map(l => `<div class="row"><span>${l.qty} × ${l.title}<br><small class="muted">${l.sub || ''}</small></span><b>${money(l.price * l.qty)}</b></div>`).join('') : '<p class="muted">Your cart is empty.</p>';
      $('#co-sub').textContent = money(st); $('#co-ship').textContent = sh.quote ? 'Quote via contact page' : (ship ? money(ship) + (sh.hatches ? ' (incl. hatch oversize)' : '') : 'Free'); $('#co-total').textContent = money(st + ship);
      const cbl = $('#co-btn-lbl'); if (cbl) cbl.textContent = sh.quote ? 'Request shipping quote' : (sh.hatches >= 3 ? 'Request pallet quote' : 'Continue to secure checkout');
      const cob = $('#co-btn'); if (cob) cob.classList.toggle('disabled', !cart.length);
      if (!cart.length) $('#co-ship').textContent = '–';
    }
  }
  const openCart = () => { $('#drawer')?.classList.add('open'); $('#overlay')?.classList.add('open'); document.body.style.overflow = 'hidden'; };
  const closeCart = () => { $('#drawer')?.classList.remove('open'); $('#overlay')?.classList.remove('open'); document.body.style.overflow = ''; };
  $$('[data-open-cart]').forEach(b => b.addEventListener('click', (e) => { e.preventDefault(); openCart(); }));
  $$('[data-close-cart]').forEach(b => b.addEventListener('click', closeCart));
  $('#overlay')?.addEventListener('click', () => { closeCart(); closeSearch(); });
  let toastT; function toast(msg) { const t = $('#toast'); if (!t) return; t.querySelector('span').textContent = msg; t.classList.add('on'); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('on'), 2600); }

  // quick add from cards
  document.addEventListener('click', (e) => {
    const a = e.target.closest('[data-add-sku]'); if (!a) return;
    e.preventDefault();
    const { p, v } = bySku[a.dataset.addSku] || {};
    if (!p || v.price == null) { location.href = ROOT + 'products/' + a.dataset.product + '.html'; return; }
    addLine({ type: 'product', id: p.id, skus: [v.sku], title: p.name, sub: v.label + ' · ' + v.sku, price: v.price, qty: 1, image: p.images[0] });
  });

  /* ---------- search ---------- */
  const openSearch = () => { $('#search').classList.add('open'); setTimeout(() => $('#search-input')?.focus(), 50); };
  const closeSearch = () => $('#search')?.classList.remove('open');
  $$('[data-open-search]').forEach(b => b.addEventListener('click', (e) => { e.preventDefault(); openSearch(); }));
  $('#search-close')?.addEventListener('click', closeSearch);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { closeSearch(); closeCart(); $('#mnav')?.classList.remove('open'); } });
  const si = $('#search-input');
  if (si) {
    const res = $('#search-res');
    const norm = (t) => t.toLowerCase().replace(/[\s-]+/g, '');
    const idx = C.products.map(p => ({ p, txt: (p.name + ' ' + p.tagline + ' ' + p.summary + ' ' + p.variants.map(v => v.sku).join(' ') + ' ' + p.category).toLowerCase(), n: norm(p.name + ' ' + p.variants.map(v => v.sku).join(' ')) }))
      .concat((C.bundles || []).map(b => ({ b, txt: (b.name + ' kit bundle ' + b.tagline + ' ' + b.summary).toLowerCase(), n: norm(b.name + ' kit') })));
    si.addEventListener('input', () => {
      const q = si.value.trim().toLowerCase();
      if (!q) { res.innerHTML = ''; return; }
      const all = idx.filter(x => q.split(/\s+/).every(w => x.txt.includes(w)) || x.n.includes(norm(q)));
      const hits = all.slice(0, 8);
      res.innerHTML = hits.map(x => x.p
        ? `<a href="${ROOT}products/${x.p.id}.html"><img src="${ROOT + x.p.images[0]}" alt=""><div><b>${x.p.name}</b><span>${x.p.tagline}</span></div></a>`
        : `<a href="${ROOT}bundles/${x.b.id}.html"><img src="${ROOT + x.b.images[0]}" alt=""><div><b>${x.b.name} <em class="gold">· Kit</em></b><span>${x.b.tagline}</span></div></a>`).join('') + (all.length > 8 ? `<a class="search-more" href="${ROOT}shop.html?q=${encodeURIComponent(si.value.trim())}">See all ${all.length} results</a>` : '') || '<p class="muted">No results. Try "Le Mans", "12V", "hatch" or an article number.</p>';
    });
  }

  /* ---------- PDP ---------- */
  const pdp = $('[data-pdp]');
  if (pdp) {
    const p = byId[pdp.dataset.pdp];
    const optNames = Object.keys(p.variants[0].options || {});
    let sel = { ...p.variants[0].options };
    const cur = () => p.variants.find(v => optNames.every(k => v.options[k] === sel[k])) || p.variants.find(v => v.options[optNames[0]] === sel[optNames[0]]) || p.variants[0];
    function renderOpts() {
      optNames.forEach(k => {
        const box = $(`[data-opt="${k}"]`); if (!box) return;
        const vals = [...new Set(p.variants.map(v => v.options[k]))];
        box.innerHTML = vals.map(val => {
          const avail = p.variants.some(v => v.options[k] === val && optNames.every(o => o === k || v.options[o] === sel[o]));
          const sw = /colour/i.test(k) ? `<i class="sw" style="background:${swatch(val)}"></i>` : '';
          return `<button class="opt ${sel[k] === val ? 'on' : ''} ${avail ? '' : 'dim'}" data-k="${k}" data-v="${val}" ${avail ? '' : 'title="Not available with the current selection; selecting it switches the other option"'}>${sw}${val}</button>`;
        }).join('');
        const lbl = $(`[data-opt-label="${k}"]`); if (lbl) lbl.textContent = sel[k];
      });
      const v = cur();
      $('#pdp-sku').textContent = 'Article no. ' + v.sku;
      $('#pdp-price').textContent = v.price == null ? 'Quote' : money(v.price);
      const was = $('#pdp-was'); if (was) { was.textContent = v.compare_at ? 'RRP ' + money(v.compare_at) : ''; was.style.display = v.compare_at ? '' : 'none'; }
      const sv = $('#pdp-save'); if (sv) { if (v.compare_at && v.price) { sv.textContent = Math.round((1 - v.price / v.compare_at) * 100) + '% below RRP'; sv.style.display = ''; } else sv.style.display = 'none'; }
      const sp = $('#sticky-price'); if (sp) sp.textContent = v.price == null ? 'Quote' : money(v.price);
      // gallery follows the chosen option when the product maps options to images
      try { const map = JSON.parse(pdp.dataset.imgmap || '{}'); const hit = Object.keys(map).find(k => Object.values(sel).includes(k)); if (hit != null) { const th = $$('.thumbs button')[map[hit]]; if (th && !th.classList.contains('on')) th.click(); } } catch (e) {}
      updateAddons();
    }
    function swatch(val) {
      const m = { 'white': '#FFFFFF', 'black': '#111', 'grey': '#9A9A9A', 'light grey': '#CFCFCF', 'dark grey': '#55585C', 'light grey / dark grey': 'linear-gradient(90deg,#CFCFCF 50%,#55585C 50%)' };
      return m[val.toLowerCase()] || '#ddd';
    }
    pdp.addEventListener('click', (e) => {
      const b = e.target.closest('.opt[data-k]'); if (!b) return;
      sel[b.dataset.k] = b.dataset.v;
      // realign other options to a valid variant
      if (!p.variants.some(v => optNames.every(k => v.options[k] === sel[k]))) {
        const v = p.variants.find(v => v.options[b.dataset.k] === b.dataset.v); sel = { ...v.options };
      }
      renderOpts();
    });
    const qtyI = $('#qty');
    const getQ = () => { const q = Math.max(1, parseInt(qtyI?.value, 10) || 1); if (qtyI) qtyI.value = q; return q; };
    $('#qty-minus')?.addEventListener('click', () => { qtyI.value = Math.max(1, getQ() - 1); updateAddons(); });
    $('#qty-plus')?.addEventListener('click', () => { qtyI.value = getQ() + 1; updateAddons(); });
    qtyI?.addEventListener('change', () => { getQ(); updateAddons(); });
    function addonVariant(i) {
      const ap = byId[i.dataset.product]; if (!ap) return bySku[i.dataset.sku];
      // an explicit choice in the add-on picker wins; otherwise follow the colour / voltage of the main product
      const pick = i.parentElement.querySelector('.addon-var');
      if (pick && pick.dataset.user === '1' && bySku[pick.value]) return bySku[pick.value];
      const want = cur().options || {};
      const match = ap.variants.find(v => v.price != null && Object.keys(v.options || {}).every(k => !want[k] || v.options[k] === want[k]) && Object.keys(want).some(k => v.options && v.options[k] === want[k]));
      return match ? { p: ap, v: match } : bySku[i.dataset.sku];
    }
    // picture of a specific variant when the product maps options to images, else the main photo
    function imgFor(ap, v) { const map = ap.image_by_option || {}; const hit = Object.values(v.options || {}).find(x => map[x] != null); return hit != null && ap.images[map[hit]] ? ap.images[map[hit]] : (ap.images[0] || ''); }
    function renderPick(row, ap, v) {
      const tiles = row.querySelector('.addon-tiles'); const vars = row.querySelector('.addon-vars'); if (!tiles || !vars) return;
      $$('.tile', tiles).forEach(t => t.classList.toggle('on', t.dataset.pid === ap.id));
      const priced = ap.variants.filter(x => x.price != null);
      const key = ap.id + '|' + v.sku; if (vars.dataset.key === key) return; vars.dataset.key = key;
      vars.innerHTML = priced.length > 1 ? priced.map(x => { const col = (x.options || {}).Colour; const map = ap.image_by_option || {}; const hasImg = Object.values(x.options || {}).some(o => map[o] != null); return `<button type="button" class="opt vchip${x.sku === v.sku ? ' on' : ''}" data-sku="${x.sku}">${hasImg ? `<img src="${ROOT + imgFor(ap, x)}" alt="">` : col ? `<i class="sw" style="background:${swatch(col)}"></i>` : ''}${x.label} <small>${money(x.price)}</small></button>`; }).join('') : '';
    }
    function syncAddonRow(i) {
      const { p: ap, v } = addonVariant(i); const row = i.parentElement;
      const pick = row.querySelector('.addon-var'); if (pick && pick.value !== v.sku) pick.value = v.sku;
      const grp = row.classList.contains('addon-group');
      const ttl = row.querySelector('.addon-title'); if (ttl && !grp && ttl.textContent !== ap.short_name) ttl.textContent = ap.short_name;
      const im = row.querySelector('.addon-main img'); const want = imgFor(ap, v); if (im && want && im.dataset.src !== want) { im.src = ROOT + want; im.dataset.src = want; im.dataset.pid = ap.id; }
      const sub = row.querySelector('.addon-sub'); if (sub) sub.textContent = (grp ? ap.short_name + (v.label !== ap.short_name ? ' · ' + v.label : '') : v.label) + ' · ' + v.sku;
      const pr = row.querySelector('.p'); if (pr) pr.textContent = '+ ' + money(v.price);
      renderPick(row, ap, v);
    }
    function updateAddons() {
      const v = cur(); const q = qtyI ? getQ() : 1; let total = (v.price || 0);
      $$('.addon input').forEach(syncAddonRow);
      $$('.addon input:checked').forEach(i => total += +(addonVariant(i).v.price));
      const t = $('#addon-total'); if (t) t.textContent = money(total * q) + (q > 1 ? ' for ' + q + ' sets' : '');
      // same parts cheaper as a kit? compare the chosen set with every kit's item list
      const hint = $('#addon-kit-hint');
      if (hint) {
        const chosen = [v.sku].concat($$('.addon input:checked').map(i => addonVariant(i).v.sku)).sort().join('|');
        const kit = (C.bundles || []).find(b => b.items.length === chosen.split('|').length && b.items.every(it => it.qty === 1) && b.items.map(it => it.sku || (it.choices.find(s => chosen.split('|').includes(s)) || it.choices[0])).sort().join('|') === chosen);
        if (kit) { const full = kit.items.reduce((s, it) => s + bySku[it.sku || (it.choices.find(x => chosen.split('|').includes(x)) || it.choices[0])].v.price, 0); const kp = Math.floor(full * (1 - kit.discount)); hint.innerHTML = 'Same parts cheaper as a kit: <a href="' + ROOT + 'bundles/' + kit.id + '.html">' + kit.name + '</a> for <b>' + money(kp) + '</b> instead of ' + money(full) + '.'; hint.style.display = ''; }
        else hint.style.display = 'none';
      }
    }
    $$('.addon input').forEach(i => i.addEventListener('change', updateAddons));
    const chooseAddon = (row, sku) => { const s = row.querySelector('.addon-var'); const hit = bySku[sku]; if (!s || !hit) return; s.value = sku; s.dataset.user = '1'; const i = row.querySelector('input'); i.dataset.sku = hit.v.sku; i.dataset.product = hit.p.id; i.checked = true; updateAddons(); };
    $$('.addon-var').forEach(s => s.addEventListener('change', () => chooseAddon(s.parentElement, s.value)));
    $$('.addon').forEach(row => row.addEventListener('click', (e) => {
      const t = e.target.closest('.tile'); if (t) { const tp = byId[t.dataset.pid]; const first = tp && tp.variants.find(x => x.price != null); if (first) chooseAddon(row, first.sku); return; }
      const ch = e.target.closest('.vchip'); if (ch) chooseAddon(row, ch.dataset.sku);
    }));
    const add = () => {
      const v = cur(); if (v.price == null) return;
      const q = getQ();
      addLine({ type: 'product', id: p.id, skus: [v.sku], title: p.name, sub: v.label + ' · ' + v.sku, price: v.price, qty: q, image: p.images[0] });
      $$('.addon input:checked').forEach(i => { const { p: ap, v: av } = addonVariant(i); const aq = ap.id === 'control-unit' && p.category === 'roof-hatches' ? Math.ceil(q / 2) : q; addLine({ type: 'product', id: ap.id, skus: [av.sku], title: ap.name, sub: av.label + ' · ' + av.sku, price: av.price, qty: aq, image: imgFor(ap, av) }); i.checked = false; });
      updateAddons();
    };
    $('#add-btn')?.addEventListener('click', add);
    $('#sticky-add')?.addEventListener('click', add);
    // gallery
    $$('.thumbs button').forEach(b => b.addEventListener('click', () => {
      $$('.thumbs button').forEach(x => x.classList.remove('on')); b.classList.add('on');
      const img = $('#gallery-img'); img.src = b.dataset.src; img.className = b.dataset.scene ? 'scene' : '';
    }));
    // tabs
    $$('.tab-nav button').forEach(b => b.addEventListener('click', () => {
      $$('.tab-nav button').forEach(x => x.classList.remove('on')); b.classList.add('on');
      $$('.tab-panel').forEach(x => x.classList.toggle('on', x.id === b.dataset.tab));
    }));
    renderOpts();
    document.body.classList.add('has-sticky');
  }

  /* ---------- Bundle builder ---------- */
  const bb = $('[data-bundle]');
  if (bb) {
    const b = bundleById[bb.dataset.bundle];
    const choice = b.items.map(it => it.sku || it.choices[0]);
    function calc() {
      let full = 0;
      b.items.forEach((it, i) => { const { v } = bySku[choice[i]]; full += v.price * it.qty; });
      const price = Math.floor(full * (1 - b.discount));
      return { full, price };
    }
    function render() {
      b.items.forEach((it, i) => {
        const { p, v } = bySku[choice[i]];
        const row = $(`[data-bitem="${i}"]`);
        row.querySelector('.b-price').innerHTML = money(v.price * it.qty) + `<small>${it.qty > 1 ? it.qty + ' × ' : ''}${v.sku}</small>`;
        const opts = row.querySelector('.b-opts');
        if (opts) opts.innerHTML = it.choices.map(s => `<button class="opt ${s === choice[i] ? 'on' : ''}" data-i="${i}" data-sku="${s}">${bySku[s].v.label}</button>`).join('');
      });
      const { full, price } = calc();
      $('#b-full').textContent = money(full); $('#b-price').textContent = money(price); $('#b-save').textContent = 'You save ' + money(full - price) + ' (' + Math.round(b.discount * 100) + '%)';
      const sp = $('#sticky-price'); if (sp) sp.textContent = money(price);
    }
    bb.addEventListener('click', (e) => { const o = e.target.closest('.opt[data-i]'); if (!o) return; choice[+o.dataset.i] = o.dataset.sku; render(); });
    const add = () => {
      const { price } = calc();
      const sub = b.items.map((it, i) => (it.qty > 1 ? it.qty + '× ' : '') + bySku[choice[i]].p.short_name + (bySku[choice[i]].v.label && bySku[choice[i]].v.label !== bySku[choice[i]].p.short_name ? ' (' + bySku[choice[i]].v.label + ')' : '')).join(' + ');
      addLine({ type: 'bundle', id: b.id, skus: choice.slice(), title: b.name, sub, price, qty: 1, image: b.images[0] });
    };
    $('#add-btn')?.addEventListener('click', add);
    $('#sticky-add')?.addEventListener('click', add);
    $$('.tab-nav button').forEach(bt => bt.addEventListener('click', () => {
      $$('.tab-nav button').forEach(x => x.classList.remove('on')); bt.classList.add('on');
      $$('.tab-panel').forEach(x => x.classList.toggle('on', x.id === bt.dataset.tab));
    }));
    render();
    document.body.classList.add('has-sticky');
  }

  /* ---------- Shop filters ---------- */
  const shop = $('[data-shop]');
  if (shop) {
    const cards = $$('[data-card]', shop);
    const state = { cat: new Set(), veh: new Set(), volt: new Set(), sort: 'featured', q: '' };
    const params = new URLSearchParams(location.search);
    if (params.get('cat')) state.cat.add(params.get('cat'));
    if (params.get('veh')) state.veh.add(params.get('veh'));
    if (params.get('q')) state.q = params.get('q').toLowerCase();
    function apply() {
      let vis = 0;
      cards.forEach(c => {
        const d = c.dataset;
        let ok = true;
        if (state.cat.size && !state.cat.has(d.cat)) ok = false;
        if (state.veh.size && ![...state.veh].some(v => (d.veh || '').split(',').includes(v))) ok = false;
        if (state.volt.size && ![...state.volt].some(v => (d.volt || '').split(',').includes(v))) ok = false;
        if (state.q && !(d.txt || '').includes(state.q)) ok = false;
        c.style.display = ok ? '' : 'none'; if (ok) vis++;
      });
      const grid = $('#shop-grid');
      const pv = (c, d) => { const p = +c.dataset.price; return p >= 99999 ? d : p; };
      const sorted = cards.slice().sort((a, b) => {
        if (state.sort === 'price-asc') return pv(a, 1e9) - pv(b, 1e9);
        if (state.sort === 'price-desc') return pv(b, -1) - pv(a, -1);
        if (state.sort === 'name') return a.dataset.name.localeCompare(b.dataset.name);
        return +a.dataset.order - +b.dataset.order;
      });
      sorted.forEach(c => grid.appendChild(c));
      $('#shop-count').textContent = vis + ' product' + (vis === 1 ? '' : 's');
      let em = $('#shop-empty'); if (!em) { em = document.createElement('div'); em.id = 'shop-empty'; em.className = 'empty'; em.innerHTML = '<b>No products match these filters</b>Try fewer filters or search by article number.'; grid.parentNode.insertBefore(em, grid.nextSibling); }
      em.style.display = vis ? 'none' : '';
      const ap = $('#apply-f'); if (ap) ap.textContent = 'Show ' + vis + ' product' + (vis === 1 ? '' : 's');
      $$('[data-f]').forEach(i => { const [k, v] = i.dataset.f.split(':'); i.checked = state[k].has(v); });
    }
    $$('[data-f]').forEach(i => i.addEventListener('change', () => { const [k, v] = i.dataset.f.split(':'); i.checked ? state[k].add(v) : state[k].delete(v); apply(); }));
    $('#sort')?.addEventListener('change', (e) => { state.sort = e.target.value; apply(); });
    $('#shop-q')?.addEventListener('input', (e) => { state.q = e.target.value.toLowerCase(); apply(); });
    $('#clear-f')?.addEventListener('click', () => { state.cat.clear(); state.veh.clear(); state.volt.clear(); state.q = ''; if ($('#shop-q')) $('#shop-q').value = ''; apply(); });
    $('#mob-filter')?.addEventListener('click', () => { $('.filters').classList.add('open'); document.body.style.overflow = 'hidden'; });
    $('#apply-f')?.addEventListener('click', () => { $('.filters').classList.remove('open'); document.body.style.overflow = ''; });
    apply();
  }

  /* ---------- checkout (hands the cart to Shopify Checkout) ---------- */
  const cof = $('#checkout-form');
  if (cof) {
    const cc = $('#co-country');
    if (cc) { cc.value = localStorage.getItem('pegasus_country') || 'Netherlands'; cc.addEventListener('change', () => { localStorage.setItem('pegasus_country', cc.value); renderCart(); }); }
    // A kit maps to one Shopify variant: KIT-<ID> plus the chosen option SKUs, in the same order the CSV import generated them
    const kitSku = (l) => {
      const b = bundleById[l.id] || { items: [] };
      const g = b.items.map((it, i) => it.choices ? (l.skus || [])[i] : null).filter(Boolean).slice(0, 3);
      const S0 = C.shopify; const real0 = (sku) => (S0 && S0.alias && S0.alias[sku]) || sku;
      return 'KIT-' + l.id.toUpperCase() + (g.length ? '-' + g.map(real0).join('-') : '');
    };
    cof.addEventListener('submit', (e) => {
      e.preventDefault();
      if (!cart.length) { toast('Your cart is empty'); return; }
      const country = localStorage.getItem('pegasus_country') || 'Netherlands';
      const shq = shipping(subtotal(), country);
      if (shq.quote || shq.hatches >= 3) { location.href = ROOT + 'contact.html?quote=1'; return; }
      const S = C.shopify;
      const real = (sku) => (S && S.alias && S.alias[sku]) || sku;
      const parts = [];
      for (const l of cart) {
        const id = S && S.variants && S.variants[l.type === 'bundle' ? kitSku(l) : real((l.skus || [])[0])];
        if (!id) { toast('One item needs manual handling. Taking you to our contact page.'); setTimeout(() => { location.href = ROOT + 'contact.html?quote=1'; }, 1400); return; }
        parts.push(id + ':' + l.qty);
      }
      // hand the visible cart over to Shopify; keep a 2h backup so an abandoned checkout can be restored
      localStorage.setItem('pegasus_handoff', JSON.stringify({ t: Date.now(), lines: cart }));
      cart = []; save();
      location.href = S.store + '/cart/' + parts.join(',');
    });
  }
  const ty = $('#order-id'); if (ty) { const qp = new URLSearchParams(location.search); if (qp.get('form')) { $('#ty-order').style.display = 'none'; $('#ty-form').style.display = ''; $('#ty-eyebrow').textContent = 'Message received'; } else { ty.textContent = qp.get('o') ? ' ' + qp.get('o') : ''; } }

  /* ---------- forms: decode endpoint at runtime ---------- */
  $$('form[data-fs]').forEach(f => { try { f.action = atob(f.dataset.fs); } catch (e) {} f.addEventListener('submit', () => { const b = f.querySelector('button'); if (b) { b.disabled = true; b.textContent = 'Sending…'; } }); });

  /* ---------- contact prefill ---------- */
  (function () {
    const ta = $('.contact-grid textarea'); if (!ta) return;
    const q = new URLSearchParams(location.search);
    if (q.get('datasheet')) ta.value = 'Please send me the technical datasheet and drawing for article ' + q.get('datasheet') + '.';
    if (q.get('product') && byId[q.get('product')]) ta.value = 'Please send me a quote for: ' + byId[q.get('product')].name + '. Vehicle / application: ';
    if (q.get('quote') && cart.length) {
      const country = localStorage.getItem('pegasus_country') || 'my country';
      ta.value = 'Please quote shipping to ' + country + ' for this order:\n' + cart.map(l => l.qty + ' x ' + l.title + (l.sub ? ' (' + l.sub + ')' : '')).join('\n') + '\nOrder value: ' + money(subtotal()) + ' incl. VAT.\nDelivery address: ';
    }
  })();

  /* ---------- newsletter / contact (demo) ---------- */
  $$('form[data-demo]').forEach(f => f.addEventListener('submit', (e) => { e.preventDefault(); toast('Thank you, we will be in touch within 24 hours.'); f.reset(); }));

  renderCart();
})();
