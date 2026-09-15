/* Household Ledger — single-file SPA (no build step). */
(() => {
  "use strict";

  // ---------- state ----------
  const S = { user: null, cfg: { app_name: "Household Ledger", currency_symbol: "₹" }, cats: [], srcs: [] };
  const $ = (sel, el = document) => el.querySelector(sel);
  const app = $("#app");
  const charts = {};

  const KIND_LABEL = { cash: "Cash", bank: "Bank account", credit_card: "Credit card", upi: "UPI", wallet: "Wallet" };
  const INV_LABEL = { equity: "Equity", mutual_fund: "Mutual fund", fd: "Fixed deposit", ppf: "PPF", other: "Other" };

  // ---------- helpers ----------
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const nf = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const money = (v, sign) => {
    const n = Number(v || 0);
    const s = `${S.cfg.currency_symbol}${nf.format(Math.abs(n))}`;
    return sign && n < 0 ? `−${s}` : s;
  };
  const money0 = (v) => `${S.cfg.currency_symbol}${new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(Number(v || 0))}`;
  const today = () => new Date().toISOString().slice(0, 10);
  const monthKey = (d) => d.toISOString().slice(0, 7);
  const monthLabel = (ym) => { const [y, m] = ym.split("-"); return new Date(y, m - 1, 1).toLocaleString("en-IN", { month: "long", year: "numeric" }); };
  const shortMonth = (ym) => { const [y, m] = ym.split("-"); return new Date(y, m - 1, 1).toLocaleString("en-IN", { month: "short", year: "2-digit" }); };
  const fmtDate = (iso) => new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  const isDark = (hex) => { const n = parseInt(hex.slice(1), 16); return (((n >> 16) & 255) * 299 + ((n >> 8) & 255) * 587 + (n & 255) * 114) / 1000 < 150; };

  let toastT;
  const toast = (msg) => { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("show"), 2400); };

  async function api(path, opts = {}) {
    const r = await fetch("/api" + path, {
      headers: opts.body ? { "Content-Type": "application/json" } : {},
      ...opts,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    if (r.status === 401 && !path.startsWith("/auth/login")) { S.user = null; render(); throw new Error("Signed out"); }
    if (r.status === 204) return null;
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : (data.detail?.[0]?.msg || "Something went wrong"));
    return data;
  }
  const loadLookups = async () => { [S.cats, S.srcs] = await Promise.all([api("/categories"), api("/sources")]); };

  // ---------- modal form ----------
  function modal({ title, body, submit = "Save", onSubmit, danger }) {
    const d = document.createElement("dialog");
    d.innerHTML = `<form method="dialog"><h3>${esc(title)}</h3>${body}
      <div class="err" aria-live="assertive"></div>
      <div class="dlg-actions">
        ${danger ? `<button type="button" class="btn danger" data-act="danger">${esc(danger)}</button><span class="grow" style="flex:1"></span>` : ""}
        <button type="button" class="btn secondary" data-act="cancel">Cancel</button>
        <button type="submit" class="btn">${esc(submit)}</button>
      </div></form>`;
    document.body.appendChild(d);
    const form = $("form", d), err = $(".err", d);
    const close = () => { d.close(); d.remove(); };
    $("[data-act=cancel]", d).onclick = close;
    d.addEventListener("cancel", (e) => { e.preventDefault(); close(); });
    if (danger) $("[data-act=danger]", d).onclick = async () => { try { await onSubmit(null, "danger"); close(); } catch (e) { err.textContent = e.message; } };
    form.onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(form).entries());
      form.querySelectorAll("input[type=checkbox]").forEach((c) => (fd[c.name] = c.checked));
      $("button[type=submit]", d).disabled = true;
      try { await onSubmit(fd, "submit"); close(); }
      catch (ex) { err.textContent = ex.message; $("button[type=submit]", d).disabled = false; }
    };
    d.showModal();
    const first = form.querySelector("input:not([type=hidden]),select,textarea"); if (first) first.focus();
    return d;
  }
  const confirmDelete = (what) => new Promise((res) => modal({
    title: `Delete ${what}?`, body: `<p class="muted" style="margin:0">This can't be undone.</p>`, submit: "Delete",
    onSubmit: async () => res(true),
  }).addEventListener("close", () => res(false)));

  // ---------- shell ----------
  const NAV = [["dashboard", "Dashboard"], ["transactions", "Transactions"], ["investments", "Savings"], ["reports", "Reports"], ["categories", "Categories"], ["sources", "Sources"]];
  function shell(view, content) {
    const links = NAV.concat(S.user.is_admin ? [["users", "People"]] : []).concat([["account", "Account"]]);
    app.innerHTML = `
      <nav class="rail" aria-label="Main">
        <div class="brand">${esc(S.cfg.app_name)}<small>one ledger for the house</small></div>
        ${links.map(([k, l]) => `<a href="#/${k}" class="${view === k ? "active" : ""}">${l}</a>`).join("")}
        <div class="spacer"></div>
        <div class="who">${esc(S.user.name)}</div>
      </nav>
      <main>${content}</main>`;
  }

  // ---------- login ----------
  function renderLogin() {
    app.innerHTML = `<div class="login-wrap"><div class="login">
      <h1>${esc(S.cfg.app_name)}</h1><p class="lede">Sign in with the account set up for you.</p>
      <form>
        <label>Email <input name="email" type="email" autocomplete="username" required autofocus></label>
        <label>Password <input name="password" type="password" autocomplete="current-password" required></label>
        <div class="err" aria-live="assertive"></div>
        <button class="btn" type="submit">Sign in</button>
      </form></div></div>`;
    $("form", app).onsubmit = async (e) => {
      e.preventDefault();
      const b = $("button", app), err = $(".err", app); b.disabled = true; err.textContent = "";
      try {
        S.user = await api("/auth/login", { method: "POST", body: Object.fromEntries(new FormData(e.target)) });
        await loadLookups(); location.hash = "#/dashboard"; render();
      } catch (ex) { err.textContent = ex.message; b.disabled = false; }
    };
  }

  // ---------- dashboard ----------
  const dash = { mode: "month", month: monthKey(new Date()), start: "", end: "" };
  async function renderDashboard() {
    const q = dash.mode === "month" ? `?start=${dash.month}-01&end=${lastDay(dash.month)}` : `?start=${dash.start}&end=${dash.end}`;
    let d;
    try { d = await api("/dashboard" + q); } catch (e) { return shell("dashboard", `<p class="err">${esc(e.message)}</p>`); }
    const gain = Number(d.investments_value) - Number(d.investments_invested);
    shell("dashboard", `
      <h1>Dashboard</h1>
      <div class="toolbar">
        <div class="period">
          <div class="seg"><button class="${dash.mode === "month" ? "on" : ""}" data-mode="month">Month</button><button class="${dash.mode === "range" ? "on" : ""}" data-mode="range">Date range</button></div>
          ${dash.mode === "month" ? `
            <button class="btn secondary small" data-nav="-1" aria-label="Previous month">‹</button>
            <span class="month">${monthLabel(dash.month)}</span>
            <button class="btn secondary small" data-nav="1" aria-label="Next month">›</button>
            <input type="month" value="${dash.month}" id="mpick" aria-label="Pick month">`
          : `<input type="date" id="rs" value="${d.start}"> <span class="muted">to</span> <input type="date" id="re" value="${d.end}"> <button class="btn secondary small" id="apply">Apply</button>`}
        </div>
        <div class="grow"></div>
        <button class="btn" id="quick-add">Add entry</button>
      </div>
      <div class="figures">
        <div><div class="k">Income</div><div class="v num income">${money(d.income)}</div></div>
        <div><div class="k">Expenses</div><div class="v num expense">${money(d.expense)}</div></div>
        <div><div class="k">Left over</div><div class="v num ${Number(d.net) < 0 ? "expense" : ""}">${money(d.net, true)}</div>
          <div class="muted" style="font-size:13px">${Number(d.income) ? Math.round(Number(d.net) / Number(d.income) * 100) + "% of income saved" : ""}</div></div>
      </div>
      <div class="split">
        <div><h2>Where the money went</h2>
          ${d.expense_by_category.length ? `<div class="chart-box pie"><canvas id="pie"></canvas></div>` : `<div class="empty">No expenses in this period yet.</div>`}
        </div>
        <div><h2>By category</h2>
          ${d.expense_by_category.length ? `<ul class="legend">${d.expense_by_category.map((c) => `<li><span class="sw" style="background:${c.color}"></span><span>${esc(c.icon)} ${esc(c.name)} <span class="muted">· ${c.count}</span></span><span class="num">${money(c.total)}</span><span class="pct num">${(Number(c.total) / Number(d.expense) * 100).toFixed(0)}%</span></li>`).join("")}</ul>` : `<p class="muted">Add an expense and it shows up here.</p>`}
        </div>
      </div>
      <h2>Twelve-month trend</h2>
      <div class="chart-box trend"><canvas id="trend"></canvas></div>
      <p class="muted" style="font-size:13px">Bars are monthly income and expenses; the line is cumulative savings from all recorded history.</p>
      <h2>Savings &amp; investments</h2>
      ${Number(d.investments_invested) || Number(d.investments_value) ? `
      <div class="figures">
        <div><div class="k">Contributed</div><div class="v num">${money(d.investments_invested)}</div></div>
        <div><div class="k">Current value</div><div class="v num invest">${money(d.investments_value)}</div></div>
        <div><div class="k">Gain</div><div class="v num ${gain < 0 ? "expense" : "income"}">${money(gain, true)}</div>
          <div class="muted" style="font-size:13px">${Number(d.investments_invested) ? (gain / Number(d.investments_invested) * 100).toFixed(1) + "% on contributions" : ""}</div></div>
      </div>` : `<div class="empty">Track equity, mutual funds, FDs and PPF under <a href="#/investments">Savings</a>.</div>`}
    `);
    app.querySelectorAll("[data-mode]").forEach((b) => (b.onclick = () => { dash.mode = b.dataset.mode; if (!dash.start) { dash.start = d.start; dash.end = d.end; } renderDashboard(); }));
    app.querySelectorAll("[data-nav]").forEach((b) => (b.onclick = () => { dash.month = shiftMonth(dash.month, +b.dataset.nav); renderDashboard(); }));
    const mp = $("#mpick"); if (mp) mp.onchange = () => { if (mp.value) { dash.month = mp.value; renderDashboard(); } };
    const ap = $("#apply"); if (ap) ap.onclick = () => { dash.start = $("#rs").value; dash.end = $("#re").value; if (dash.start && dash.end) renderDashboard(); };
    $("#quick-add").onclick = () => txForm(null, renderDashboard);

    if (d.expense_by_category.length) {
      charts.pie = new Chart($("#pie"), {
        type: "doughnut",
        data: { labels: d.expense_by_category.map((c) => c.name), datasets: [{ data: d.expense_by_category.map((c) => Number(c.total)), backgroundColor: d.expense_by_category.map((c) => c.color), borderColor: "#F6F7F4", borderWidth: 2 }] },
        options: { cutout: "58%", plugins: { legend: { display: false }, tooltip: { callbacks: { label: (t) => ` ${money(t.raw)}` } } } },
      });
    }
    charts.trend = new Chart($("#trend"), {
      data: {
        labels: d.trend.map((p) => shortMonth(p.month)),
        datasets: [
          { type: "bar", label: "Income", data: d.trend.map((p) => Number(p.income)), backgroundColor: "#1F6F5F", borderRadius: 3 },
          { type: "bar", label: "Expenses", data: d.trend.map((p) => Number(p.expense)), backgroundColor: "#C8878A", borderRadius: 3 },
          { type: "line", label: "Cumulative savings", data: d.trend.map((p) => Number(p.cumulative)), borderColor: "#1B2A24", backgroundColor: "#1B2A24", tension: .3, pointRadius: 3, yAxisID: "y2" },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
        scales: { y: { ticks: { callback: (v) => money0(v) }, grid: { color: "#E3E6E0" } }, y2: { position: "right", grid: { drawOnChartArea: false }, ticks: { callback: (v) => money0(v) } }, x: { grid: { display: false } } },
        plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } }, tooltip: { callbacks: { label: (t) => ` ${t.dataset.label}: ${money(t.raw, true)}` } } },
      },
    });
  }
  const shiftMonth = (ym, n) => { const [y, m] = ym.split("-").map(Number); const d = new Date(y, m - 1 + n, 1); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; };
  const lastDay = (ym) => { const [y, m] = ym.split("-").map(Number); return `${ym}-${String(new Date(y, m, 0).getDate()).padStart(2, "0")}`; };

  // ---------- transactions ----------
  const tx = { page: 1, type: "", category_id: "", source_id: "", q: "", month: monthKey(new Date()), all: false };
  async function renderTransactions() {
    const p = new URLSearchParams({ page: tx.page, page_size: 50 });
    if (!tx.all) { p.set("start", tx.month + "-01"); p.set("end", lastDay(tx.month)); }
    for (const k of ["type", "category_id", "source_id", "q"]) if (tx[k]) p.set(k, tx[k]);
    let data;
    try { data = await api("/transactions?" + p); } catch (e) { return shell("transactions", `<p class="err">${esc(e.message)}</p>`); }
    const pages = Math.max(1, Math.ceil(data.total / data.page_size));
    const opt = (list, sel, fmt) => list.map((x) => `<option value="${x.id}" ${String(sel) === String(x.id) ? "selected" : ""}>${esc(fmt(x))}</option>`).join("");
    shell("transactions", `
      <h1>Transactions</h1>
      <div class="toolbar">
        <div class="seg"><button class="${!tx.all ? "on" : ""}" data-all="0">Month</button><button class="${tx.all ? "on" : ""}" data-all="1">All time</button></div>
        <input type="month" id="tmonth" value="${tx.month}" ${tx.all ? "disabled" : ""} aria-label="Month">
        <select id="ftype" aria-label="Type"><option value="">All types</option><option value="expense" ${tx.type === "expense" ? "selected" : ""}>Expenses</option><option value="income" ${tx.type === "income" ? "selected" : ""}>Income</option></select>
        <select id="fcat" aria-label="Category"><option value="">All categories</option>${opt(S.cats, tx.category_id, (c) => `${c.icon} ${c.name}`)}</select>
        <select id="fsrc" aria-label="Source"><option value="">All sources</option>${opt(S.srcs, tx.source_id, (s) => s.name)}</select>
        <input type="search" id="fq" placeholder="Search notes" value="${esc(tx.q)}" aria-label="Search notes">
        <div class="grow"></div>
        <button class="btn" id="add">Add entry</button>
      </div>
      ${data.items.length ? `<table><thead><tr><th>Date</th><th>Category</th><th class="hide-m">Source</th><th class="hide-m">Note</th><th class="r">Amount</th><th></th></tr></thead><tbody>
        ${data.items.map((t) => `<tr data-id="${t.id}">
          <td class="num">${fmtDate(t.date)}</td>
          <td><span class="chip"><span class="ic" style="background:${t.category_color}">${esc(t.category_icon)}</span>${esc(t.category_name)}</span>${t.is_recurring ? `<span class="recur">recurring</span>` : ""}</td>
          <td class="hide-m muted">${esc(t.source_name)}</td>
          <td class="hide-m">${esc(t.note || "")} <span class="muted" style="font-size:12px">${data.items.some((x) => x.user_name !== t.user_name) ? "· " + esc(t.user_name) : ""}</span></td>
          <td class="r num ${t.type}">${t.type === "expense" ? "−" : "+"}${money(t.amount)}</td>
          <td class="actions"><button class="btn secondary small" data-edit="${t.id}">Edit</button></td></tr>`).join("")}
      </tbody></table>
      <div class="pager"><span>${data.total} entries</span><button class="btn secondary small" id="prev" ${tx.page <= 1 ? "disabled" : ""}>‹</button><span>${tx.page} / ${pages}</span><button class="btn secondary small" id="next" ${tx.page >= pages ? "disabled" : ""}>›</button></div>`
      : `<div class="empty">Nothing recorded here yet. Add your first entry.</div>`}
    `);
    const rerun = () => { tx.page = 1; renderTransactions(); };
    app.querySelectorAll("[data-all]").forEach((b) => (b.onclick = () => { tx.all = b.dataset.all === "1"; rerun(); }));
    $("#tmonth").onchange = (e) => { if (e.target.value) { tx.month = e.target.value; rerun(); } };
    $("#ftype").onchange = (e) => { tx.type = e.target.value; rerun(); };
    $("#fcat").onchange = (e) => { tx.category_id = e.target.value; rerun(); };
    $("#fsrc").onchange = (e) => { tx.source_id = e.target.value; rerun(); };
    let qt; $("#fq").oninput = (e) => { clearTimeout(qt); qt = setTimeout(() => { tx.q = e.target.value.trim(); rerun(); }, 350); };
    $("#add").onclick = () => txForm(null, renderTransactions);
    const pv = $("#prev"), nx = $("#next");
    if (pv) pv.onclick = () => { tx.page--; renderTransactions(); };
    if (nx) nx.onclick = () => { tx.page++; renderTransactions(); };
    app.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => txForm(data.items.find((t) => t.id === +b.dataset.edit), renderTransactions)));
  }

  function txForm(t, after) {
    const type = t?.type || "expense";
    const catOpts = (ty, sel) => S.cats.filter((c) => c.type === ty).map((c) => `<option value="${c.id}" ${sel === c.id ? "selected" : ""}>${esc(c.icon)} ${esc(c.name)}</option>`).join("");
    const d = modal({
      title: t ? "Edit entry" : "Add entry", submit: t ? "Save changes" : "Add entry", danger: t ? "Delete" : null,
      body: `
        <div class="seg" role="radiogroup" aria-label="Type"><button type="button" class="${type === "expense" ? "on" : ""}" data-t="expense">Expense</button><button type="button" class="${type === "income" ? "on" : ""}" data-t="income">Income</button></div>
        <input type="hidden" name="type" value="${type}">
        <div class="row">
          <label>Amount <input name="amount" type="number" step="0.01" min="0.01" inputmode="decimal" required value="${t ? t.amount : ""}"></label>
          <label>Date <input name="date" type="date" required value="${t ? t.date : today()}"></label>
        </div>
        <div class="row">
          <label>Category <select name="category_id" required>${catOpts(type, t?.category_id)}</select></label>
          <label>Paid via <select name="source_id" required>${S.srcs.map((s) => `<option value="${s.id}" ${t?.source_id === s.id ? "selected" : ""}>${esc(s.name)}</option>`).join("")}</select></label>
        </div>
        <label>Note <input name="note" maxlength="500" value="${esc(t?.note || "")}" placeholder="optional"></label>
        <label class="check"><input type="checkbox" name="is_recurring" ${t?.is_recurring ? "checked" : ""}> Repeats every month</label>`,
      onSubmit: async (fd, act) => {
        if (act === "danger") { await api(`/transactions/${t.id}`, { method: "DELETE" }); toast("Entry deleted"); return after(); }
        const body = { ...fd, amount: Number(fd.amount), category_id: +fd.category_id, source_id: +fd.source_id, note: fd.note || null };
        await api(t ? `/transactions/${t.id}` : "/transactions", { method: t ? "PUT" : "POST", body });
        toast(t ? "Changes saved" : "Entry added"); after();
      },
    });
    d.querySelectorAll("[data-t]").forEach((b) => (b.onclick = () => {
      d.querySelectorAll("[data-t]").forEach((x) => x.classList.toggle("on", x === b));
      $("input[name=type]", d).value = b.dataset.t;
      $("select[name=category_id]", d).innerHTML = catOpts(b.dataset.t);
    }));
  }

  // ---------- categories ----------
  async function renderCategories() {
    const cats = await api("/categories?include_archived=true"); S.cats = cats.filter((c) => !c.is_archived);
    const group = (ty) => cats.filter((c) => c.type === ty);
    const table = (ty) => `<h2>${ty === "expense" ? "Expense" : "Income"} categories</h2>
      <table><tbody>${group(ty).map((c) => `<tr>
        <td><span class="chip"><span class="ic" style="background:${c.color}">${esc(c.icon)}</span>${esc(c.name)}</span>${c.is_archived ? `<span class="recur">archived</span>` : ""}</td>
        <td class="actions">${c.is_archived ? `<button class="btn secondary small" data-restore="${c.id}">Restore</button>` : `<button class="btn secondary small" data-edit="${c.id}">Edit</button> <button class="btn danger small" data-del="${c.id}">Delete</button>`}</td>
      </tr>`).join("")}</tbody></table>`;
    shell("categories", `<h1>Categories</h1><p class="lede">Categories with history can't be deleted; they're archived and hidden from the entry form instead.</p>
      <div class="toolbar"><div class="grow"></div><button class="btn" id="add">New category</button></div>${table("expense")}${table("income")}`);
    const form = (c) => modal({
      title: c ? "Edit category" : "New category", submit: c ? "Save changes" : "Create category",
      body: `<label>Name <input name="name" required maxlength="80" value="${esc(c?.name || "")}"></label>
        <div class="row3">
          <label>Type <select name="type">${["expense", "income"].map((t) => `<option value="${t}" ${(c?.type || "expense") === t ? "selected" : ""}>${t[0].toUpperCase() + t.slice(1)}</option>`).join("")}</select></label>
          <label>Icon <input name="icon" maxlength="16" value="${esc(c?.icon || "•")}" placeholder="emoji"></label>
          <label>Colour <input name="color" type="color" value="${c?.color || "#6B7C75"}"></label>
        </div>`,
      onSubmit: async (fd) => { await api(c ? `/categories/${c.id}` : "/categories", { method: c ? "PUT" : "POST", body: fd }); toast(c ? "Changes saved" : "Category created"); renderCategories(); },
    });
    $("#add").onclick = () => form(null);
    app.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => form(cats.find((c) => c.id === +b.dataset.edit))));
    app.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => { if (await confirmDelete("category")) { await api(`/categories/${b.dataset.del}`, { method: "DELETE" }); toast("Category removed"); renderCategories(); } }));
    app.querySelectorAll("[data-restore]").forEach((b) => (b.onclick = async () => { await api(`/categories/${b.dataset.restore}/restore`, { method: "POST" }); renderCategories(); }));
  }

  // ---------- sources ----------
  async function renderSources() {
    const srcs = await api("/sources?include_archived=true"); S.srcs = srcs.filter((s) => !s.is_archived);
    shell("sources", `<h1>Payment sources</h1><p class="lede">Turn on balance tracking for accounts you want a running total on. Credit cards and UPI usually don't need it.</p>
      <div class="toolbar"><div class="grow"></div><button class="btn" id="add">New source</button></div>
      <table><thead><tr><th>Name</th><th>Kind</th><th class="r">Balance</th><th></th></tr></thead><tbody>
      ${srcs.map((s) => `<tr><td>${esc(s.name)}${s.is_archived ? `<span class="recur">archived</span>` : ""}</td><td class="muted">${KIND_LABEL[s.kind]}</td>
        <td class="r num ${s.balance !== null && Number(s.balance) < 0 ? "expense" : ""}">${s.track_balance ? money(s.balance, true) : `<span class="muted">—</span>`}</td>
        <td class="actions">${s.is_archived ? `<button class="btn secondary small" data-restore="${s.id}">Restore</button>` : `<button class="btn secondary small" data-edit="${s.id}">Edit</button> <button class="btn danger small" data-del="${s.id}">Delete</button>`}</td></tr>`).join("")}
      </tbody></table>`);
    const form = (s) => modal({
      title: s ? "Edit source" : "New source", submit: s ? "Save changes" : "Create source",
      body: `<label>Name <input name="name" required maxlength="80" value="${esc(s?.name || "")}"></label>
        <div class="row">
          <label>Kind <select name="kind">${Object.entries(KIND_LABEL).map(([k, l]) => `<option value="${k}" ${(s?.kind || "bank") === k ? "selected" : ""}>${l}</option>`).join("")}</select></label>
          <label>Opening balance <input name="opening_balance" type="number" step="0.01" value="${s?.opening_balance ?? 0}"></label>
        </div>
        <label class="check"><input type="checkbox" name="track_balance" ${s?.track_balance ? "checked" : ""}> Keep a running balance</label>`,
      onSubmit: async (fd) => { await api(s ? `/sources/${s.id}` : "/sources", { method: s ? "PUT" : "POST", body: { ...fd, opening_balance: Number(fd.opening_balance || 0) } }); toast(s ? "Changes saved" : "Source created"); renderSources(); },
    });
    $("#add").onclick = () => form(null);
    app.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => form(srcs.find((s) => s.id === +b.dataset.edit))));
    app.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => { if (await confirmDelete("source")) { await api(`/sources/${b.dataset.del}`, { method: "DELETE" }); toast("Source removed"); renderSources(); } }));
    app.querySelectorAll("[data-restore]").forEach((b) => (b.onclick = async () => { await api(`/sources/${b.dataset.restore}/restore`, { method: "POST" }); renderSources(); }));
  }

  // ---------- investments ----------
  async function renderInvestments() {
    const list = await api("/investments");
    const tot = list.reduce((a, h) => { a.i += Number(h.invested); a.v += Number(h.current_value ?? h.invested); return a; }, { i: 0, v: 0 });
    shell("investments", `<h1>Savings &amp; investments</h1><p class="lede">Log what you put in; update the current value whenever you check your statement.</p>
      ${list.length ? `<div class="figures">
        <div><div class="k">Contributed</div><div class="v num">${money(tot.i)}</div></div>
        <div><div class="k">Current value</div><div class="v num invest">${money(tot.v)}</div></div>
        <div><div class="k">Gain</div><div class="v num ${tot.v - tot.i < 0 ? "expense" : "income"}">${money(tot.v - tot.i, true)}</div></div></div>` : ""}
      <div class="toolbar" style="margin-top:18px"><div class="grow"></div><button class="btn" id="add">New holding</button></div>
      ${list.length ? list.map((h) => `<section class="holding">
        <header><span class="name">${esc(h.name)}</span><span class="kind">${INV_LABEL[h.kind]}${h.last_valued ? ` · valued ${fmtDate(h.last_valued)}` : ""}</span>
          <span style="flex:1"></span><button class="btn secondary small" data-entry="${h.id}">Add entry</button> <button class="btn secondary small" data-edit="${h.id}">Edit</button></header>
        <div class="nums"><div><span>Contributed</span><b class="num">${money(h.invested)}</b></div><div><span>Current value</span><b class="num invest">${h.current_value !== null ? money(h.current_value) : "—"}</b></div>
          ${h.current_value !== null ? `<div><span>Gain</span><b class="num ${Number(h.current_value) - Number(h.invested) < 0 ? "expense" : "income"}">${money(Number(h.current_value) - Number(h.invested), true)}</b></div>` : ""}</div>
        ${h.note ? `<p class="muted" style="margin:0 0 8px;font-size:13px">${esc(h.note)}</p>` : ""}
        ${h.entries.length ? `<details><summary>${h.entries.length} entries</summary><table><thead><tr><th>Date</th><th class="r">Contribution</th><th class="r">Value</th><th></th></tr></thead><tbody>
          ${h.entries.slice().reverse().map((e) => `<tr><td class="num">${fmtDate(e.date)} <span class="muted" style="font-size:12px">${e.date.slice(0, 4)}</span></td><td class="r num">${Number(e.contribution) ? money(e.contribution, true) : "—"}</td><td class="r num">${e.current_value !== null ? money(e.current_value) : "—"}</td><td class="actions"><button class="btn danger small" data-del-entry="${h.id}:${e.id}">Remove</button></td></tr>`).join("")}
        </tbody></table></details>` : `<p class="muted" style="font-size:13px">No entries yet.</p>`}
      </section>`).join("") : `<div class="empty">No holdings yet. Add a PPF, a mutual fund, an FD — anything you want to watch grow.</div>`}`);
    const form = (h) => modal({
      title: h ? "Edit holding" : "New holding", submit: h ? "Save changes" : "Create holding", danger: h ? "Delete" : null,
      body: `<label>Name <input name="name" required maxlength="120" value="${esc(h?.name || "")}" placeholder="e.g. PPF at SBI"></label>
        <label>Kind <select name="kind">${Object.entries(INV_LABEL).map(([k, l]) => `<option value="${k}" ${(h?.kind || "mutual_fund") === k ? "selected" : ""}>${l}</option>`).join("")}</select></label>
        <label>Note <input name="note" maxlength="500" value="${esc(h?.note || "")}" placeholder="optional"></label>`,
      onSubmit: async (fd, act) => {
        if (act === "danger") { if (await confirmDelete("holding")) { await api(`/investments/${h.id}`, { method: "DELETE" }); toast("Holding removed"); renderInvestments(); } return; }
        await api(h ? `/investments/${h.id}` : "/investments", { method: h ? "PUT" : "POST", body: { ...fd, note: fd.note || null } }); toast(h ? "Changes saved" : "Holding created"); renderInvestments();
      },
    });
    const entry = (h) => modal({
      title: `Add entry · ${h.name}`, submit: "Add entry",
      body: `<label>Date <input name="date" type="date" required value="${today()}"></label>
        <div class="row"><label>Contribution <input name="contribution" type="number" step="0.01" value="0" inputmode="decimal"></label>
        <label>Current value <input name="current_value" type="number" step="0.01" inputmode="decimal" placeholder="leave blank to skip"></label></div>
        <p class="muted" style="margin:0;font-size:13px">Contribution is money added (negative for a withdrawal). Current value is the total worth today, from your statement.</p>`,
      onSubmit: async (fd) => { await api(`/investments/${h.id}/entries`, { method: "POST", body: { date: fd.date, contribution: Number(fd.contribution || 0), current_value: fd.current_value === "" ? null : Number(fd.current_value) } }); toast("Entry added"); renderInvestments(); },
    });
    $("#add").onclick = () => form(null);
    app.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => form(list.find((h) => h.id === +b.dataset.edit))));
    app.querySelectorAll("[data-entry]").forEach((b) => (b.onclick = () => entry(list.find((h) => h.id === +b.dataset.entry))));
    app.querySelectorAll("[data-del-entry]").forEach((b) => (b.onclick = async () => { const [h, e] = b.dataset.delEntry.split(":"); await api(`/investments/${h}/entries/${e}`, { method: "DELETE" }); toast("Entry removed"); renderInvestments(); }));
  }

  // ---------- reports ----------
  const rep = { month: monthKey(new Date()) };
  async function renderReports() {
    const r = await api(`/reports/summary?month=${rep.month}`);
    const rows = (slices, total) => slices.length ? `<table><thead><tr><th>Category</th><th class="r">Entries</th><th class="r">Amount</th><th class="r">Share</th></tr></thead><tbody>
      ${slices.map((c) => `<tr><td><span class="chip"><span class="ic" style="background:${c.color}">${esc(c.icon)}</span>${esc(c.name)}</span></td><td class="r num">${c.count}</td><td class="r num">${money(c.total)}</td><td class="r num muted">${total ? (Number(c.total) / total * 100).toFixed(1) : 0}%</td></tr>`).join("")}
      <tr><td><b>Total</b></td><td class="r num">${slices.reduce((a, c) => a + c.count, 0)}</td><td class="r num"><b>${money(total)}</b></td><td></td></tr></tbody></table>` : `<p class="muted">Nothing here for this month.</p>`;
    shell("reports", `<h1>Monthly report</h1>
      <div class="toolbar">
        <div class="period"><button class="btn secondary small" data-nav="-1" aria-label="Previous month">‹</button><span class="month">${monthLabel(rep.month)}</span><button class="btn secondary small" data-nav="1" aria-label="Next month">›</button><input type="month" id="mpick" value="${rep.month}" aria-label="Pick month"></div>
        <div class="grow"></div>
        <a class="btn secondary" href="/api/reports/export.csv?month=${rep.month}" download>Download CSV</a>
        <a class="btn secondary" href="/api/reports/export.pdf?month=${rep.month}" download>Download PDF</a>
      </div>
      <div class="figures">
        <div><div class="k">Income</div><div class="v num income">${money(r.income)}</div></div>
        <div><div class="k">Expenses</div><div class="v num expense">${money(r.expense)}</div></div>
        <div><div class="k">Saved</div><div class="v num ${Number(r.net) < 0 ? "expense" : ""}">${money(r.net, true)}</div><div class="muted" style="font-size:13px">${r.transaction_count} entries · ${r.savings_rate.toFixed(0)}% savings rate</div></div>
      </div>
      <h2>Expenses by category</h2>${rows(r.expense_by_category, Number(r.expense))}
      <h2>Income by category</h2>${rows(r.income_by_category, Number(r.income))}`);
    app.querySelectorAll("[data-nav]").forEach((b) => (b.onclick = () => { rep.month = shiftMonth(rep.month, +b.dataset.nav); renderReports(); }));
    $("#mpick").onchange = (e) => { if (e.target.value) { rep.month = e.target.value; renderReports(); } };
  }

  // ---------- users (admin) ----------
  async function renderUsers() {
    const users = await api("/users");
    shell("users", `<h1>People</h1><p class="lede">Everyone here sees the same household ledger. There's no sign-up page; you add people yourself.</p>
      <div class="toolbar"><div class="grow"></div><button class="btn" id="add">Add person</button></div>
      <table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th></th></tr></thead><tbody>
      ${users.map((u) => `<tr><td>${esc(u.name)}${!u.is_active ? `<span class="recur">disabled</span>` : ""}</td><td class="muted">${esc(u.email)}</td><td class="muted">${u.is_admin ? "Admin" : "Member"}</td><td class="actions"><button class="btn secondary small" data-edit="${u.id}">Edit</button></td></tr>`).join("")}
      </tbody></table>`);
    const form = (u) => modal({
      title: u ? `Edit ${u.name}` : "Add person", submit: u ? "Save changes" : "Add person",
      body: `${u ? "" : `<label>Email <input name="email" type="email" required></label>`}
        <label>Name <input name="name" required maxlength="100" value="${esc(u?.name || "")}"></label>
        <label>${u ? "New password (leave blank to keep)" : "Password"} <input name="password" type="password" ${u ? "" : "required"} minlength="8" autocomplete="new-password"></label>
        <label class="check"><input type="checkbox" name="is_admin" ${u?.is_admin ? "checked" : ""} ${u?.id === S.user.id ? "disabled" : ""}> Can manage people</label>
        ${u && u.id !== S.user.id ? `<label class="check"><input type="checkbox" name="is_active" ${u.is_active ? "checked" : ""}> Account enabled</label>` : ""}`,
      onSubmit: async (fd) => {
        if (u) { const body = { name: fd.name, is_admin: fd.is_admin, is_active: fd.is_active }; if (fd.password) body.password = fd.password; if (u.id === S.user.id) { delete body.is_admin; delete body.is_active; } await api(`/users/${u.id}`, { method: "PATCH", body }); }
        else await api("/users", { method: "POST", body: fd });
        toast(u ? "Changes saved" : "Person added"); renderUsers();
      },
    });
    $("#add").onclick = () => form(null);
    app.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => form(users.find((u) => u.id === +b.dataset.edit))));
  }

  // ---------- account ----------
  function renderAccount() {
    shell("account", `<h1>Account</h1><p class="lede">Signed in as ${esc(S.user.name)} (${esc(S.user.email)}).</p>
      <h2>Change password</h2>
      <form id="pw" style="display:grid;gap:12px;max-width:380px">
        <label>Current password <input name="current_password" type="password" required autocomplete="current-password"></label>
        <label>New password <input name="new_password" type="password" required minlength="8" autocomplete="new-password"></label>
        <div class="err" aria-live="assertive"></div><div><button class="btn" type="submit">Update password</button></div>
      </form>
      <h2>Session</h2><p class="muted">You stay signed in for 7 days and the session extends while you use the app.</p>
      <button class="btn secondary" id="logout">Sign out</button>`);
    $("#pw").onsubmit = async (e) => { e.preventDefault(); const err = $("#pw .err"); err.textContent = ""; try { await api("/auth/password", { method: "POST", body: Object.fromEntries(new FormData(e.target)) }); e.target.reset(); toast("Password updated"); } catch (ex) { err.textContent = ex.message; } };
    $("#logout").onclick = async () => { await api("/auth/logout", { method: "POST" }); S.user = null; location.hash = ""; render(); };
  }

  // ---------- router ----------
  const VIEWS = { dashboard: renderDashboard, transactions: renderTransactions, categories: renderCategories, sources: renderSources, investments: renderInvestments, reports: renderReports, users: renderUsers, account: renderAccount };
  async function render() {
    Object.values(charts).forEach((c) => c?.destroy()); for (const k in charts) delete charts[k];
    if (!S.user) return renderLogin();
    const view = (location.hash.replace(/^#\//, "") || "dashboard").split("?")[0];
    const fn = VIEWS[view] || renderDashboard;
    try { await fn(); } catch (e) { shell(view, `<p class="err">${esc(e.message)}</p>`); }
    window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", render);

  (async () => {
    try { S.cfg = await api("/config"); document.title = S.cfg.app_name; } catch { /* keep defaults */ }
    try { S.user = await api("/auth/me"); await loadLookups(); } catch { S.user = null; }
    render();
  })();
})();
