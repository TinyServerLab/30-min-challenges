import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Boxes, Download, Plus, Search, SlidersHorizontal } from 'lucide-react'
import { api, apiUrl, thumbUrl } from '../lib/api'
import { fmtDate, money, STATUS_LABEL } from '../lib/format'
import { CategoryIcon, Empty, PageLoader, Spinner, WarrantyBadge, useToast } from '../components/ui'
import AssetRow from '../components/AssetRow'

const WARRANTY_OPTS = [['', 'Any warranty'], ['active', 'Under warranty'], ['expiring', 'Expiring soon'], ['expired', 'Expired'], ['none', 'No warranty']]
const SORT_OPTS = [['purchase_date:desc', 'Newest purchase'], ['purchase_date:asc', 'Oldest purchase'], ['expiry:asc', 'Warranty ending first'],
  ['price:desc', 'Price: high to low'], ['price:asc', 'Price: low to high'], ['name:asc', 'Name A–Z'], ['created:desc', 'Recently added']]

export default function Assets() {
  const [sp, setSp] = useSearchParams()
  const [data, setData] = useState(null)
  const [cats, setCats] = useState([])
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState(sp.get('q') || '')
  const [showFilters, setShowFilters] = useState(false)
  const nav = useNavigate()
  const toast = useToast()

  const params = useMemo(() => ({
    q: sp.get('q') || '', category_id: sp.get('category_id') || '', warranty: sp.get('warranty') || '',
    status: sp.get('status') || 'current', sort: sp.get('sort') || 'purchase_date',
    order: sp.get('order') || 'desc', page: sp.get('page') || '1', page_size: 50,
  }), [sp])

  const set = (patch) => {
    const n = new URLSearchParams(sp)
    Object.entries(patch).forEach(([k, v]) => (v === undefined || v === null || v === '' ? n.delete(k) : n.set(k, v)))
    if (!('page' in patch)) n.delete('page')
    setSp(n, { replace: true })
  }

  useEffect(() => { api('categories').then(setCats).catch(() => {}) }, [])
  useEffect(() => {
    setLoading(true)
    api('assets', { params }).then(setData).catch((e) => toast(e.message, 'error')).finally(() => setLoading(false))
  }, [params, toast])

  // debounce search box
  useEffect(() => {
    const t = setTimeout(() => { if (q !== (sp.get('q') || '')) set({ q }) }, 300)
    return () => clearTimeout(t)
  }, [q]) // eslint-disable-line react-hooks/exhaustive-deps

  const activeFilters = ['category_id', 'warranty'].filter((k) => sp.get(k)).length + (sp.get('status') && sp.get('status') !== 'current' ? 1 : 0)
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const exportHref = apiUrl('assets/export.csv', { ...params, page: undefined, page_size: undefined, sort: undefined, order: undefined })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Assets</h1>
          {data && <p className="text-sm text-slate-500">{data.total} item{data.total === 1 ? '' : 's'} · {money(data.total_value)}</p>}
        </div>
        <div className="flex gap-2">
          <a className="btn-secondary hidden sm:inline-flex" href={exportHref}><Download size={16} /> CSV</a>
          <button className="btn-primary" onClick={() => nav('/assets/new')}><Plus size={18} /> <span className="hidden sm:inline">Add asset</span></button>
        </div>
      </div>

      <div className="card p-3 space-y-3">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input className="input pl-9" placeholder="Search name, brand, model, serial, store…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <button className={`btn-secondary sm:hidden relative ${activeFilters ? 'border-brand-500 text-brand-700' : ''}`} onClick={() => setShowFilters((s) => !s)}>
            <SlidersHorizontal size={16} />{activeFilters > 0 && <span className="text-xs">{activeFilters}</span>}
          </button>
        </div>
        <div className={`${showFilters ? 'grid' : 'hidden'} sm:grid grid-cols-2 sm:grid-cols-4 gap-2`}>
          <select className="input" value={params.category_id} onChange={(e) => set({ category_id: e.target.value })}>
            <option value="">All categories</option>
            {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select className="input" value={params.warranty} onChange={(e) => set({ warranty: e.target.value })}>
            {WARRANTY_OPTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <select className="input" value={params.status} onChange={(e) => set({ status: e.target.value === 'current' ? '' : e.target.value })}>
            <option value="current">In use / in repair</option>
            <option value="all">All statuses</option>
            {Object.entries(STATUS_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <select className="input" value={`${params.sort}:${params.order}`} onChange={(e) => { const [s, o] = e.target.value.split(':'); set({ sort: s, order: o }) }}>
            {SORT_OPTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
      </div>

      {!data ? <PageLoader /> : data.items.length === 0 ? (
        <div className="card">
          <Empty icon={Boxes} title={params.q || activeFilters ? 'Nothing matches' : 'No assets yet'}
            action={<button className="btn-primary" onClick={() => nav('/assets/new')}><Plus size={18} /> Add asset</button>}>
            {params.q || activeFilters ? 'Try a different search or clear the filters.' : 'Add your first purchase with its invoice.'}
          </Empty>
        </div>
      ) : (
        <div className={`card overflow-hidden transition-opacity ${loading ? 'opacity-60' : ''}`}>
          {/* mobile list */}
          <div className="sm:hidden divide-y divide-slate-100">{data.items.map((a) => <AssetRow key={a.id} a={a} />)}</div>
          {/* desktop table */}
          <table className="hidden sm:table w-full text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500 text-left">
              <tr>
                <th className="font-medium px-4 py-2.5">Item</th>
                <th className="font-medium px-4 py-2.5 hidden md:table-cell">Purchased</th>
                <th className="font-medium px-4 py-2.5 text-right">Price</th>
                <th className="font-medium px-4 py-2.5">Warranty</th>
                <th className="font-medium px-4 py-2.5 hidden xl:table-cell">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((a) => (
                <tr key={a.id} className="hover:bg-slate-50 cursor-pointer" onClick={() => nav(`/assets/${a.id}`)}>
                  <td className="px-4 py-3">
                    <Link to={`/assets/${a.id}`} className="flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
                      {a.thumb_attachment_id
                        ? <img src={thumbUrl(a.thumb_attachment_id)} alt="" loading="lazy" className="w-10 h-10 rounded-xl object-cover bg-slate-100" />
                        : <CategoryIcon icon={a.category_icon} color={a.category_color} />}
                      <div className="min-w-0">
                        <div className="font-medium text-slate-900 truncate max-w-[18rem]">{a.name}</div>
                        <div className="text-xs text-slate-500 truncate max-w-[18rem]">{[a.brand, a.model, a.category_name].filter(Boolean).join(' · ')}</div>
                      </div>
                    </Link>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    <div>{fmtDate(a.purchase_date)}</div>
                    <div className="text-xs text-slate-500 truncate max-w-[10rem]">{a.vendor}</div>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums font-medium">{money(a.purchase_price, a.currency)}</td>
                  <td className="px-4 py-3">
                    <WarrantyBadge state={a.warranty_state} days={a.days_left} />
                    {a.effective_expiry_date && <div className="text-[11px] text-slate-500 mt-1">until {fmtDate(a.effective_expiry_date)}</div>}
                  </td>
                  <td className="px-4 py-3 hidden xl:table-cell text-slate-600">{STATUS_LABEL[a.status]}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {pages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100 text-sm">
              <button className="btn-secondary btn-sm" disabled={data.page <= 1} onClick={() => set({ page: data.page - 1 })}>Previous</button>
              <span className="text-slate-500 flex items-center gap-2">{loading && <Spinner className="w-4 h-4" />}Page {data.page} of {pages}</span>
              <button className="btn-secondary btn-sm" disabled={data.page >= pages} onClick={() => set({ page: data.page + 1 })}>Next</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
