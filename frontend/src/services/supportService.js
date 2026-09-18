// src/services/supportService.js
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

const getAuthToken = () => localStorage.getItem('brainopx_token')

async function request(path, options = {}) {
  const token = getAuthToken()
  const headers = {
    ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    ...(options.headers || {}),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload.detail || `API Error: ${response.status}`)
  }
  return response.json()
}

// ─── USER SIDE ──────────────────────────────────────────────

export const listMyTickets = () => request('/support/tickets')

export const createSupportTicket = ({ subject, body, request_id }) =>
  request('/support/tickets', {
    method: 'POST',
    body: JSON.stringify({ subject, body, request_id }),
  })

export const getMyTicket = (id) => request(`/support/tickets/${id}`)

export const sendUserReply = (id, body) =>
  request(`/support/tickets/${id}/messages`, {
    method: 'POST',
    body: JSON.stringify({ body }),
  })

// ─── SPECIALIST SIDE ─────────────────────────────────────────

export const listSpecialistTickets = (status) =>
  request(`/support/specialist/tickets${status ? `?status=${encodeURIComponent(status)}` : ''}`)

export const getSpecialistTicket = (id) => request(`/support/specialist/tickets/${id}`)

export const sendSpecialistReply = (id, body) =>
  request(`/support/specialist/tickets/${id}/messages`, {
    method: 'POST',
    body: JSON.stringify({ body }),
  })

export const claimTicket = (id) =>
  request(`/support/specialist/tickets/${id}/claim`, { method: 'POST' })

export const resolveTicket = (id) =>
  request(`/support/specialist/tickets/${id}/resolve`, { method: 'POST' })

export const reopenTicket = (id) =>
  request(`/support/specialist/tickets/${id}/reopen`, { method: 'POST' })
