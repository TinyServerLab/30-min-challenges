import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";

const empty = { name: "", type: "expense", icon: "", color: "#64748b" };

export default function Categories() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(empty);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    setItems(await api.get("/categories"));
  }
  useEffect(() => { load().catch((e) => setError(e.message)); }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      if (editingId) await api.patch(`/categories/${editingId}`, form);
      else await api.post("/categories", form);
      setForm(empty);
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(id) {
    if (!confirm("Delete this category?")) return;
    try {
      await api.del(`/categories/${id}`);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Categories</h2>
      {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</div>}

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-4 grid grid-cols-2 sm:grid-cols-5 gap-3 items-end">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Name</label>
          <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Type</label>
          <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm">
            <option value="expense">Expense</option>
            <option value="income">Income</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Icon (emoji/label)</label>
          <input value={form.icon} onChange={(e) => setForm({ ...form, icon: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Color</label>
          <input type="color" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })}
            className="w-full h-9 border border-slate-300 rounded" />
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
        {items.map((c) => (
          <div key={c.id} className="flex items-center justify-between px-4 py-2.5">
            <div className="flex items-center gap-3">
              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: c.color }} />
              <span className="text-sm">{c.icon} {c.name}</span>
              <span className="text-xs text-slate-400">{c.type}</span>
            </div>
            <div className="flex gap-3 text-xs">
              <button onClick={() => { setEditingId(c.id); setForm(c); }} className="text-slate-500 hover:text-slate-900">Edit</button>
              <button onClick={() => handleDelete(c.id)} className="text-rose-500 hover:text-rose-700">Delete</button>
            </div>
          </div>
        ))}
        {items.length === 0 && <p className="px-4 py-8 text-center text-slate-400 text-sm">No categories yet.</p>}
      </div>
    </div>
  );
}
