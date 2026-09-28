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
  const [savingsTrend, setSavingsTrend] = useState([]);
  const [investmentTrend, setInvestmentTrend] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setError("");
    Promise.all([
      api.get(`/dashboard/summary?start=${start}&end=${end}`),
      api.get(`/dashboard/savings-trend?months=12`),
      api.get(`/dashboard/investment-trend?months=12`),
    ])
      .then(([s, savings, inv]) => {
        if (cancelled) return;
        setSummary(s);
        setSavingsTrend(savings.map((p) => ({ ...p, cumulative_savings: Number(p.cumulative_savings) })));
        setInvestmentTrend(
          inv.map((p) => ({
            ...p,
            cumulative_contribution: Number(p.cumulative_contribution),
            cumulative_current_value: Number(p.cumulative_current_value),
          }))
        );
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

  const hasInvestmentData = investmentTrend.some(
    (p) => p.cumulative_contribution !== 0 || p.cumulative_current_value !== 0
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-xl font-semibold">Dashboard</h2>
        <div className="flex flex-wrap items-center gap-2 text-sm">
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
          <h3 className="text-sm font-semibold text-slate-600 mb-2">Cash savings trend (12 months)</h3>
          <p className="text-xs text-slate-400 mb-2">Cumulative income minus expenses. Investments are tracked separately below.</p>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={savingsTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => Number(v).toFixed(2)} />
              <Line type="monotone" dataKey="cumulative_savings" name="Cumulative savings" stroke="#0f172a" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-sm font-semibold text-slate-600 mb-2">Investment growth (12 months)</h3>
        <p className="text-xs text-slate-400 mb-2">Contributed vs. current value, on its own timeline — not merged into cash savings.</p>
        {!hasInvestmentData ? (
          <p className="text-sm text-slate-400 py-8 text-center">No investment entries yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={investmentTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => Number(v).toFixed(2)} />
              <Legend />
              <Line type="monotone" dataKey="cumulative_contribution" name="Contributed" stroke="#0ea5e9" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="cumulative_current_value" name="Current value" stroke="#16a34a" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
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
