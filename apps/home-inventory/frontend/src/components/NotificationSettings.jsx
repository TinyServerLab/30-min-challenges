import { useEffect, useState } from 'react'
import {
  AlertTriangle, Bell, BellRing, CheckCircle2, ChevronDown, Mail, MessageSquare, RefreshCw, Send, Settings2,
} from 'lucide-react'
import { api } from '../core/api'
import { useAuth } from '../core/auth'
import { Field, Spinner, useToast } from './ui'

const META = {
  email: { icon: Mail, color: '#0f766e', blurb: 'A daily digest to every family member who has email reminders on.' },
  ntfy: { icon: BellRing, color: '#475569', blurb: 'Phone push through the ntfy app.' },
  discord: { icon: MessageSquare, color: '#5865F2', blurb: 'Posts the digest into a channel of your Discord server.' },
  telegram: { icon: Send, color: '#229ED9', blurb: 'Sends the digest to you, or to a family group, from your own bot.' },
}

function tierText(days) {
  const before = days.filter((d) => d > 0)
  const list = before.length > 1 ? `${before.slice(0, -1).join(', ')} and ${before.at(-1)}` : before.join('')
  const onDay = days.includes(0)
  return [list && `${list} days before they end`, onDay && 'on the day itself'].filter(Boolean).join(', and ')
}

const fmtWhen = (iso) => new Date(iso).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })

export function Switch({ checked, onChange, disabled, label }) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label} disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 disabled:opacity-50 ${checked ? 'bg-brand-700' : 'bg-slate-300'}`}>
      <span className={`inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-5' : 'translate-x-0.5'}`} />
    </button>
  )
}

function StatusLine({ c }) {
  if (c.problem) return <span className="text-amber-700 flex items-center gap-1"><AlertTriangle size={13} /> {c.problem}</span>
  if (c.last_ok === false) {
    return <span className="text-rose-700 flex items-start gap-1"><AlertTriangle size={13} className="mt-0.5 shrink-0" /> {c.last_error || 'Last delivery failed'}</span>
  }
  if (c.last_ok) return <span className="text-emerald-700 flex items-center gap-1"><CheckCircle2 size={13} /> Delivered {fmtWhen(c.last_attempt_at)}</span>
  return <span className="text-slate-500">{c.enabled ? 'Ready — nothing sent yet' : 'Off'}</span>
}

// ------------------------------------------------------------------ Discord
function DiscordForm({ c, onSaved, onTest, testing }) {
  const toast = useToast()
  const [url, setUrl] = useState('')
  const [mention, setMention] = useState(c.config?.mention || '')
  const [busy, setBusy] = useState(false)
  const has = c.has_secret?.webhook_url

  const save = async (enable) => {
    setBusy(true)
    try {
      const config = { mention }
      if (url.trim()) config.webhook_url = url.trim()
      const body = { config }
      if (enable) body.enabled = true
      onSaved(await api('notifications/channels/discord', { method: 'PUT', body }))
      setUrl('')
      toast(enable ? 'Discord switched on' : 'Saved')
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }

  return (
    <div className="space-y-3">
      <ol className="text-xs text-slate-600 list-decimal pl-4 space-y-0.5">
        <li>In Discord, open <b>Server Settings → Integrations → Webhooks → New Webhook</b>.</li>
        <li>Pick the channel (e.g. <i>#home</i>), then <b>Copy Webhook URL</b> and paste it below.</li>
      </ol>
      <Field label="Webhook URL" hint={has ? `Saved: ${c.config.webhook_url} — leave empty to keep it` : undefined}>
        <input className="input font-mono text-xs" autoComplete="off" spellCheck={false} value={url}
          onChange={(e) => setUrl(e.target.value)} placeholder={has ? 'Paste a new URL to replace it' : 'https://discord.com/api/webhooks/…'} />
      </Field>
      <Field label="Ping when posting" hint="Optional. For a role use <@&ROLE_ID>, for a person <@USER_ID>.">
        <div className="flex gap-2">
          <select className="input w-40" value={['', '@here', '@everyone'].includes(mention) ? mention : 'custom'}
            onChange={(e) => setMention(e.target.value === 'custom' ? '<@&>' : e.target.value)}>
            <option value="">Nobody</option>
            <option value="@here">@here</option>
            <option value="@everyone">@everyone</option>
            <option value="custom">Role / person…</option>
          </select>
          {!['', '@here', '@everyone'].includes(mention) && (
            <input className="input font-mono text-xs" value={mention} onChange={(e) => setMention(e.target.value)} placeholder="<@&123456789012345678>" />
          )}
        </div>
      </Field>
      <div className="flex flex-wrap gap-2">
        <button className="btn-primary btn-sm" disabled={busy} onClick={() => save(!c.enabled && (has || url.trim()))}>
          {busy ? 'Saving…' : !c.enabled ? 'Save & switch on' : 'Save'}
        </button>
        <button className="btn-secondary btn-sm" disabled={!has || testing} onClick={onTest}>{testing ? 'Sending…' : 'Send test message'}</button>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ Telegram
function TelegramForm({ c, onSaved, onTest, testing }) {
  const toast = useToast()
  const [token, setToken] = useState('')
  const [chatId, setChatId] = useState(c.config?.chat_id || '')
  const [chatTitle, setChatTitle] = useState(c.config?.chat_title || '')
  const [found, setFound] = useState(null)       // {bot, chats}
  const [busy, setBusy] = useState('')
  const hasToken = c.has_secret?.bot_token

  const find = async () => {
    setBusy('find')
    try {
      const r = await api('notifications/telegram/chats', { method: 'POST', body: { bot_token: token.trim() || null } })
      setFound(r)
      if (r.chats.length === 1 && !chatId) { setChatId(r.chats[0].id); setChatTitle(r.chats[0].title) }
    } catch (e) { toast(e.message, 'error') } finally { setBusy('') }
  }

  const save = async (enable) => {
    setBusy('save')
    try {
      const config = { chat_id: String(chatId).trim(), chat_title: chatTitle }
      if (token.trim()) config.bot_token = token.trim()
      const body = { config }
      if (enable) body.enabled = true
      onSaved(await api('notifications/channels/telegram', { method: 'PUT', body }))
      setToken('')
      toast(enable ? 'Telegram switched on' : 'Saved')
    } catch (e) { toast(e.message, 'error') } finally { setBusy('') }
  }

  const ready = (hasToken || token.trim()) && String(chatId).trim()
  const botLink = found?.bot?.username

  return (
    <div className="space-y-4">
      <div>
        <div className="text-xs font-semibold text-slate-700 mb-1">1 · Create a bot</div>
        <p className="text-xs text-slate-600 mb-2">In Telegram, chat with <b>@BotFather</b>, send <code className="bg-slate-100 px-1 rounded">/newbot</code>, pick a name, and paste the token it gives you.</p>
        <Field label="Bot token" hint={hasToken ? `Saved: ${c.config.bot_token} — leave empty to keep it` : undefined}>
          <input className="input font-mono text-xs" autoComplete="off" spellCheck={false} value={token}
            onChange={(e) => setToken(e.target.value)} placeholder={hasToken ? 'Paste a new token to replace it' : '123456789:AAH…'} />
        </Field>
      </div>

      <div>
        <div className="text-xs font-semibold text-slate-700 mb-1">2 · Choose where to send</div>
        <p className="text-xs text-slate-600 mb-2">
          Open {botLink ? <a className="text-brand-700 underline" href={`https://t.me/${botLink}`} target="_blank" rel="noreferrer">@{botLink}</a> : 'your bot'} and press <b>Start</b>
          {' '}— or add it to your family group and send any message there. Then:
        </p>
        <button className="btn-secondary btn-sm" disabled={busy === 'find' || !(hasToken || token.trim())} onClick={find}>
          {busy === 'find' ? <Spinner className="w-4 h-4" /> : <RefreshCw size={14} />} Find my chat
        </button>
        {found && (
          found.chats.length === 0 ? (
            <p className="text-xs text-amber-800 bg-amber-50 rounded-lg px-3 py-2 mt-2">
              No messages yet. Send “hi” to @{found.bot.username} in Telegram, then press Find my chat again.
            </p>
          ) : (
            <div className="mt-2 space-y-1.5">
              {found.chats.map((ch) => (
                <label key={ch.id} className={`flex items-center gap-3 rounded-xl border px-3 py-2 cursor-pointer ${String(chatId) === ch.id ? 'border-brand-600 bg-brand-50' : 'border-slate-200 hover:bg-slate-50'}`}>
                  <input type="radio" name="tgchat" className="accent-brand-700" checked={String(chatId) === ch.id} onChange={() => { setChatId(ch.id); setChatTitle(ch.title) }} />
                  <span className="text-sm flex-1">{ch.title}</span>
                  <span className="text-[11px] text-slate-500">{ch.type === 'private' ? 'Direct message' : ch.type}</span>
                </label>
              ))}
            </div>
          )
        )}
        <details className="mt-2">
          <summary className="text-xs text-slate-500 cursor-pointer">Enter chat ID manually</summary>
          <input className="input font-mono text-xs mt-2 max-w-xs" value={chatId} onChange={(e) => { setChatId(e.target.value); setChatTitle('') }} placeholder="-1001234567890 or @channel" />
        </details>
        {chatId && <p className="text-xs text-slate-600 mt-2">Sending to: <b>{chatTitle || chatId}</b></p>}
      </div>

      <div className="flex flex-wrap gap-2">
        <button className="btn-primary btn-sm" disabled={busy === 'save' || !ready} onClick={() => save(!c.enabled)}>
          {busy === 'save' ? 'Saving…' : !c.enabled ? 'Save & switch on' : 'Save'}
        </button>
        <button className="btn-secondary btn-sm" disabled={!!c.problem || testing} onClick={onTest}>{testing ? 'Sending…' : 'Send test message'}</button>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ section
export default function NotificationSettings({ Section }) {
  const { user } = useAuth()
  const toast = useToast()
  const [channels, setChannels] = useState(null)
  const [st, setSt] = useState(null)
  const [open, setOpen] = useState(null)
  const [testing, setTesting] = useState(null)
  const [running, setRunning] = useState(false)
  const admin = user.is_admin

  const load = () => {
    api('notifications/channels').then(setChannels).catch((e) => toast(e.message, 'error'))
    api('notifications/status').then(setSt).catch(() => {})
  }
  useEffect(load, []) // eslint-disable-line react-hooks/exhaustive-deps

  const replace = (row) => { setChannels((cs) => cs.map((c) => (c.channel === row.channel ? row : c))); api('notifications/status').then(setSt) }

  const toggle = async (c, on) => {
    if (on && c.problem) {
      if (c.managed_in_app) setOpen(c.channel)
      else toast(c.problem, 'error')
      return
    }
    try { replace(await api(`notifications/channels/${c.channel}`, { method: 'PUT', body: { enabled: on } })); toast(`${c.label} ${on ? 'on' : 'off'}`) } catch (e) { toast(e.message, 'error') }
  }

  const test = async (c) => {
    setTesting(c.channel)
    try {
      const r = await api(`notifications/channels/${c.channel}/test`, { method: 'POST' })
      toast(r.detail, r.ok ? 'ok' : 'error')
    } catch (e) { toast(e.message, 'error') } finally {
      setTesting(null)
      api('notifications/channels').then(setChannels)
    }
  }

  const runNow = async () => {
    setRunning(true)
    try {
      const r = await api('notifications/run', { method: 'POST' })
      const sent = Object.entries(r.sent).filter(([, n]) => n).map(([k, n]) => `${channels.find((c) => c.channel === k)?.label || k}: ${n}`)
      if (r.errors.length) toast(r.errors.join(' · '), 'error')
      else toast(sent.length ? `Sent — ${sent.join(', ')}` : r.due ? 'Already sent — nothing new to send' : 'Nothing is due right now')
    } catch (e) { toast(e.message, 'error') } finally { setRunning(false); load() }
  }

  if (!channels || !st) return null
  const anyOn = channels.some((c) => c.enabled && !c.problem)

  return (
    <Section icon={Bell} title="Notifications">
      <p className="text-sm text-slate-600 -mt-2 mb-4">
        Every day at <b>{st.reminder_time}</b> ({st.timezone}), each channel that is switched on gets one message
        listing the warranties about to end — {tierText(st.reminder_days)}.
      </p>

      <ul className="space-y-2">
        {channels.map((c) => {
          const M = META[c.channel]
          const expanded = open === c.channel
          return (
            <li key={c.channel} className={`rounded-2xl border ${c.enabled && !c.problem ? 'border-brand-200 bg-brand-50/30' : 'border-slate-200'}`}>
              <div className="flex items-center gap-3 p-3">
                <div className="w-10 h-10 rounded-xl grid place-items-center shrink-0 text-white" style={{ background: M.color }}><M.icon size={19} /></div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-slate-900 flex items-center gap-2">
                    {c.label}
                    {c.channel === 'telegram' && c.config?.chat_title && <span className="text-xs font-normal text-slate-500 truncate">→ {c.config.chat_title}</span>}
                    {!c.managed_in_app && <span className="chip bg-slate-100 text-slate-500 font-normal">.env</span>}
                  </div>
                  <div className="text-xs mt-0.5"><StatusLine c={c} /></div>
                </div>
                {admin && c.managed_in_app && (
                  <button className="btn-ghost btn-sm" onClick={() => setOpen(expanded ? null : c.channel)} aria-expanded={expanded} aria-label={`${c.problem ? 'Set up' : 'Edit'} ${c.label}`}>
                    <Settings2 size={15} /> <span className="hidden sm:inline">{c.problem ? 'Set up' : 'Edit'}</span>
                    <ChevronDown size={14} className={`transition ${expanded ? 'rotate-180' : ''}`} />
                  </button>
                )}
                {admin && !c.managed_in_app && !c.problem && (
                  <button className="btn-ghost btn-sm" disabled={testing === c.channel} onClick={() => test(c)}>{testing === c.channel ? 'Sending…' : 'Test'}</button>
                )}
                <Switch checked={c.enabled && !c.problem} disabled={!admin} label={`${c.label} notifications`} onChange={(on) => toggle(c, on)} />
              </div>
              {expanded && (
                <div className="border-t border-slate-200/70 p-4 bg-white rounded-b-2xl">
                  <p className="text-xs text-slate-500 mb-3">{M.blurb}</p>
                  {c.channel === 'discord'
                    ? <DiscordForm c={c} onSaved={replace} onTest={() => test(c)} testing={testing === c.channel} />
                    : <TelegramForm c={c} onSaved={replace} onTest={() => test(c)} testing={testing === c.channel} />}
                </div>
              )}
            </li>
          )
        })}
      </ul>

      <div className="flex flex-wrap items-center justify-between gap-3 mt-4 pt-4 border-t border-slate-100">
        <p className="text-sm text-slate-600">
          {st.due_now ? `${st.due_now} warranty reminder${st.due_now > 1 ? 's are' : ' is'} due now.` : 'No reminders are due right now.'}
          {!anyOn && ' Switch on at least one channel to get reminders.'}
        </p>
        {admin && anyOn && (
          <button className="btn-secondary btn-sm" disabled={running} onClick={runNow}>{running ? 'Sending…' : 'Send due reminders now'}</button>
        )}
      </div>
      {!admin && <p className="text-xs text-slate-500 mt-2">Only an admin can change these.</p>}
    </Section>
  )
}
