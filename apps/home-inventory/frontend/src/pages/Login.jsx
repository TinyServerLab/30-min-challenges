import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Lock } from 'lucide-react'
import { useAuth } from '../lib/auth'

export default function Login() {
  const { user, login } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [form, setForm] = useState({ login: '', password: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={loc.state?.from || '/'} replace />

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setErr('')
    try {
      await login(form.login, form.password)
      nav(loc.state?.from || '/', { replace: true })
    } catch (ex) {
      setErr(ex.message)
    } finally { setBusy(false) }
  }

  return (
    <div className="min-h-full grid place-items-center px-4 py-10 bg-gradient-to-br from-brand-50 via-slate-50 to-slate-100">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-7">
          <svg viewBox="0 0 64 64" className="w-14 h-14 mb-3 drop-shadow"><rect width="64" height="64" rx="14" fill="#0f766e" /><path d="M14 30 32 15l18 15v19a3 3 0 0 1-3 3H17a3 3 0 0 1-3-3z" fill="none" stroke="#fff" strokeWidth="4" strokeLinejoin="round" /><path d="m24 37 6 6 11-12" fill="none" stroke="#99f6e4" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
          <h1 className="text-xl font-semibold text-slate-900">Home Inventory</h1>
          <p className="text-sm text-slate-500">Assets, invoices &amp; warranties</p>
        </div>
        <form onSubmit={submit} className="card p-6 space-y-4">
          <div>
            <label className="label" htmlFor="login">Email or username</label>
            <input id="login" className="input" autoComplete="username" autoFocus required
              value={form.login} onChange={(e) => setForm({ ...form, login: e.target.value })} />
          </div>
          <div>
            <label className="label" htmlFor="pw">Password</label>
            <input id="pw" type="password" className="input" autoComplete="current-password" required
              value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </div>
          {err && <div className="text-sm text-rose-700 bg-rose-50 rounded-lg px-3 py-2">{err}</div>}
          <button className="btn-primary w-full" disabled={busy}><Lock size={16} /> {busy ? 'Signing in…' : 'Sign in'}</button>
        </form>
        <p className="text-center text-xs text-slate-500 mt-5">Family access only · accounts are created by the admin</p>
      </div>
    </div>
  )
}
