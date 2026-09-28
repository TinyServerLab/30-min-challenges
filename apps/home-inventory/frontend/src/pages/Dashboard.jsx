import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Boxes, Camera, IndianRupee, ShieldAlert, ShieldCheck, ShieldX } from 'lucide-react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { api } from '../core/api'
import { useAuth } from '../core/auth'
import { compactMoney, money } from '../core/format'
import { Empty, PageLoader, StatCard, useToast } from '../components/ui'
import AssetRow from '../components/AssetRow'

export default function Dashboard() {
  const [d, setD] = useState(null)
  const { user } = useAuth()
  const nav = useNavigate()
  const toast = useToast()

  useEffect(() => { api('dashboard').then(setD).catch((e) => toast(e.message, 'error')) }, [toast])
  if (!d) return <PageLoader />

  const c = d.counts
  const hello = new Date().getHours() < 12 ? 'Good morning' : new Date().getHours() < 17 ? 'Good afternoon' : 'Good evening'

  if (c.assets === 0 && d.recent.length === 0) {
    return (
      <div className="card mt-4">
        <Empty icon={Camera} title={`${hello}, ${user.display_name}`}
          action={<button className="btn-primary" onClick={() => nav('/assets/new')}><Camera size={18} /> Add your first invoice</button>}>
          Snap a photo of a bill or upload the PDF. The details get filled in for you, and you get a reminder before the warranty runs out.
        </Empty>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">{hello}, {user.display_name}</p>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Your home at a glance</h1>
        </div>
        <button className="btn-primary hidden sm:inline-flex" onClick={() => nav('/assets/new')}><Camera size={18} /> Add invoice</button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Assets tracked" value={c.assets} icon={Boxes} tone="brand" onClick={() => nav('/assets')}
          sub={`${compactMoney(d.value.total)} total value`} />
        <StatCard label="Under warranty" value={c.under_warranty} icon={ShieldCheck} tone="green" onClick={() => nav('/assets?warranty=active')}
          sub={`${compactMoney(d.value.covered)} covered`} />
        <StatCard label={`Expiring ≤ ${d.expiring_window_days} days`} value={c.expiring_soon} icon={ShieldAlert} tone="amber"
          onClick={() => nav('/assets?warranty=expiring')} sub={c.expiring_soon ? 'Check these soon' : 'Nothing urgent'} />
        <StatCard label="Out of warranty" value={c.expired} icon={ShieldX} tone="red" onClick={() => nav('/assets?warranty=expired')}
          sub={c.no_warranty ? `${c.no_warranty} never had one` : 'Still in use'} />
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <section className="card lg:col-span-2 overflow-hidden">
          <div className="flex items-center justify-between px-4 pt-4 pb-2">
            <h2 className="font-semibold">Warranties ending in the next 90 days</h2>
            <Link to="/assets?sort=expiry&order=asc&warranty=active" className="text-sm text-brand-700 hover:underline">All</Link>
          </div>
          {d.upcoming.length ? (
            <div className="divide-y divide-slate-100">{d.upcoming.map((a) => <AssetRow key={a.id} a={a} />)}</div>
          ) : (
            <p className="px-4 pb-6 pt-2 text-sm text-slate-500">No warranties end in the next 90 days.</p>
          )}
          {d.recently_expired.length > 0 && (
            <>
              <div className="px-4 pt-4 pb-2 text-xs font-medium text-slate-500 uppercase tracking-wide border-t border-slate-100">Expired recently</div>
              <div className="divide-y divide-slate-100">{d.recently_expired.map((a) => <AssetRow key={a.id} a={a} />)}</div>
            </>
          )}
        </section>

        <section className="card p-4">
          <div className="flex items-center justify-between mb-1">
            <h2 className="font-semibold">Value by category</h2>
            <IndianRupee size={16} className="text-slate-400" />
          </div>
          {d.by_category.length ? (
            <>
              <div className="h-48">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={d.by_category.map((x) => ({ ...x, value: Number(x.value) }))} dataKey="value" nameKey="name"
                      innerRadius={52} outerRadius={80} paddingAngle={2} stroke="#fff" strokeWidth={2} isAnimationActive={false}>
                      {d.by_category.map((x) => <Cell key={x.name} fill={x.color} />)}
                    </Pie>
                    <Tooltip formatter={(v) => money(v)} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="space-y-1.5 mt-2">
                {d.by_category.map((x) => (
                  <li key={x.name} className="flex items-center gap-2 text-sm">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ background: x.color }} />
                    <span className="flex-1 truncate text-slate-600">{x.name}</span>
                    <span className="text-slate-400 text-xs">{x.count}</span>
                    <span className="tabular-nums font-medium w-20 text-right">{compactMoney(x.value)}</span>
                  </li>
                ))}
              </ul>
            </>
          ) : <p className="text-sm text-slate-500">No data yet</p>}
        </section>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <section className="card overflow-hidden lg:col-span-2">
          <div className="flex items-center justify-between px-4 pt-4 pb-2">
            <h2 className="font-semibold">Recently added</h2>
            <Link to="/assets?sort=created" className="text-sm text-brand-700 hover:underline">View all</Link>
          </div>
          <div className="divide-y divide-slate-100">{d.recent.map((a) => <AssetRow key={a.id} a={a} showExpiry={false} />)}</div>
        </section>
        <section className="card p-4 space-y-3">
          <h2 className="font-semibold">Spending</h2>
          <div>
            <div className="text-xs text-slate-500">Purchases this year</div>
            <div className="text-2xl font-semibold tabular-nums">{money(d.value.this_year)}</div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Repairs &amp; service this year</div>
            <div className="text-lg font-semibold tabular-nums">{money(d.value.service_this_year)}</div>
          </div>
          <Link to="/spending" className="btn-secondary w-full">Open spending report</Link>
        </section>
      </div>
    </div>
  )
}
