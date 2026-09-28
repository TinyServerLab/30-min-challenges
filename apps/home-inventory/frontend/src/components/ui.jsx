import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import {
  AirVent, Armchair, Box, Car, CheckCircle2, Laptop, Loader2, Microwave, ShieldAlert, ShieldCheck,
  ShieldOff, ShieldX, Smartphone, Tv, WashingMachine, Wind, Wrench, X,
} from 'lucide-react'
import { daysText } from '../lib/format'

export const ICONS = {
  smartphone: Smartphone, laptop: Laptop, tv: Tv, microwave: Microwave, washing: WashingMachine,
  wind: Wind, ac: AirVent, sofa: Armchair, car: Car, wrench: Wrench, box: Box,
}

export function CategoryIcon({ icon, color, size = 'md' }) {
  const I = ICONS[icon] || Box
  const s = size === 'sm' ? 'w-8 h-8' : size === 'lg' ? 'w-14 h-14' : 'w-10 h-10'
  const is = size === 'sm' ? 16 : size === 'lg' ? 26 : 20
  return (
    <div className={`${s} rounded-xl grid place-items-center shrink-0`} style={{ background: (color || '#64748b') + '1a', color: color || '#64748b' }}>
      <I size={is} strokeWidth={1.8} />
    </div>
  )
}

const STATE = {
  active: { cls: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20', Icon: ShieldCheck },
  expiring: { cls: 'bg-amber-50 text-amber-800 ring-amber-600/25', Icon: ShieldAlert },
  expired: { cls: 'bg-rose-50 text-rose-700 ring-rose-600/20', Icon: ShieldX },
  none: { cls: 'bg-slate-100 text-slate-600 ring-slate-500/15', Icon: ShieldOff },
}

export function WarrantyBadge({ state, days, compact }) {
  const s = STATE[state] || STATE.none
  return (
    <span className={`chip ring-1 ring-inset ${s.cls}`}>
      <s.Icon size={13} />
      {compact && state === 'active' ? 'Covered' : daysText(days)}
    </span>
  )
}

export function Spinner({ className = '' }) {
  return <Loader2 className={`animate-spin text-brand-600 ${className}`} size={22} />
}

export function PageLoader() {
  return <div className="py-24 grid place-items-center"><Spinner /></div>
}

export function Empty({ icon: I = Box, title, children, action }) {
  return (
    <div className="text-center py-14 px-6">
      <div className="mx-auto w-14 h-14 rounded-2xl bg-brand-50 text-brand-700 grid place-items-center mb-4"><I size={26} /></div>
      <h3 className="font-semibold text-slate-800">{title}</h3>
      {children && <p className="text-sm text-slate-500 mt-1 max-w-sm mx-auto">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function Modal({ open, onClose, title, children, wide }) {
  useEffect(() => {
    if (!open) return
    const h = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-slate-900/40 backdrop-blur-[2px] p-0 sm:p-4" onMouseDown={onClose}>
      <div className={`bg-white w-full ${wide ? 'sm:max-w-3xl' : 'sm:max-w-lg'} rounded-t-2xl sm:rounded-2xl shadow-xl max-h-[92vh] flex flex-col`} onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 h-14 border-b border-slate-100 shrink-0">
          <h3 className="font-semibold">{title}</h3>
          <button className="btn-ghost btn-sm" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>
        <div className="p-5 overflow-y-auto">{children}</div>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ toasts
const ToastCtx = createContext(() => {})
export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const push = useCallback((msg, kind = 'ok') => {
    const id = Math.random()
    setItems((x) => [...x, { id, msg, kind }])
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), kind === 'error' ? 6000 : 3000)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed z-[60] bottom-20 sm:bottom-6 left-1/2 -translate-x-1/2 flex flex-col gap-2 w-[min(92vw,420px)]">
        {items.map((t) => (
          <div key={t.id} className={`rounded-xl px-4 py-3 text-sm shadow-lg flex items-start gap-2 ${t.kind === 'error' ? 'bg-rose-600 text-white' : 'bg-slate-900 text-white'}`}>
            {t.kind !== 'error' && <CheckCircle2 size={18} className="text-emerald-400 shrink-0" />}
            <span>{t.msg}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}
export const useToast = () => useContext(ToastCtx)

export function Field({ label, children, hint, className = '' }) {
  return (
    <label className={`block ${className}`}>
      <span className="label">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-slate-500 mt-1">{hint}</span>}
    </label>
  )
}

export function StatCard({ label, value, sub, icon: I, tone = 'slate', onClick }) {
  const tones = {
    slate: 'bg-slate-100 text-slate-700', green: 'bg-emerald-100 text-emerald-700',
    amber: 'bg-amber-100 text-amber-700', red: 'bg-rose-100 text-rose-700', brand: 'bg-brand-100 text-brand-700',
  }
  const C = onClick ? 'button' : 'div'
  return (
    <C onClick={onClick} className={`card p-4 text-left ${onClick ? 'hover:border-brand-300 hover:shadow-sm transition' : ''}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-500">{label}</span>
        {I && <span className={`w-8 h-8 rounded-lg grid place-items-center ${tones[tone]}`}><I size={16} /></span>}
      </div>
      <div className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-0.5">{sub}</div>}
    </C>
  )
}
