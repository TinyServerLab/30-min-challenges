import { Link } from 'react-router-dom'
import { thumbUrl } from '../core/api'
import { fmtDate, money } from '../core/format'
import { CategoryIcon, WarrantyBadge } from './ui'

export default function AssetRow({ a, showExpiry = true }) {
  return (
    <Link to={`/assets/${a.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition">
      {a.thumb_attachment_id ? (
        <img src={thumbUrl(a.thumb_attachment_id)} alt="" loading="lazy" className="w-10 h-10 rounded-xl object-cover bg-slate-100 shrink-0" />
      ) : (
        <CategoryIcon icon={a.category_icon} color={a.category_color} />
      )}
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium text-slate-900 truncate">{a.name}</div>
        <div className="text-xs text-slate-500 truncate">
          {[a.brand, a.category_name, a.location].filter(Boolean).join(' · ') || 'Uncategorised'}
        </div>
      </div>
      <div className="text-right shrink-0">
        {showExpiry ? (
          <>
            <WarrantyBadge state={a.warranty_state} days={a.days_left} />
            {a.effective_expiry_date && <div className="text-[11px] text-slate-500 mt-1">{fmtDate(a.effective_expiry_date)}</div>}
          </>
        ) : (
          <>
            <div className="text-sm font-medium tabular-nums">{money(a.purchase_price, a.currency)}</div>
            <div className="text-[11px] text-slate-500">{fmtDate(a.purchase_date)}</div>
          </>
        )}
      </div>
    </Link>
  )
}
