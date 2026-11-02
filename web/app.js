// Sale Radar front end: static, loads data/*.json and searches in the browser.
const $ = (id) => document.getElementById(id);
const PAGE = 48;
let products = [], history = null, shown = PAGE, results = [];
const rs = (n) => "Rs " + Math.round(n).toLocaleString("en-PK");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// Watchlist: per-device, stored in the browser
const store = {
  get() { try { return JSON.parse(localStorage.getItem("watch") || "{}"); } catch { return {}; } },
  set(v) { try { localStorage.setItem("watch", JSON.stringify(v)); } catch {} },
};

// Simple synonym map so Roman-Urdu / local words match
const SYN = { tracksuit: ["track suit", "jogger set", "co-ord"], earbuds: ["tws", "earphones", "airpods", "buds"],
  shalwar: ["shalwar kameez", "kurta"], lawn: ["unstitched"], hoodie: ["sweatshirt"], joggers: ["trouser", "pants"] };
const norm = (s) => s.toLowerCase().normalize("NFKD").replace(/[^a-z0-9 ]+/g, " ");

function score(p, terms) {
  if (!terms.length) return 1;
  const hay = p._hay;
  let s = 0;
  for (const alts of terms) {
    let best = 0;
    for (const t of alts) {
      if (p._title.includes(t)) best = Math.max(best, 3);
      else if (hay.includes(t)) best = Math.max(best, 1);
    }
    if (!best) return 0; // every term must match
    s += best;
  }
  return s;
}

function search() {
  const q = norm($("q").value).trim();
  const terms = q ? q.split(/\s+/).map((w) => [w, ...(SYN[w] || []).map(norm)]) : [];
  const st = $("store").value, sale = $("saleOnly").checked, stock = $("stockOnly").checked;
  const watch = $("watchOnly").checked ? store.get() : null;
  results = [];
  for (const p of products) {
    if (st && p.store !== st) continue;
    if (sale && !p.compare_at) continue;
    if (stock && !p.in_stock) continue;
    if (watch && !watch[p.id]) continue;
    const s = score(p, terms);
    if (s) results.push([s, p]);
  }
  const sort = $("sort").value;
  const cmp = { rel: (a, b) => b[0] - a[0] || b[1].discount - a[1].discount, low: (a, b) => a[1].price - b[1].price,
    high: (a, b) => b[1].price - a[1].price, disc: (a, b) => b[1].discount - a[1].discount }[sort];
  results.sort(cmp);
  shown = PAGE;
  render();
}

function card(p) {
  const badges = [
    p.discount ? `<span class="b sale">-${p.discount}%</span>` : "",
    p.lowest && p.price <= p.lowest && p.discount ? `<span class="b low">Lowest price</span>` : "",
    !p.in_stock ? `<span class="b out">Out of stock</span>` : "",
  ].join("");
  return `<div class="card" data-id="${esc(p.id)}">
    ${p.image ? `<img loading="lazy" src="${esc(p.image)}" alt="">` : `<img alt="">`}
    <div class="body"><div class="store">${esc(p.store)}</div>
    <div class="title">${esc(p.title)}</div>
    <div class="price">${rs(p.price)}${p.compare_at ? `<span class="was">${rs(p.compare_at)}</span>` : ""}</div>
    <div class="badges">${badges}</div></div></div>`;
}

function render() {
  const g = $("grid");
  g.innerHTML = results.length ? results.slice(0, shown).map((r) => card(r[1])).join("")
    : `<div class="empty">No products found. Try another word or clear filters.</div>`;
  $("more").hidden = shown >= results.length;
  const saleCount = results.filter((r) => r[1].compare_at).length;
  $("meta").textContent = `${results.length.toLocaleString()} products · ${saleCount.toLocaleString()} on sale`;
}

function chart(pts) {
  if (!pts || pts.length < 2) return `<p style="color:var(--mute)">Price history builds up daily. Check back soon.</p>`;
  const W = 480, H = 120, P = 24, ys = pts.map((p) => p[1]);
  const lo = Math.min(...ys), hi = Math.max(...ys), span = hi - lo || 1;
  const x = (i) => P + (i * (W - 2 * P)) / (pts.length - 1), y = (v) => H - P - ((v - lo) * (H - 2 * P)) / span;
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" width="100%"><path d="${d}" fill="none" stroke="var(--brand)" stroke-width="2"/>
    <text x="${P}" y="12">${rs(hi)}</text><text x="${P}" y="${H - 6}">${rs(lo)}</text>
    <text x="${W - P}" y="${H - 6}" text-anchor="end">${esc(pts.at(-1)[0])}</text></svg>`;
}

async function showProduct(id) {
  const p = products.find((x) => x.id === id);
  if (!p) return;
  if (!history) history = await fetch("data/history.json").then((r) => r.json()).catch(() => ({}));
  // Same-product-elsewhere: other stores with similar titles
  const words = new Set(p._title.split(" ").filter((w) => w.length > 2));
  const similar = products.filter((o) => o.store !== p.store && o.in_stock)
    .map((o) => [o, o._title.split(" ").filter((w) => words.has(w)).length / Math.max(words.size, 1)])
    .filter(([, s]) => s >= 0.5).sort((a, b) => a[0].price - b[0].price).slice(0, 5);
  const watched = !!store.get()[id];
  $("dlg").innerHTML = `<h3 style="margin-top:0">${esc(p.title)}</h3>
    <div class="row"><span><b>${esc(p.store)}</b></span><span class="price">${rs(p.price)}${p.compare_at ? `<span class="was">${rs(p.compare_at)}</span>` : ""}</span></div>
    <p style="font-size:13px;color:var(--mute)">Lowest price seen: ${rs(p.lowest ?? p.price)}</p>
    ${chart(history[id])}
    ${similar.length ? `<h4>Similar at other stores</h4>` + similar.map(([o]) =>
      `<div class="row"><span>${esc(o.store)} · ${esc(o.title)}</span><a href="${esc(o.url)}" target="_blank" rel="noopener">${rs(o.price)}</a></div>`).join("") : ""}
    <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
      <a href="${esc(p.url)}" target="_blank" rel="noopener"><button class="primary">Buy at ${esc(p.store)}</button></a>
      <button id="watchBtn">${watched ? "★ Watching" : "☆ Watch price"}</button>
      <button onclick="dlg.close()">Close</button></div>`;
  $("watchBtn").onclick = () => {
    const w = store.get();
    if (w[id]) delete w[id]; else w[id] = p.price;
    store.set(w);
    $("watchBtn").textContent = w[id] ? "★ Watching" : "☆ Watch price";
  };
  $("dlg").showModal();
}

function checkWatchlist() {
  // On each visit, tell the user if a watched item got cheaper
  const w = store.get(), drops = [];
  for (const p of products) if (w[p.id] && p.price < w[p.id]) { drops.push(`${p.title} (${p.store}): ${rs(w[p.id])} → ${rs(p.price)}`); w[p.id] = p.price; }
  if (drops.length) {
    store.set(w);
    $("meta").insertAdjacentHTML("beforebegin", `<div style="background:var(--good);color:#fff;padding:10px;border-radius:10px;margin-bottom:10px">
      ⬇ Price dropped on your watchlist:<br>${drops.map(esc).join("<br>")}</div>`);
  }
}

async function init() {
  try {
    const data = await fetch("data/products.json").then((r) => r.json());
    products = data.products.map((p) => ({ ...p, _title: norm(p.title), _hay: norm([p.title, p.type, p.vendor, p.store, ...(p.tags || [])].join(" ")) }));
    const stores = [...new Set(products.map((p) => p.store))].sort();
    $("store").insertAdjacentHTML("beforeend", stores.map((s) => `<option>${esc(s)}</option>`).join(""));
    checkWatchlist();
    search();
    $("meta").textContent += ` · updated ${new Date(data.updated).toLocaleString()}`;
  } catch (e) {
    $("meta").textContent = "Could not load product data. Run the scraper first.";
  }
}

let t;
$("q").addEventListener("input", () => { clearTimeout(t); t = setTimeout(search, 150); });
["store", "sort", "saleOnly", "stockOnly", "watchOnly"].forEach((id) => $(id).addEventListener("change", search));
$("more").onclick = () => { shown += PAGE; render(); };
$("grid").addEventListener("click", (e) => { const c = e.target.closest(".card"); if (c) showProduct(c.dataset.id); });
init();
