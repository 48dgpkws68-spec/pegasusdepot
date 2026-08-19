# Pegasus Depot · pegasusdepot.com

Static, Shopify-ready storefront for premium vehicle ventilation (rooftop ventilators, valves, switches, roof hatches, LED lighting).

- `data/catalog.json` · products, variants, prices (incl. VAT), specs, copy
- `data/bundles.json` · kits (components, discount)
- `data/vehicles.json` · shop-by-vehicle landing pages
- `src/site.css`, `src/site.js` · design system + cart/variant/bundle logic (localStorage cart)
- `build.py` · generates every HTML page, `assets/js/catalog.js`, `sitemap.xml`, `shopify-products.csv`, `shopify-bundles.csv`
- `assets/img/` · optimised product + scene images (webp), `assets/pdf/` · datasheets

Build: `python3 build.py` (needs Pillow). Prices: see `PRICING.md`.
