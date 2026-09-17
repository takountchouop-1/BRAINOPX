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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  List,
  ListItem,
  ListItemText,
  InputBase,
  CircularProgress,
  Fade,
  Grow,
  Alert,
  Stepper,
  Step,
  StepLabel,
  Tooltip,
  IconButton,
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField
} from '@mui/material'

import CloudUploadIconImport from '@mui/icons-material/CloudUpload'
import SendIconImport from '@mui/icons-material/Send'
import CheckCircleIconImport from '@mui/icons-material/CheckCircle'
import ErrorIconImport from '@mui/icons-material/Error'
import ChatIconImport from '@mui/icons-material/Chat'
import DownloadIconImport from '@mui/icons-material/Download'
import RefreshIconImport from '@mui/icons-material/Refresh'
import AttachFileIconImport from '@mui/icons-material/AttachFile'
import WarningAmberIconImport from '@mui/icons-material/WarningAmber'
import InsertDriveFileIconImport from '@mui/icons-material/InsertDriveFile'
import DragIndicatorIconImport from '@mui/icons-material/DragIndicator'
import { ResizableChatPanel } from '../components/ResizablePanel.jsx'
import ChatMessage, {
  conversationBackground,
  composerBackground,
  assistantContentStyles,
  TypingIndicator,
} from '../components/ChatMessage.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const CloudUploadIcon = CloudUploadIconImport?.default || CloudUploadIconImport
const SendIcon = SendIconImport?.default || SendIconImport
const CheckCircleIcon = CheckCircleIconImport?.default || CheckCircleIconImport
const ErrorIcon = ErrorIconImport?.default || ErrorIconImport
const ChatIcon = ChatIconImport?.default || ChatIconImport
const DownloadIcon = DownloadIconImport?.default || DownloadIconImport
const RefreshIcon = RefreshIconImport?.default || RefreshIconImport
const AttachFileIcon = AttachFileIconImport?.default || AttachFileIconImport
const WarningAmberIcon = WarningAmberIconImport?.default || WarningAmberIconImport
const InsertDriveFileIcon = InsertDriveFileIconImport?.default || InsertDriveFileIconImport

// ─── CONSTANTS ───────────────────────────────────────────────────────────────

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// How long the assistant is allowed to "think" (wait on a response) before
// giving up and surfacing an error instead of hanging indefinitely.
const THINKING_TIMEOUT_MS = 5 * 60 * 1000 // 5 minutes (within the 3-6 min window)

const NETWORK_ERROR_MESSAGE = 'Network problem, check your network and try back.'
const LOAD_ERROR_MESSAGE = 'An error occurred while trying to load the info.'

// Human labels for the anomaly kinds report_analysis_service.py detects,
// used by the resolution cards rendered in the chat panel.
const ANOMALY_KIND_LABELS = {
  missing_value: 'Missing value',
  invalid_format: 'Invalid format',
  duplicate: 'Duplicate value',
  negative_value: 'Negative value',
  unknown_code: 'Unknown reference',
  inconsistent_value: 'Inconsistent value',
  incomplete_relationship: 'Incomplete relationship',
  duplicate_row: 'Duplicate row',
}

// Wraps fetch with a timeout so a stalled connection doesn't hang forever,
// and tags network-ish failures (timeout / connectivity) so callers can
// show a network-specific message instead of a generic one.
const fetchWithThinkingTimeout = async (url, options = {}) => {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), THINKING_TIMEOUT_MS)
  try {
    return await fetch(url, { ...options, signal: controller.signal })
  } catch (err) {
    if (err.name === 'AbortError' || err instanceof TypeError) {
      err.isNetworkError = true
    }
    throw err
  } finally {
    clearTimeout(timeoutId)
  }
}

// Maps backend status strings to frontend labels and colors
const STATUS_CONFIG = {
  draft:                        { label: 'Draft',                         color: 'default',  step: 0 },
  file_submitted:               { label: 'Pending',                       color: 'warning',  step: 1 },
  analysis_in_progress:         { label: 'Analysis in Progress',          color: 'warning',  step: 2 },
  additional_information_required: { label: 'Additional Info Required',   color: 'error',    step: 3 },
  waiting_for_support_response: { label: 'Waiting for Response',          color: 'warning',  step: 3 },
  data_corrected:               { label: 'Data Corrected',                color: 'info',     step: 4 },
  data_validated:               { label: 'Data Validated',                color: 'success',  step: 5 },
  script_generated:             { label: 'Script Generated',              color: 'success',  step: 6 },
  processing_completed:         { label: 'Processing Completed',          color: 'success',  step: 6 },
  escalation_required:          { label: 'Escalation Required',           color: 'error',    step: 3 },
}

const PROCESS_STEPS = [
  'Draft',
  'File Submitted',
  'Analysis',
  'Clarification',
  'Validated',
  'Script Generated',
  'Completed'
]

// ─── MAIN COMPONENT ───────────────────────────────────────────────────────────

const ConfigurationIngest = ({ searchTerm = '', setSearchTerm = () => {} }) => {

  // The signed-in person, shown by their profile picture on their
  // own messages.
  const { user } = useAuth()

  // Task Template Selection
  const [availableTasks, setAvailableTasks] = useState([])
  const [selectedTaskId, setSelectedTaskId] = useState('')
  const [tasksLoading, setTasksLoading] = useState(true)

  // Active Configuration Request State
  const [requestId, setRequestId] = useState(null)
  const [requestStatus, setRequestStatus] = useState('draft')
  const [uploadedFile, setUploadedFile] = useState(null)
  const [isDragging, setIsDragging] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  // Where the uploaded file itself lives on the server — lets the user
  // open/download it, fix a flagged cell directly in Excel, and send
  // the corrected file back via resubmitCorrectedFile below.
  const [fileUrl, setFileUrl] = useState(null)
  const [isResubmittingFile, setIsResubmittingFile] = useState(false)
  const resubmitFileInputRef = useRef(null)

  // Validation Errors from Backend Rules Engine
  const [validationErrors, setValidationErrors] = useState([])

  // Add this with your other state declarations
const [matchInfo, setMatchInfo] = useState(null)

  // Manual template selection — shown when the backend's auto-match
  // (column-header similarity, see template_matcher.py) can't confidently
  // pick a task template for the uploaded file.
  const [showTemplateSelection, setShowTemplateSelection] = useState(false)
  const [availableTemplates, setAvailableTemplates] = useState([])
  const [pendingUploadFile, setPendingUploadFile] = useState(null)
  const [isUploadingWithTemplate, setIsUploadingWithTemplate] = useState(false)

  // Stats state
  const [stats, setStats] = useState({ total: 0, solved: 0, remaining: 0, progress: 0 })

  // Generated Script from Backend
  const [generatedScript, setGeneratedScript] = useState(null)
  const [isGeneratingScript, setIsGeneratingScript] = useState(false)
  const [scriptGenError, setScriptGenError] = useState(null)

  // Report-analysis anomalies: every kind of issue found in the
  // upload (missing/invalid/duplicate/unknown reference/inconsistent/
  // incomplete relationship), each resolved by a correction, a
  // reference file, or (conflicts/incomplete relationships) a
  // decision.
  const [anomalies, setAnomalies] = useState([])
  const [isSubmittingReferenceFile, setIsSubmittingReferenceFile] = useState(false)
  const [isSubmittingDecision, setIsSubmittingDecision] = useState(false)
  const [correctionDrafts, setCorrectionDrafts] = useState({}) // { [anomalyId]: text }
  const [submittingCorrectionId, setSubmittingCorrectionId] = useState(null)
  // Whether the user wants to fix flagged anomalies by typing corrected
  // values here in chat, or by reopening the Excel file and resubmitting
  // it — asked once via the card rendered when needsCorrectionModeChoice
  // is true, then remembered for the rest of the request.
  const [correctionMode, setCorrectionMode] = useState(null)
  const [needsCorrectionModeChoice, setNeedsCorrectionModeChoice] = useState(false)
  const [isSubmittingCorrectionMode, setIsSubmittingCorrectionMode] = useState(false)
  // Which open anomaly the next attached file resolves — set by the
  // "Attach production extract" button on that anomaly's card, so
  // submitReferenceFile targets the right one instead of guessing.
  const [referenceFileAnomalyId, setReferenceFileAnomalyId] = useState(null)

  // Conversational Chat State
  const [chatMessages, setChatMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [isChatLoading, setIsChatLoading] = useState(false)
const [pendingFile, setPendingFile] = useState(null)
  const [welcomeLoading, setWelcomeLoading] = useState(false)
  const [stepProgress, setStepProgress] = useState(null)

  // Set once the AI has asked for a file/screenshot after several
  // confused turns on the current step (see guided_engine.py). While
  // true, an attached file is sent to /step-attachment rather than
  // /reference-file, and images are accepted alongside documents.
  const [awaitingAttachment, setAwaitingAttachment] = useState(false)
  const [isSubmittingStepAttachment, setIsSubmittingStepAttachment] = useState(false)

  // Editing mode: correcting the answer of an already-completed step
  const [editStep, setEditStep] = useState(null) // { stepIndex, ruleName, value, previewHtml }
  const [editValue, setEditValue] = useState('')
  const [editSaving, setEditSaving] = useState(false)
  const [editResultHtml, setEditResultHtml] = useState(null)
  const [editSucceeded, setEditSucceeded] = useState(false)

  // Recovering from an AI failure on the active step: regenerating an
  // unavailable example, or re-editing a just-rejected answer.
  const [regenerating, setRegenerating] = useState(false)
  const [aiUnavailableDismissed, setAiUnavailableDismissed] = useState(false)

  // Polling timer ref
  const pollRef = useRef(null)
  const isChatLoadingRef = useRef(false)
  const chatEndRef = useRef(null)
  // Whether the chat panel was scrolled to (or near) the bottom before
  // this update — read below to decide whether a new message should
  // pull the view down, or leave the user's scroll position alone.
  const isChatAtBottomRef = useRef(true)
  const fileInputRef = useRef(null)
  const composerInputRef = useRef(null)
  const chatFileInputRef = useRef(null)

  // Filter available tasks based on search term
  const filteredTasks = availableTasks.filter((task) => {
    const searchLower = searchTerm.toLowerCase()
    return (
      task.name.toLowerCase().includes(searchLower) ||
      (task.description && task.description.toLowerCase().includes(searchLower)) ||
      (task.type && task.type.toLowerCase().includes(searchLower))
    )
  })

  // ─── LIFECYCLE ───────────────────────────────────────────────────────────────

  useEffect(() => {
    fetchTasks()
    return () => clearInterval(pollRef.current)
  }, [])

  // ─── TASK SELECTION: AI responds instantly ────────────────────────────────
  useEffect(() => {
    if (!selectedTaskId) {
      // No task selected → clear chat
      setChatMessages([])
      return
    }

const fetchWelcome = async () => {
      setWelcomeLoading(true)
      try {
        const token = localStorage.getItem('brainopx_token')
        const resp = await fetchWithThinkingTimeout(`${API_BASE}/api/requests/task-welcome/${selectedTaskId}`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        if (resp.ok) {
          const data = await resp.json()
          // If the backend created a draft request (with rules), set the state
          // so the chat input is enabled and the step-by-step workflow shows
          if (data.request_id) {
            setRequestId(data.request_id)
            setRequestStatus('file_submitted')  // enables chat input
            setStepProgress(data.step_progress || null)
            setChatMessages(data.conversation && data.conversation.length > 0
              ? data.conversation
              : [{
                  sender: 'ai',
                  text: data.welcome_message,
                  timestamp: new Date().toISOString(),
                  _animate: true,
                }]
            )
          } else {
            // No rules — just show the welcome message (file upload required)
            setChatMessages([{
              sender: 'ai',
              text: data.welcome_message,
              timestamp: new Date().toISOString(),
              _animate: true,
            }])
          }
        } else {
          setChatMessages([{
            sender: 'ai',
            text: LOAD_ERROR_MESSAGE,
            timestamp: new Date().toISOString(),
            _animate: true,
          }])
        }
      } catch (err) {
        console.error('Failed to load task welcome:', err)
        setChatMessages([{
          sender: 'ai',
          text: err.isNetworkError ? NETWORK_ERROR_MESSAGE : LOAD_ERROR_MESSAGE,
          timestamp: new Date().toISOString(),
          _animate: true,
        }])
      } finally {
        setWelcomeLoading(false)
      }
    }

    fetchWelcome()
  }, [selectedTaskId])

  useEffect(() => {
    const lastMessage = chatMessages[chatMessages.length - 1]
    // Always follow the user's own message; for an incoming AI reply,
    // only auto-scroll if they hadn't scrolled up to read history.
    if (isChatAtBottomRef.current || lastMessage?.sender === 'user') {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
      isChatAtBottomRef.current = true
    }
  }, [chatMessages])

  const CHAT_NEAR_BOTTOM_THRESHOLD_PX = 80
  const handleChatScroll = (e) => {
    const el = e.currentTarget
    isChatAtBottomRef.current =
      el.scrollHeight - el.scrollTop - el.clientHeight < CHAT_NEAR_BOTTOM_THRESHOLD_PX
  }

  // Keeps the composer's attachment routing correct across a page
  // reload or the background poll, not just right after a chat reply.
  useEffect(() => {
    if (stepProgress && typeof stepProgress.awaiting_attachment === 'boolean') {
      setAwaitingAttachment(stepProgress.awaiting_attachment)
    }
  }, [stepProgress])

  useEffect(() => {
    clearInterval(pollRef.current)
    if (requestId && !['processing_completed', 'script_generated', 'escalation_required'].includes(requestStatus)) {
      pollRef.current = setInterval(() => fetchRequestState(requestId), 5000)
    }
    return () => clearInterval(pollRef.current)
  }, [requestId, requestStatus])



  

  // ─── API CALLS ────────────────────────────────────────────────────────────────

  const fetchTasks = async () => {
    setTasksLoading(true)
    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetch(`${API_BASE}/api/tasks`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (resp.ok) {
        const data = await resp.json()
        setAvailableTasks(data)
      }
    } catch (err) {
      console.error('Failed to load tasks:', err)
    } finally {
      setTasksLoading(false)
    }
  }

  // Shared by the auto-match upload and the manual-template upload: both
  // land the file on a configuration request and seed the same chat/stats/
  // step-workflow state once the backend has picked (or been told) a task.
  const applyUploadResponse = (data, file) => {
    setRequestId(data.id)
    setRequestStatus(data.status)
    setValidationErrors(data.validation_errors || [])
    setChatMessages(data.conversation || [])
    setUploadedFile(file)
    setFileUrl(data.file_url || null)

    if (data.match_summary) {
      setMatchInfo({
        taskName: data.task_name,
        matchScore: data.match_score,
        matchedColumns: data.match_summary.matched_columns,
        missingColumns: data.match_summary.missing_columns,
      })
    }

    // If the task has rules, the AI has already run per-rule workflows and
    // seeded the conversation with an instant rule-aware response. Display
    // the per-rule verdicts in the validation report area.
    if (data.rule_results && data.rule_results.length > 0) {
      // The pre-seeded conversation is already in data.conversation
      setStats({
        total: data.rule_results.length,
        solved: data.rule_results.filter(r => r.status === 'passed').length,
        remaining: data.rule_results.filter(r => r.status !== 'passed').length,
        progress: Math.round(
          (data.rule_results.filter(r => r.status === 'passed').length / data.rule_results.length) * 100
        ),
      })
    }

    // Store step-by-step workflow progress
    if (data.step_progress) {
      setStepProgress(data.step_progress)
    }
  }

const uploadFile = async (file) => {
  setIsUploading(true)
  setUploadError(null)

  const formData = new FormData()
  formData.append('file', file)

  try {
    const token = localStorage.getItem('brainopx_token')
    const resp = await fetch(`${API_BASE}/api/requests/upload`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    })

    if (!resp.ok) {
      const payload = await resp.json().catch(() => null)
      throw new Error(payload?.detail || 'File upload failed.')
    }

    const data = await resp.json()

    // Auto-match couldn't confidently pick a template — let the user
    // choose from the active ones instead of guessing.
    if (data.requires_manual_selection) {
      setAvailableTemplates(data.available_templates || [])
      setPendingUploadFile(file)
      setShowTemplateSelection(true)
      return
    }

    applyUploadResponse(data, file)
  } catch (err) {
    setUploadError(err.message)
  } finally {
    setIsUploading(false)
  }
}

  // User picked a template by hand from the manual-selection dialog
  // (auto-match came back inconclusive). Re-sends the same file, this
  // time pinned to a task_id so the backend skips matching entirely.
  const uploadWithTemplate = async (taskId) => {
    if (!pendingUploadFile) return
    setIsUploadingWithTemplate(true)
    setUploadError(null)

    const formData = new FormData()
    formData.append('file', pendingUploadFile)
    formData.append('task_id', taskId)

    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetch(`${API_BASE}/api/requests/upload-with-template`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })

      if (!resp.ok) {
        const payload = await resp.json().catch(() => null)
        throw new Error(payload?.detail || 'File upload failed.')
      }

      const data = await resp.json()
      applyUploadResponse(data, pendingUploadFile)
      setShowTemplateSelection(false)
      setAvailableTemplates([])
      setPendingUploadFile(null)
    } catch (err) {
      setUploadError(err.message)
    } finally {
      setIsUploadingWithTemplate(false)
    }
  }

  const cancelTemplateSelection = () => {
    if (isUploadingWithTemplate) return
    setShowTemplateSelection(false)
    setAvailableTemplates([])
    setPendingUploadFile(null)
  }

  const fetchRequestState = useCallback(async (id) => {
    // A chat send is in flight: its own response handler will apply the
    // fresh conversation once the assistant replies. Skip this poll tick
    // so it doesn't overwrite chatMessages with the pre-reply state from
    // the server and make the just-sent message flash away.
    if (isChatLoadingRef.current) return

    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetch(`${API_BASE}/api/requests/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (resp.ok) {
        const data = await resp.json()
        setRequestStatus(data.status)
        setValidationErrors(data.validation_errors || [])
        setChatMessages(data.conversation || [])
        if (data.generated_script) setGeneratedScript(data.generated_script)
        setAnomalies(data.anomalies || [])
        setCorrectionMode(data.correction_mode || null)
        setNeedsCorrectionModeChoice(Boolean(data.needs_correction_mode_choice))
        if (data.file_url) setFileUrl(data.file_url)
        // Update stats
        updateStats(data.validation_errors || [])
      }
    } catch (err) {
      console.error('Polling failed:', err)
    }
  }, [])

  // Helper function to update stats
  const updateStats = (errors) => {
    const total = errors.length
    const solved = errors.filter(e => e.status === 'solved').length
    const remaining = total - solved
    const progress = total > 0 ? Math.round((solved / total) * 100) : 0
    setStats({ total, solved, remaining, progress })
  }

  // A reference/production-extract file was attached via the paperclip
  // button. Sends it straight to the anomaly it was requested for,
  // rather than folding it into the free-text chat endpoints (which
  // have no notion of file turns).
  const submitReferenceFile = async () => {
    if (!pendingFile || !requestId) return

    // Prefer the anomaly the "Attach production extract" button was
    // clicked on; fall back to the first open anomaly of any kind so
    // the composer's paperclip still does something sensible.
    const targetAnomaly = referenceFileAnomalyId
      ? anomalies.find((a) => a.id === referenceFileAnomalyId)
      : anomalies.find((a) => a.status === 'open')
    if (!targetAnomaly) {
      setPendingFile(null)
      setReferenceFileAnomalyId(null)
      return
    }

    setIsSubmittingReferenceFile(true)
    isChatLoadingRef.current = true

    const formData = new FormData()
    formData.append('file', pendingFile)
    formData.append('linked_anomaly_id', targetAnomaly.id)

    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetchWithThinkingTimeout(`${API_BASE}/api/requests/${requestId}/reference-file`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })

      if (resp.ok) {
        const data = await resp.json()
        setChatMessages(data.conversation || [])
        fetchRequestState(requestId)
      } else {
        const errorData = await resp.json().catch(() => null)
        throw new Error(errorData?.detail || 'Could not process the reference file.')
      }
    } catch (err) {
      console.error('Reference file submission failed:', err)
      const message = err.isNetworkError ? NETWORK_ERROR_MESSAGE : LOAD_ERROR_MESSAGE
      setChatMessages((prev) => [
        ...prev,
        { sender: 'ai', text: message, timestamp: new Date().toISOString(), _animate: true },
      ])
    } finally {
      setPendingFile(null)
      setReferenceFileAnomalyId(null)
      setIsSubmittingReferenceFile(false)
      isChatLoadingRef.current = false
    }
  }

  // The file/screenshot the AI asked for after several confused turns
  // on the current step. Never compared against anything — it only
  // gives the AI more context for its next explanation.
  const submitStepAttachment = async () => {
    if (!pendingFile || !requestId) return

    setIsSubmittingStepAttachment(true)
    isChatLoadingRef.current = true

    const formData = new FormData()
    formData.append('file', pendingFile)

    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetchWithThinkingTimeout(`${API_BASE}/api/requests/${requestId}/step-attachment`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })

      if (resp.ok) {
        const data = await resp.json()
        setChatMessages(data.conversation || [])
        setAwaitingAttachment(false)
        if (data.progress) setStepProgress(data.progress)
      } else {
        const errorData = await resp.json().catch(() => null)
        throw new Error(errorData?.detail || 'Could not process that attachment.')
      }
    } catch (err) {
      console.error('Step attachment submission failed:', err)
      const message = err.isNetworkError ? NETWORK_ERROR_MESSAGE : LOAD_ERROR_MESSAGE
      setChatMessages((prev) => [
        ...prev,
        { sender: 'ai', text: message, timestamp: new Date().toISOString(), _animate: true },
      ])
    } finally {
      setPendingFile(null)
      setIsSubmittingStepAttachment(false)
      isChatLoadingRef.current = false
    }
  }

  // Records whether the user wants to fix flagged anomalies here in
  // chat or by reopening the Excel file and resubmitting it — posted
  // from the choice card rendered above the anomaly list the first
  // time an open anomaly appears.
  const submitCorrectionMode = async (mode) => {
    if (!requestId) return
    setIsSubmittingCorrectionMode(true)
    isChatLoadingRef.current = true

    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetchWithThinkingTimeout(`${API_BASE}/api/requests/${requestId}/correction-mode`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ mode }),
      })

      if (resp.ok) {
        const data = await resp.json()
        setChatMessages(data.conversation || [])
        setCorrectionMode(data.correction_mode || null)
        setNeedsCorrectionModeChoice(false)
        fetchRequestState(requestId)
      } else {
        const errorData = await resp.json().catch(() => null)
        throw new Error(errorData?.detail || 'Could not record that choice.')
      }
    } catch (err) {
      console.error('Correction mode submission failed:', err)
      const message = err.isNetworkError ? NETWORK_ERROR_MESSAGE : LOAD_ERROR_MESSAGE
      setChatMessages((prev) => [
        ...prev,
        { sender: 'ai', text: message, timestamp: new Date().toISOString(), _animate: true },
      ])
    } finally {
      setIsSubmittingCorrectionMode(false)
      isChatLoadingRef.current = false
    }
  }

  // Records an update/ignore decision for a conflict anomaly, posted
  // from the decision buttons rendered in the chat.
  const submitDecision = async (anomalyId, decision) => {
    if (!requestId) return
    setIsSubmittingDecision(true)
    isChatLoadingRef.current = true

    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetchWithThinkingTimeout(`${API_BASE}/api/requests/${requestId}/decision`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ anomaly_id: anomalyId, decision }),
      })

      if (resp.ok) {
        const data = await resp.json()
        setChatMessages(data.conversation || [])
        fetchRequestState(requestId)
      } else {
        const errorData = await resp.json().catch(() => null)
        throw new Error(errorData?.detail || 'Could not record that decision.')
      }
    } catch (err) {
      console.error('Decision submission failed:', err)
      const message = err.isNetworkError ? NETWORK_ERROR_MESSAGE : LOAD_ERROR_MESSAGE
      setChatMessages((prev) => [
        ...prev,
        { sender: 'ai', text: message, timestamp: new Date().toISOString(), _animate: true },
      ])
    } finally {
      setIsSubmittingDecision(false)
      isChatLoadingRef.current = false
    }
  }

  // Submits a corrected value for a flagged row/column, posted from
  // the correction field rendered on that anomaly's card.
  const submitCorrection = async (anomalyId) => {
    const correctedValue = (correctionDrafts[anomalyId] || '').trim()
    if (!requestId || !correctedValue) return

    setSubmittingCorrectionId(anomalyId)
    isChatLoadingRef.current = true

    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetchWithThinkingTimeout(`${API_BASE}/api/requests/${requestId}/correction`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ anomaly_id: anomalyId, corrected_value: correctedValue }),
      })

      if (resp.ok) {
        const data = await resp.json()
        setChatMessages(data.conversation || [])
        if (data.accepted) {
          setCorrectionDrafts((prev) => {
            const next = { ...prev }
            delete next[anomalyId]
            return next
          })
        }
        fetchRequestState(requestId)
      } else {
        const errorData = await resp.json().catch(() => null)
        throw new Error(errorData?.detail || 'Could not submit that correction.')
      }
    } catch (err) {
      console.error('Correction submission failed:', err)
      const message = err.isNetworkError ? NETWORK_ERROR_MESSAGE : LOAD_ERROR_MESSAGE
      setChatMessages((prev) => [
        ...prev,
        { sender: 'ai', text: message, timestamp: new Date().toISOString(), _animate: true },
      ])
    } finally {
      setSubmittingCorrectionId(null)
      isChatLoadingRef.current = false
    }
  }

  // "Open the file, fix it in Excel, send it back" — the corrected
  // file replaces the one on this same request, and gets re-validated
  // from scratch.
  const resubmitCorrectedFile = async (file) => {
    if (!file || !requestId) return

    setIsResubmittingFile(true)
    isChatLoadingRef.current = true

    const formData = new FormData()
    formData.append('file', file)

    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetchWithThinkingTimeout(`${API_BASE}/api/requests/${requestId}/resubmit-file`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })

      if (resp.ok) {
        const data = await resp.json()
        setChatMessages(data.conversation || [])
        setValidationErrors(data.validation_errors || [])
        updateStats(data.validation_errors || [])
        setRequestStatus(data.status)
        if (data.file_url) setFileUrl(data.file_url)
        fetchRequestState(requestId)
      } else {
        const errorData = await resp.json().catch(() => null)
        throw new Error(errorData?.detail || 'Could not process the corrected file.')
      }
    } catch (err) {
      console.error('Resubmit failed:', err)
      const message = err.isNetworkError ? NETWORK_ERROR_MESSAGE : LOAD_ERROR_MESSAGE
      setChatMessages((prev) => [
        ...prev,
        { sender: 'ai', text: message, timestamp: new Date().toISOString(), _animate: true },
      ])
    } finally {
      setIsResubmittingFile(false)
      isChatLoadingRef.current = false
    }
  }

const sendChatMessage = async (e) => {
    e.preventDefault()
    if (!chatInput.trim() && !pendingFile) return

    // A main-file upload, a reference file, and a step attachment each
    // take their own dedicated path — none of them is a chat turn the
    // existing step-chat/generic-chat endpoints understand.
    if (pendingFile) {
      if (canAttachMainFile) {
        // No request yet — this attachment is the file to be analyzed,
        // sent straight from the conversation instead of the upload
        // dropzone in the left panel.
        const fileToAnalyze = pendingFile
        setPendingFile(null)
        await uploadFile(fileToAnalyze)
      } else if (awaitingAttachment) {
        // The AI's own attachment request takes priority: it's what
        // the user is being asked for.
        await submitStepAttachment()
      } else {
        await submitReferenceFile()
      }
      return
    }

    const messageText = chatInput.trim()
    setChatInput('')
    setIsChatLoading(true)
    isChatLoadingRef.current = true

    const optimisticUserMsg = { sender: 'user', text: messageText, timestamp: new Date().toISOString() }
    setChatMessages((prev) => [...prev, optimisticUserMsg])

    try {
      const token = localStorage.getItem('brainopx_token')
      
      // Determine which endpoint to use: step-by-step or generic chat
      const hasActiveWorkflow = stepProgress && stepProgress.total_steps > 0 && !stepProgress.all_completed
      
      let resp
      if (hasActiveWorkflow) {
        // Use the step-by-step chat endpoint
        const formData = new FormData()
        formData.append('message', messageText)
        resp = await fetchWithThinkingTimeout(`${API_BASE}/api/requests/${requestId}/step-chat`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
          body: formData
        })
      } else {
        // Use the generic chat endpoint
        resp = await fetchWithThinkingTimeout(`${API_BASE}/api/chat`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            request_id: requestId,
            user_message: messageText
          })
        })
      }

      if (resp.ok) {
        const data = await resp.json()
        
        // Update messages from response. The user's bubble carries
        // whether the value it holds satisfied the step.
        setChatMessages((prev) => {
          const filtered = prev.filter(msg => msg.text !== messageText || msg.sender !== 'user')
          return [
            ...filtered,
            {
              sender: 'user',
              text: messageText,
              validated: data.passed === true,
              timestamp: new Date().toISOString(),
            },
            {
              sender: 'ai',
              text: data.ai_response,
              passed: data.passed === true,
              timestamp: new Date().toISOString(),
              _animate: true,
            }
          ]
        })
        
        // Update other state
        if (data.status) setRequestStatus(data.status)
        if (data.validation_errors) setValidationErrors(data.validation_errors)
        if (data.generated_script) setGeneratedScript(data.generated_script)
        
        // Update step progress from step-chat response
        if (data.progress) {
          setStepProgress(data.progress)
        }

        // The AI just asked for a file/screenshot after several
        // confused turns on this step (or the user resolved/skipped
        // that request) — reflect it so the composer knows whether an
        // attached file should go to /step-attachment.
        setAwaitingAttachment(Boolean(data.awaiting_attachment))

        // Finishing the walkthrough completes the request outright
        // (mirrors the backend, which now persists this directly
        // instead of leaving it at 'data_validated').
        if (data.all_completed) {
          setRequestStatus('processing_completed')
        }
        
        // Update stats from response
        if (data.stats) {
          setStats(data.stats)
        } else {
          updateStats(data.validation_errors || [])
        }
      } else {
        const errorData = await resp.json()
        throw new Error(errorData.detail || 'Chat failed')
      }
    } catch (err) {
      console.error('Chat failed:', err)
      const message = err.isNetworkError ? NETWORK_ERROR_MESSAGE : LOAD_ERROR_MESSAGE
      setChatMessages((prev) => [
        ...prev,
        { sender: 'ai', text: message, timestamp: new Date().toISOString(), _animate: true }
      ])
    } finally {
      setIsChatLoading(false)
      isChatLoadingRef.current = false
    }
  }

  // ─── EDITING MODE: correcting an already-completed step ────────────────────

  const openEditDialog = async (stepIndex, ruleName) => {
    setEditResultHtml(null)
    setEditSucceeded(false)
    setEditStep({ stepIndex, ruleName, previewHtml: null })
    setEditValue('')

    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetch(`${API_BASE}/api/requests/${requestId}/completed-steps`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (resp.ok) {
        const data = await resp.json()
        const found = (data.steps || []).find((s) => s.step_index === stepIndex)
        if (found) {
          setEditValue(found.user_value || '')
          setEditStep({ stepIndex, ruleName, previewHtml: found.preview_html || null })
        }
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
    if (!editStep || !editValue.trim()) return
    setEditSaving(true)
    setEditResultHtml(null)

    try {
      const token = localStorage.getItem('brainopx_token')
      const formData = new FormData()
      formData.append('step_index', String(editStep.stepIndex))
      formData.append('value', editValue)

      const resp = await fetch(`${API_BASE}/api/requests/${requestId}/step-edit`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      })

      if (resp.ok) {
        const data = await resp.json()
        setEditResultHtml(data.ai_response || '')
        setEditSucceeded(!!data.edited)

        if (data.edited) {
          // Resync the chip list and conversation so the correction
          // is reflected everywhere without disturbing the user's
          // current position in the workflow.
          if (data.conversation) setChatMessages(data.conversation)

          const progressResp = await fetch(`${API_BASE}/api/requests/${requestId}/step-progress`, {
            headers: { 'Authorization': `Bearer ${token}` }
          })
          if (progressResp.ok) {
            setStepProgress(await progressResp.json())
          }
        }
      } else {
        const errorData = await resp.json()
        setEditResultHtml(`<span class="failure-message">${errorData.detail || 'The correction could not be saved.'}</span>`)
      }
    } catch (err) {
      console.error('Saving the correction failed:', err)
      setEditResultHtml('<span class="failure-message">Sorry, I encountered an error. Please try again.</span>')
    } finally {
      setEditSaving(false)
    }
  }

  // ─── RECOVERING FROM AN AI FAILURE ON THE ACTIVE STEP ──────────────────────

  const regenerateExample = async () => {
    if (!requestId || regenerating) return
    setRegenerating(true)

    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetch(`${API_BASE}/api/requests/${requestId}/step-regenerate`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      })

      if (resp.ok) {
        const data = await resp.json()
        if (data.conversation) setChatMessages(data.conversation)

        const progressResp = await fetch(`${API_BASE}/api/requests/${requestId}/step-progress`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
        if (progressResp.ok) {
          setStepProgress(await progressResp.json())
        }
      }
    } catch (err) {
      console.error('Regenerating the example failed:', err)
    } finally {
      setRegenerating(false)
    }
  }

  // Auto-dismiss the "AI couldn't generate an example" banner if the user
  // doesn't act on it. Re-arms every time a fresh ai_unavailable state
  // arrives (e.g. a retry that fails again), so the banner reappears.
  useEffect(() => {
    if (stepProgress?.example_source !== 'ai_unavailable') return

    setAiUnavailableDismissed(false)

    const timer = setTimeout(() => {
      setAiUnavailableDismissed(true)
    }, 6000)

    return () => clearTimeout(timer)
  }, [stepProgress])

  const editLastAnswer = () => {
    const previous = chatMessages[chatMessages.length - 2]
    if (previous?.sender !== 'user') return
    setChatInput(previous.text || '')
    composerInputRef.current?.focus()
  }

  const downloadScript = () => {
    if (!generatedScript) return
    const blob = new Blob([generatedScript], { type: 'text/sql' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `brainopx_config_${requestId}.sql`
    a.click()
    URL.revokeObjectURL(url)
  }

  // Manual retry for when the automatic generation (fired the moment
  // the walkthrough completes) failed — e.g. a Groq rate limit — or
  // the user just wants another attempt.
  const regenerateScript = async () => {
    if (!requestId || isGeneratingScript) return
    setIsGeneratingScript(true)
    setScriptGenError(null)
    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetch(`${API_BASE}/api/requests/${requestId}/regenerate-workflow-script`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(body.detail || `Script generation failed (${resp.status}).`)
      }
      const data = await resp.json()
      setGeneratedScript(data.generated_script || null)
    } catch (err) {
      setScriptGenError(err.message || 'Script generation failed.')
    } finally {
      setIsGeneratingScript(false)
    }
  }

  const handleReset = () => {
    clearInterval(pollRef.current)
    setRequestId(null)
    setRequestStatus('draft')
    setUploadedFile(null)
    setUploadError(null)
    setValidationErrors([])
    setChatMessages([])
    setGeneratedScript(null)
    setPendingFile(null)
    setSelectedTaskId('')
    setStats({ total: 0, solved: 0, remaining: 0, progress: 0 })
    setMatchInfo(null)
    setShowTemplateSelection(false)
    setAvailableTemplates([])
    setPendingUploadFile(null)
  }

  // ─── DRAG & DROP HANDLERS ─────────────────────────────────────────────────────

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) uploadFile(file)
  }

  const handleDragOver = (e) => { e.preventDefault(); setIsDragging(true) }
  const handleDragLeave = () => setIsDragging(false)
  const handleFileInputChange = (e) => { if (e.target.files?.[0]) uploadFile(e.target.files[0]) }

  // ─── DERIVED DISPLAY VALUES ───────────────────────────────────────────────────

  const statusConfig = STATUS_CONFIG[requestStatus] || STATUS_CONFIG.draft
  const activeStep = statusConfig.step
  const isCompleted = ['script_generated', 'processing_completed'].includes(requestStatus)

  const openErrors = validationErrors.filter(e => e.status === 'open')
  const resolvedErrors = validationErrors.filter(e => e.status === 'solved')

  const selectedTask = availableTasks.find((t) => t.id === selectedTaskId)
  // The step-by-step "Rule Workflow Progress" bar only makes sense for
  // skill_engine tasks (each rule is walked one at a time). report_analyses
  // tasks are validated as a whole batch against the Excel template, so
  // they surface progress through the validation report instead.
  const isSkillEngineTask = selectedTask?.category === 'skill_engine'
  const hasActiveStepWorkflow = stepProgress && stepProgress.total_steps > 0 && !stepProgress.all_completed
  const lastChatMessage = chatMessages[chatMessages.length - 1]
  const secondLastChatMessage = chatMessages[chatMessages.length - 2]
  const canEditLastAnswer =
    lastChatMessage?.sender === 'ai' &&
    lastChatMessage?.passed === false &&
    secondLastChatMessage?.sender === 'user'

  // No request has been created yet — a file attached from the
  // composer at this point is the main configuration file to analyze
  // (the same thing the upload dropzone does), not a reference/step
  // attachment for an already-running conversation.
  const canAttachMainFile = !requestId

  // ─── RENDER ───────────────────────────────────────────────────────────────────

  return (
    <Box sx={{ p: 2 }}>
      <Box sx={{ width: '100%', maxWidth: '100%' }}>

      {/* ── Page Title ─────────────────────────────────────────────── */}
      <Box sx={{
        mb: 2,
        borderBottom: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`,
        pb: 1.5,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        flexWrap: 'wrap',
        gap: 2
      }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700, fontFamily: "'Outfit', sans-serif", mb: 0.5 }}>
            Configuration Ingest
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Upload a BRAINOPX Excel configuration file, review validation errors, resolve them through chat, and download the final script.
          </Typography>
        </Box>

        {requestId && (
          <Button
            startIcon={<RefreshIcon />}
            variant="outlined"
            onClick={handleReset}
            sx={{ textTransform: 'none', borderRadius: 2 }}
          >
            Start New Request
          </Button>
        )}
      </Box>

      {/* ── Status Stepper ─────────────────────────────────────────── */}
      <Paper
        elevation={0}
        sx={{
          p: 2,
          mb: 3,
          borderRadius: 3,
          background: (theme) => theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.02)' : '#f8fbff',
          border: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}`
        }}
      >
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
          <Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, textTransform: 'uppercase' }}>
              Request Status
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.3 }}>
              <Chip
                label={statusConfig.label}
                color={statusConfig.color}
                size="small"
                sx={{ fontWeight: 700, fontSize: 11 }}
              />
              {requestId && (
                <Typography variant="caption" sx={{ color: 'text.muted', fontFamily: 'monospace' }}>
                  ID: #{requestId}
                </Typography>
              )}
            </Box>
          </Box>
          {validationErrors.length > 0 && (
            <Stack direction="row" spacing={1} alignItems="center">
              <Chip
                icon={<CheckCircleIcon />}
                label={`${stats.solved} / ${stats.total} solved`}
                color={stats.remaining === 0 ? 'success' : 'info'}
                size="small"
                sx={{ fontWeight: 700, fontSize: 10 }}
              />
              <Chip
                icon={<ErrorIcon />}
                label={`${stats.remaining} remaining`}
                color={stats.remaining === 0 ? 'success' : 'error'}
                size="small"
                variant="outlined"
                sx={{ fontWeight: 700, fontSize: 10 }}
              />
            </Stack>
          )}
        </Stack>

        {/* Progress Bar */}
        {validationErrors.length > 0 && (
          <Box sx={{ mb: 1.5 }}>
            <Stack direction="row" justifyContent="space-between" sx={{ mb: 0.5 }}>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Progress
              </Typography>
              <Typography variant="caption" sx={{ fontWeight: 700, color: stats.progress === 100 ? 'success.main' : 'text.primary' }}>
                {stats.progress}%
              </Typography>
            </Stack>
            <LinearProgress
              variant="determinate"
              value={stats.progress}
              color={stats.progress === 100 ? 'success' : 'primary'}
              sx={{ height: 8, borderRadius: 4 }}
            />
          </Box>
        )}

<Stepper activeStep={activeStep} alternativeLabel sx={{ '& .MuiStepLabel-label': { fontSize: 10 } }}>
          {PROCESS_STEPS.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {/* Step-by-Step Workflow Progress — Skill Engine tasks only */}
        {isSkillEngineTask && stepProgress && stepProgress.total_steps > 0 && (
          <Box sx={{ mt: 2, pt: 2, borderTop: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}` }}>
            <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, textTransform: 'uppercase', mb: 1, display: 'block' }}>
              Rule Workflow Progress
            </Typography>
            <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', gap: 0.5 }}>
              {stepProgress.steps && stepProgress.steps.map((step, idx) => {
                const editable = step.status === 'completed' && !stepProgress.all_completed
                return (
                  <Tooltip
                    key={idx}
                    title={editable ? `${step.rule_name} — click to edit your answer` : `${step.rule_name} (${step.status})`}
                  >
                    <Chip
                      label={`${step.step_index + 1}. ${step.rule_name}`}
                      color={
                        step.status === 'completed' ? 'success' :
                        step.status === 'active' ? 'primary' :
                        step.status === 'validated' ? 'info' :
                        'default'
                      }
                      variant={step.status === 'active' ? 'filled' : 'outlined'}
                      size="small"
                      onClick={editable ? () => openEditDialog(step.step_index, step.rule_name) : undefined}
                      sx={{
                        fontWeight: 600,
                        fontSize: 10,
                        opacity: step.status === 'pending' ? 0.5 : 1,
                        cursor: editable ? 'pointer' : 'default',
                      }}
                      icon={
                        step.status === 'completed' ? <CheckCircleIcon /> :
                        step.status === 'active' ? <CircularProgress size={10} /> :
                        null
                      }
                    />
                  </Tooltip>
                )
              })}
            </Stack>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 1 }}>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                {stepProgress.completed_steps}/{stepProgress.total_steps} rules completed
              </Typography>
              <Typography variant="caption" sx={{ fontWeight: 700, color: stepProgress.all_completed ? 'success.main' : 'text.primary' }}>
                {stepProgress.progress}%
              </Typography>
            </Stack>
            <LinearProgress
              variant="determinate"
              value={stepProgress.progress}
              color={stepProgress.all_completed ? 'success' : 'primary'}
              sx={{ height: 6, borderRadius: 3, mt: 0.5 }}
            />
          </Box>
        )}
      </Paper>

      {/* ── Main Content Grid ───────────────────────────────────────── */}
      <Grid container spacing={2}>

        {/* ── LEFT PANEL ─────────────────────────────────────────── */}
        {/* Stays beside the conversation at every stage — the upload
            and task controls never move or disappear once a
            walkthrough starts. */}
        <Grid item xs={12} md={6}>
          <Stack spacing={2}>

            {/* Always available — the task can be switched and another
                file uploaded at any point, including mid-conversation. */}
              <Grow in={true}>
                <Paper sx={{
                  p: 2.25, borderRadius: 3,
                  background: (theme) => theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : '#ffffff',
                  border: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`
                }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5, fontFamily: "'Outfit', sans-serif" }}>
                    Task &amp; configuration file
                  </Typography>

                  <FormControl fullWidth sx={{ mb: 2 }}>
                    <InputLabel id="task-label">Configuration Task Template</InputLabel>
                    <Select
                      labelId="task-label"
                      value={selectedTaskId}
                      label="Configuration Task Template"
                      onChange={(e) => setSelectedTaskId(e.target.value)}
                      disabled={tasksLoading}
                    >
                      {tasksLoading ? (
                        <MenuItem disabled><CircularProgress size={14} sx={{ mr: 1 }} /> Loading tasks...</MenuItem>
                      ) : filteredTasks.length === 0 ? (
                        <MenuItem disabled>
                          {searchTerm ? `No tasks match "${searchTerm}"` : 'No task templates found. Create one in Task Management first.'}
                        </MenuItem>
                      ) : (
                        filteredTasks.map((t) => (
                          <MenuItem key={t.id} value={t.id}>
                            <Stack>
                              <Typography variant="body2" sx={{ fontWeight: 600 }}>{t.name}</Typography>
                              <Typography variant="caption" sx={{ color: 'text.secondary' }}>{t.type}</Typography>
                            </Stack>
                          </MenuItem>
                        ))
                      )}
                    </Select>
                  </FormControl>

                  {uploadError && (
                    <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }} onClose={() => setUploadError(null)}>
                      {uploadError}
                    </Alert>
                  )}
{matchInfo && (
  <Paper sx={{ p: 2, borderRadius: 2, bgcolor: 'rgba(76, 175, 80, 0.05)', border: '1px solid rgba(76, 175, 80, 0.2)' }}>
<Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'success.main' }}>
      Template Matched: {matchInfo.taskName}
    </Typography>
    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
      Match Score: {matchInfo.matchScore}%
    </Typography>
    <Box sx={{ mt: 1 }}>
      <Typography variant="caption" sx={{ fontWeight: 600 }}>
        Matched Columns: {matchInfo.matchedColumns.join(', ')}
      </Typography>
      {matchInfo.missingColumns.length > 0 && (
<Typography variant="caption" sx={{ display: 'block', color: 'warning.main' }}>
          Missing Columns: {matchInfo.missingColumns.join(', ')}
        </Typography>
      )}
    </Box>
  </Paper>
)}
                  <Box
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => !isUploading && fileInputRef.current?.click()}
                    sx={{
                      border: '2px dashed',
                      borderColor: isDragging ? 'primary.main' : (theme) => theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#cbd5e1',
                      borderRadius: 3,
                      p: 4,
                      textAlign: 'center',
                      background: isDragging
                        ? 'rgba(79,70,229,0.04)'
                        : (theme) => theme.palette.mode === 'dark' ? 'rgba(0,0,0,0.1)' : '#f8fbff',
                      cursor: isUploading ? 'wait' : 'pointer',
                      transition: 'all 0.2s ease',
                      '&:hover': {
                        borderColor: 'primary.main',
                        background: 'rgba(79, 70, 229, 0.02)'
                      }
                    }}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      style={{ display: 'none' }}
                      accept=".xlsx,.xls,.csv"
                      onChange={handleFileInputChange}
                    />

                    {isUploading ? (
                      <>
                        <CircularProgress size={32} sx={{ mb: 1 }} />
                        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                          Uploading and analysing...
                        </Typography>
                        <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
                          The rules engine is checking your file against the task definition.
                        </Typography>
                      </>
                    ) : (
                      <>
                        <CloudUploadIcon sx={{ fontSize: 40, color: 'text.secondary', mb: 1 }} />
                        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
                          Drag & Drop your Excel configuration file here
                        </Typography>
                        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                          or click to browse files (.xlsx, .xls, .csv)
                        </Typography>
                      </>
                    )}
                  </Box>
                </Paper>
              </Grow>

            {uploadedFile && requestStatus !== 'draft' && (
              <Paper sx={{
                p: 1.5, borderRadius: 2,
                border: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`,
                display: 'flex', alignItems: 'center', gap: 2
              }}>
                <InsertDriveFileIcon color="success" />
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{uploadedFile.name}</Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    {(uploadedFile.size / 1024).toFixed(1)} KB • Submitted successfully
                  </Typography>
                </Box>
                <Chip label="Submitted" color="success" size="small" sx={{ fontWeight: 700 }} />
              </Paper>
            )}

            {requestStatus === 'analysis_in_progress' && (
              <Paper sx={{ p: 3, borderRadius: 3, textAlign: 'center' }}>
                <CircularProgress size={32} sx={{ mb: 1 }} />
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Rules Engine Running...
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  Checking column schemas, value formats, mandatory fields, and business rule constraints.
                </Typography>
                <LinearProgress sx={{ mt: 2, borderRadius: 2 }} />
              </Paper>
            )}

            {validationErrors.length > 0 && (
              <Fade in={true}>
                <Paper sx={{
                  p: 2.5, 
                  borderRadius: 3,
                  border: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`,
                  width: '100%',
                  maxWidth: '100%',
                  overflow: 'hidden',
                }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1, flexWrap: 'wrap', gap: 1 }}>
                    <Typography variant="h6" sx={{ fontWeight: 700, fontFamily: "'Outfit', sans-serif", display: 'flex', alignItems: 'center', gap: 1 }}>
                      {openErrors.length > 0 ? <WarningAmberIcon color="warning" /> : <CheckCircleIcon color="success" />}
                      Validation Report
                    </Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                      {resolvedErrors.length}/{validationErrors.length} resolved
                    </Typography>
                  </Box>

                  {fileUrl && (
                    <Stack direction="row" spacing={1} sx={{ mb: 1.5 }} flexWrap="wrap" useFlexGap>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<AttachFileIcon fontSize="small" />}
                        onClick={() => window.open(`${API_BASE}${fileUrl}`, '_blank', 'noopener,noreferrer')}
                      >
                        Open Excel file
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={isResubmittingFile ? <CircularProgress size={14} /> : <CloudUploadIcon fontSize="small" />}
                        disabled={isResubmittingFile}
                        onClick={() => resubmitFileInputRef.current?.click()}
                      >
                        Resubmit corrected file
                      </Button>
                      <input
                        ref={resubmitFileInputRef}
                        type="file"
                        accept=".xlsx,.xls,.csv"
                        style={{ display: 'none' }}
                        onChange={(e) => {
                          const picked = e.target.files?.[0]
                          e.target.value = ''
                          if (picked) resubmitCorrectedFile(picked)
                        }}
                      />
                    </Stack>
                  )}

                  <Box sx={{ width: '100%', overflowX: 'auto' }}>
                    <TableContainer 
                      component={Paper} 
                      variant="outlined" 
                      sx={{ 
                        borderRadius: 2,
                        minWidth: 0,
                        width: '100%',
                      }}
                    >
                      <Table size="small" sx={{ minWidth: 500, tableLayout: 'fixed' }}>
                        <TableHead sx={{
                          bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.02)' : '#f9fafb'
                        }}>
                          <TableRow>
                            <TableCell sx={{ fontWeight: 700, width: 45 }}>Row</TableCell>
                            <TableCell sx={{ fontWeight: 700, width: 100 }}>Column</TableCell>
                            <TableCell sx={{ fontWeight: 700, width: 110 }}>Submitted Value</TableCell>
                            <TableCell sx={{ fontWeight: 700, width: 130 }}>Rule Violated</TableCell>
                            <TableCell sx={{ fontWeight: 700, width: 75 }}>Status</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {validationErrors.map((err, idx) => (
                            <TableRow
                              key={idx}
                              sx={{
                                opacity: err.status === 'solved' ? 0.6 : 1,
                                transition: 'opacity 0.4s ease',
                                bgcolor: err.status === 'solved' ? 'rgba(76, 175, 80, 0.05)' : 'transparent',
                              }}
                            >
                              <TableCell sx={{ fontWeight: 700 }}>{err.row}</TableCell>
                              <TableCell sx={{ fontFamily: 'monospace', fontSize: 11, color: 'info.main', fontWeight: 600 }}>
                                {err.column}
                              </TableCell>
                              <TableCell sx={{ textDecoration: err.status === 'solved' ? 'line-through' : 'none', fontSize: 11 }}>
                                <Tooltip title={err.message || ''}>
                                  <span>{err.submitted_value ?? err.value ?? '—'}</span>
                                </Tooltip>
                              </TableCell>
                              <TableCell sx={{ fontSize: 10, color: 'text.secondary', wordBreak: 'break-word' }}>
                                {err.rule_violated ?? err.rule ?? '—'}
                              </TableCell>
                              <TableCell>
                                <Tooltip title={fileUrl ? 'Open the Excel file to fix this in place' : ''}>
                                  <Chip
                                    label={err.status === 'solved' ? 'Solved' : 'Open'}
                                    color={err.status === 'solved' ? 'success' : 'error'}
                                    size="small"
                                    onClick={fileUrl ? () => window.open(`${API_BASE}${fileUrl}`, '_blank', 'noopener,noreferrer') : undefined}
                                    sx={{
                                      fontSize: 9,
                                      height: 18,
                                      fontWeight: 700,
                                      cursor: fileUrl ? 'pointer' : 'default',
                                    }}
                                  />
                                </Tooltip>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </Box>
                  
{/* Fixed: Correction summary using resolvedErrors */}
                  {resolvedErrors.length > 0 && (
                    <Box sx={{ mt: 2, p: 1.5, bgcolor: 'rgba(76, 175, 80, 0.08)', borderRadius: 2 }}>
                      <Typography variant="caption" sx={{ fontWeight: 700, color: 'success.main' }}>
                        Corrections made:
                      </Typography>
                      {resolvedErrors.map((err, idx) => (
                        <Typography key={idx} variant="caption" display="block" sx={{ color: 'text.secondary', mt: 0.5 }}>
                          • Row {err.row}, column "{err.column}": {err.user_correction || 'Fixed'}
                        </Typography>
                      ))}
                    </Box>
                  )}
                </Paper>
              </Fade>
            )}

            {generatedScript && (
              <Fade in={Boolean(generatedScript)}>
                <Paper sx={{
                  p: 2.5, borderRadius: 3,
                  border: '1px solid rgba(16,185,129,0.3)',
                  bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(16,185,129,0.03)' : 'rgba(16,185,129,0.01)'
                }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
                    <Typography variant="h6" sx={{ fontWeight: 700, fontFamily: "'Outfit', sans-serif", display: 'flex', alignItems: 'center', gap: 1 }}>
                      <CheckCircleIcon color="success" /> BRAINOPX Configuration Script
                    </Typography>
                    <Stack direction="row" spacing={1}>
                      <Tooltip title="Regenerate script">
                        <span>
                          <IconButton
                            onClick={regenerateScript}
                            disabled={isGeneratingScript}
                            sx={{ border: '1px solid rgba(0,0,0,0.12)' }}
                          >
                            {isGeneratingScript ? <CircularProgress size={18} /> : <RefreshIcon fontSize="small" />}
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Button
                        variant="contained"
                        startIcon={<DownloadIcon />}
                        color="success"
                        onClick={downloadScript}
                        sx={{ textTransform: 'none', borderRadius: 2 }}
                      >
                        Download Script
                      </Button>
                    </Stack>
                  </Stack>

                  {scriptGenError && (
                    <Alert severity="warning" sx={{ mb: 1.5, borderRadius: 2 }} onClose={() => setScriptGenError(null)}>
                      {scriptGenError}
                    </Alert>
                  )}

                  <Paper
                    variant="outlined"
                    sx={{
                      p: 2,
                      fontFamily: 'monospace',
                      fontSize: 11,
                      lineHeight: 1.5,
                      background: '#040711',
                      color: '#84f7c2',
                      borderRadius: 2,
                      border: '1px solid rgba(255,255,255,0.08)',
                      maxHeight: 200,
                      overflowY: 'auto',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                    }}
                  >
                    {generatedScript}
                  </Paper>
                </Paper>
              </Fade>
            )}

            {isCompleted && !generatedScript && (
              <Fade in>
                <Paper sx={{ p: 2.5, borderRadius: 3, border: '1px dashed rgba(0,0,0,0.2)' }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2}>
                    <Box>
                      <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                        No script yet
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {scriptGenError || 'Script generation did not run or failed for this task.'}
                      </Typography>
                    </Box>
                    <Button
                      variant="outlined"
                      startIcon={isGeneratingScript ? <CircularProgress size={16} /> : <RefreshIcon />}
                      onClick={regenerateScript}
                      disabled={isGeneratingScript}
                      sx={{ textTransform: 'none', borderRadius: 2, whiteSpace: 'nowrap' }}
                    >
                      Generate Script
                    </Button>
                  </Stack>
                </Paper>
              </Fade>
            )}

          </Stack>
        </Grid>

{/* ── RIGHT PANEL: AI Chat ─────────────────────────────────── */}
        <Grid item xs={12} md={6} sx={{ position: 'relative' }}>
<ResizableChatPanel
            defaultSize={560}
            sx={{
              position: 'sticky',
              top: 16,
              height: 'calc(100vh - 200px)',
              // A single rounded surface. The conversation's gradient
              // runs to its edges, so it is clipped to the corners.
              borderRadius: 3,
              overflow: 'hidden',
              border: (theme) =>
                theme.palette.mode === 'dark'
                  ? '1px solid rgba(255,255,255,0.08)'
                  : '1px solid rgba(79,70,229,0.14)',
              boxShadow: (theme) =>
                theme.palette.mode === 'dark'
                  ? '0 10px 30px rgba(0,0,0,0.36)'
                  : '0 10px 34px rgba(79,70,229,0.08)',
            }}
          >

            <Box sx={{
              p: 1.5,
              bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)',
              borderBottom: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}`,
              display: 'flex',
              alignItems: 'center',
              gap: 1
            }}>
              <ChatIcon color="primary" />
              <Box sx={{ flex: 1 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>BRAINOPX AI Assistant</Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  {requestStatus === 'draft'
                    ? 'Upload a file to begin'
                    : `Context: ${statusConfig.label}`}
                </Typography>
              </Box>
              {isChatLoading && <CircularProgress size={14} />}
            </Box>

            <Box
              onScroll={handleChatScroll}
              sx={{
              flex: 1,
              px: 2.5,
              py: 3,
              overflowY: 'auto',
              background: conversationBackground,
            }}>
              {/* Across the full width, lines would run too long to
                  read comfortably, so the conversation is held to a
                  centred column the way a chat client does. */}
              <Box sx={{
                display: 'flex',
                flexDirection: 'column',
                // Room for the lifted cards, so their shadows are not
                // clipped by the next message.
                gap: 2.25,
                minHeight: '100%',
                width: '100%',
                maxWidth: '100%',
                mx: 'auto',
              }}>

              {chatMessages.length === 0 && !welcomeLoading ? (
                <Box sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: '100%',
                  color: 'text.disabled',
                  gap: 0.5
                }}>
                  <ChatIcon sx={{ fontSize: 32, opacity: 0.3 }} />
                  <Typography variant="body2" align="center" sx={{ maxWidth: 200 }}>
                    Select a task and upload your Excel file to start the AI-guided validation process.
                  </Typography>
                </Box>
              ) : (
                chatMessages.map((msg, idx) => (
                  <ChatMessage
                    key={idx}
                    sender={msg.sender}
                    text={msg.text || msg.content}
                    timestamp={msg.timestamp}
                    validated={msg.validated}
                    html={msg.sender === 'ai'}
                    user={user}
                    animate={Boolean(msg._animate)}
                  />
                ))
              )}

              {/* Asked once, the first time an open anomaly appears: does
                  the user want to type corrected values here in chat, or
                  reopen the Excel file, fix it there, and resubmit it for
                  another check? Reference-file/update/ignore actions below
                  aren't gated on this — only the plain correction field is. */}
              {needsCorrectionModeChoice && (
                <Paper
                  variant="outlined"
                  sx={{ p: 2, borderRadius: 2, borderColor: 'primary.main', bgcolor: 'action.hover' }}
                >
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                    How would you like to fix these?
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1.5 }}>
                    You can type each corrected value here in the chat, or reopen the Excel
                    file, fix it there, and resubmit it for another check.
                  </Typography>
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    <Button
                      size="small"
                      variant="contained"
                      disabled={isSubmittingCorrectionMode}
                      onClick={() => submitCorrectionMode('chat')}
                    >
                      Correct here in chat
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      disabled={isSubmittingCorrectionMode}
                      onClick={() => submitCorrectionMode('excel')}
                    >
                      I'll fix it in Excel
                    </Button>
                  </Stack>
                </Paper>
              )}

              {/* Conflicts found between the upload and a reference file:
                  each needs an explicit update-vs-ignore decision before
                  the request can move on. */}
              {anomalies.filter((a) => a.status === 'open' && a.kind === 'conflict').map((a) => (
                <Paper
                  key={a.id}
                  variant="outlined"
                  sx={{ p: 2, borderRadius: 2, borderColor: 'warning.main', bgcolor: 'rgba(237,108,2,0.06)' }}
                >
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                    Conflict on row {a.row}, column "{a.column}"
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1.5 }}>
                    Code "{a.code}" differs from the reference file. Update the existing record, or ignore this row?
                  </Typography>
                  <Stack direction="row" spacing={1}>
                    <Button
                      size="small"
                      variant="contained"
                      color="warning"
                      disabled={isSubmittingDecision}
                      onClick={() => submitDecision(a.id, 'update')}
                    >
                      Update existing
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      disabled={isSubmittingDecision}
                      onClick={() => submitDecision(a.id, 'ignore')}
                    >
                      Ignore
                    </Button>
                  </Stack>
                </Paper>
              ))}

              {/* Every other open anomaly kind: a correction field (fix
                  the value yourself), an "attach production extract"
                  action (generalized reference-file flow), and — for
                  incomplete relationships, which aren't the user's own
                  row to fix — an update/ignore decision like conflicts. */}
              {anomalies.filter((a) => a.status === 'open' && a.kind !== 'conflict').map((a) => (
                <Paper
                  key={a.id}
                  variant="outlined"
                  sx={{ p: 2, borderRadius: 2, borderColor: 'divider', bgcolor: 'action.hover' }}
                >
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                    {ANOMALY_KIND_LABELS[a.kind] || 'Issue'} — row {a.row}
                    {a.column ? <> , column "{a.column}"</> : null}
                    {a.kind === 'duplicate_row' && a.conflict_detail?.duplicate_of_row != null
                      ? ` (matches row ${a.conflict_detail.duplicate_of_row})`
                      : null}
                  </Typography>
                  {a.code != null && a.code !== '' && (
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1.5 }}>
                      Submitted value: "{a.code}"
                    </Typography>
                  )}

                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                    {a.kind !== 'incomplete_relationship' && a.kind !== 'duplicate_row' && (
                      correctionMode === 'excel' ? (
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          Fix this in the Excel file and resubmit it — see the "Open file" button above.
                        </Typography>
                      ) : correctionMode === 'chat' ? (
                        <>
                          <TextField
                            size="small"
                            placeholder="Corrected value"
                            value={correctionDrafts[a.id] || ''}
                            onChange={(e) => setCorrectionDrafts((prev) => ({ ...prev, [a.id]: e.target.value }))}
                            disabled={submittingCorrectionId === a.id}
                            sx={{ minWidth: 160 }}
                          />
                          <Button
                            size="small"
                            variant="contained"
                            disabled={submittingCorrectionId === a.id || !(correctionDrafts[a.id] || '').trim()}
                            onClick={() => submitCorrection(a.id)}
                          >
                            {submittingCorrectionId === a.id ? <CircularProgress size={16} /> : 'Submit correction'}
                          </Button>
                        </>
                      ) : null
                    )}
                    {a.kind !== 'duplicate_row' && (
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<AttachFileIcon fontSize="small" />}
                        disabled={isSubmittingReferenceFile}
                        onClick={() => {
                          setReferenceFileAnomalyId(a.id)
                          chatFileInputRef.current?.click()
                        }}
                      >
                        Attach production extract
                      </Button>
                    )}
                    {a.kind === 'incomplete_relationship' && (
                      <>
                        <Button
                          size="small"
                          variant="contained"
                          color="warning"
                          disabled={isSubmittingDecision}
                          onClick={() => submitDecision(a.id, 'update')}
                        >
                          Update existing
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          disabled={isSubmittingDecision}
                          onClick={() => submitDecision(a.id, 'ignore')}
                        >
                          Ignore
                        </Button>
                      </>
                    )}
                    {a.kind === 'duplicate_row' && (
                      <>
                        <Button
                          size="small"
                          variant="contained"
                          color="warning"
                          disabled={isSubmittingDecision}
                          onClick={() => submitDecision(a.id, 'update')}
                        >
                          Keep row
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          disabled={isSubmittingDecision}
                          onClick={() => submitDecision(a.id, 'ignore')}
                        >
                          Remove row
                        </Button>
                      </>
                    )}
                  </Stack>
                </Paper>
              ))}

              {/* Task just selected/launched — the welcome message is
                  still in flight, so the assistant shows as thinking
                  rather than the chat sitting empty. */}
              {welcomeLoading && <TypingIndicator label="Assistant is getting your task ready" />}

              {isChatLoading && <TypingIndicator label="AI is analysing your response" />}

              <div ref={chatEndRef} />
              </Box>
            </Box>

            {hasActiveStepWorkflow && !isChatLoading && (
              stepProgress.example_source === 'ai_unavailable' && !aiUnavailableDismissed ? (
                <Box sx={{
                  px: 1.5,
                  py: 0.8,
                  bgcolor: 'rgba(220,38,38,0.06)',
                  borderTop: '1px solid rgba(220,38,38,0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1
                }}>
                  <Typography variant="caption" sx={{ flex: 1, color: 'text.secondary' }}>
                    The AI couldn't generate an example for this step.
                  </Typography>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={regenerateExample}
                    disabled={regenerating}
                  >
                    {regenerating ? 'Trying…' : 'Try again'}
                  </Button>
                </Box>
              ) : canEditLastAnswer ? (
                <Box sx={{
                  px: 1.5,
                  py: 0.8,
                  bgcolor: 'rgba(79,70,229,0.06)',
                  borderTop: '1px solid rgba(79,70,229,0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1
                }}>
                  <Typography variant="caption" sx={{ flex: 1, color: 'text.secondary' }}>
                    Want to fix your last answer instead of retyping it?
                  </Typography>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={editLastAnswer}
                  >
                    Edit & resend
                  </Button>
                </Box>
              ) : null
            )}

            {pendingFile && (
              <Box sx={{
                px: 1.5,
                py: 0.8,
                bgcolor: 'rgba(79,70,229,0.06)',
                borderTop: '1px solid rgba(79,70,229,0.15)',
                display: 'flex',
                alignItems: 'center',
                gap: 1
              }}>
                {(isSubmittingReferenceFile || isSubmittingStepAttachment || isUploading)
                  ? <CircularProgress size={16} />
                  : <AttachFileIcon fontSize="small" color="primary" />}
                <Typography variant="caption" sx={{ flex: 1 }}>
                  {(isSubmittingReferenceFile || isSubmittingStepAttachment || isUploading)
                    ? `Analyzing ${pendingFile.name}…`
                    : canAttachMainFile
                    ? `${pendingFile.name} — ready to analyze`
                    : pendingFile.name}
                </Typography>
                <IconButton size="small" onClick={() => setPendingFile(null)} disabled={isSubmittingReferenceFile || isSubmittingStepAttachment || isUploading}>
                  <Typography variant="caption">×</Typography>
                </IconButton>
              </Box>
            )}

            <Box
              component="form"
              onSubmit={sendChatMessage}
              sx={{
                px: 2.5,
                pt: 1,
                pb: 2,
                // No divider: the composer fades out of the
                // conversation's gradient rather than sitting in its
                // own band.
                background: composerBackground,
                // Lines up with the centred conversation column.
                '& > .composer': {
                  width: '100%',
                  maxWidth: '100%',
                  mx: 'auto',
                },
              }}
            >
              <input
                ref={chatFileInputRef}
                type="file"
                style={{ display: 'none' }}
                accept={
                  awaitingAttachment
                    ? '.xlsx,.xls,.csv,.txt,.pdf,.docx,.doc,.png,.jpg,.jpeg,.webp'
                    : canAttachMainFile
                    ? '.xlsx,.xls,.csv'
                    : '.xlsx,.xls,.csv,.txt'
                }
                onChange={(e) => setPendingFile(e.target.files?.[0] || null)}
              />

              {/* One rounded field holding the text and its actions,
                  rather than three controls side by side. */}
              <Box
                className="composer"
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
                  inputRef={composerInputRef}
                  fullWidth
                  multiline
                  maxRows={8}
                  disabled={requestStatus === 'draft' || isCompleted || isChatLoading}
                  placeholder={
                    requestStatus === 'draft'
                      ? 'Attach or upload a configuration file to start...'
                      : isCompleted
                      ? 'Processing complete.'
                      : 'Ask anything...'
                  }
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      if (chatInput.trim()) sendChatMessage(e)
                    }
                  }}
                  sx={{ fontSize: 15, lineHeight: 1.5, p: 0 }}
                />

                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    mt: 0.5,
                  }}
                >
                  <Tooltip title={
                    awaitingAttachment
                      ? 'Attach a file or screenshot to help explain'
                      : canAttachMainFile
                      ? 'Attach the Excel file to analyze'
                      : 'Attach complementary file (e.g. production extract)'
                  }>
                    <span>
                      <IconButton
                        size="small"
                        onClick={() => chatFileInputRef.current?.click()}
                        disabled={isCompleted || isSubmittingReferenceFile || isSubmittingStepAttachment || isUploading}
                        sx={{ color: (awaitingAttachment || canAttachMainFile) ? '#4f46e5' : 'text.secondary' }}
                      >
                        <AttachFileIcon sx={{ fontSize: 18 }} />
                      </IconButton>
                    </span>
                  </Tooltip>

                  <IconButton
                    type="submit"
                    disabled={
                      (!chatInput.trim() && !pendingFile) ||
                      isChatLoading ||
                      isSubmittingReferenceFile ||
                      isSubmittingStepAttachment ||
                      isUploading ||
                      isCompleted ||
                      (requestStatus === 'draft' && !pendingFile)
                    }
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
</ResizableChatPanel>
        </Grid>
      </Grid>

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

      {/* ── Manual template selection: auto-match was inconclusive ──── */}
      <Dialog open={showTemplateSelection} onClose={cancelTemplateSelection} fullWidth maxWidth="sm">
        <DialogTitle>Which configuration task is this file for?</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
            {pendingUploadFile?.name ? `"${pendingUploadFile.name}" ` : 'This file '}
            didn't clearly match a task template's expected columns. Pick the right one below.
          </Typography>
          {availableTemplates.length === 0 ? (
            <Alert severity="warning">No task templates are available yet.</Alert>
          ) : (
            <Stack spacing={1}>
              {availableTemplates.map((tpl) => (
                <Paper
                  key={tpl.id}
                  variant="outlined"
                  onClick={() => !isUploadingWithTemplate && uploadWithTemplate(tpl.id)}
                  sx={{
                    p: 1.5,
                    borderRadius: 2,
                    cursor: isUploadingWithTemplate ? 'wait' : 'pointer',
                    '&:hover': { borderColor: 'primary.main', background: 'rgba(79,70,229,0.03)' },
                  }}
                >
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>{tpl.name}</Typography>
                  {tpl.description && (
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
                      {tpl.description}
                    </Typography>
                  )}
                  {tpl.expected_columns?.length > 0 && (
                    <Typography variant="caption" sx={{ color: 'text.disabled', display: 'block', mt: 0.5 }}>
                      Expected columns: {tpl.expected_columns.join(', ')}
                    </Typography>
                  )}
                </Paper>
              ))}
            </Stack>
          )}
          {isUploadingWithTemplate && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 2 }}>
              <CircularProgress size={16} />
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>Uploading and analysing...</Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={cancelTemplateSelection} disabled={isUploadingWithTemplate}>Cancel</Button>
        </DialogActions>
      </Dialog>
      </Box>
    </Box>
  )
}

export default ConfigurationIngest
