const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

const getAuthToken = () => {
  return localStorage.getItem('brainopx_token')
}

const handleResponse = async (response) => {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `API Error: ${response.status}`)
  }
  return response.json()
}

export const fetchNotifications = async () => {
  const token = getAuthToken()
  const response = await fetch(`${API_BASE_URL}/notifications/`, {
    headers: { 'Authorization': `Bearer ${token}` }
  })
  return handleResponse(response)
}

export const fetchUnreadCount = async () => {
  const token = getAuthToken()
  const response = await fetch(`${API_BASE_URL}/notifications/unread-count`, {
    headers: { 'Authorization': `Bearer ${token}` }
  })
  return handleResponse(response)
}

export const markAsRead = async (notificationId) => {
  const token = getAuthToken()
  const response = await fetch(`${API_BASE_URL}/notifications/${notificationId}/read`, {
    method: 'PUT',
    headers: { 'Authorization': `Bearer ${token}` }
  })
  return handleResponse(response)
}

export const markAllAsRead = async () => {
  const token = getAuthToken()
  const response = await fetch(`${API_BASE_URL}/notifications/read-all`, {
    method: 'PUT',
    headers: { 'Authorization': `Bearer ${token}` }
  })
  return handleResponse(response)
}

