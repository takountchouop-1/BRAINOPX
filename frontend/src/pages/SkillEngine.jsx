import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Box,
  Typography,
  Grid,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Paper,
  Chip,
  LinearProgress,
  Stack,
  TextField,
  Alert,
  CircularProgress,
  IconButton,
  Tooltip,
  Divider,
  Card,
  CardHeader,
  CardContent,
  InputBase,
  Collapse,
  Fade,
  Grow,
  Stepper,
  Step,
  StepLabel,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material'

import PlayArrowIconImport from '@mui/icons-material/PlayArrow'
import EditIconImport from '@mui/icons-material/Edit'
import CloudUploadIconImport from '@mui/icons-material/CloudUpload'
import SendIconImport from '@mui/icons-material/Send'
import CheckCircleIconImport from '@mui/icons-material/CheckCircle'
import ErrorIconImport from '@mui/icons-material/Error'
import WarningIconImport from '@mui/icons-material/Warning'
import ChatIconImport from '@mui/icons-material/Chat'
import SmartToyIconImport from '@mui/icons-material/SmartToy'
import RefreshIconImport from '@mui/icons-material/Refresh'
import RuleIconImport from '@mui/icons-material/Rule'
import UploadFileIconImport from '@mui/icons-material/UploadFile'
import ChatMessage, {
  conversationBackground,
  composerBackground,
  assistantContentStyles,
  TypingDots,
} from '../components/ChatMessage.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const PlayArrowIcon = PlayArrowIconImport?.default || PlayArrowIconImport
const CloudUploadIcon = CloudUploadIconImport?.default || CloudUploadIconImport
const SendIcon = SendIconImport?.default || SendIconImport
const CheckCircleIcon = CheckCircleIconImport?.default || CheckCircleIconImport
const ErrorIcon = ErrorIconImport?.default || ErrorIconImport
const WarningIcon = WarningIconImport?.default || WarningIconImport
const ChatIcon = ChatIconImport?.default || ChatIconImport
const SmartToyIcon = SmartToyIconImport?.default || SmartToyIconImport
const RefreshIcon = RefreshIconImport?.default || RefreshIconImport
const RuleIcon = RuleIconImport?.default || RuleIconImport
const UploadFileIcon = UploadFileIconImport?.default || UploadFileIconImport
const EditIcon = EditIconImport?.default || EditIconImport

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const STATUS_META = {
  passed: { label: 'Passed', color: 'success', icon: 'passed' },
  needs_work: { label: 'Needs Work', color: 'warning', icon: 'warning' },
  not_answered: { label: 'Not Answered', color: 'error', icon: 'error' },
}

// Border helpers (avoid nested template literals inside sx props)
const borderLight = (theme) =>
  theme.palette.mode === 'dark' ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)'

const borderFaint = (theme) =>
  theme.palette.mode === 'dark' ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)'

const borderCard = (theme) =>
  theme.palette.mode === 'dark' ? '1px solid rgba(255,255,255,0.1)' : '1px solid #e5e7eb'

const SkillEngine = () => {
  // The signed-in person, shown by their profile picture on their
  // own messages.
  const { user } = useAuth()

  const [tasks, setTasks] = useState([])
  const [tasksLoading, setTasksLoading] = useState(true)
  const [selectedTaskId, setSelectedTaskId] = useState('')

  // Rules source
  const [rulesFile, setRulesFile] = useState(null)
  const [inputFile, setInputFile] = useState(null)
  const [inputText, setInputText] = useState('')

  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState(null)
  const [run, setRun] = useState(null)

// Per-rule chat state
  const [activeChatRule, setActiveChatRule] = useState(null)
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const chatEndRef = useRef(null)

  // Rule Router state
  const [routerInput, setRouterInput] = useState('')
  const [routerChat, setRouterChat] = useState([])
  const [routerLoading, setRouterLoading] = useState(false)

  // Guided Walkthrough state
  const [guidedSession, setGuidedSession] = useState(null)
  const [guidedInput, setGuidedInput] = useState('')
  const [guidedLoading, setGuidedLoading] = useState(false)
  const [guidedChat, setGuidedChat] = useState([])

  // Editing mode: correcting the answer of an already-completed step
  const [editStep, setEditStep] = useState(null) // { stepIndex, ruleName, previewHtml }
  const [editValue, setEditValue] = useState('')
  const [editSaving, setEditSaving] = useState(false)
  const [editResultHtml, setEditResultHtml] = useState(null)
  const [editSucceeded, setEditSucceeded] = useState(false)
  const guidedEndRef = useRef(null)

  // Summary table: every input the user entered during the guided
  // walkthrough, shown once it finishes so they can review — and
  // correct — any of it in one place.
  const [summarySteps, setSummarySteps] = useState([])
  const [summaryLoading, setSummaryLoading] = useState(false)

  const loadSummarySteps = useCallback(async () => {
    if (!guidedSession?.session_id) return
    setSummaryLoading(true)
    try {
      const { getCompletedGuidedSteps } = await import('../services/skillEngineService.js')
      const data = await getCompletedGuidedSteps({ sessionId: guidedSession.session_id })
      setSummarySteps(data.steps || [])
    } catch (err) {
      console.error('Could not load the summary table:', err)
    } finally {
      setSummaryLoading(false)
    }
  }, [guidedSession?.session_id])

  useEffect(() => {
    if (guidedSession?.all_completed) {
      loadSummarySteps()
    }
  }, [guidedSession?.all_completed, loadSummarySteps])

  // The conversation now fills the panel, so it has to follow the
  // newest message the way a chat window does.
  useEffect(() => {
    guidedEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [guidedChat, guidedLoading])

  useEffect(() => {
    fetchTasks()
  }, [])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [run, activeChatRule, chatLoading])

  const fetchTasks = async () => {
    setTasksLoading(true)
    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetch(`${API_BASE}/api/tasks`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (resp.ok) {
        const data = await resp.json()
        setTasks(data)
      }
    } catch (err) {
      console.error('Failed to load tasks:', err)
    } finally {
      setTasksLoading(false)
    }
  }

  const handleReset = () => {
    setRun(null)
    setSelectedTaskId('')
    setRulesFile(null)
    setInputFile(null)
    setInputText('')
    setError(null)
    setActiveChatRule(null)
    setChatInput('')
  }

  const runWorkflows = async (e) => {
    e?.preventDefault()
    setError(null)
    setIsRunning(true)

    try {
      const { startRun } = await import('../services/skillEngineService.js')
      const data = await startRun({
        taskId: selectedTaskId || undefined,
        rulesFile: rulesFile || undefined,
        inputFile: inputFile || undefined,
        inputText: inputText || undefined,
      })
      setRun(data)
    } catch (err) {
      setError(err.message || 'Failed to run rule workflows.')
    } finally {
      setIsRunning(false)
    }
  }

  const toggleChat = (ruleId) => {
    setActiveChatRule((prev) => (prev === ruleId ? null : ruleId))
    setChatInput('')
  }

  const sendChat = async (ruleId, e) => {
    e?.preventDefault()
    if (!chatInput.trim() || chatLoading) return

    const message = chatInput.trim()
    setChatInput('')
    setChatLoading(true)

    // Show the message immediately instead of waiting for the round
    // trip — otherwise it looks like it never sent while the AI thinks.
    const optimisticUserMsg = { sender: 'user', text: message, timestamp: new Date().toISOString() }
    setRun((prev) => {
      if (!prev) return prev
      const results = prev.results.map((r) =>
        r.rule_id === ruleId
          ? { ...r, conversation: [...(r.conversation || []), optimisticUserMsg] }
          : r
      )
      return { ...prev, results }
    })

    try {
      const { sendRuleChat } = await import('../services/skillEngineService.js')
      const data = await sendRuleChat({ runId: run.id, ruleId, message })

      setRun((prev) => {
        if (!prev) return prev
        const results = prev.results.map((r) =>
          r.rule_id === ruleId ? { ...r, conversation: data.conversation } : r
        )
        return { ...prev, results }
      })
    } catch (err) {
      console.error('Chat failed:', err)
    } finally {
      setChatLoading(false)
    }
  }

// ── Rule Router handlers ──────────────────────────────────────────────
  const sendRouteMessage = async (e) => {
    e?.preventDefault()
    if (!routerInput.trim() || routerLoading) return

    const message = routerInput.trim()
    setRouterInput('')
    setRouterLoading(true)

    const userMsg = { sender: 'user', text: message, timestamp: new Date().toISOString() }
    setRouterChat((prev) => [...prev, userMsg])

    try {
      const { routeMessage } = await import('../services/skillEngineService.js')
      const data = await routeMessage({ runId: run.id, message })

      setRouterChat((prev) => [
        ...prev,
        {
          sender: 'ai',
          text: `**Routed to Rule: ${data.matched_rule?.name || 'Unknown'}**\n\n${data.ai_response}`,
          timestamp: new Date().toISOString(),
          matchedRule: data.matched_rule,
        },
      ])
    } catch (err) {
      setRouterChat((prev) => [
        ...prev,
        { sender: 'ai', text: `Routing failed: ${err.message}`, timestamp: new Date().toISOString() },
      ])
    } finally {
      setRouterLoading(false)
    }
  }

// ── Guided Walkthrough handlers ─────────────────────────────────────────
  const startGuided = async () => {
    setGuidedLoading(true)
    setGuidedChat([])
    setGuidedSession(null)

    try {
      const { startGuidedSession } = await import('../services/skillEngineService.js')
      const data = await startGuidedSession({ runId: run.id })

      // Backend returns: { session: { session_id, steps, current_step_index, ... }, initial_message }
      setGuidedSession(data.session || data)
      setGuidedChat([
        {
          sender: 'ai',
          text: data.initial_message || 'Welcome! Let me guide you through the rules.',
          timestamp: new Date().toISOString(),
        },
      ])
    } catch (err) {
      setGuidedChat([
        { sender: 'ai', text: `Could not start guided session: ${err.message}`, timestamp: new Date().toISOString() },
      ])
    } finally {
      setGuidedLoading(false)
    }
  }

  const submitGuidedMessage = async (e) => {
    e?.preventDefault()
    if (!guidedInput.trim() || guidedLoading || !guidedSession) return

    const message = guidedInput.trim()
    setGuidedInput('')
    setGuidedLoading(true)

    const userMsg = { sender: 'user', text: message, timestamp: new Date().toISOString() }
    setGuidedChat((prev) => [...prev, userMsg])

    try {
      const { sendGuidedMessage: sendGuided } = await import('../services/skillEngineService.js')
      const data = await sendGuided({ sessionId: guidedSession.session_id, message })

      // Update session state with the returned session data
      if (data.session) {
        setGuidedSession(data.session)
      }
      setGuidedChat((prev) => {
        const next = [...prev]

        // Mark the value the user just sent as validated or not, so
        // the bubble itself carries the outcome.
        for (let i = next.length - 1; i >= 0; i -= 1) {
          if (next[i].sender === 'user') {
            next[i] = { ...next[i], validated: data.passed === true }
            break
          }
        }

        return [
          ...next,
          {
            sender: 'ai',
            text: data.ai_response,
            passed: data.passed === true,
            timestamp: new Date().toISOString(),
          },
        ]
      })
    } catch (err) {
      setGuidedChat((prev) => [
        ...prev,
        { sender: 'ai', text: `Error: ${err.message}`, timestamp: new Date().toISOString() },
      ])
    } finally {
      setGuidedLoading(false)
    }
  }

  // ─── EDITING MODE: correcting an already-completed guided step ─────────────

  const openEditDialog = async (stepIndex, ruleName) => {
    setEditResultHtml(null)
    setEditSucceeded(false)
    setEditStep({ stepIndex, ruleName, previewHtml: null })
    setEditValue('')

    try {
      const { getCompletedGuidedSteps } = await import('../services/skillEngineService.js')
      const data = await getCompletedGuidedSteps({ sessionId: guidedSession.session_id })
      const found = (data.steps || []).find((s) => s.step_index === stepIndex)
      if (found) {
        setEditValue(found.user_value || '')
        setEditStep({ stepIndex, ruleName, previewHtml: found.preview_html || null })
      }
    } catch (err) {
      console.error('Could not load the previous answer:', err)
    }
  }

  const closeEditDialog = () => {
    setEditStep(null)
    setEditValue('')
    setEditResultHtml(null)
    setEditSucceeded(false)
  }

  const saveEditedStep = async () => {
    if (!editStep || !editValue.trim() || !guidedSession) return
    setEditSaving(true)
    setEditResultHtml(null)

    try {
      const { editGuidedStep } = await import('../services/skillEngineService.js')
      const data = await editGuidedStep({
        sessionId: guidedSession.session_id,
        stepIndex: editStep.stepIndex,
        value: editValue,
      })

      setEditResultHtml(data.ai_response || '')
      setEditSucceeded(!!data.edited)

      if (data.edited) {
        // The user's current position in the walkthrough is untouched
        // by the edit — this only refreshes the step list/answers.
        if (data.session) setGuidedSession(data.session)

        // Regenerate the summary table's row for this step so the
        // corrected input (and its result) is reflected immediately.
        loadSummarySteps()

        setGuidedChat((prev) => [
          ...prev,
          {
            sender: 'ai',
            text: data.ai_response,
            passed: true,
            timestamp: new Date().toISOString(),
          },
        ])
      }
    } catch (err) {
      setEditResultHtml(`<span class="failure-message">${err.message}</span>`)
    } finally {
      setEditSaving(false)
    }
  }

  const getStatusMeta = (status) => STATUS_META[status] || STATUS_META.not_answered
  const getStatusIcon = (key) => {
    if (key === 'passed') return <CheckCircleIcon fontSize="small" />
    if (key === 'warning') return <WarningIcon fontSize="small" />
    return <ErrorIcon fontSize="small" />
  }

  const stats = run?.summary_stats || {}
  const progress = stats.progress ?? 0
  const skillTasks = tasks.filter((t) => t.category === 'skill_engine')

  return (
    <Box sx={{ p: 3 }}>
      {/* ── Page Title ─────────────────────────────────────────── */}
      <Box
        sx={{
          mb: 3,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 2,
        }}
      >
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700, mb: 0.5, fontFamily: "'Outfit', sans-serif" }}>
            Rule Engine
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Upload a set of rules. Each rule triggers its own dedicated AI workflow to help you achieve its task.
          </Typography>
        </Box>
        {run && (
          <Button
            startIcon={<RefreshIcon />}
            variant="outlined"
            onClick={handleReset}
            sx={{ textTransform: 'none', borderRadius: 2 }}
          >
            Start New Run
          </Button>
        )}
      </Box>

      {/* ── Setup Card (shown before a run) ─────────────────────── */}
      {!run && (
        <Grow in={true}>
          <Paper
            sx={{
              p: 3,
              borderRadius: 3,
              mb: 3,
              border: borderLight,
            }}
          >
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
              <RuleIcon color="primary" />
              <Typography variant="h6" sx={{ fontWeight: 700, fontFamily: "'Outfit', sans-serif" }}>
                Step 1: Choose your rules
              </Typography>
            </Stack>

            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel id="task-select-label">Use a Skill Engine Task (recommended)</InputLabel>
              <Select
                labelId="task-select-label"
                value={selectedTaskId}
                label="Use a Skill Engine Task (recommended)"
                onChange={(e) => {
                  setSelectedTaskId(e.target.value)
                  setRulesFile(null)
                }}
                disabled={tasksLoading}
              >
                {tasksLoading ? (
                  <MenuItem disabled>
                    <CircularProgress size={14} sx={{ mr: 1 }} /> Loading tasks...
                  </MenuItem>
                ) : skillTasks.length === 0 ? (
                  <MenuItem disabled>No Skill Engine tasks found. Create one in Task Management.</MenuItem>
                ) : (
                  skillTasks.map((t) => (
                    <MenuItem key={t.id} value={t.id}>
                      <Stack>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {t.name}
                        </Typography>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          {t.template_filename}
                        </Typography>
                      </Stack>
                    </MenuItem>
                  ))
                )}
              </Select>
            </FormControl>

            <Divider sx={{ my: 2 }}>or</Divider>

            <Button
              component="label"
              variant="outlined"
              startIcon={<UploadFileIcon />}
              sx={{ textTransform: 'none', py: 1.5, borderRadius: 2, mb: 1 }}
            >
              {rulesFile ? rulesFile.name : 'Upload a rules file (.txt, .pdf, .docx, .xlsx)'}
              <input
                type="file"
                hidden
                accept=".txt,.pdf,.doc,.docx,.xlsx,.xls,.csv"
                onChange={(e) => {
                  setRulesFile(e.target.files?.[0] || null)
                  setSelectedTaskId('')
                }}
              />
            </Button>

            <Typography variant="h6" sx={{ fontWeight: 700, mt: 3, mb: 2, fontFamily: "'Outfit', sans-serif" }}>
              Step 2: Provide your input to evaluate
            </Typography>

            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Button
                  component="label"
                  variant="outlined"
                  startIcon={<CloudUploadIcon />}
                  fullWidth
                  sx={{ textTransform: 'none', py: 2, borderRadius: 2 }}
                >
                  {inputFile ? inputFile.name : 'Upload input file (optional)'}
                  <input
                    type="file"
                    hidden
                    accept=".txt,.pdf,.doc,.docx,.xlsx,.xls,.csv"
                    onChange={(e) => {
                      setInputFile(e.target.files?.[0] || null)
                    }}
                  />
                </Button>
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  multiline
                  minRows={3}
                  label="Or paste your input text here"
                  placeholder="Paste the data, text, or description the AI should evaluate against each rule..."
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                />
              </Grid>
            </Grid>

            {error && (
              <Alert severity="error" sx={{ mt: 2, borderRadius: 2 }} onClose={() => setError(null)}>
                {error}
              </Alert>
            )}

            <Button
              variant="contained"
              startIcon={isRunning ? <CircularProgress size={16} color="inherit" /> : <PlayArrowIcon />}
              onClick={runWorkflows}
              disabled={isRunning || (!selectedTaskId && !rulesFile)}
              sx={{
                mt: 3,
                textTransform: 'none',
                px: 4,
                borderRadius: 2,
                background: 'linear-gradient(90deg, #6b1f8a 0%, #a02bbf 50%, #ff4ea1 100%)',
              }}
            >
              {isRunning ? 'Running Rule Workflows...' : 'Run Rule Workflows'}
            </Button>

            {isRunning && (
              <Box sx={{ mt: 2 }}>
                <LinearProgress sx={{ borderRadius: 2 }} />
                <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.5 }}>
                  The AI is parsing the rules and running a dedicated workflow for each one...
                </Typography>
              </Box>
            )}
          </Paper>
        </Grow>
      )}

      {/* ── Results View (after a run) ─────────────────────────── */}
      {run && (
        <Fade in={Boolean(run)}>
          <Box>
            {/* Summary banner */}
            <Paper sx={{ p: 2.5, borderRadius: 3, mb: 3, border: borderLight }}>
              <Stack
                direction="row"
                justifyContent="space-between"
                alignItems="center"
                flexWrap="wrap"
                gap={1.5}
              >
                <Box>
                  <Typography
                    variant="caption"
                    sx={{ color: 'text.secondary', fontWeight: 600, textTransform: 'uppercase' }}
                  >
                    Run #{run.id} — Rule Workflow Results
                  </Typography>
                  <Typography variant="h6" sx={{ fontWeight: 700, mt: 0.3 }}>
                    {stats.passed ?? 0} / {stats.total ?? 0} rules passed
                  </Typography>
                </Box>
                <Stack direction="row" spacing={1}>
                  <Chip
                    icon={<CheckCircleIcon />}
                    label={`${stats.passed ?? 0} passed`}
                    color="success"
                    size="small"
                    sx={{ fontWeight: 700 }}
                  />
                  <Chip
                    icon={<WarningIcon />}
                    label={`${stats.needs_work ?? 0} needs work`}
                    color="warning"
                    size="small"
                    sx={{ fontWeight: 700 }}
                  />
                  <Chip
                    icon={<ErrorIcon />}
                    label={`${stats.not_answered ?? 0} not answered`}
                    color="error"
                    size="small"
                    sx={{ fontWeight: 700 }}
                  />
                </Stack>
              </Stack>
              <Box sx={{ mt: 1.5 }}>
                <Stack direction="row" justifyContent="space-between" sx={{ mb: 0.5 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    Overall Progress
                  </Typography>
                  <Typography variant="caption" sx={{ fontWeight: 700 }}>
                    {progress}%
                  </Typography>
                </Stack>
                <LinearProgress
                  variant="determinate"
                  value={progress}
                  color={progress === 100 ? 'success' : 'primary'}
                  sx={{ height: 8, borderRadius: 4 }}
                />
              </Box>
            </Paper>

            {/* Rules list */}
            <Typography
              variant="subtitle2"
              sx={{
                fontWeight: 700,
                mb: 1.5,
                color: 'text.secondary',
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
              }}
            >
              {run.rules.length} Rule{run.rules.length !== 1 ? 's' : ''} Detected — each has its own AI workflow
            </Typography>

            <Grid container spacing={2}>
              {run.rules.map((rule, idx) => {
                const result = run.results.find((r) => r.rule_id === rule.id) || {}
                const statusMeta = getStatusMeta(result.status)
                const isChatOpen = activeChatRule === rule.id

                return (
                  <Grid item xs={12} key={rule.id}>
                    <Card sx={{ borderRadius: 3, border: borderCard, boxShadow: 'none', overflow: 'visible' }}>
                      <CardHeader
                        avatar={
                          <Box
                            sx={{
                              width: 36,
                              height: 36,
                              borderRadius: '50%',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              bgcolor:
                                statusMeta.color === 'success'
                                  ? 'rgba(76,175,80,0.12)'
                                  : statusMeta.color === 'warning'
                                  ? 'rgba(255,152,0,0.12)'
                                  : 'rgba(244,67,54,0.12)',
                              color: `${statusMeta.color}.main`,
                            }}
                          >
                            {getStatusIcon(statusMeta.icon)}
                          </Box>
                        }
                        title={
                          <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap">
                            <Typography variant="body1" sx={{ fontWeight: 700 }}>
                              {idx + 1}. {rule.name}
                            </Typography>
                            <Chip
                              label={statusMeta.label}
                              color={statusMeta.color}
                              size="small"
                              sx={{ fontWeight: 700, fontSize: '0.65rem' }}
                            />
                          </Stack>
                        }
                        subheader={
                          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            Task: {rule.task}
                          </Typography>
                        }
                        action={
                          <Tooltip title={isChatOpen ? 'Close chat' : 'Chat about this rule'}>
                            <IconButton
                              onClick={() => toggleChat(rule.id)}
                              color={isChatOpen ? 'primary' : 'default'}
                            >
                              <ChatIcon />
                            </IconButton>
                          </Tooltip>
                        }
                      />

                      <CardContent sx={{ pt: 0 }}>
                        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1.5 }}>
                          <strong style={{ color: 'text.primary' }}>Description:</strong> {rule.description}
                        </Typography>

                        {/* AI Verdict */}
                        <Paper
                          variant="outlined"
                          sx={{
                            p: 1.5,
                            borderRadius: 2,
                            bgcolor: (theme) =>
                              theme.palette.mode === 'dark' ? 'rgba(0,0,0,0.15)' : 'rgba(0,0,0,0.02)',
                          }}
                        >
                          <Stack direction="row" spacing={1} alignItems="flex-start">
                            <SmartToyIcon fontSize="small" color="primary" sx={{ mt: 0.2 }} />
                            <Box sx={{ flex: 1 }}>
                              <Typography
                                variant="caption"
                                sx={{ fontWeight: 700, color: 'primary.main', display: 'block', mb: 0.5 }}
                              >
                                AI Workflow Verdict
                              </Typography>
                              {result.summary && (
                                <Typography variant="body2" sx={{ mb: 1 }}>
                                  {result.summary}
                                </Typography>
                              )}
                              {result.guidance && (
                                <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                                  <strong>Guidance:</strong> {result.guidance}
                                </Typography>
                              )}
                              {result.next_action && (
                                <Typography variant="body2" sx={{ mb: 1 }}>
                                  <strong>Next action:</strong> {result.next_action}
                                </Typography>
                              )}
                              {result.suggested_fix && (
                                <Typography variant="body2" sx={{ mb: 1 }}>
                                  <strong>Suggested fix:</strong> {result.suggested_fix}
                                </Typography>
                              )}
                              {result.questions?.length > 0 && (
                                <Box sx={{ mt: 1 }}>
                                  <Typography variant="caption" sx={{ fontWeight: 700 }}>
                                    Questions for you:
                                  </Typography>
                                  {result.questions.map((q, qi) => (
                                    <Typography
                                      key={qi}
                                      variant="caption"
                                      display="block"
                                      sx={{ color: 'text.secondary' }}
                                    >
                                      • {q}
                                    </Typography>
                                  ))}
                                </Box>
                              )}
                              {!result.summary && !result.guidance && (
                                <Typography variant="caption" sx={{ color: 'text.disabled' }}>
                                  No verdict available yet.
                                </Typography>
                              )}
                            </Box>
                          </Stack>
                        </Paper>

                        {/* Rule chat */}
                        <Collapse in={isChatOpen}>
                          <Box sx={{ mt: 2, border: borderLight, borderRadius: 2 }}>
                            <Box
                              sx={{
                                px: 1.5,
                                py: 1,
                                bgcolor: (theme) =>
                                  theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)',
                                borderBottom: borderFaint,
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1,
                              }}
                            >
                              <ChatIcon fontSize="small" color="primary" />
                              <Typography variant="caption" sx={{ fontWeight: 700 }}>
                                Rule Chat — "{rule.name}"
                              </Typography>
                            </Box>

                            <Box
                              sx={{
                                p: 1.5,
                                maxHeight: 220,
                                overflowY: 'auto',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: 1,
                              }}
                            >
                              {!result.conversation || result.conversation.length === 0 ? (
                                <Typography
                                  variant="caption"
                                  sx={{ color: 'text.disabled', textAlign: 'center', py: 2 }}
                                >
                                  Ask a follow-up question about this rule.
                                </Typography>
                              ) : (
                                result.conversation.map((msg, mi) => (
                                  <Box
                                    key={mi}
                                    sx={{
                                      alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                                      maxWidth: '85%',
                                    }}
                                  >
                                    <Box
                                      sx={{
                                        p: 1,
                                        borderRadius:
                                          msg.sender === 'ai' ? '4px 12px 12px 12px' : '12px 4px 12px 12px',
                                        bgcolor:
                                          msg.sender === 'ai'
                                            ? (theme) =>
                                                theme.palette.mode === 'dark'
                                                  ? 'rgba(255,255,255,0.05)'
                                                  : '#f1f5f9'
                                            : '#4f46e5',
color: msg.sender === 'ai' ? 'inherit' : '#fff',
                                        fontSize: 16,
                                      }}
                                    >
<Typography variant="body1" sx={{ whiteSpace: 'pre-line', fontSize: 16, lineHeight: 1.5 }}>
                                        {msg.text}
                                      </Typography>
                                    </Box>
                                  </Box>
                                ))
                              )}
                              {chatLoading && activeChatRule === rule.id && (
                                <Box
                                  sx={{
                                    alignSelf: 'flex-start',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 0.5,
                                  }}
                                >
                                  <TypingDots />
                                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                    AI is responding...
                                  </Typography>
                                </Box>
                              )}
                              <div ref={chatEndRef} />
                            </Box>

                            <Box
                              component="form"
                              onSubmit={(e) => sendChat(rule.id, e)}
                              sx={{
                                p: 1,
                                borderTop: borderFaint,
                                display: 'flex',
                                gap: 0.5,
                              }}
                            >
                              <InputBase
                                fullWidth
placeholder="Ask about this rule..."
                                value={chatInput}
                                onChange={(e) => setChatInput(e.target.value)}
                                disabled={chatLoading}
                                sx={{
                                  bgcolor: (theme) =>
                                    theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : '#ffffff',
                                  border: borderLight,
                                  borderRadius: 2,
                                  px: 1.5,
                                  py: 0.8,
                                  fontSize: 16,
                                  flex: 1,
                                }}
                              />
                              <IconButton
                                type="submit"
                                disabled={!chatInput.trim() || chatLoading}
                                sx={{
                                  bgcolor: 'primary.main',
                                  color: '#fff',
                                  '&:hover': { bgcolor: 'primary.dark' },
                                  '&.Mui-disabled': {
                                    bgcolor: 'rgba(255,255,255,0.06)',
                                    color: 'text.disabled',
                                  },
                                  p: 0.8,
                                }}
                              >
                                <SendIcon fontSize="small" />
                              </IconButton>
                            </Box>
                          </Box>
                        </Collapse>
                      </CardContent>
                    </Card>
                  </Grid>
                )
              })}
</Grid>

            {/* ── Rule Router Section ───────────────────────────────── */}
            <Paper sx={{ p: 2.5, borderRadius: 3, mt: 3, border: borderLight }}>
              <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
                <SmartToyIcon color="secondary" />
                <Typography variant="h6" sx={{ fontWeight: 700, fontFamily: "'Outfit', sans-serif" }}>
                   Rule Router — Ask a question
                </Typography>
              </Stack>
              <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 2 }}>
                Type a free-form question. The AI will route it to the most relevant rule and respond specifically for that rule's task.
              </Typography>

              {/* Router Chat Messages */}
              <Box sx={{ maxHeight: 200, overflowY: 'auto', mb: 1.5, display: 'flex', flexDirection: 'column', gap: 1 }}>
                {routerChat.length === 0 ? (
                  <Typography variant="caption" sx={{ color: 'text.disabled', textAlign: 'center', py: 2 }}>
                    Ask a question to get started.
                  </Typography>
                ) : (
                  routerChat.map((msg, i) => (
                    <Box
                      key={i}
                      sx={{
                        alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                        maxWidth: '88%',
                      }}
                    >
                      <Box
                        sx={{
                          p: 1,
                          borderRadius: msg.sender === 'ai' ? '4px 12px 12px 12px' : '12px 4px 12px 12px',
bgcolor: msg.sender === 'ai'
                            ? (theme) => theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : '#f1f5f9'
                            : '#4f46e5',
                          color: msg.sender === 'ai' ? 'inherit' : '#fff',
                          fontSize: 16,
                        }}
                      >
                        <Typography variant="caption" sx={{ whiteSpace: 'pre-line', fontSize: 16 }}>
                          {msg.text}
                        </Typography>
                      </Box>
                    </Box>
                  ))
                )}
                {routerLoading && (
                  <Box sx={{ alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <TypingDots />
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>Routing...</Typography>
                  </Box>
                )}
              </Box>

              <Box component="form" onSubmit={sendRouteMessage} sx={{ display: 'flex', gap: 0.5 }}>
                <InputBase
                  fullWidth
placeholder="e.g. What do I need to do for the security policy?"
                  value={routerInput}
                  onChange={(e) => setRouterInput(e.target.value)}
                  disabled={routerLoading}
                  sx={{
                    bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : '#ffffff',
                    border: borderLight,
                    borderRadius: 2,
                    px: 1.5,
                    py: 0.8,
                    fontSize: 16,
                    flex: 1,
                  }}
                />
                <IconButton
                  type="submit"
                  disabled={!routerInput.trim() || routerLoading}
                  sx={{ bgcolor: 'secondary.main', color: '#fff', '&:hover': { bgcolor: 'secondary.dark' }, p: 0.8 }}
                >
                  <SendIcon fontSize="small" />
                </IconButton>
              </Box>
            </Paper>

            {/* ── Guided Walkthrough Section ──────────────────────────── */}
            <Paper
              sx={{
                p: 2.5,
                borderRadius: 3,
                mt: 3,
                border: borderLight,
                // Once a walkthrough is running this behaves like a
                // chat window: it fills the viewport, the messages
                // scroll inside it, and the input stays at the foot.
                ...(guidedSession && {
                  display: 'flex',
                  flexDirection: 'column',
                  height: 'calc(100vh - 200px)',
                  minHeight: 460,
                  // The conversation bleeds to the panel edges, so it
                  // has to be clipped to the rounded corners.
                  overflow: 'hidden',
                }),
              }}
            >
              <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
                <RuleIcon color="success" />
                <Typography variant="h6" sx={{ fontWeight: 700, fontFamily: "'Outfit', sans-serif" }}>
                   Guided Walkthrough
                </Typography>
              </Stack>
              <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 2 }}>
                Let the AI walk you through each rule's task one at a time. Complete each step to advance.
              </Typography>

              {!guidedSession ? (
                <Button
                  variant="contained"
                  color="success"
                  startIcon={guidedLoading ? <CircularProgress size={16} color="inherit" /> : <PlayArrowIcon />}
                  onClick={startGuided}
                  disabled={guidedLoading}
                  sx={{ textTransform: 'none', borderRadius: 2 }}
                >
                  {guidedLoading ? 'Starting...' : 'Start Guided Walkthrough'}
                </Button>
              ) : (
<>
                  {/* Guided Progress — session object has fields directly: total_steps, completed_steps, current_step_index, progress, all_completed, steps */}
                  {guidedSession && guidedSession.total_steps > 0 && (
                    <Box sx={{ mb: 2, flexShrink: 0 }}>
                      <Stack direction="row" justifyContent="space-between" sx={{ mb: 0.5 }}>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          Step {(guidedSession.current_step_index || 0) + 1} of {guidedSession.total_steps}
                        </Typography>
                        <Typography variant="caption" sx={{ fontWeight: 700 }}>
                          {guidedSession.progress || 0}%
                        </Typography>
                      </Stack>
                      <LinearProgress
                        variant="determinate"
                        value={guidedSession.progress || 0}
                        color={guidedSession.all_completed ? 'success' : 'primary'}
                        sx={{ height: 6, borderRadius: 3 }}
                      />
                      <Stack direction="row" spacing={0.5} sx={{ mt: 1, flexWrap: 'wrap', gap: 0.5 }}>
                        {guidedSession.steps?.map((step, si) => {
                          const editable = step.status === 'completed'
                          return (
                            <Tooltip
                              key={si}
                              title={editable ? `${step.rule_name} — click to edit your answer` : step.rule_name}
                            >
                              <Chip
                                label={`${si + 1}. ${step.rule_name}`}
                                color={
                                  step.status === 'completed' ? 'success' :
                                  step.status === 'active' ? 'primary' :
                                  step.status === 'validated' ? 'info' : 'default'
                                }
                                variant={step.status === 'active' ? 'filled' : 'outlined'}
                                size="small"
                                onClick={editable ? () => openEditDialog(si, step.rule_name) : undefined}
                                sx={{
                                  fontWeight: 600,
                                  fontSize: 10,
                                  opacity: step.status === 'pending' ? 0.5 : 1,
                                  cursor: editable ? 'pointer' : 'default',
                                }}
                                icon={step.status === 'completed' ? <CheckCircleIcon /> : undefined}
                              />
                            </Tooltip>
                          )
                        })}
                      </Stack>
                    </Box>
                  )}

                  {/* Guided Chat */}
                  <Box
                    sx={{
                      // Takes whatever height the panel has left, so
                      // the conversation grows with the window
                      // instead of sitting in a small box.
                      flex: 1,
                      minHeight: 0,
                      overflowY: 'auto',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 2.25,
                      px: 2.5,
                      py: 3,
                      mx: -2.5,
                      background: conversationBackground,
                      borderTop: borderFaint,
                    }}
                  >
                    {guidedChat.map((msg, i) => (
                      <ChatMessage
                        key={i}
                        sender={msg.sender}
                        text={msg.text}
                        timestamp={msg.timestamp}
                        validated={msg.validated}
                        html={msg.sender === 'ai'}
                        user={user}
                      />
                    ))}
                    {guidedLoading && (
                      <Box sx={{ alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <TypingDots />
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>Processing...</Typography>
                      </Box>
                    )}
                    <div ref={guidedEndRef} />
                  </Box>

                  {/* ── Summary table: every input entered, once the walkthrough is done ── */}
                  {guidedSession?.all_completed && (
                    <Box sx={{ flexShrink: 0, mx: -2.5, px: 2.5, pt: 2, pb: 1 }}>
                      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                          Your Answers — {summarySteps.length} of {guidedSession.total_steps} steps
                        </Typography>
                        {summaryLoading && <CircularProgress size={16} />}
                      </Stack>
                      <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1.5 }}>
                        Review what you entered for each step. Click Edit to correct any answer — the
                        table updates with the new result once it's accepted.
                      </Typography>
                      <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
                        <Table size="small">
                          <TableHead>
                            <TableRow>
                              <TableCell sx={{ fontWeight: 700, width: 40 }}>#</TableCell>
                              <TableCell sx={{ fontWeight: 700 }}>Step</TableCell>
                              <TableCell sx={{ fontWeight: 700 }}>Your Input</TableCell>
                              <TableCell sx={{ fontWeight: 700, width: 80 }} align="right">
                                Action
                              </TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {summarySteps.map((step, i) => (
                              <TableRow key={step.step_index ?? i} hover>
                                <TableCell sx={{ color: 'text.secondary' }}>{i + 1}</TableCell>
                                <TableCell sx={{ fontWeight: 600 }}>{step.rule_name}</TableCell>
                                <TableCell>
                                  {step.preview_html ? (
                                    <Box
                                      sx={assistantContentStyles}
                                      dangerouslySetInnerHTML={{ __html: step.preview_html }}
                                    />
                                  ) : (
                                    <Typography variant="body2" sx={{ whiteSpace: 'pre-line' }}>
                                      {step.user_value}
                                    </Typography>
                                  )}
                                </TableCell>
                                <TableCell align="right">
                                  <Tooltip title="Modify this answer">
                                    <IconButton
                                      size="small"
                                      onClick={() => openEditDialog(step.step_index, step.rule_name)}
                                    >
                                      <EditIcon fontSize="small" />
                                    </IconButton>
                                  </Tooltip>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </TableContainer>
                    </Box>
                  )}

                  <Box
                    component="form"
                    onSubmit={submitGuidedMessage}
                    sx={{
                      flexShrink: 0,
                      // Fades out of the conversation's gradient
                      // rather than sitting in its own band.
                      mx: -2.5,
                      px: 2.5,
                      pt: 1,
                      pb: 0.5,
                      background: composerBackground,
                    }}
                  >
                    {/* One rounded field holding the text and its
                        send action, rather than two side by side. */}
                    <Box
                      sx={{
                        bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : '#ffffff',
                        border: (theme) => `1.5px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.10)' : 'rgba(79,70,229,0.20)'}`,
                        borderRadius: '22px',
                        px: 2.25,
                        pt: 2,
                        pb: 1,
                        boxShadow: (theme) =>
                          theme.palette.mode === 'dark'
                            ? '0 8px 24px rgba(0,0,0,0.36)'
                            : '0 10px 30px rgba(79,70,229,0.10), 0 2px 6px rgba(16,24,40,0.04)',
                        transition: 'border-color 140ms ease, box-shadow 140ms ease',
                        '&:focus-within': {
                          borderColor: 'rgba(79,70,229,0.55)',
                          boxShadow: '0 10px 30px rgba(79,70,229,0.16), 0 0 0 4px rgba(79,70,229,0.10)',
                        },
                      }}
                    >
                      <InputBase
                        fullWidth
                        multiline
                        maxRows={10}
                        placeholder="Ask anything... (Shift+Enter for a new line)"
                        value={guidedInput}
                        onChange={(e) => setGuidedInput(e.target.value)}
                        // A list or table step is entered one row per
                        // line, so Enter sends and Shift+Enter breaks.
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault()
                            submitGuidedMessage(e)
                          }
                        }}
                        disabled={guidedLoading || guidedSession?.all_completed}
                        sx={{ fontSize: 15, lineHeight: 1.5, p: 0 }}
                      />

                      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 0.5 }}>
                        <IconButton
                          type="submit"
                          disabled={!guidedInput.trim() || guidedLoading || guidedSession?.all_completed}
                          sx={{
                            bgcolor: '#4f46e5',
                            color: '#fff',
                            width: 34,
                            height: 34,
                            '&:hover': { bgcolor: '#4338ca' },
                            '&.Mui-disabled': {
                              bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
                              color: 'text.disabled',
                            },
                          }}
                        >
                          <SendIcon sx={{ fontSize: 17 }} />
                        </IconButton>
                      </Box>
                    </Box>
                  </Box>
                </>
              )}
            </Paper>
          </Box>
        </Fade>
      )}

      {/* ── Editing Mode: correct an already-completed step's answer ── */}
      <Dialog open={!!editStep} onClose={closeEditDialog} fullWidth maxWidth="sm">
        <DialogTitle>Editing: {editStep?.ruleName}</DialogTitle>
        <DialogContent>
          {editStep?.previewHtml && (
            <Box
              sx={[assistantContentStyles, { mb: 2 }]}
              dangerouslySetInnerHTML={{ __html: editStep.previewHtml }}
            />
          )}
          <TextField
            autoFocus
            fullWidth
            multiline
            minRows={2}
            maxRows={8}
            label="Corrected value"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            disabled={editSaving}
          />
          {editResultHtml && (
            <Box
              sx={[assistantContentStyles, { mt: 2 }]}
              dangerouslySetInnerHTML={{ __html: editResultHtml }}
            />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeEditDialog}>{editSucceeded ? 'Close' : 'Cancel'}</Button>
          <Button
            variant="contained"
            onClick={saveEditedStep}
            disabled={editSaving || !editValue.trim()}
          >
            {editSaving ? 'Saving…' : 'Save correction'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

export default SkillEngine

