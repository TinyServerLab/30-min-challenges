import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";

const fmt = (v) => Number(v || 0).toFixed(2);
const pct = (v) => (v === null || v === undefined ? "—" : `${Number(v).toFixed(1)}%`);

export default function SavingsPlan() {
  const [months, setMonths] = useState(3);
  const [cutPct, setCutPct] = useState(20);
  const [plan, setPlan] = useState(null);
  const [capDrafts, setCapDrafts] = useState({});
  const [error, setError] = useState("");

  async function load() {
    const p = await api.get(`/savings/plan?months=${months}&cut_pct=${cutPct}`);
    setPlan(p);
    setCapDrafts({});
  }
  useEffect(() => { load().catch((e) => setError(e.message)); }, [months, cutPct]);

  async function run(fn) {
    setError("");
    try {
      await fn();
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  const saveCap = (c) => {
    const value = Number(capDrafts[c.category_id] ?? c.suggested_cap);
    if (!(value > 0)) {
      setError(`Enter a cap above 0 for ${c.category_name}.`);
      return;
    }
    run(() => api.put(`/savings/caps/${c.category_id}`, { monthly_limit: value }));
  };
  const removeCap = (c) => run(() => api.del(`/savings/caps/${c.category_id}`));
  const cancelSub = (s) => run(() => api.patch(`/subscriptions/${s.subscription_id}`, { status: "cancelled" }));

  const discretionary = plan?.categories.filter((c) => !c.essential) || [];
  const essentials = plan?.categories.filter((c) => c.essential) || [];
  const capped = plan?.categories.filter((c) => c.cap !== null) || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-xl font-semibold">Savings plan</h2>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <label className="text-slate-500">Based on last</label>
          <select value={months} onChange={(e) => setMonths(Number(e.target.value))} className="border border-slate-300 rounded px-2 py-1">
            {[1, 3, 6, 12].map((m) => <option key={m} value={m}>{m} month{m > 1 ? "s" : ""}</option>)}
          </select>
          <label className="text-slate-500">Trim discretionary by</label>
          <select value={cutPct} onChange={(e) => setCutPct(Number(e.target.value))} className="border border-slate-300 rounded px-2 py-1">
            {[10, 20, 30, 50].map((p) => <option key={p} value={p}>{p}%</option>)}
          </select>
        </div>
      </div>

      {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</div>}

      {plan && (
        <>
          <p className="text-xs text-slate-400">
            Averages from {plan.window_start} to {plan.window_end} (full months only).
          </p>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Card label="Avg income / month" value={fmt(plan.avg_monthly_income)} tone="text-emerald-600" />
            <Card label="Avg spending / month" value={fmt(plan.avg_monthly_expense)} tone="text-rose-600" />
            <Card label="Savings rate" value={pct(plan.current_savings_rate)}
              hint={plan.projected_savings_rate !== null ? `→ ${pct(plan.projected_savings_rate)} with this plan` : "Add income to see a rate"} />
            <Card label="Plan saves / month" value={fmt(plan.total_monthly_savings)} tone="text-emerald-600"
              hint={`${fmt(plan.total_yearly_savings)} a year`} />
          </div>

          <Section
            title="1. Cancel subscriptions you don't use"
            subtitle={`Active subscriptions marked "rarely use" or "don't use". Saves ${fmt(plan.subscription_savings)} / month.`}
          >
            {plan.cancel_subscriptions.length === 0 ? (
              <p className="text-sm text-slate-400 py-4 text-center">
                Nothing flagged. Rate how much you use each one on the <Link to="/subscriptions" className="underline">Subscriptions</Link> page.
              </p>
            ) : (
              <div className="divide-y">
                {plan.cancel_subscriptions.map((s) => (
                  <div key={s.subscription_id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                    <span>
                      {s.name} <span className="text-slate-400">· {s.usage === "unused" ? "not used" : "rarely used"}</span>
                    </span>
                    <span className="flex items-center gap-3">
                      <span className="text-emerald-600 font-medium">+{fmt(s.monthly_cost)} / mo</span>
                      <button onClick={() => cancelSub(s)} className="text-xs border border-slate-300 rounded px-2 py-1 hover:bg-slate-50">Mark cancelled</button>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Section>

          <Section
            title={`2. Trim discretionary spending`}
            subtitle={`Suggested cap is your average minus ${plan.cut_pct}% (excluding subscriptions already counted above). Adopt a cap to track it each month. Saves ${fmt(plan.category_savings)} / month.`}
          >
            {discretionary.length === 0 ? (
              <p className="text-sm text-slate-400 py-4 text-center">
                No discretionary spending in this period. Mark categories like Dining Out or Shopping as non-essential on the <Link to="/categories" className="underline">Categories</Link> page.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-slate-500 border-b">
                      <th className="px-3 py-2">Category</th>
                      <th className="px-3 py-2 text-right">Avg / month</th>
                      <th className="px-3 py-2 text-right">Suggested cap</th>
                      <th className="px-3 py-2">Your cap</th>
                      <th className="px-3 py-2 text-right">Saves / month</th>
                    </tr>
                  </thead>
                  <tbody>
                    {discretionary.map((c) => (
                      <tr key={c.category_id} className="border-b last:border-0">
                        <td className="px-3 py-2">
                          <span className="inline-block w-2.5 h-2.5 rounded-full mr-2" style={{ backgroundColor: c.color }} />
                          {c.category_name}
                        </td>
                        <td className="px-3 py-2 text-right">{fmt(c.avg_monthly)}</td>
                        <td className="px-3 py-2 text-right text-slate-500">{fmt(c.suggested_cap)}</td>
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-2">
                            <input
                              type="number" step="0.01" min="0.01"
                              value={capDrafts[c.category_id] ?? c.cap ?? c.suggested_cap ?? ""}
                              onChange={(e) => setCapDrafts({ ...capDrafts, [c.category_id]: e.target.value })}
                              className="w-24 border border-slate-300 rounded px-2 py-1 text-sm"
                            />
                            <button onClick={() => saveCap(c)} className="text-xs border border-slate-300 rounded px-2 py-1 hover:bg-slate-50">
                              {c.cap === null ? "Adopt" : "Update"}
                            </button>
                            {c.cap !== null && (
                              <button onClick={() => removeCap(c)} className="text-xs text-rose-500 hover:text-rose-700">Remove</button>
                            )}
                          </div>
                        </td>
                        <td className="px-3 py-2 text-right text-emerald-600 font-medium">{fmt(c.suggested_saving)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          {capped.length > 0 && (
            <Section title="This month vs. your caps" subtitle="Spending so far this month in each capped category.">
              <div className="space-y-3">
                {capped.map((c) => {
                  const used = Number(c.this_month) / Number(c.cap);
                  const bar = used > 1 ? "bg-rose-500" : used > 0.8 ? "bg-amber-500" : "bg-emerald-500";
                  return (
                    <div key={c.category_id}>
                      <div className="flex justify-between text-sm mb-1">
                        <span>{c.category_name}</span>
                        <span className={used > 1 ? "text-rose-600 font-medium" : "text-slate-500"}>
                          {fmt(c.this_month)} / {fmt(c.cap)}
                          {used > 1 && ` · over by ${fmt(Number(c.this_month) - Number(c.cap))}`}
                        </span>
                      </div>
                      <div className="h-2 bg-slate-100 rounded">
                        <div className={`h-2 rounded ${bar}`} style={{ width: `${Math.min(used, 1) * 100}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Section>
          )}

          {essentials.length > 0 && (
            <Section title="Essentials (not targeted)" subtitle="Shown for context. Change what counts as essential on the Categories page.">
              <div className="divide-y">
                {essentials.map((c) => (
                  <div key={c.category_id} className="flex justify-between py-2 text-sm">
                    <span>
                      <span className="inline-block w-2.5 h-2.5 rounded-full mr-2" style={{ backgroundColor: c.color }} />
                      {c.category_name}
                    </span>
                    <span className="text-slate-500">{fmt(c.avg_monthly)} / mo</span>
                  </div>
                ))}
              </div>
            </Section>
          )}
        </>
      )}
    </div>
  );
}

function Section({ title, subtitle, children }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-semibold text-slate-600">{title}</h3>
      {subtitle && <p className="text-xs text-slate-400 mb-3">{subtitle}</p>}
      {children}
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
