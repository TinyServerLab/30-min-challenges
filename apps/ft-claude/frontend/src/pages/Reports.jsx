import React, { useState } from "react";
import { api } from "../api/client.js";

function firstOfMonth(d = new Date()) {
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}
function lastOfMonth(d = new Date()) {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0).toISOString().slice(0, 10);
}

export default function Reports() {
  const [start, setStart] = useState(firstOfMonth());
  const [end, setEnd] = useState(lastOfMonth());
  const [summary, setSummary] = useState(null);
  const [breakdown, setBreakdown] = useState([]);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(false);

  async function runReport() {
    setError("");
    try {
      const y = Number(start.slice(0, 4));
      const m = Number(start.slice(5, 7));
      const [s, b] = await Promise.all([
        api.get(`/reports/monthly-summary?year=${y}&month=${m}`),
        api.get(`/reports/category-breakdown?start=${start}&end=${end}&type=expense`),
      ]);
      setSummary(s);
      setBreakdown(b);
    } catch (err) {
      setError(err.message);
    }
  }

  async function download(format) {
    setDownloading(true);
    setError("");
    try {
      const res = await api.raw(`/reports/export?start=${start}&end=${end}&format=${format}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `transactions_${start}_to_${end}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Reports</h2>

      <div className="bg-white rounded-lg shadow p-4 flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs text-slate-500 mb-1">From</label>
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="border border-slate-300 rounded px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">To</label>
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="border border-slate-300 rounded px-2 py-1.5 text-sm" />
        </div>
        <button onClick={runReport} className="bg-slate-900 text-white rounded px-4 py-1.5 text-sm">Run report</button>
        <button onClick={() => download("csv")} disabled={downloading} className="border border-slate-300 rounded px-4 py-1.5 text-sm">Export CSV</button>
        <button onClick={() => download("pdf")} disabled={downloading} className="border border-slate-300 rounded px-4 py-1.5 text-sm">Export PDF</button>
      </div>

      {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</div>}

      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <SummaryCard label="Income" value={summary.total_income} tone="text-emerald-600" />
          <SummaryCard label="Expenses" value={summary.total_expense} tone="text-rose-600" />
          <SummaryCard label="Net" value={summary.net} tone="text-slate-900" />
        </div>
      )}

      {breakdown.length > 0 && (
        <div className="bg-white rounded-lg shadow divide-y">
          {breakdown.map((b) => (
            <div key={b.category_id} className="flex items-center justify-between px-4 py-2.5 text-sm">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: b.color }} />
                {b.category_name}
              </div>
              <span>{Number(b.total).toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value, tone }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`text-2xl font-semibold mt-1 ${tone}`}>{Number(value).toFixed(2)}</p>
    </div>
  );
}
