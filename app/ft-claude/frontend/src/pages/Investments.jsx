import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";

const empty = {
  kind: "mutual_fund",
  label: "",
  contribution_amount: "",
  current_value: "",
  entry_date: new Date().toISOString().slice(0, 10),
  note: "",
};
const KINDS = [
  ["equity", "Equity"],
  ["mutual_fund", "Mutual Fund"],
  ["fd", "Fixed Deposit"],
  ["ppf", "PPF"],
  ["other", "Other"],
];

export default function Investments() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(empty);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    setItems(await api.get("/investments"));
  }
  useEffect(() => { load().catch((e) => setError(e.message)); }, []);

  const totalContribution = items.reduce((s, i) => s + Number(i.contribution_amount), 0);
  const totalCurrent = items.reduce((s, i) => s + Number(i.current_value), 0);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    const payload = {
      ...form,
      contribution_amount: Number(form.contribution_amount || 0),
      current_value: Number(form.current_value || 0),
    };
    try {
      if (editingId) await api.patch(`/investments/${editingId}`, payload);
      else await api.post("/investments", payload);
      setForm(empty);
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(id) {
    if (!confirm("Delete this investment entry?")) return;
    await api.del(`/investments/${id}`);
    await load();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Investments</h2>
        <div className="text-sm text-slate-500">
          Contributed <span className="font-medium text-slate-900">{totalContribution.toFixed(2)}</span> ·
          Current value <span className="font-medium text-slate-900">{totalCurrent.toFixed(2)}</span>
        </div>
      </div>

      {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</div>}

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-4 grid grid-cols-2 sm:grid-cols-6 gap-3 items-end">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Kind</label>
          <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm">
            {KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Label</label>
          <input required value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm" placeholder="e.g. Nifty 50 Index Fund" />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Contribution</label>
          <input type="number" step="0.01" value={form.contribution_amount}
            onChange={(e) => setForm({ ...form, contribution_amount: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Current value</label>
          <input type="number" step="0.01" value={form.current_value}
            onChange={(e) => setForm({ ...form, current_value: e.target.value })}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Date</label>
          <input type="date" required value={form.entry_date}
            onChange={(e) => setForm({ ...form, entry_date: e.target.value })}
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

      <div className="bg-white rounded-lg shadow overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b">
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Kind</th>
              <th className="px-3 py-2">Label</th>
              <th className="px-3 py-2 text-right">Contributed</th>
              <th className="px-3 py-2 text-right">Current value</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((i) => (
              <tr key={i.id} className="border-b last:border-0 hover:bg-slate-50">
                <td className="px-3 py-2">{i.entry_date}</td>
                <td className="px-3 py-2">{i.kind.replace("_", " ")}</td>
                <td className="px-3 py-2">{i.label}</td>
                <td className="px-3 py-2 text-right">{Number(i.contribution_amount).toFixed(2)}</td>
                <td className="px-3 py-2 text-right">{Number(i.current_value).toFixed(2)}</td>
                <td className="px-3 py-2 text-right whitespace-nowrap">
                  <button onClick={() => { setEditingId(i.id); setForm(i); }} className="text-slate-500 hover:text-slate-900 mr-3 text-xs">Edit</button>
                  <button onClick={() => handleDelete(i.id)} className="text-rose-500 hover:text-rose-700 text-xs">Delete</button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={6} className="px-3 py-8 text-center text-slate-400">No investment entries yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
