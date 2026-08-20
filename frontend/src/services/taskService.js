import { authFetch } from './Authenticationservice.js'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

/**
 * Utility to handle 401 responses by redirecting to login.
 * If the backend returns 401, the token is expired or invalid → redirect.
 */
async function authFetchHandler(url, options = {}) {
  const token = localStorage.getItem('brainopx_token')
  
  // No token → redirect to login
  if (!token) {
    window.location.href = '/login'
    throw new Error('Not authenticated')
  }

  const resp = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${token}`,
    },
  })

  // 401 → token expired/invalid → clear & redirect
  if (resp.status === 401) {
    localStorage.removeItem('brainopx_token')
    localStorage.removeItem('brainopx_user')
    window.location.href = '/login'
    throw new Error('Session expired. Please login again.')
  }

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(err?.detail || 'Failed to fetch tasks.')
  }
  return resp.json()
}

// List all tasks
export const listTasks = async () => {
  return authFetchHandler(`${API_BASE}/api/tasks`)
}

// Get a single task
export const getTask = async (taskId) => {
  return authFetchHandler(`${API_BASE}/api/tasks/${taskId}`)
}

// Create a new task
export const createTask = async ({ name, description, category, file }) => {
  const formData = new FormData()
  formData.append('name', name)
  formData.append('description', description || '')
  formData.append('category', category || 'report_analyses')
  formData.append('target_table', '')
  formData.append('file', file)

  return authFetchHandler(`${API_BASE}/api/tasks`, {
    method: 'POST',
    body: formData,
  })
}

// Update an existing task
export const updateTask = async (taskId, { name, description, category, file }) => {
  const formData = new FormData()
  formData.append('name', name)
  formData.append('description', description || '')
  formData.append('category', category || 'report_analyses')
  formData.append('target_table', '')
  if (file) formData.append('file', file)

  return authFetchHandler(`${API_BASE}/api/tasks/${taskId}`, {
    method: 'PUT',
    body: formData,
  })
}

// Delete a task
export const deleteTask = async (taskId) => {
  return authFetchHandler(`${API_BASE}/api/tasks/${taskId}`, {
    method: 'DELETE',
  })
}
