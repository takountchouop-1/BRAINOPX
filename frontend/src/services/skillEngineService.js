const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

/**
 * Utility to handle auth and 401 redirects for skill-engine API calls.
 */
async function skillFetch(url, options = {}) {
  const token = localStorage.getItem('brainopx_token')

  if (!token) {
    window.location.href = '/login'
    throw new Error('Not authenticated')
  }

  const isFormData = options.body instanceof FormData
  const headers = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(options.headers || {}),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const resp = await fetch(`${API_BASE}${url}`, { ...options, headers })

  if (resp.status === 401) {
    localStorage.removeItem('brainopx_token')
    window.location.href = '/login'
    throw new Error('Session expired. Please login again.')
  }

  if (!resp.ok) {
    const payload = await resp.json().catch(() => ({}))
    throw new Error(payload?.detail || 'Skill Engine request failed.')
  }

  return resp.json()
}

/**
 * Parse a Skill Engine task's rules file into structured rules.
 * Rules are cached on the task's category_metadata.
 */
export const parseTaskRules = async (taskId) => {
  return skillFetch(`/api/skill-engine/tasks/${taskId}/parse-rules`, {
    method: 'POST',
  })
}

/**
 * Start a Rule Engine run.
 *
 * @param {Object} opts
 * @param {number} [opts.taskId] - existing Skill Engine task to pull rules from
 * @param {File}   [opts.rulesFile] - standalone rules file
 * @param {File}   [opts.inputFile] - file containing the input/data to evaluate
 * @param {string} [opts.inputText] - pasted input/data to evaluate
 */
export const startRun = async ({ taskId, rulesFile, inputFile, inputText }) => {
  const formData = new FormData()
  if (taskId) formData.append('task_id', String(taskId))
  if (rulesFile) formData.append('file', rulesFile)
  if (inputFile) formData.append('input_file', inputFile)
  if (inputText) formData.append('input_text', inputText)

  return skillFetch('/api/skill-engine/runs', {
    method: 'POST',
    body: formData,
  })
}

/**
 * Get a run and its per-rule results.
 */
export const getRun = async (runId) => {
  return skillFetch(`/api/skill-engine/runs/${runId}`)
}

/**
 * Send a follow-up message for a single rule's conversation thread.
 */
export const sendRuleChat = async ({ runId, ruleId, message }) => {
  const formData = new FormData()
  formData.append('message', message)
  return skillFetch(`/api/skill-engine/runs/${runId}/rules/${ruleId}/chat`, {
    method: 'POST',
    body: formData,
  })
}

/**
 * Re-run the AI workflow for one rule with updated input text.
 */
export const reEvaluateRule = async ({ runId, ruleId, inputText }) => {
  const formData = new FormData()
  formData.append('input_text', inputText)
  return skillFetch(`/api/skill-engine/runs/${runId}/rules/${ruleId}/re-evaluate`, {
    method: 'POST',
    body: formData,
  })
}

/**
 * Route a user's free-form message to the most relevant rule in a run.
 * The AI analyses the message against each rule's task and keywords,
 * and returns the matched rule and a rule-specific response.
 */
export const routeMessage = async ({ runId, message }) => {
  const formData = new FormData()
  formData.append('message', message)
  return skillFetch(`/api/skill-engine/runs/${runId}/route`, {
    method: 'POST',
    body: formData,
  })
}

/**
 * Start a guided step-by-step walkthrough for a run.
 * The AI walks the user through each rule's task one at a time.
 * Returns the first step's prompt and the session_id.
 */
export const startGuidedSession = async ({ runId }) => {
  const formData = new FormData()
  formData.append('run_id', String(runId))
  return skillFetch('/api/skill-engine/guided-sessions', {
    method: 'POST',
    body: formData,
  })
}

/**
 * Send a message to an active guided session.
 * The AI processes the input against the current step (rule).
 * Advances to the next step when the current one is passed.
 */
export const sendGuidedMessage = async ({ sessionId, message }) => {
  const formData = new FormData()
  formData.append('message', message)
  return skillFetch(`/api/skill-engine/guided-sessions/${sessionId}/message`, {
    method: 'POST',
    body: formData,
  })
}

/**
 * Get the current state of a guided session.
 */
export const getGuidedSession = async ({ sessionId }) => {
  return skillFetch(`/api/skill-engine/guided-sessions/${sessionId}`)
}

/**
 * List the steps already completed in a guided session, with what
 * the user submitted for each. Source list for editing mode.
 */
export const getCompletedGuidedSteps = async ({ sessionId }) => {
  return skillFetch(`/api/skill-engine/guided-sessions/${sessionId}/completed-steps`)
}

/**
 * Correct the answer already submitted for a completed step of a
 * guided session, without disturbing the session's current position.
 */
export const editGuidedStep = async ({ sessionId, stepIndex, value }) => {
  const formData = new FormData()
  formData.append('step_index', String(stepIndex))
  formData.append('value', value)
  return skillFetch(`/api/skill-engine/guided-sessions/${sessionId}/edit`, {
    method: 'POST',
    body: formData,
  })
}

