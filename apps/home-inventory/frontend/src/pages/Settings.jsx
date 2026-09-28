import { useEffect, useState } from 'react'
import { Bell, KeyRound, Pencil, Plus, Tags, Trash2, User, Users } from 'lucide-react'
import { api } from '../core/api'
import { useAuth } from '../core/auth'
import { fmtDate } from '../core/format'
import { CategoryIcon, Field, ICONS, Modal, useToast } from '../components/ui'

// validated categorical palette + neutral
const PALETTE = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948', '#64748b']

function Section({ icon: I, title, children, action }) {
  return (
    <section className="card p-4 sm:p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold flex items-center gap-2"><I size={18} className="text-brand-700" /> {title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

function Profile() {
  const { user, setUser } = useAuth()
  const toast = useToast()
  const [name, setName] = useState(user.display_name)
  const [pw, setPw] = useState({ current_password: '', new_password: '', confirm: '' })

  const saveProfile = async (patch) => {
    try { setUser(await api('auth/me', { method: 'PATCH', body: patch })); toast('Saved') } catch (e) { toast(e.message, 'error') }
  }
  const changePw = async (e) => {
    e.preventDefault()
    if (pw.new_password !== pw.confirm) return toast('New passwords do not match', 'error')
    try {
      await api('auth/change-password', { method: 'POST', body: { current_password: pw.current_password, new_password: pw.new_password } })
      setPw({ current_password: '', new_password: '', confirm: '' })
      toast('Password changed. Other devices were signed out.')
    } catch (ex) { toast(ex.message, 'error') }
  }

  return (
    <div className="grid lg:grid-cols-2 gap-5">
      <Section icon={User} title="Your profile">
        <div className="space-y-3">
          <Field label="Email"><input className="input" disabled value={user.email} /></Field>
          <Field label="Display name">
            <div className="flex gap-2">
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
              <button className="btn-secondary" disabled={!name.trim() || name === user.display_name} onClick={() => saveProfile({ display_name: name.trim() })}>Save</button>
            </div>
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="accent-brand-700 w-4 h-4" checked={user.notify_email} onChange={(e) => saveProfile({ notify_email: e.target.checked })} />
            Email me warranty expiry reminders
          </label>
        </div>
      </Section>
      <Section icon={KeyRound} title="Change password">
        <form onSubmit={changePw} className="space-y-3">
          <Field label="Current password"><input type="password" className="input" autoComplete="current-password" required value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="New password" hint="At least 10 characters"><input type="password" className="input" autoComplete="new-password" minLength={10} required value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
            <Field label="Repeat new password"><input type="password" className="input" autoComplete="new-password" required value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} /></Field>
          </div>
          <button className="btn-primary">Update password</button>
        </form>
      </Section>
    </div>
  )
}

function Reminders() {
  const { user } = useAuth()
  const toast = useToast()
  const [st, setSt] = useState(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { api('notifications/status').then(setSt).catch(() => {}) }, [])
  if (!st) return null

  const run = async (path, label) => {
    setBusy(true)
    try {
      const r = await api(path, { method: 'POST' })
      toast(`${label}: ${JSON.stringify(r.sent ?? r)}`)
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }
  return (
    <Section icon={Bell} title="Warranty reminders">
      <div className="grid sm:grid-cols-3 gap-3 text-sm">
        <div className="rounded-xl bg-slate-50 p-3"><div className="text-xs text-slate-500">Channels</div><div className="font-medium mt-0.5">{st.channels.length ? st.channels.join(', ') : 'None configured'}</div></div>
        <div className="rounded-xl bg-slate-50 p-3"><div className="text-xs text-slate-500">Sent</div><div className="font-medium mt-0.5">{st.reminder_days.map((d) => (d === 0 ? 'on the day' : `${d}d`)).join(' · ')} before expiry</div></div>
        <div className="rounded-xl bg-slate-50 p-3"><div className="text-xs text-slate-500">Daily check</div><div className="font-medium mt-0.5">{st.reminder_time} ({st.timezone})</div></div>
      </div>
      <p className="text-sm text-slate-600 mt-3">
        {st.due_now ? `${st.due_now} warranty reminder${st.due_now > 1 ? 's are' : ' is'} due right now.` : 'No reminders are due right now.'}
        {!st.channels.length && ' Set SMTP_* (email) or NTFY_URL (phone push) in the .env file to get reminders; until then the dashboard shows what is expiring.'}
      </p>
      {user.is_admin && st.channels.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-3">
          <button className="btn-secondary btn-sm" disabled={busy} onClick={() => run('notifications/test', 'Test')}>Send test notification</button>
          <button className="btn-secondary btn-sm" disabled={busy} onClick={() => run('notifications/run', 'Sent')}>Send due reminders now</button>
        </div>
      )}
    </Section>
  )
}

function UsersAdmin() {
  const { user: me } = useAuth()
  const toast = useToast()
  const [users, setUsers] = useState([])
  const [form, setForm] = useState(null)
  const [reset, setReset] = useState(null)
  const load = () => api('users').then(setUsers).catch(() => {})
  useEffect(() => { load() }, [])

  const create = async (e) => {
    e.preventDefault()
    try { await api('users', { method: 'POST', body: form }); setForm(null); load(); toast('User created') } catch (ex) { toast(ex.message, 'error') }
  }
  const patch = async (u, body) => {
    try { await api(`users/${u.id}`, { method: 'PATCH', body }); load() } catch (ex) { toast(ex.message, 'error') }
  }
  const doReset = async (e) => {
    e.preventDefault()
    try { await api(`users/${reset.id}/reset-password`, { method: 'POST', body: { new_password: reset.pw } }); setReset(null); toast('Password reset') } catch (ex) { toast(ex.message, 'error') }
  }

  return (
    <Section icon={Users} title="Family members"
      action={<button className="btn-secondary btn-sm" onClick={() => setForm({ email: '', display_name: '', username: '', password: '', is_admin: false })}><Plus size={14} /> Add</button>}>
      <ul className="divide-y divide-slate-100">
        {users.map((u) => (
          <li key={u.id} className="py-3 flex flex-wrap items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-brand-100 text-brand-800 grid place-items-center text-sm font-semibold">{u.display_name[0]?.toUpperCase()}</div>
            <div className="flex-1 min-w-40">
              <div className="text-sm font-medium">{u.display_name} {u.is_admin && <span className="chip bg-brand-50 text-brand-800 ml-1">Admin</span>} {!u.is_active && <span className="chip bg-slate-200 text-slate-600 ml-1">Disabled</span>}</div>
              <div className="text-xs text-slate-500">{u.email}{u.username ? ` · ${u.username}` : ''} · last login {u.last_login_at ? fmtDate(u.last_login_at) : 'never'}</div>
            </div>
            {u.id !== me.id && (
              <div className="flex gap-1.5">
                <button className="btn-ghost btn-sm" onClick={() => setReset({ ...u, pw: '' })}>Reset password</button>
                <button className="btn-ghost btn-sm" onClick={() => patch(u, { is_admin: !u.is_admin })}>{u.is_admin ? 'Remove admin' : 'Make admin'}</button>
                <button className="btn-ghost btn-sm" onClick={() => patch(u, { is_active: !u.is_active })}>{u.is_active ? 'Disable' : 'Enable'}</button>
              </div>
            )}
          </li>
        ))}
      </ul>

      <Modal open={!!form} onClose={() => setForm(null)} title="Add family member">
        {form && (
          <form onSubmit={create} className="space-y-3">
            <Field label="Name"><input className="input" required value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></Field>
            <Field label="Email"><input type="email" className="input" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
            <Field label="Username (optional)" hint="Can be used instead of email to sign in"><input className="input" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></Field>
            <Field label="Initial password" hint="At least 10 characters. Ask them to change it after first login."><input type="password" className="input" minLength={10} required autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-brand-700 w-4 h-4" checked={form.is_admin} onChange={(e) => setForm({ ...form, is_admin: e.target.checked })} /> Admin (can manage users and categories)</label>
            <div className="flex justify-end gap-2 pt-2"><button type="button" className="btn-secondary" onClick={() => setForm(null)}>Cancel</button><button className="btn-primary">Create</button></div>
          </form>
        )}
      </Modal>
      <Modal open={!!reset} onClose={() => setReset(null)} title={`Reset password for ${reset?.display_name}`}>
        {reset && (
          <form onSubmit={doReset} className="space-y-3">
            <Field label="New password" hint="They will be signed out everywhere"><input type="password" className="input" minLength={10} required autoComplete="new-password" value={reset.pw} onChange={(e) => setReset({ ...reset, pw: e.target.value })} /></Field>
            <div className="flex justify-end gap-2"><button type="button" className="btn-secondary" onClick={() => setReset(null)}>Cancel</button><button className="btn-primary">Reset</button></div>
          </form>
        )}
      </Modal>
    </Section>
  )
}

function CategoriesAdmin() {
  const toast = useToast()
  const [cats, setCats] = useState([])
  const [edit, setEdit] = useState(null)
  const load = () => api('categories').then(setCats)
  useEffect(() => { load() }, [])

  const save = async (e) => {
    e.preventDefault()
    const body = { name: edit.name, icon: edit.icon, color: edit.color, sort_order: Number(edit.sort_order || 0) }
    try { await api(edit.id ? `categories/${edit.id}` : 'categories', { method: edit.id ? 'PUT' : 'POST', body }); setEdit(null); load() } catch (ex) { toast(ex.message, 'error') }
  }
  const del = async (c) => {
    if (!confirm(`Delete category "${c.name}"? ${c.asset_count} asset(s) will become uncategorised.`)) return
    await api(`categories/${c.id}`, { method: 'DELETE' }); load()
  }

  return (
    <Section icon={Tags} title="Categories"
      action={<button className="btn-secondary btn-sm" onClick={() => setEdit({ name: '', icon: 'box', color: PALETTE[cats.length % PALETTE.length], sort_order: 500 })}><Plus size={14} /> Add</button>}>
      <ul className="grid sm:grid-cols-2 gap-2">
        {cats.map((c) => (
          <li key={c.id} className="flex items-center gap-3 rounded-xl border border-slate-200 p-2">
            <CategoryIcon icon={c.icon} color={c.color} size="sm" />
            <span className="flex-1 text-sm">{c.name} <span className="text-xs text-slate-400">· {c.asset_count}</span></span>
            <button className="text-slate-400 hover:text-slate-700 p-1" onClick={() => setEdit({ ...c })}><Pencil size={14} /></button>
            <button className="text-slate-400 hover:text-rose-600 p-1" onClick={() => del(c)}><Trash2 size={14} /></button>
          </li>
        ))}
      </ul>
      <Modal open={!!edit} onClose={() => setEdit(null)} title={edit?.id ? 'Edit category' : 'New category'}>
        {edit && (
          <form onSubmit={save} className="space-y-4">
            <Field label="Name"><input className="input" required maxLength={60} value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></Field>
            <div>
              <span className="label">Icon</span>
              <div className="flex flex-wrap gap-2">
                {Object.keys(ICONS).map((k) => (
                  <button type="button" key={k} onClick={() => setEdit({ ...edit, icon: k })} className={`rounded-xl p-0.5 ${edit.icon === k ? 'ring-2 ring-brand-600' : ''}`}>
                    <CategoryIcon icon={k} color={edit.color} size="sm" />
                  </button>
                ))}
              </div>
            </div>
            <div>
              <span className="label">Colour</span>
              <div className="flex flex-wrap gap-2">
                {PALETTE.map((col) => (
                  <button type="button" key={col} onClick={() => setEdit({ ...edit, color: col })} className={`w-8 h-8 rounded-full ${edit.color === col ? 'ring-2 ring-offset-2 ring-slate-800' : ''}`} style={{ background: col }} aria-label={col} />
                ))}
              </div>
            </div>
            <Field label="Sort order"><input type="number" className="input w-28" value={edit.sort_order} onChange={(e) => setEdit({ ...edit, sort_order: e.target.value })} /></Field>
            <div className="flex justify-end gap-2"><button type="button" className="btn-secondary" onClick={() => setEdit(null)}>Cancel</button><button className="btn-primary">Save</button></div>
          </form>
        )}
      </Modal>
    </Section>
  )
}

export default function Settings() {
  const { user } = useAuth()
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
      <Profile />
      <Reminders />
      {user.is_admin && <UsersAdmin />}
      {user.is_admin && <CategoriesAdmin />}
    </div>
  )
}
