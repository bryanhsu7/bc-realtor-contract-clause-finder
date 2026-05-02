/**
 * Base URL for API requests. Empty string = same origin (Vite dev proxy `/api` → :8000).
 * Set VITE_API_URL when the frontend is hosted separately from the API.
 */
export function getApiBaseUrl() {
  const raw = import.meta.env.VITE_API_URL
  if (raw == null || raw === '') return ''
  return String(raw).replace(/\/$/, '')
}

export function apiUrl(path) {
  const base = getApiBaseUrl()
  const p = path.startsWith('/') ? path : `/${path}`
  return base ? `${base}${p}` : p
}

/** User-visible explanation when chat streaming fails */
export function describeChatRequestFailure(error, httpStatus) {
  const status = httpStatus ?? error?.httpStatus
  if (status === 401 || status === 403) {
    return (
      'The API rejected this request (authentication). Check backend configuration and keys.'
    )
  }
  const msg = error?.message || String(error)
  if (
    msg.includes('Failed to fetch') ||
    msg.includes('NetworkError') ||
    msg.includes('Network request failed') ||
    msg.includes('Load failed')
  ) {
    return (
      "**Can't reach the assistant API.**\n\n" +
      'Start the backend from the project root with `OPENAI_API_KEY` set, then try again:\n\n' +
      '`source venv/bin/activate && python -m backend.main`\n\n' +
      'With `npm run dev`, requests go to `/api` on port **3000**, which proxies to the API on **8000**.'
    )
  }
  if (status >= 500) {
    return `The server returned an error (${status}). Check the terminal running the backend.`
  }
  if (status >= 400) {
    const t = msg.trim()
    return t.length > 400 ? `${t.slice(0, 400)}…` : t || `Request failed (${status}).`
  }
  const t = msg.trim()
  return t.length > 400 ? `${t.slice(0, 400)}…` : t || 'Something went wrong. Please try again.'
}
