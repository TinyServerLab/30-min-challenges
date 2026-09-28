import { useState } from 'react'
import { Download, ExternalLink, FileText, Trash2 } from 'lucide-react'
import { api, fileUrl, thumbUrl } from '../lib/api'
import { fileSize, KIND_LABEL } from '../lib/format'
import { Modal, useToast } from './ui'

export default function Attachments({ items, onChange, editable = true }) {
  const [view, setView] = useState(null)
  const toast = useToast()

  const remove = async (a) => {
    if (!confirm(`Delete ${a.original_filename}?`)) return
    try {
      await api(`attachments/${a.id}`, { method: 'DELETE' })
      onChange?.(items.filter((x) => x.id !== a.id))
    } catch (e) { toast(e.message, 'error') }
  }
  const setKind = async (a, kind) => {
    try {
      const u = await api(`attachments/${a.id}`, { method: 'PATCH', body: { kind } })
      onChange?.(items.map((x) => (x.id === a.id ? u : x)))
    } catch (e) { toast(e.message, 'error') }
  }

  if (!items.length) return null
  return (
    <>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {items.map((a) => (
          <div key={a.id} className="group rounded-xl border border-slate-200 overflow-hidden bg-white">
            <button type="button" onClick={() => setView(a)} className="block w-full aspect-[4/3] bg-slate-100 relative">
              {a.has_thumb
                ? <img src={thumbUrl(a.id)} alt={a.original_filename} className="w-full h-full object-cover object-top" loading="lazy" />
                : <div className="w-full h-full grid place-items-center text-slate-400"><FileText size={32} /></div>}
              {a.content_type === 'application/pdf' && <span className="absolute top-2 left-2 chip bg-rose-600 text-white">PDF</span>}
            </button>
            <div className="p-2">
              {editable ? (
                <select className="w-full text-xs font-medium bg-transparent -ml-0.5 focus:outline-none" value={a.kind} onChange={(e) => setKind(a, e.target.value)}>
                  {Object.entries(KIND_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              ) : <div className="text-xs font-medium">{KIND_LABEL[a.kind]}</div>}
              <div className="flex items-center justify-between gap-1 mt-0.5">
                <span className="text-[11px] text-slate-500 truncate" title={a.original_filename}>{fileSize(a.size_bytes)} · {a.original_filename}</span>
                {editable && <button type="button" className="text-slate-400 hover:text-rose-600 p-1" onClick={() => remove(a)} title="Delete"><Trash2 size={14} /></button>}
              </div>
            </div>
          </div>
        ))}
      </div>

      <Modal open={!!view} onClose={() => setView(null)} title={view ? `${KIND_LABEL[view.kind]} · ${view.original_filename}` : ''} wide>
        {view && (
          <div className="space-y-3">
            <div className="rounded-xl bg-slate-100 overflow-hidden">
              {view.content_type === 'application/pdf'
                ? <iframe title="pdf" src={fileUrl(view.id)} className="w-full h-[65vh]" />
                : <img src={fileUrl(view.id)} alt="" className="w-full max-h-[70vh] object-contain" />}
            </div>
            <div className="flex gap-2 justify-end">
              <a className="btn-secondary btn-sm" href={fileUrl(view.id)} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Open</a>
              <a className="btn-secondary btn-sm" href={fileUrl(view.id, true)}><Download size={14} /> Download</a>
            </div>
          </div>
        )}
      </Modal>
    </>
  )
}
