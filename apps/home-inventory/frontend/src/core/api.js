// All URLs are resolved against <base href>, which the server sets to BASE_PATH (e.g. /inventory/).
export const BASE_URL = new URL('.', document.baseURI)
export const BASENAME = BASE_URL.pathname.replace(/\/$/, '') // "/inventory" or ""

export const apiUrl = (path, params) => {
  const u = new URL('api/' + path.replace(/^\//, ''), BASE_URL)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') u.searchParams.set(k, v)
    })
  }
  return u.toString()
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

let onUnauthorized = () => {}
export const setUnauthorizedHandler = (fn) => (onUnauthorized = fn)

export async function api(path, { method = 'GET', body, params, form, raw } = {}) {
  const headers = { 'X-Requested-With': 'fetch' }
  let payload
  if (form) payload = form
  else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  const res = await fetch(apiUrl(path, params), { method, headers, body: payload, credentials: 'same-origin' })
  if (res.status === 401 && !path.startsWith('auth/login')) {
    onUnauthorized()
    throw new ApiError(401, 'Session expired')
  }
  if (!res.ok) {
    let msg = res.statusText
    try {
      const j = await res.json()
      msg = typeof j.detail === 'string' ? j.detail
        : Array.isArray(j.detail) ? j.detail.map((d) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join('; ')
        : msg
    } catch { /* not json */ }
    throw new ApiError(res.status, msg)
  }
  if (raw) return res
  if (res.status === 204) return null
  return res.json()
}

export const fileUrl = (id, download) => apiUrl(`attachments/${id}/file`, download ? { download: 1 } : undefined)
export const thumbUrl = (id) => apiUrl(`attachments/${id}/thumb`)
