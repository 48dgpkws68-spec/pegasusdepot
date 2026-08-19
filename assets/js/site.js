/* Pegasus Depot · storefront logic (static prototype, Shopify-ready data model) */
(function () {
  if (location.search.includes('capture')) document.documentElement.classList.add('capture');
  const C = window.CATALOG;
  if (!C) return;
  const ROOT = document.documentElement.getAttribute('data-root') || '';
  const money = (n) => '€' + (Math.round(n * 100) / 100).toLocaleString('en-IE', { minimumFractionDigits: n % 1 ? 2 : 0, maximumFractionDigits: 2 });
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const byId = {}; C.products.forEach(p => byId[p.id] = p);
  const bySku = {}; C.products.forEach(p => p.variants.forEach(v => bySku[v.sku] = { p, v }));
  const bundleById = {}; (C.bundles || []).forEach(b => bundleById[b.id] = b);

  /* ---------- cart ---------- */
  const KEY = 'pegasus_cart_v1';
  let cart = [];
  try { cart = JSON.parse(localStorage.getItem(KEY) || '[]'); } catch (e) { cart = []; }
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
  const count = () => cart.reduce((s, l) => s + l.qty, 0);

  function renderCart() {
    $$('.cart-count').forEach(el => el.textContent = count() || '');
    const body = $('#cart-body'); if (!body) return;
    if (!cart.length) {
      body.innerHTML = '<div class="empty"><b>Your cart is empty</b>Add a rooftop ventilator, a kit or an accessory to get started.<br><br><a class="btn btn-dark btn-sm" href="' + ROOT + 'shop.html">Browse the shop</a></div>';
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
    const ship = st >= free || st === 0 ? 0 : 9.95;
    $('#cart-sub').textContent = money(st);
    $('#cart-ship').textContent = st === 0 ? '–' : (ship ? money(ship) : 'Free');
    $('#cart-total').textContent = money(st + ship);
    const bar = $('#ship-bar'); const txt = $('#ship-txt');
    if (bar) { bar.style.width = Math.min(100, st / free * 100) + '%'; }
    if (txt) { txt.innerHTML = st >= free ? '<b>You have unlocked free EU shipping.</b>' : 'Add <b>' + money(free - st) + '</b> for free EU shipping'; }
    const co = $('#checkout-btn'); if (co) co.classList.toggle('disabled', !cart.length);
    body.onclick = (e) => {
      const q = e.target.closest('[data-q]'); if (q) { const [i, d] = q.dataset.q.split(':').map(Number); setQty(i, cart[i].qty + d); }
      const r = e.target.closest('[data-rm]'); if (r) { e.preventDefault(); setQty(+r.dataset.rm, 0); }
    };
    // checkout page summary
    const sum = $('#co-lines');
    if (sum) {
      sum.innerHTML = cart.length ? cart.map(l => `<div class="row"><span>${l.qty} × ${l.title}<br><small class="muted">${l.sub || ''}</small></span><b>${money(l.price * l.qty)}</b></div>`).join('') : '<p class="muted">Your cart is empty.</p>';
      $('#co-sub').textContent = money(st); $('#co-ship').textContent = ship ? money(ship) : 'Free'; $('#co-total').textContent = money(st + ship);
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

  /* ---------- header: mega menu, mobile nav, search ---------- */
  $$('.nav > li').forEach(li => {
    let t; li.addEventListener('mouseenter', () => { clearTimeout(t); $$('.nav > li').forEach(x => x.classList.remove('open')); li.classList.add('open'); });
    li.addEventListener('mouseleave', () => { t = setTimeout(() => li.classList.remove('open'), 120); });
  });
  $('#burger')?.addEventListener('click', () => $('#mnav').classList.add('open'));
  $('#mnav-close')?.addEventListener('click', () => $('#mnav').classList.remove('open'));
  const openSearch = () => { $('#search').classList.add('open'); setTimeout(() => $('#search-input')?.focus(), 50); };
  const closeSearch = () => $('#search')?.classList.remove('open');
  $$('[data-open-search]').forEach(b => b.addEventListener('click', (e) => { e.preventDefault(); openSearch(); }));
  $('#search-close')?.addEventListener('click', closeSearch);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { closeSearch(); closeCart(); $('#mnav')?.classList.remove('open'); } });
  const si = $('#search-input');
  if (si) {
    const res = $('#search-res');
    const idx = C.products.map(p => ({ p, txt: (p.name + ' ' + p.tagline + ' ' + p.summary + ' ' + p.variants.map(v => v.sku).join(' ') + ' ' + p.category).toLowerCase() }))
      .concat((C.bundles || []).map(b => ({ b, txt: (b.name + ' ' + b.tagline + ' ' + b.summary).toLowerCase() })));
    si.addEventListener('input', () => {
      const q = si.value.trim().toLowerCase();
      if (!q) { res.innerHTML = ''; return; }
      const hits = idx.filter(x => q.split(/\s+/).every(w => x.txt.includes(w))).slice(0, 8);
      res.innerHTML = hits.map(x => x.p
        ? `<a href="${ROOT}products/${x.p.id}.html"><img src="${ROOT + x.p.images[0]}" alt=""><div><b>${x.p.name}</b><span>${x.p.tagline}</span></div></a>`
        : `<a href="${ROOT}bundles/${x.b.id}.html"><img src="${ROOT + x.b.images[0]}" alt=""><div><b>${x.b.name} <em class="gold">· Kit</em></b><span>${x.b.tagline}</span></div></a>`).join('') || '<p class="muted">No results. Try "Le Mans", "12V", "hatch" or an article number.</p>';
    });
  }

  /* ---------- reveal on scroll ---------- */
  const io = 'IntersectionObserver' in window ? new IntersectionObserver((es) => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }), { threshold: .08 }) : null;
  $$('.reveal').forEach(el => io ? io.observe(el) : el.classList.add('in'));

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
          return `<button class="opt ${sel[k] === val ? 'on' : ''} ${avail ? '' : 'dim'}" data-k="${k}" data-v="${val}">${sw}${val}</button>`;
        }).join('');
        const lbl = $(`[data-opt-label="${k}"]`); if (lbl) lbl.textContent = sel[k];
      });
      const v = cur();
      $('#pdp-sku').textContent = 'Article no. ' + v.sku;
      $('#pdp-price').textContent = v.price == null ? 'Quote' : money(v.price);
      const was = $('#pdp-was'); if (was) { was.textContent = v.compare_at ? money(v.compare_at) : ''; was.style.display = v.compare_at ? '' : 'none'; }
      const sv = $('#pdp-save'); if (sv) { if (v.compare_at && v.price) { sv.textContent = 'Save ' + Math.round((1 - v.price / v.compare_at) * 100) + '%'; sv.style.display = ''; } else sv.style.display = 'none'; }
      const sp = $('#sticky-price'); if (sp) sp.textContent = v.price == null ? 'Quote' : money(v.price);
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
    $('#qty-minus')?.addEventListener('click', () => { qtyI.value = Math.max(1, +qtyI.value - 1); });
    $('#qty-plus')?.addEventListener('click', () => { qtyI.value = +qtyI.value + 1; });
    function updateAddons() {
      const v = cur(); let total = (v.price || 0);
      $$('.addon input:checked').forEach(i => total += +i.dataset.price);
      const t = $('#addon-total'); if (t) t.textContent = money(total);
    }
    $$('.addon input').forEach(i => i.addEventListener('change', updateAddons));
    const add = () => {
      const v = cur(); if (v.price == null) return;
      const q = Math.max(1, +($('#qty')?.value || 1));
      addLine({ type: 'product', id: p.id, skus: [v.sku], title: p.name, sub: v.label + ' · ' + v.sku, price: v.price, qty: q, image: p.images[0] });
      $$('.addon input:checked').forEach(i => { const { p: ap, v: av } = bySku[i.dataset.sku]; addLine({ type: 'product', id: ap.id, skus: [av.sku], title: ap.name, sub: av.label + ' · ' + av.sku, price: av.price, qty: q, image: ap.images[0] }); i.checked = false; });
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
      const price = Math.round(full * (1 - b.discount));
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
      $$('[data-f]').forEach(i => { const [k, v] = i.dataset.f.split(':'); i.checked = state[k].has(v); });
    }
    $$('[data-f]').forEach(i => i.addEventListener('change', () => { const [k, v] = i.dataset.f.split(':'); i.checked ? state[k].add(v) : state[k].delete(v); apply(); }));
    $('#sort')?.addEventListener('change', (e) => { state.sort = e.target.value; apply(); });
    $('#shop-q')?.addEventListener('input', (e) => { state.q = e.target.value.toLowerCase(); apply(); });
    $('#clear-f')?.addEventListener('click', () => { state.cat.clear(); state.veh.clear(); state.volt.clear(); state.q = ''; if ($('#shop-q')) $('#shop-q').value = ''; apply(); });
    $('#mob-filter')?.addEventListener('click', () => $('.filters').classList.toggle('open'));
    apply();
  }

  /* ---------- checkout (prototype) ---------- */
  const cof = $('#checkout-form');
  if (cof) {
    cof.addEventListener('submit', (e) => {
      e.preventDefault();
      if (!cart.length) { toast('Your cart is empty'); return; }
      const order = { id: 'PD-' + Math.random().toString(36).slice(2, 8).toUpperCase(), lines: cart, total: $('#co-total').textContent };
      localStorage.setItem('pegasus_last_order', JSON.stringify(order));
      cart = []; save();
      location.href = ROOT + 'thank-you.html?o=' + order.id;
    });
  }
  const ty = $('#order-id'); if (ty) { const o = new URLSearchParams(location.search).get('o'); ty.textContent = o || 'PD-DEMO'; }

  /* ---------- newsletter / contact (demo) ---------- */
  $$('form[data-demo]').forEach(f => f.addEventListener('submit', (e) => { e.preventDefault(); toast('Thank you, we will be in touch within 24 hours.'); f.reset(); }));

  renderCart();
})();
