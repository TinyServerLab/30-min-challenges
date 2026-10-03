import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Pencil, Phone, Plus, Trash2, Wrench } from 'lucide-react'
import { api } from '../core/api'
import { fmtDate, money, STATUS_LABEL, todayISO } from '../core/format'
import { CategoryIcon, Field, Modal, PageLoader, WarrantyBadge, useToast } from '../components/ui'
import Attachments from '../components/Attachments'
import Uploader from '../components/Uploader'

const SERVICE_KINDS = { repair: 'Repair', service: 'Service', claim: 'Warranty claim', installation: 'Installation', other: 'Other' }

function Timeline({ a }) {
  const start = new Date(a.warranty_start_date || a.purchase_date).getTime()
  const mfr = a.warranty_expiry_date && new Date(a.warranty_expiry_date).getTime()
  const ext = a.ext_warranty_expiry_date && new Date(a.ext_warranty_expiry_date).getTime()
  const end = Math.max(mfr || 0, ext || 0)
  if (!end) return null
  const now = Date.now()
  const span = Math.max(end, now) - start
  const pct = (t) => `${Math.min(100, Math.max(0, ((t - start) / span) * 100))}%`
  return (
    <div className="pt-1">
      <div className="relative h-3 rounded-full bg-slate-100 overflow-hidden">
        {mfr && <div className="absolute inset-y-0 left-0 bg-emerald-400" style={{ width: pct(mfr) }} />}
        {ext && <div className="absolute inset-y-0 bg-sky-400" style={{ left: pct(mfr || start), width: `calc(${pct(ext)} - ${pct(mfr || start)})` }} />}
      </div>
      <div className="relative h-5">
        <div className="absolute -top-4 w-0.5 h-5 bg-slate-800" style={{ left: pct(now) }} />
        <div className="absolute top-1 text-[10px] font-medium text-slate-700 -translate-x-1/2" style={{ left: pct(now) }}>Today</div>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
        <span><span className="inline-block w-2 h-2 rounded-full bg-emerald-400 mr-1" />Manufacturer: {fmtDate(a.warranty_expiry_date)}</span>
        {ext && <span><span className="inline-block w-2 h-2 rounded-full bg-sky-400 mr-1" />Extended{a.ext_warranty_provider ? ` (${a.ext_warranty_provider})` : ''}: {fmtDate(a.ext_warranty_expiry_date)}</span>}
      </div>
    </div>
  )
}

function Row({ label, children }) {
  if (children === null || children === undefined || children === '') return null
  return (
    <div className="flex justify-between gap-4 py-2 text-sm border-b border-slate-100 last:border-0">
      <dt className="text-slate-500 shrink-0">{label}</dt>
      <dd className="text-right text-slate-800 break-words min-w-0">{children}</dd>
    </div>
  )
}

const EMPTY_SVC = { service_date: todayISO(), kind: 'repair', description: '', vendor: '', cost: '', under_warranty: false, reference_number: '' }

export default function AssetDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const toast = useToast()
  const [a, setA] = useState(null)
  const [svc, setSvc] = useState(null) // form state; null = closed

  const load = useCallback(() => api(`assets/${id}`).then(setA).catch((e) => { toast(e.message, 'error'); nav('/assets') }), [id, nav, toast])
  useEffect(() => { load() }, [load])

  if (!a) return <PageLoader />

  const del = async () => {
    if (!confirm(`Delete "${a.name}" and all its files? This cannot be undone.\n\nTip: set status to Sold/Disposed instead to keep the history.`)) return
    try { await api(`assets/${a.id}`, { method: 'DELETE' }); toast('Deleted'); nav('/assets', { replace: true }) } catch (e) { toast(e.message, 'error') }
  }

  const saveSvc = async (e) => {
    e.preventDefault()
    const body = { ...svc, cost: svc.cost === '' ? '0' : String(svc.cost) }
    try {
      await api(svc.id ? `services/${svc.id}` : `assets/${a.id}/services`, { method: svc.id ? 'PUT' : 'POST', body })
      setSvc(null); load(); toast('Saved')
    } catch (ex) { toast(ex.message, 'error') }
  }
  const delSvc = async (s) => {
    if (!confirm('Delete this record?')) return
    await api(`services/${s.id}`, { method: 'DELETE' }); load()
  }

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <div className="flex items-center justify-between gap-2">
        <Link to="/assets" className="btn-ghost btn-sm"><ArrowLeft size={18} /> Assets</Link>
        <div className="flex gap-2">
          <button className="btn-danger btn-sm" onClick={del}><Trash2 size={14} /> <span className="hidden sm:inline">Delete</span></button>
          <Link to={`/assets/${a.id}/edit`} className="btn-primary btn-sm"><Pencil size={14} /> Edit</Link>
        </div>
      </div>

      <div className="card p-5">
        <div className="flex items-start gap-4">
          <CategoryIcon icon={a.category_icon} color={a.category_color} size="lg" />
          <div className="min-w-0 flex-1">
            <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-slate-900">{a.name}</h1>
            <p className="text-sm text-slate-500">{[a.brand, a.model, a.category_name].filter(Boolean).join(' · ')}</p>
            <div className="flex flex-wrap items-center gap-2 mt-2">
              <WarrantyBadge state={a.warranty_state} days={a.days_left} />
              {a.status !== 'active' && <span className="chip bg-slate-800 text-white">{STATUS_LABEL[a.status]}</span>}
            </div>
          </div>
          <div className="text-right hidden sm:block">
            <div className="text-2xl font-semibold tabular-nums">{money(a.purchase_price, a.currency, true)}</div>
            <div className="text-xs text-slate-500">bought {fmtDate(a.purchase_date)}</div>
          </div>
        </div>
        <div className="mt-5"><Timeline a={a} /></div>
      </div>

      <div className="grid lg:grid-cols-5 gap-5">
        <div className="lg:col-span-2 space-y-5">
          <section className="card p-4">
            <h2 className="font-semibold mb-1">Details</h2>
            <dl>
              <Row label="Price">{money(a.purchase_price, a.currency, true)}</Row>
              <Row label="Purchased">{fmtDate(a.purchase_date)}</Row>
              <Row label="Store">{a.vendor}</Row>
              <Row label="Invoice no.">{a.invoice_number}</Row>
              <Row label="Paid by">{a.payment_method}</Row>
              <Row label="Serial / IMEI">{a.serial_number && <span className="font-mono text-xs">{a.serial_number}</span>}</Row>
              <Row label="Location">{a.location}</Row>
              <Row label="Used by">{a.owner_name}</Row>
              <Row label="Warranty">{a.warranty_expiry_manual ? 'Custom date' : a.warranty_months ? `${a.warranty_months} months` : 'None'}{a.warranty_start_date ? ` from ${fmtDate(a.warranty_start_date)}` : ''}</Row>
              <Row label="Covered until">{fmtDate(a.effective_expiry_date)}</Row>
              <Row label="Extended by">{a.ext_warranty_provider && `${a.ext_warranty_provider}${a.ext_warranty_cost ? ` · ${money(a.ext_warranty_cost)}` : ''}`}</Row>
              <Row label="Support">{a.support_contact && (
                /^[+\d][\d\s-]{6,}$/.test(a.support_contact)
                  ? <a className="text-brand-700 inline-flex items-center gap-1" href={`tel:${a.support_contact.replace(/\s/g, '')}`}><Phone size={13} />{a.support_contact}</a>
                  : /^https?:\/\//.test(a.support_contact) ? <a className="text-brand-700 underline" href={a.support_contact} target="_blank" rel="noreferrer">{a.support_contact}</a> : a.support_contact)}
              </Row>
            </dl>
            {a.notes && <p className="text-sm text-slate-700 whitespace-pre-wrap bg-slate-50 rounded-xl p-3 mt-2">{a.notes}</p>}
          </section>
        </div>

        <div className="lg:col-span-3 space-y-5">
          <section className="card p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">Invoice &amp; files</h2>
              <span className="text-xs text-slate-500">{a.attachments.length} file{a.attachments.length === 1 ? '' : 's'}</span>
            </div>
            <Attachments items={a.attachments} onChange={(items) => setA({ ...a, attachments: items })} />
            <Uploader compact kind={a.attachments.some((x) => x.kind === 'invoice') ? 'photo' : 'invoice'} assetId={a.id}
              onUploaded={(r) => setA((p) => ({ ...p, attachments: [...p.attachments, r.attachment] }))} />
          </section>

          <section className="card p-4">
            <div className="flex items-center justify-between mb-2">
              <div>
                <h2 className="font-semibold">Service &amp; repairs</h2>
                {a.services.length > 0 && <p className="text-xs text-slate-500">Total spent {money(a.service_cost_total)}</p>}
              </div>
              <button className="btn-secondary btn-sm" onClick={() => setSvc({ ...EMPTY_SVC, under_warranty: a.warranty_state === 'active' || a.warranty_state === 'expiring' })}><Plus size={14} /> Add</button>
            </div>
            {a.services.length === 0 ? (
              <p className="text-sm text-slate-500 py-3">No service history. Log repairs and warranty claims here, with the complaint number.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {a.services.map((s) => (
                  <li key={s.id} className="py-3 flex gap-3">
                    <div className="w-8 h-8 rounded-lg bg-slate-100 text-slate-600 grid place-items-center shrink-0"><Wrench size={15} /></div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium">{s.description}</div>
                      <div className="text-xs text-slate-500">
                        {fmtDate(s.service_date)} · {SERVICE_KINDS[s.kind]}{s.vendor ? ` · ${s.vendor}` : ''}{s.reference_number ? ` · Ref ${s.reference_number}` : ''}
                        {s.under_warranty && <span className="chip bg-emerald-50 text-emerald-700 ml-1">Under warranty</span>}
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-sm font-medium tabular-nums">{money(s.cost)}</div>
                      <div className="flex gap-1 justify-end mt-1">
                        <button className="text-slate-400 hover:text-slate-700" onClick={() => setSvc({ ...s, vendor: s.vendor || '', reference_number: s.reference_number || '' })}><Pencil size={13} /></button>
                        <button className="text-slate-400 hover:text-rose-600" onClick={() => delSvc(s)}><Trash2 size={13} /></button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>

      <Modal open={!!svc} onClose={() => setSvc(null)} title={svc?.id ? 'Edit service record' : 'Add service record'}>
        {svc && (
          <form onSubmit={saveSvc} className="grid grid-cols-2 gap-3">
            <Field label="Date"><input type="date" className="input" required value={svc.service_date} onChange={(e) => setSvc({ ...svc, service_date: e.target.value })} /></Field>
            <Field label="Type">
              <select className="input" value={svc.kind} onChange={(e) => setSvc({ ...svc, kind: e.target.value })}>
                {Object.entries(SERVICE_KINDS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </Field>
            <Field label="What was done" className="col-span-2"><input className="input" required value={svc.description} onChange={(e) => setSvc({ ...svc, description: e.target.value })} placeholder="e.g. Compressor replaced" /></Field>
            <Field label="Service centre"><input className="input" value={svc.vendor} onChange={(e) => setSvc({ ...svc, vendor: e.target.value })} /></Field>
            <Field label="Cost (₹)"><input type="number" min="0" step="0.01" className="input" value={svc.cost} onChange={(e) => setSvc({ ...svc, cost: e.target.value })} /></Field>
            <Field label="Complaint / ticket no."><input className="input" value={svc.reference_number} onChange={(e) => setSvc({ ...svc, reference_number: e.target.value })} /></Field>
            <label className="flex items-center gap-2 text-sm mt-6">
              <input type="checkbox" className="accent-brand-700 w-4 h-4" checked={svc.under_warranty} onChange={(e) => setSvc({ ...svc, under_warranty: e.target.checked })} /> Covered by warranty
            </label>
            <div className="col-span-2 flex justify-end gap-2 pt-2">
              <button type="button" className="btn-secondary" onClick={() => setSvc(null)}>Cancel</button>
              <button className="btn-primary">Save</button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  )
}
