import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { AlertTriangle, ArrowLeft, ChevronDown, Save, Sparkles } from 'lucide-react'
import { api } from '../core/api'
import { fmtDate, STATUS_LABEL, todayISO } from '../core/format'
import { Field, PageLoader, useToast } from '../components/ui'
import Uploader from '../components/Uploader'
import Attachments from '../components/Attachments'

const EMPTY = {
  name: '', brand: '', model: '', serial_number: '', category_id: '', location: '', owner_name: '',
  purchase_date: todayISO(), purchase_price: '', currency: 'INR', vendor: '', invoice_number: '', payment_method: '',
  warranty_months: 12, warranty_start_date: '', warranty_expiry_manual: false, warranty_expiry_date: '',
  ext_warranty_provider: '', ext_warranty_months: '', ext_warranty_expiry_date: '', ext_warranty_cost: '',
  support_contact: '', status: 'active', notes: '',
}
const WARRANTY_CHIPS = [[0, 'None'], [6, '6 mo'], [12, '1 yr'], [24, '2 yr'], [36, '3 yr'], [60, '5 yr'], [120, '10 yr']]
const PAYMENT = ['UPI', 'Credit card', 'Debit card', 'Cash', 'Net banking', 'EMI', 'Gift / other']
const OCR_FIELDS = ['name', 'brand', 'model', 'serial_number', 'vendor', 'invoice_number', 'purchase_date', 'purchase_price', 'warranty_months']

// 12 months from 10 Jan 2025 → 9 Jan 2026 (same rule as the server)
function addMonthsInclusive(iso, months) {
  if (!iso || !months) return null
  const [y, m, d] = iso.split('-').map(Number)
  const target = new Date(Date.UTC(y, m - 1 + Number(months), 1))
  const last = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate()
  target.setUTCDate(Math.min(d, last))
  target.setUTCDate(target.getUTCDate() - 1)
  return target.toISOString().slice(0, 10)
}
const nextDay = (iso) => { const t = new Date(iso + 'T00:00:00Z'); t.setUTCDate(t.getUTCDate() + 1); return t.toISOString().slice(0, 10) }

export default function AssetForm() {
  const { id } = useParams()
  const editing = !!id
  const nav = useNavigate()
  const toast = useToast()
  const [f, setF] = useState(editing ? null : EMPTY)
  const [cats, setCats] = useState([])
  const [sugg, setSugg] = useState({ brands: [], vendors: [], locations: [], owners: [], payment_methods: [] })
  const [attachments, setAttachments] = useState([])
  const [suggested, setSuggested] = useState(new Set())
  const [dupOf, setDupOf] = useState(null)
  const [ocrNote, setOcrNote] = useState('')
  const [showExt, setShowExt] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api('categories').then(setCats)
    api('assets/suggestions').then(setSugg).catch(() => {})
    if (editing) {
      api(`assets/${id}`).then((a) => {
        const v = { ...EMPTY }
        Object.keys(EMPTY).forEach((k) => { v[k] = a[k] ?? '' })
        v.warranty_expiry_manual = !!a.warranty_expiry_manual
        setF(v)
        setAttachments(a.attachments)
        setShowExt(!!(a.ext_warranty_provider || a.ext_warranty_months || a.ext_warranty_expiry_date))
      }).catch((e) => toast(e.message, 'error'))
    }
  }, [id, editing, toast])

  const set = (k) => (e) => {
    const v = e?.target ? (e.target.type === 'checkbox' ? e.target.checked : e.target.value) : e
    setF((p) => ({ ...p, [k]: v }))
    if (suggested.has(k)) setSuggested((s) => { const n = new Set(s); n.delete(k); return n })
  }

  const expiry = useMemo(() => {
    if (!f) return null
    if (f.warranty_expiry_manual) return f.warranty_expiry_date || null
    return addMonthsInclusive(f.warranty_start_date || f.purchase_date, f.warranty_months)
  }, [f])
  const extExpiry = useMemo(() => {
    if (!f || !f.ext_warranty_months) return f?.ext_warranty_expiry_date || null
    return addMonthsInclusive(expiry ? nextDay(expiry) : f.purchase_date, f.ext_warranty_months)
  }, [f, expiry])

  const onInvoice = (r) => {
    setAttachments((a) => [...a, r.attachment])
    if (r.duplicate_of_asset_id) setDupOf(r.duplicate_of_asset_id)
    const ex = r.extracted
    if (!ex) { setOcrNote(r.ocr_available ? 'Could not read text from this file — please fill in the details.' : ''); return }
    const filled = new Set()
    const n = { ...f }
    OCR_FIELDS.forEach((k) => {
      const v = ex[k]
      if (v === null || v === undefined || v === '') return
      const blank = f[k] === '' || f[k] === null || (k === 'purchase_date' && f[k] === todayISO()) || (k === 'warranty_months' && Number(f[k]) === 12)
      if (blank) { n[k] = typeof v === 'number' ? v : String(v); filled.add(k) }
    })
    setF(n)
    setSuggested(filled)
    setOcrNote(filled.size ? `Filled ${filled.size} field${filled.size > 1 ? 's' : ''} from the invoice. Check the highlighted ones.` : 'No details could be read from the invoice. Please fill them in.')
  }

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    const num = (v) => (v === '' || v === null ? null : v)
    const body = {
      ...f,
      category_id: f.category_id ? Number(f.category_id) : null,
      purchase_price: f.purchase_price === '' ? '0' : String(f.purchase_price),
      warranty_months: Number(f.warranty_months || 0),
      warranty_start_date: num(f.warranty_start_date),
      warranty_expiry_date: f.warranty_expiry_manual ? num(f.warranty_expiry_date) : null,
      ext_warranty_months: f.ext_warranty_months === '' ? null : Number(f.ext_warranty_months),
      ext_warranty_expiry_date: f.ext_warranty_months ? null : num(f.ext_warranty_expiry_date),
      ext_warranty_cost: num(f.ext_warranty_cost),
      attachment_ids: attachments.filter((a) => !a.asset_id).map((a) => a.id),
    }
    try {
      const a = await api(editing ? `assets/${id}` : 'assets', { method: editing ? 'PUT' : 'POST', body })
      toast(editing ? 'Saved' : 'Asset added')
      nav(`/assets/${a.id}`, { replace: true })
    } catch (ex) {
      toast(ex.message, 'error')
    } finally { setSaving(false) }
  }

  if (!f) return <PageLoader />
  const sg = (k) => (suggested.has(k) ? 'suggested' : '')

  return (
    <form onSubmit={submit} className="max-w-3xl mx-auto space-y-5">
      <div className="flex items-center gap-3">
        <Link to={editing ? `/assets/${id}` : '/assets'} className="btn-ghost btn-sm"><ArrowLeft size={18} /></Link>
        <h1 className="text-xl font-semibold tracking-tight">{editing ? 'Edit asset' : 'Add asset'}</h1>
      </div>

      {/* 1. invoice */}
      <section className="card p-4 sm:p-5 space-y-3">
        <h2 className="font-semibold">Invoice &amp; photos</h2>
        {!editing && !attachments.some((a) => a.kind === 'invoice') && (
          <Uploader kind="invoice" extract onUploaded={onInvoice} label="Photograph or upload the invoice" />
        )}
        {ocrNote && (
          <div className="flex items-start gap-2 text-sm rounded-xl bg-amber-50 text-amber-900 px-3 py-2">
            <Sparkles size={16} className="mt-0.5 shrink-0" /> {ocrNote}
          </div>
        )}
        {dupOf && (
          <div className="flex items-start gap-2 text-sm rounded-xl bg-rose-50 text-rose-800 px-3 py-2">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            <span>This exact file is already attached to <Link className="underline font-medium" to={`/assets/${dupOf}`}>another asset</Link>.</span>
          </div>
        )}
        <Attachments items={attachments} onChange={setAttachments} />
        {(editing || attachments.length > 0) && (
          <Uploader compact kind={attachments.some((a) => a.kind === 'invoice') ? 'photo' : 'invoice'} assetId={editing ? id : undefined}
            onUploaded={(r) => setAttachments((a) => [...a, r.attachment])} label="Add more files" />
        )}
      </section>

      {/* 2. product */}
      <section className="card p-4 sm:p-5">
        <h2 className="font-semibold mb-3">Product</h2>
        <div className="grid sm:grid-cols-2 gap-3">
          <Field label="Name *" className="sm:col-span-2">
            <input className={`input ${sg('name')}`} required maxLength={200} value={f.name} onChange={set('name')} placeholder="e.g. Samsung 253L Refrigerator" />
          </Field>
          <Field label="Brand"><input className={`input ${sg('brand')}`} list="brands" value={f.brand} onChange={set('brand')} /></Field>
          <Field label="Model number"><input className={`input ${sg('model')}`} value={f.model} onChange={set('model')} /></Field>
          <Field label="Serial / IMEI"><input className={`input ${sg('serial_number')}`} value={f.serial_number} onChange={set('serial_number')} /></Field>
          <Field label="Category">
            <select className="input" value={f.category_id} onChange={set('category_id')}>
              <option value="">Choose…</option>
              {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </Field>
          <Field label="Room / location"><input className="input" list="locations" value={f.location} onChange={set('location')} placeholder="Kitchen, Bedroom 1…" /></Field>
          <Field label="Used by"><input className="input" list="owners" value={f.owner_name} onChange={set('owner_name')} placeholder="Family member" /></Field>
        </div>
      </section>

      {/* 3. purchase */}
      <section className="card p-4 sm:p-5">
        <h2 className="font-semibold mb-3">Purchase</h2>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Purchase date *"><input type="date" className={`input ${sg('purchase_date')}`} required max={todayISO()} value={f.purchase_date} onChange={set('purchase_date')} /></Field>
          <Field label="Price (₹) *">
            <input type="number" inputMode="decimal" step="0.01" min="0" className={`input ${sg('purchase_price')}`} required value={f.purchase_price} onChange={set('purchase_price')} placeholder="0" />
          </Field>
          <Field label="Store / website"><input className={`input ${sg('vendor')}`} list="vendors" value={f.vendor} onChange={set('vendor')} placeholder="Amazon, Croma…" /></Field>
          <Field label="Invoice number"><input className={`input ${sg('invoice_number')}`} value={f.invoice_number} onChange={set('invoice_number')} /></Field>
          <Field label="Paid by" className="col-span-2 sm:col-span-1">
            <input className="input" list="payments" value={f.payment_method} onChange={set('payment_method')} />
          </Field>
        </div>
      </section>

      {/* 4. warranty */}
      <section className="card p-4 sm:p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Warranty</h2>
          <span className="text-sm text-slate-600">{expiry ? <>Covered until <b>{fmtDate(expiry)}</b></> : 'No warranty'}</span>
        </div>
        {!f.warranty_expiry_manual && (
          <>
            <div className="flex flex-wrap gap-2">
              {WARRANTY_CHIPS.map(([m, l]) => (
                <button type="button" key={m} onClick={() => set('warranty_months')(m)}
                  className={`chip px-3 py-1.5 text-sm border ${Number(f.warranty_months) === m ? 'bg-brand-700 text-white border-brand-700' : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'}`}>{l}</button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Months"><input type="number" min="0" max="600" className={`input ${sg('warranty_months')}`} value={f.warranty_months} onChange={set('warranty_months')} /></Field>
              <Field label="Starts on" hint="Leave empty to use the purchase date (or set the installation date)">
                <input type="date" className="input" value={f.warranty_start_date} onChange={set('warranty_start_date')} />
              </Field>
            </div>
          </>
        )}
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" className="accent-brand-700 w-4 h-4" checked={f.warranty_expiry_manual} onChange={set('warranty_expiry_manual')} />
          I know the exact expiry date
        </label>
        {f.warranty_expiry_manual && (
          <Field label="Warranty expires on"><input type="date" className="input max-w-xs" required value={f.warranty_expiry_date} onChange={set('warranty_expiry_date')} /></Field>
        )}

        <div className="border-t border-slate-100 pt-3">
          <button type="button" className="flex items-center gap-2 text-sm font-medium text-slate-700" onClick={() => setShowExt((s) => !s)}>
            <ChevronDown size={16} className={`transition ${showExt ? 'rotate-180' : ''}`} /> Extended warranty / AMC
            {extExpiry && <span className="font-normal text-slate-500">· until {fmtDate(extExpiry)}</span>}
          </button>
          {showExt && (
            <div className="grid grid-cols-2 gap-3 mt-3">
              <Field label="Provider" className="col-span-2 sm:col-span-1"><input className="input" value={f.ext_warranty_provider} onChange={set('ext_warranty_provider')} placeholder="e.g. Croma Zip Care, OneAssist" /></Field>
              <Field label="Cost (₹)"><input type="number" step="0.01" min="0" className="input" value={f.ext_warranty_cost} onChange={set('ext_warranty_cost')} /></Field>
              <Field label="Extra months" hint="Starts after the manufacturer warranty ends">
                <input type="number" min="0" max="600" className="input" value={f.ext_warranty_months} onChange={set('ext_warranty_months')} />
              </Field>
              <Field label="…or ends on"><input type="date" className="input" disabled={!!f.ext_warranty_months} value={f.ext_warranty_months ? (extExpiry || '') : f.ext_warranty_expiry_date} onChange={set('ext_warranty_expiry_date')} /></Field>
            </div>
          )}
        </div>
      </section>

      {/* 5. other */}
      <section className="card p-4 sm:p-5">
        <h2 className="font-semibold mb-3">Other</h2>
        <div className="grid sm:grid-cols-2 gap-3">
          <Field label="Service centre / support contact"><input className="input" value={f.support_contact} onChange={set('support_contact')} placeholder="Phone number or URL" /></Field>
          <Field label="Status">
            <select className="input" value={f.status} onChange={set('status')}>
              {Object.entries(STATUS_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
          <Field label="Notes" className="sm:col-span-2"><textarea rows={3} className="input" value={f.notes} onChange={set('notes')} /></Field>
        </div>
      </section>

      <div className="sticky bottom-20 lg:bottom-4 z-20 flex justify-end gap-2 bg-slate-50/80 backdrop-blur py-2">
        <Link to={editing ? `/assets/${id}` : '/assets'} className="btn-secondary">Cancel</Link>
        <button className="btn-primary min-w-32" disabled={saving}><Save size={16} /> {saving ? 'Saving…' : 'Save'}</button>
      </div>

      <datalist id="brands">{sugg.brands.map((x) => <option key={x} value={x} />)}</datalist>
      <datalist id="vendors">{[...new Set([...sugg.vendors, 'Amazon', 'Flipkart', 'Croma', 'Reliance Digital', 'Vijay Sales'])].map((x) => <option key={x} value={x} />)}</datalist>
      <datalist id="locations">{[...new Set([...sugg.locations, 'Living room', 'Kitchen', 'Master bedroom', 'Kids room', 'Study', 'Balcony', 'Garage'])].map((x) => <option key={x} value={x} />)}</datalist>
      <datalist id="owners">{sugg.owners.map((x) => <option key={x} value={x} />)}</datalist>
      <datalist id="payments">{[...new Set([...sugg.payment_methods, ...PAYMENT])].map((x) => <option key={x} value={x} />)}</datalist>
    </form>
  )
}
