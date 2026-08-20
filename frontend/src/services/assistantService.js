const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function authFetchHandler(url, options = {}) {
  const token = localStorage.getItem('brainopx_token')

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

  if (resp.status === 401) {
    localStorage.removeItem('brainopx_token')
    localStorage.removeItem('brainopx_user')
    window.location.href = '/login'
    throw new Error('Session expired. Please login again.')
  }

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(err?.detail || 'Assistant request failed.')
  }
  return resp.json()
}

export const sendAssistantMessage = async ({
  message,
  conversationId = null,
  taskId = null,
  attachmentIds = null,
}) => {
  return authFetchHandler(`${API_BASE}/api/assistant/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      task_id: taskId,
      attachment_ids: attachmentIds && attachmentIds.length ? attachmentIds : null,
    }),
  })
}

export const uploadAssistantAttachment = async ({ file, conversationId = null }) => {
  const formData = new FormData()
  formData.append('file', file)
  if (conversationId) formData.append('conversation_id', conversationId)

  return authFetchHandler(`${API_BASE}/api/assistant/attachments`, {
    method: 'POST',
    body: formData,
  })
}

// authFetchHandler always parses the response as JSON, which doesn't work for a
// binary file download — this does its own fetch, blob, and browser-side save.
export const downloadAssistantExport = async ({ conversationId, format }) => {
  const token = localStorage.getItem('brainopx_token')
  if (!token) {
    window.location.href = '/login'
    throw new Error('Not authenticated')
  }

  const resp = await fetch(
    `${API_BASE}/api/assistant/conversations/${conversationId}/export?format=${format}`,
    { headers: { Authorization: `Bearer ${token}` } }
  )

  if (resp.status === 401) {
    localStorage.removeItem('brainopx_token')
    localStorage.removeItem('brainopx_user')
    window.location.href = '/login'
    throw new Error('Session expired. Please login again.')
  }

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(err?.detail || 'Export failed.')
  }

  const disposition = resp.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  const filename = match ? match[1] : `assistant-export.${format}`

  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export const listAssistantConversations = async () => {
  return authFetchHandler(`${API_BASE}/api/assistant/conversations`)
}

export const getAssistantConversation = async (conversationId) => {
  return authFetchHandler(`${API_BASE}/api/assistant/conversations/${conversationId}`)
}

export const deleteAssistantConversation = async (conversationId) => {
  return authFetchHandler(`${API_BASE}/api/assistant/conversations/${conversationId}`, {
    method: 'DELETE',
  })
}

export const clearAssistantConversations = async () => {
  return authFetchHandler(`${API_BASE}/api/assistant/conversations`, {
    method: 'DELETE',
  })
}
