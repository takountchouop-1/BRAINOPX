const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const TOKEN_STORAGE_KEY = 'brainopx_token'

async function handleResponse(response) {
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const message = payload?.detail || payload?.error || 'Something went wrong.'
    throw new Error(message)
  }
  return response.json()
}

export async function login({ email, password }) {
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
    credentials: 'include',
  })

  const data = await handleResponse(response)
  
  //  Store the token
  if (data.access_token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token)
  }
  
  //  Store user info
  if (data.user) {
    localStorage.setItem('user_name', data.user.full_name || 'User')
  }
  
  return data
}

export async function requestPasswordReset({ email }) {
  const response = await fetch(`${API_BASE_URL}/api/auth/request-password-reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })

  return handleResponse(response)
}

export async function verifyResetCode({ email, code }) {
  const response = await fetch(`${API_BASE_URL}/api/auth/verify-reset-code`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, code }),
  })

  return handleResponse(response)
}

export async function resetPassword({ email, code, newPassword }) {
  const response = await fetch(`${API_BASE_URL}/api/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, code, new_password: newPassword }),
  })

  return handleResponse(response)
}

/**
 * authFetch — use this for any request that needs to prove who's logged in.
 * Automatically attaches the stored JWT as an Authorization header.
 *
 * If `options.body` is a FormData instance (used for file uploads), we
 * deliberately do NOT set Content-Type ourselves — the browser sets it
 * automatically with the correct multipart boundary. Setting it manually
 * would break the upload.
 */
export async function authFetch(path, options = {}) {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY)
  
  //  Redirect to login if no token
  if (!token) {
    console.warn('No token found, redirecting to login...')
    window.location.href = '/login'
    throw new Error('Not authenticated')
  }
  
  const isFormData = options.body instanceof FormData

  const headers = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(options.headers || {}),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

  //  Handle 401 - token expired
  if (response.status === 401) {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    window.location.href = '/login'
    throw new Error('Session expired. Please login again.')
  }

  return handleResponse(response)
}

export async function getCurrentUser() {
  return authFetch('/api/auth/me')
}

//  Add logout function
export async function logout() {
  localStorage.removeItem(TOKEN_STORAGE_KEY)
  localStorage.removeItem('user_name')
  window.location.href = '/login'
}