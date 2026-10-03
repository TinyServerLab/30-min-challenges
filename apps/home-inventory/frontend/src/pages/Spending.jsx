import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../core/api'
import { compactMoney, money, MONTHS } from '../core/format'
import { PageLoader, useToast } from '../components/ui'
import AssetRow from '../components/AssetRow'

const C_PURCHASE = '#2a78d6'   // categorical slot 1
const C_SERVICE = '#eb6834'    // categorical slot 2
const AXIS = { fontSize: 11, fill: '#64748b' }

function ChartTip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const total = payload.reduce((s, p) => s + Number(p.value || 0), 0)
  return (
    <div className="rounded-xl bg-white shadow-lg ring-1 ring-slate-200 px-3 py-2 text-xs">
      <div className="font-medium text-slate-800 mb-1">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex items-center gap-2 text-slate-600">
          <span className="w-2 h-2 rounded-sm" style={{ background: p.color }} />
          <span className="flex-1">{p.name}</span><span className="tabular-nums text-slate-800">{money(p.value)}</span>
        </div>
      ))}
      {payload.length > 1 && <div className="border-t border-slate-100 mt-1 pt-1 flex justify-between text-slate-800 font-medium"><span>Total</span><span className="tabular-nums">{money(total)}</span></div>}
    </div>
  )
}

export default function Spending() {
  const [year, setYear] = useState(new Date().getFullYear())
  const [d, setD] = useState(null)
  const [view, setView] = useState('chart')
  const toast = useToast()

  useEffect(() => { api('reports/spending', { params: { year } }).then(setD).catch((e) => toast(e.message, 'error')) }, [year, toast])
  if (!d) return <PageLoader />

  const monthly = d.monthly.map((m) => ({ label: MONTHS[m.month - 1], purchases: Number(m.purchases), services: Number(m.services) }))
  const catMax = Math.max(1, ...d.by_category.map((c) => Number(c.value)))

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Household spending</h1>
          <p className="text-sm text-slate-500">Purchases and repair costs you have recorded</p>
        </div>
        <select className="input w-28" value={year} onChange={(e) => setYear(Number(e.target.value))}>
          {d.years.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[['Total spent', d.totals.total], ['Purchases', d.totals.purchases], ['Repairs & service', d.totals.services]].map(([l, v]) => (
          <div key={l} className="card p-4"><div className="text-xs text-slate-500">{l}</div><div className="text-2xl font-semibold tabular-nums mt-1">{money(v)}</div></div>
        ))}
        <div className="card p-4"><div className="text-xs text-slate-500">Items bought</div><div className="text-2xl font-semibold tabular-nums mt-1">{d.totals.count}</div></div>
      </div>

      <section className="card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h2 className="font-semibold">Month by month, {d.year}</h2>
          <div className="flex items-center gap-4 text-xs text-slate-600">
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: C_PURCHASE }} />Purchases</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: C_SERVICE }} />Repairs &amp; service</span>
            <div className="flex rounded-lg border border-slate-200 overflow-hidden">
              {['chart', 'table'].map((v) => (
                <button key={v} onClick={() => setView(v)} className={`px-2.5 h-7 capitalize ${view === v ? 'bg-slate-800 text-white' : 'bg-white'}`}>{v}</button>
              ))}
            </div>
          </div>
        </div>
        {view === 'chart' ? (
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={monthly} margin={{ top: 4, right: 4, left: 0, bottom: 0 }} barCategoryGap="28%">
                <CartesianGrid vertical={false} stroke="#e2e8f0" strokeDasharray="0" />
                <XAxis dataKey="label" tick={AXIS} axisLine={false} tickLine={false} />
                <YAxis tick={AXIS} axisLine={false} tickLine={false} width={48} tickFormatter={compactMoney} />
                <Tooltip content={<ChartTip />} cursor={{ fill: '#f1f5f9' }} />
                <Bar dataKey="purchases" name="Purchases" stackId="a" fill={C_PURCHASE} stroke="#fff" strokeWidth={2} />
                <Bar dataKey="services" name="Repairs & service" stackId="a" fill={C_SERVICE} stroke="#fff" strokeWidth={2} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-slate-500 text-left"><tr><th className="py-1.5 font-medium">Month</th><th className="py-1.5 font-medium text-right">Purchases</th><th className="py-1.5 font-medium text-right">Repairs</th><th className="py-1.5 font-medium text-right">Total</th></tr></thead>
              <tbody className="divide-y divide-slate-100 tabular-nums">
                {monthly.map((m) => (
                  <tr key={m.label}><td className="py-1.5">{m.label}</td><td className="text-right">{money(m.purchases)}</td><td className="text-right">{money(m.services)}</td><td className="text-right font-medium">{money(m.purchases + m.services)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="grid lg:grid-cols-2 gap-5">
        <section className="card p-4">
          <h2 className="font-semibold mb-3">By category</h2>
          {d.by_category.length === 0 ? <p className="text-sm text-slate-500">No purchases in {d.year}</p> : (
            <ul className="space-y-3">
              {d.by_category.map((c) => (
                <li key={c.name}>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="text-slate-700">{c.name} <span className="text-slate-400 text-xs">· {c.count}</span></span>
                    <span className="font-medium tabular-nums">{money(c.value)}</span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full" style={{ width: `${(Number(c.value) / catMax) * 100}%`, background: c.color }} /></div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card p-4">
          <h2 className="font-semibold mb-3">Where you bought</h2>
          {d.by_vendor.length === 0 ? <p className="text-sm text-slate-500">No purchases in {d.year}</p> : (
            <table className="w-full text-sm">
              <tbody className="divide-y divide-slate-100">
                {d.by_vendor.map((v) => (
                  <tr key={v.name}><td className="py-2 text-slate-700">{v.name}</td><td className="py-2 text-right text-slate-400 text-xs">{v.count} item{v.count > 1 ? 's' : ''}</td><td className="py-2 text-right font-medium tabular-nums">{money(v.value)}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        {d.yearly.length > 1 && (
          <section className="card p-4">
            <h2 className="font-semibold mb-3">Purchases per year</h2>
            <div className="h-52">
              <ResponsiveContainer>
                <BarChart data={d.yearly.map((y) => ({ label: String(y.year), purchases: Number(y.value) }))} barCategoryGap="30%">
                  <CartesianGrid vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="label" tick={AXIS} axisLine={false} tickLine={false} />
                  <YAxis tick={AXIS} axisLine={false} tickLine={false} width={48} tickFormatter={compactMoney} />
                  <Tooltip content={<ChartTip />} cursor={{ fill: '#f1f5f9' }} />
                  <Bar dataKey="purchases" name="Purchases" fill={C_PURCHASE} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}
        {d.top_purchases.length > 0 && (
          <section className={`card overflow-hidden ${d.yearly.length > 1 ? '' : 'lg:col-span-2'}`}>
            <h2 className="font-semibold px-4 pt-4 pb-2">Biggest purchases in {d.year}</h2>
            <div className="divide-y divide-slate-100">{d.top_purchases.map((a) => <AssetRow key={a.id} a={a} showExpiry={false} />)}</div>
          </section>
        )}
      </div>
    </div>
  )
}
