import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";

const today = () => new Date().toISOString().slice(0, 10);

const empty = {
  name: "",
  amount: "",
  billing_cycle: "monthly",
  next_due_date: today(),
  category_id: "",
  source_id: "",
  usage: "regular",
  note: "",
};

const CYCLES = [
  ["weekly", "Weekly"],
  ["monthly", "Monthly"],
  ["quarterly", "Quarterly"],
  ["yearly", "Yearly"],
];

const USAGE = [
  ["essential", "Essential"],
  ["regular", "Use regularly"],
  ["rarely", "Rarely use"],
  ["unused", "Don't use"],
];

const USAGE_TONE = {
  essential: "bg-sky-50 text-sky-700 border-sky-200",
  regular: "bg-emerald-50 text-emerald-700 border-emerald-200",
  rarely: "bg-amber-50 text-amber-700 border-amber-200",
  unused: "bg-rose-50 text-rose-700 border-rose-200",
};

const STATUS_TONE = {
  active: "text-emerald-600",
  paused: "text-amber-600",
  cancelled: "text-slate-400 line-through",
};

const fmt = (v) => Number(v || 0).toFixed(2);

function daysUntil(iso) {
  const d = new Date(iso + "T00:00:00");
  const t = new Date(today() + "T00:00:00");
  return Math.round((d - t) / 86400000);
}

function dueLabel(iso) {
  const n = daysUntil(iso);
  if (n < 0) return `overdue by ${-n}d`;
  if (n === 0) return "due today";
  return `in ${n}d`;
}

export default function Subscriptions() {
  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [categories, setCategories] = useState([]);
  const [sources, setSources] = useState([]);
  const [form, setForm] = useState(empty);
  const [editingId, setEditingId] = useState(null);
  const [showCancelled, setShowCancelled] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    const [subs, sum, cands, cats, srcs] = await Promise.all([
      api.get("/subscriptions"),
      api.get("/subscriptions/summary"),
      api.get("/subscriptions/candidates"),
      api.get("/categories"),
      api.get("/sources"),
    ]);
    setItems(subs);
    setSummary(sum);
    setCandidates(cands);
    setCategories(cats.filter((c) => c.type === "expense"));
    setSources(srcs);
  }
  useEffect(() => { load().catch((e) => setError(e.message)); }, []);

  function resetForm() {
    setForm({ ...empty, next_due_date: today() });
    setEditingId(null);
  }

  async function run(fn, successMsg = "") {
    setError("");
    setNotice("");
    try {
      await fn();
      await load();
      if (successMsg) setNotice(successMsg);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const payload = {
      ...form,
      amount: Number(form.amount),
      category_id: form.category_id ? Number(form.category_id) : null,
      source_id: form.source_id ? Number(form.source_id) : null,
    };
    await run(async () => {
      if (editingId) await api.patch(`/subscriptions/${editingId}`, payload);
      else await api.post("/subscriptions", payload);
      resetForm();
    });
  }

  function startEdit(s) {
    setEditingId(s.id);
    setForm({
      name: s.name,
      amount: s.amount,
      billing_cycle: s.billing_cycle,
      next_due_date: s.next_due_date,
      category_id: s.category_id ? String(s.category_id) : "",
      source_id: s.source_id ? String(s.source_id) : "",
      usage: s.usage,
      note: s.note || "",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function trackCandidate(c) {
    setEditingId(null);
    setForm({
      ...empty,
      name: c.name,
      amount: c.amount,
      billing_cycle: c.billing_cycle,
      next_due_date: c.suggested_next_due_date,
      category_id: String(c.category_id),
      source_id: String(c.source_id),
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const setStatus = (s, status) =>
    run(() => api.patch(`/subscriptions/${s.id}`, { status }), `${s.name} ${status === "active" ? "resumed" : status}.`);

  const markPaid = (s) =>
    run(() => api.post(`/subscriptions/${s.id}/pay`), `Logged ${fmt(s.amount)} for ${s.name} as an expense; next due date moved forward.`);

  async function handleDelete(s) {
    if (!confirm(`Delete "${s.name}"? Use Cancel instead to keep its history.`)) return;
    await run(() => api.del(`/subscriptions/${s.id}`));
  }

  const categoryName = (id) => categories.find((c) => c.id === id)?.name || "—";
  const visible = items.filter((s) => showCancelled || s.status !== "cancelled");
  const cancelledCount = items.filter((s) => s.status === "cancelled").length;

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Subscriptions</h2>

      {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</div>}
      {notice && <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-3 py-2">{notice}</div>}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card label="Active" value={summary?.active_count ?? "—"} />
        <Card label="Per month" value={summary ? fmt(summary.monthly_total) : "—"} tone="text-rose-600" />
        <Card label="Per year" value={summary ? fmt(summary.yearly_total) : "—"} tone="text-rose-600" />
        <Card
          label="Could save / month"
          value={summary ? fmt(summary.potential_monthly_savings) : "—"}
          tone="text-emerald-600"
          hint="Subscriptions you rarely or never use"
        />
      </div>

      {summary?.upcoming?.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-sm font-semibold text-slate-600 mb-2">Renewing in the next 30 days</h3>
          <div className="divide-y">
            {summary.upcoming.map((s) => (
              <div key={s.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <span>
                  {s.name} <span className="text-slate-400">· {s.next_due_date}</span>{" "}
                  <span className={daysUntil(s.next_due_date) < 0 ? "text-rose-600" : "text-slate-500"}>({dueLabel(s.next_due_date)})</span>
                </span>
                <span className="flex items-center gap-3">
                  <span className="font-medium">{fmt(s.amount)}</span>
                  <button onClick={() => markPaid(s)} className="text-xs border border-slate-300 rounded px-2 py-1 hover:bg-slate-50">Mark paid</button>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-4 grid grid-cols-2 sm:grid-cols-4 gap-3 items-end">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Name</label>
          <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="e.g. Netflix" className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Amount</label>
          <input type="number" step="0.01" min="0.01" required value={form.amount}
            onChange={(e) => setForm({ ...form, amount: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Billed</label>
          <select value={form.billing_cycle} onChange={(e) => setForm({ ...form, billing_cycle: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm">
            {CYCLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Next due</label>
          <input type="date" required value={form.next_due_date}
            onChange={(e) => setForm({ ...form, next_due_date: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Category</label>
          <select value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm">
            <option value="">None</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Paid from</label>
          <select value={form.source_id} onChange={(e) => setForm({ ...form, source_id: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm">
            <option value="">None</option>
            {sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">How much do you use it?</label>
          <select value={form.usage} onChange={(e) => setForm({ ...form, usage: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm">
            {USAGE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Note</label>
          <input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm" />
        </div>
        <div className="col-span-2 sm:col-span-4 flex gap-2">
          <button type="submit" className="bg-slate-900 text-white rounded px-4 py-1.5 text-sm">{editingId ? "Save" : "Add subscription"}</button>
          {(editingId || form.name) && (
            <button type="button" onClick={resetForm} className="border border-slate-300 rounded px-4 py-1.5 text-sm">Cancel</button>
          )}
        </div>
      </form>

      <div className="bg-white rounded-lg shadow overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b">
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2 text-right">Amount</th>
              <th className="px-3 py-2">Billed</th>
              <th className="px-3 py-2 text-right">Per month</th>
              <th className="px-3 py-2">Next due</th>
              <th className="px-3 py-2">Category</th>
              <th className="px-3 py-2">Usage</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {visible.map((s) => (
              <tr key={s.id} className="border-b last:border-0 hover:bg-slate-50">
                <td className="px-3 py-2">
                  {s.name}
                  {s.note && <div className="text-xs text-slate-400">{s.note}</div>}
                </td>
                <td className="px-3 py-2 text-right">{fmt(s.amount)}</td>
                <td className="px-3 py-2">{s.billing_cycle}</td>
                <td className="px-3 py-2 text-right">{fmt(s.monthly_cost)}</td>
                <td className="px-3 py-2 whitespace-nowrap">
                  {s.status === "cancelled" ? `cancelled ${s.cancelled_on || ""}` : s.next_due_date}
                </td>
                <td className="px-3 py-2">{categoryName(s.category_id)}</td>
                <td className="px-3 py-2">
                  <span className={`text-xs border rounded px-1.5 py-0.5 ${USAGE_TONE[s.usage]}`}>
                    {USAGE.find(([v]) => v === s.usage)?.[1]}
                  </span>
                </td>
                <td className={`px-3 py-2 ${STATUS_TONE[s.status]}`}>{s.status}</td>
                <td className="px-3 py-2 text-right whitespace-nowrap text-xs">
                  {s.status === "active" && (
                    <>
                      <button onClick={() => markPaid(s)} className="text-slate-500 hover:text-slate-900 mr-3">Paid</button>
                      <button onClick={() => setStatus(s, "paused")} className="text-slate-500 hover:text-slate-900 mr-3">Pause</button>
                    </>
                  )}
                  {s.status !== "active" && (
                    <button onClick={() => setStatus(s, "active")} className="text-slate-500 hover:text-slate-900 mr-3">Resume</button>
                  )}
                  {s.status !== "cancelled" && (
                    <button onClick={() => setStatus(s, "cancelled")} className="text-amber-600 hover:text-amber-800 mr-3">Cancel</button>
                  )}
                  <button onClick={() => startEdit(s)} className="text-slate-500 hover:text-slate-900 mr-3">Edit</button>
                  <button onClick={() => handleDelete(s)} className="text-rose-500 hover:text-rose-700">Delete</button>
                </td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr><td colSpan={9} className="px-3 py-8 text-center text-slate-400">No subscriptions yet.</td></tr>
            )}
          </tbody>
        </table>
        {cancelledCount > 0 && (
          <div className="px-3 py-2 border-t text-xs">
            <button onClick={() => setShowCancelled((v) => !v)} className="text-slate-500 hover:text-slate-900">
              {showCancelled ? "Hide" : "Show"} {cancelledCount} cancelled
            </button>
          </div>
        )}
      </div>

      {candidates.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-sm font-semibold text-slate-600">Possible subscriptions in your transactions</h3>
          <p className="text-xs text-slate-400 mb-2">
            Expenses with the same note, amount and category in at least two months of the last six.
          </p>
          <div className="divide-y">
            {candidates.map((c) => (
              <div key={`${c.name}-${c.amount}-${c.category_id}`} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <span>
                  {c.name} <span className="text-slate-400">· {fmt(c.amount)} {c.billing_cycle} · seen {c.occurrences}× · last {c.last_date}</span>
                </span>
                <button onClick={() => trackCandidate(c)} className="text-xs border border-slate-300 rounded px-2 py-1 hover:bg-slate-50">Track</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Card({ label, value, tone = "text-slate-900", hint }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`text-2xl font-semibold mt-1 ${tone}`}>{value}</p>
      {hint && <p className="text-xs text-slate-400 mt-1">{hint}</p>}
    </div>
  );
}
