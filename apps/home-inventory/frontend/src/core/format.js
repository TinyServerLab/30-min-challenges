const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })
const inrExact = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 0, maximumFractionDigits: 2 })

export const money = (v, currency = 'INR', exact = false) => {
  const n = Number(v || 0)
  if (currency && currency !== 'INR') {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 2 }).format(n)
  }
  return (exact ? inrExact : inr).format(n)
}

export const compactMoney = (v) => {
  const n = Number(v || 0)
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(1).replace(/\.0$/, '')}Cr`
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(1).replace(/\.0$/, '')}L`
  if (n >= 1e3) return `₹${(n / 1e3).toFixed(1).replace(/\.0$/, '')}k`
  return `₹${n.toFixed(0)}`
}

export const fmtDate = (d) => {
  if (!d) return '—'
  const dt = new Date(d.length === 10 ? d + 'T00:00:00' : d)
  return dt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export const daysText = (days) => {
  if (days === null || days === undefined) return 'No warranty'
  if (days < 0) {
    const a = -days
    return a < 60 ? `Expired ${a}d ago` : `Expired ${Math.round(a / 30.4)}mo ago`
  }
  if (days === 0) return 'Ends today'
  if (days === 1) return 'Ends tomorrow'
  if (days < 60) return `${days} days left`
  if (days < 730) return `${Math.round(days / 30.4)} months left`
  return `${(days / 365).toFixed(1).replace(/\.0$/, '')} years left`
}

export const fileSize = (b) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`)

export const todayISO = () => {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

export const STATUS_LABEL = {
  active: 'In use', in_repair: 'In repair', disposed: 'Disposed', sold: 'Sold', lost: 'Lost', gifted: 'Gifted',
}
export const KIND_LABEL = {
  invoice: 'Invoice', warranty_card: 'Warranty card', photo: 'Photo', manual: 'Manual', receipt: 'Receipt', other: 'Other',
}
