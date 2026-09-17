import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";

const emptyForm = {
  amount: "",
  txn_date: new Date().toISOString().slice(0, 10),
  category_id: "",
  source_id: "",
  type: "expense",
  note: "",
  recurring: false,
};

export default function Transactions() {
  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [sources, setSources] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    const [txns, cats, srcs] = await Promise.all([
      api.get("/transactions?limit=200"),
      api.get("/categories"),
      api.get("/sources"),
    ]);
    setItems(txns);
    setCategories(cats);
    setSources(srcs);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);

  const categoriesForType = categories.filter((c) => c.type === form.type);

  function resetForm() {
    setForm(emptyForm);
    setEditingId(null);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    const payload = {
      ...form,
      amount: Number(form.amount),
      category_id: Number(form.category_id),
      source_id: Number(form.source_id),
    };
    try {
      if (editingId) {
        await api.patch(`/transactions/${editingId}`, payload);
      } else {
        await api.post("/transactions", payload);
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  function startEdit(t) {
    setEditingId(t.id);
    setForm({
      amount: t.amount,
      txn_date: t.txn_date,
      category_id: String(t.category_id),
      source_id: String(t.source_id),
      type: t.type,
      note: t.note || "",
      recurring: t.recurring,
    });
  }

  async function handleDelete(id) {
    if (!confirm("Delete this transaction?")) return;
    await api.del(`/transactions/${id}`);
    await load();
  }

  const categoryName = (id) => categories.find((c) => c.id === id)?.name || "—";
  const sourceName = (id) => sources.find((s) => s.id === id)?.name || "—";

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Transactions</h2>

      {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</div>}

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-4 grid grid-cols-2 sm:grid-cols-4 gap-3 items-end">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Type</label>
          <select
            value={form.type}
            onChange={(e) => setForm({ ...form, type: e.target.value, category_id: "" })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
          >
            <option value="expense">Expense</option>
            <option value="income">Income</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Amount</label>
          <input
            type="number" step="0.01" required min="0.01"
            value={form.amount}
            onChange={(e) => setForm({ ...form, amount: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Date</label>
          <input
            type="date" required
            value={form.txn_date}
            onChange={(e) => setForm({ ...form, txn_date: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Category</label>
          <select
            required value={form.category_id}
            onChange={(e) => setForm({ ...form, category_id: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
          >
            <option value="" disabled>Choose…</option>
            {categoriesForType.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Source</label>
          <select
            required value={form.source_id}
            onChange={(e) => setForm({ ...form, source_id: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
          >
            <option value="" disabled>Choose…</option>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
        <div className="col-span-2">
          <label className="block text-xs text-slate-500 mb-1">Note</label>
          <input
            type="text" value={form.note}
            onChange={(e) => setForm({ ...form, note: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
          />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox" checked={form.recurring}
            onChange={(e) => setForm({ ...form, recurring: e.target.checked })}
          />
          Recurring
        </label>
        <div className="flex gap-2">
          <button type="submit" className="bg-slate-900 text-white rounded px-4 py-1.5 text-sm">
            {editingId ? "Save" : "Add"}
          </button>
          {editingId && (
            <button type="button" onClick={resetForm} className="border border-slate-300 rounded px-4 py-1.5 text-sm">
              Cancel
            </button>
          )}
        </div>
      </form>

      <div className="bg-white rounded-lg shadow overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b">
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Category</th>
              <th className="px-3 py-2">Source</th>
              <th className="px-3 py-2 text-right">Amount</th>
              <th className="px-3 py-2">Note</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((t) => (
              <tr key={t.id} className="border-b last:border-0 hover:bg-slate-50">
                <td className="px-3 py-2">{t.txn_date}</td>
                <td className="px-3 py-2">
                  <span className={t.type === "income" ? "text-emerald-600" : "text-rose-600"}>{t.type}</span>
                </td>
                <td className="px-3 py-2">{categoryName(t.category_id)}</td>
                <td className="px-3 py-2">{sourceName(t.source_id)}</td>
                <td className="px-3 py-2 text-right">{Number(t.amount).toFixed(2)}</td>
                <td className="px-3 py-2 text-slate-500">{t.note}</td>
                <td className="px-3 py-2 text-right whitespace-nowrap">
                  <button onClick={() => startEdit(t)} className="text-slate-500 hover:text-slate-900 mr-3 text-xs">Edit</button>
                  <button onClick={() => handleDelete(t.id)} className="text-rose-500 hover:text-rose-700 text-xs">Delete</button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-8 text-center text-slate-400">No transactions yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
