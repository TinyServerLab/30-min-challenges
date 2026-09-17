import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";

const empty = { name: "", kind: "cash", running_balance: "" };
const KINDS = [
  ["cash", "Cash"],
  ["bank_account", "Bank Account"],
  ["credit_card", "Credit Card"],
  ["upi", "UPI"],
  ["wallet", "Wallet"],
];

export default function Sources() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(empty);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    setItems(await api.get("/sources"));
  }
  useEffect(() => { load().catch((e) => setError(e.message)); }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    const payload = {
      ...form,
      running_balance: form.running_balance === "" ? null : Number(form.running_balance),
    };
    try {
      if (editingId) await api.patch(`/sources/${editingId}`, payload);
      else await api.post("/sources", payload);
      setForm(empty);
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(id) {
    if (!confirm("Delete this payment source?")) return;
    try {
      await api.del(`/sources/${id}`);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Payment Sources</h2>
      {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</div>}

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-4 grid grid-cols-2 sm:grid-cols-4 gap-3 items-end">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Name</label>
          <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Kind</label>
          <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm">
            {KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Running balance (optional)</label>
          <input type="number" step="0.01" value={form.running_balance}
            onChange={(e) => setForm({ ...form, running_balance: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm" />
        </div>
        <div className="flex gap-2">
          <button type="submit" className="bg-slate-900 text-white rounded px-4 py-1.5 text-sm">{editingId ? "Save" : "Add"}</button>
          {editingId && (
            <button type="button" onClick={() => { setForm(empty); setEditingId(null); }} className="border border-slate-300 rounded px-4 py-1.5 text-sm">
              Cancel
            </button>
          )}
        </div>
      </form>

      <div className="bg-white rounded-lg shadow divide-y">
        {items.map((s) => (
          <div key={s.id} className="flex items-center justify-between px-4 py-2.5">
            <div className="text-sm">
              {s.name} <span className="text-xs text-slate-400">({s.kind.replace("_", " ")})</span>
            </div>
            <div className="flex items-center gap-4">
              {s.running_balance !== null && (
                <span className="text-sm text-slate-600">{Number(s.running_balance).toFixed(2)}</span>
              )}
              <div className="flex gap-3 text-xs">
                <button onClick={() => { setEditingId(s.id); setForm({ ...s, running_balance: s.running_balance ?? "" }); }} className="text-slate-500 hover:text-slate-900">Edit</button>
                <button onClick={() => handleDelete(s.id)} className="text-rose-500 hover:text-rose-700">Delete</button>
              </div>
            </div>
          </div>
        ))}
        {items.length === 0 && <p className="px-4 py-8 text-center text-slate-400 text-sm">No payment sources yet.</p>}
      </div>
    </div>
  );
}
