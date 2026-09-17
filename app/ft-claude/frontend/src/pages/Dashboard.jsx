import React, { useEffect, useState } from "react";
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line, XAxis, YAxis, CartesianGrid,
} from "recharts";
import { api } from "../api/client.js";

function firstOfMonth(d = new Date()) {
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}
function lastOfMonth(d = new Date()) {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0).toISOString().slice(0, 10);
}

export default function Dashboard() {
  const [start, setStart] = useState(firstOfMonth());
  const [end, setEnd] = useState(lastOfMonth());
  const [summary, setSummary] = useState(null);
  const [trend, setTrend] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setError("");
    Promise.all([
      api.get(`/dashboard/summary?start=${start}&end=${end}`),
      api.get(`/dashboard/networth-trend?months=12`),
    ])
      .then(([s, t]) => {
        if (cancelled) return;
        setSummary(s);
        setTrend(t.map((p) => ({ ...p, net_worth: Number(p.net_worth) })));
      })
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [start, end]);

  const pieData =
    summary?.expense_by_category.map((c) => ({
      name: c.category_name,
      value: Number(c.total),
      color: c.color,
    })) || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-xl font-semibold">Dashboard</h2>
        <div className="flex items-center gap-2 text-sm">
          <label className="text-slate-500">From</label>
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="border border-slate-300 rounded px-2 py-1" />
          <label className="text-slate-500">To</label>
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="border border-slate-300 rounded px-2 py-1" />
        </div>
      </div>

      {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</div>}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <SummaryCard label="Income" value={summary?.total_income} tone="text-emerald-600" />
        <SummaryCard label="Expenses" value={summary?.total_expense} tone="text-rose-600" />
        <SummaryCard label="Net" value={summary?.net} tone="text-slate-900" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-sm font-semibold text-slate-600 mb-2">Expenses by category</h3>
          {pieData.length === 0 ? (
            <p className="text-sm text-slate-400 py-8 text-center">No expenses in this range.</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95} paddingAngle={2}>
                  {pieData.map((d, i) => (
                    <Cell key={i} fill={d.color || "#64748b"} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => v.toFixed(2)} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-sm font-semibold text-slate-600 mb-2">Net worth trend (12 months)</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => Number(v).toFixed(2)} />
              <Line type="monotone" dataKey="net_worth" stroke="#0f172a" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ label, value, tone }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`text-2xl font-semibold mt-1 ${tone}`}>
        {value === undefined || value === null ? "—" : Number(value).toFixed(2)}
      </p>
    </div>
  );
}
