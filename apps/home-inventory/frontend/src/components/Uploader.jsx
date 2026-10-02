import { useRef, useState } from 'react'
import { Camera, FileText, Upload } from 'lucide-react'
import { api } from '../core/api'
import { Spinner, useToast } from './ui'

/** Upload one or more files. Calls onUploaded(result) per file.
 *  props: kind, assetId, extract, label, compact */
export default function Uploader({ kind = 'invoice', assetId, extract = false, onUploaded, label, compact }) {
  const [busy, setBusy] = useState('')
  const [drag, setDrag] = useState(false)
  const fileRef = useRef()
  const camRef = useRef()
  const toast = useToast()

  const upload = async (files) => {
    for (const f of files) {
      const fd = new FormData()
      fd.append('file', f)
      fd.append('kind', kind)
      if (assetId) fd.append('asset_id', assetId)
      fd.append('extract', extract ? 'true' : 'false')
      setBusy(extract ? 'Reading invoice… this can take a few seconds' : `Uploading ${f.name}…`)
      try {
        const r = await api('attachments', { method: 'POST', form: fd })
        onUploaded?.(r)
      } catch (e) {
        toast(`${f.name}: ${e.message}`, 'error')
      }
    }
    setBusy('')
  }

  const onPick = (e) => { const fs = [...e.target.files]; e.target.value = ''; if (fs.length) upload(fs) }

  const inputs = (
    <>
      <input ref={fileRef} type="file" hidden multiple={!extract} accept="image/*,application/pdf,.heic,.heif" onChange={onPick} />
      <input ref={camRef} type="file" hidden accept="image/*" capture="environment" onChange={onPick} />
    </>
  )

  if (busy) {
    return (
      <div className={`rounded-2xl border-2 border-dashed border-brand-300 bg-brand-50/50 ${compact ? 'p-4' : 'p-8'} flex items-center justify-center gap-3 text-sm text-brand-800`}>
        <Spinner /> {busy}
      </div>
    )
  }

  if (compact) {
    return (
      <div className="flex flex-wrap gap-2">
        {inputs}
        <button type="button" className="btn-secondary btn-sm" onClick={() => camRef.current.click()}><Camera size={14} /> Take photo</button>
        <button type="button" className="btn-secondary btn-sm" onClick={() => fileRef.current.click()}><Upload size={14} /> {label || 'Upload file'}</button>
      </div>
    )
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); upload([...e.dataTransfer.files]) }}
      className={`rounded-2xl border-2 border-dashed ${drag ? 'border-brand-500 bg-brand-50' : 'border-slate-300 bg-slate-50/60'} p-6 text-center transition`}>
      {inputs}
      <div className="mx-auto w-12 h-12 rounded-2xl bg-white shadow-sm grid place-items-center text-brand-700 mb-3"><FileText size={22} /></div>
      <div className="font-medium text-slate-800">{label || 'Add the invoice'}</div>
      <p className="text-xs text-slate-500 mt-1 mb-4">Photo or PDF · JPG, PNG, HEIC, PDF</p>
      <div className="flex flex-col sm:flex-row gap-2 justify-center">
        <button type="button" className="btn-primary" onClick={() => camRef.current.click()}><Camera size={18} /> Take photo</button>
        <button type="button" className="btn-secondary" onClick={() => fileRef.current.click()}><Upload size={18} /> Choose file</button>
      </div>
    </div>
  )
}
