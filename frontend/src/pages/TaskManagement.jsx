import React, { useState, useEffect, useCallback } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import {
  Box,
  Typography,
  Button,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  CircularProgress,
  IconButton,
  Tooltip,
  Snackbar,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Menu,
  Avatar,
  Stack,
  Checkbox,
} from '@mui/material'
import AddIconImport from '@mui/icons-material/Add'
import UploadFileIconImport from '@mui/icons-material/UploadFile'
import DescriptionIconImport from '@mui/icons-material/Description'
import DeleteIconImport from '@mui/icons-material/Delete'
import DeleteOutlineIconImport from '@mui/icons-material/DeleteOutline'
import EditIconImport from '@mui/icons-material/Edit'
import MoreVertIconImport from '@mui/icons-material/MoreVert'
import CheckCircleOutlineIconImport from '@mui/icons-material/CheckCircleOutline'
import ExpandMoreIconImport from '@mui/icons-material/ExpandMore'
import ChevronRightIconImport from '@mui/icons-material/ChevronRight'
import RefreshIconImport from '@mui/icons-material/Refresh'
import WarningAmberIconImport from '@mui/icons-material/WarningAmber'
import { listTasks, createTask, updateTask, deleteTask } from '../services/taskService.js'
import PaginationBar from '../components/PaginationBar.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const AddIcon = AddIconImport?.default || AddIconImport
const UploadFileIcon = UploadFileIconImport?.default || UploadFileIconImport
const DescriptionIcon = DescriptionIconImport?.default || DescriptionIconImport
const DeleteIcon = DeleteIconImport?.default || DeleteIconImport
const DeleteOutlineIcon = DeleteOutlineIconImport?.default || DeleteOutlineIconImport
const EditIcon = EditIconImport?.default || EditIconImport
const MoreVertIcon = MoreVertIconImport?.default || MoreVertIconImport
const CheckCircleOutlineIcon = CheckCircleOutlineIconImport?.default || CheckCircleOutlineIconImport
const ExpandMoreIcon = ExpandMoreIconImport?.default || ExpandMoreIconImport
const ChevronRightIcon = ChevronRightIconImport?.default || ChevronRightIconImport
const RefreshIcon = RefreshIconImport?.default || RefreshIconImport
const WarningAmberIcon = WarningAmberIconImport?.default || WarningAmberIconImport

const REQUEST_PAGE_SIZE_OPTIONS = [5, 10, 15, 20]

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const GRADIENT = 'linear-gradient(90deg, #6b1f8a 0%, #a02bbf 50%, #ff4ea1 100%)'

// Chip colors, echoing the board-style pill used to badge each
// section (à la "To Do" / "In Progress" / "Done").
const TYPE_STYLES = {
  report_analyses: { bg: 'rgba(160,43,191,0.14)', text: '#a02bbf' },
  skill_engine: { bg: 'rgba(41,121,255,0.14)', text: '#2979ff' },
}

const PRIORITY_ORDER = ['high', 'medium', 'low']

const initialsOf = (fullName) =>
  fullName
    ? fullName.split(' ').filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join('')
    : '?'

const profileUrlOf = (owner) =>
  owner?.profile_picture ? `${API_BASE}/uploads/profiles/${owner.profile_picture}` : undefined

const dateOf = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

const TaskManagement = ({ searchTerm = '', setSearchTerm = () => {} }) => {
  const { t } = useTranslation('pages')
  const { user } = useAuth()
  // Same dashboard for everyone; only creating a task template is
  // restricted. The backend enforces this regardless — this only
  // decides whether the button is shown as usable, so a member is
  // never invited to try an action that will just 403.
  const isAdmin = user?.role === 'admin'

  const TASK_TYPES = [
    {
      value: 'report_analyses',
      label: t('taskManagement.taskType.reportAnalyses'),
      description: t('taskManagement.taskType.reportAnalysesDesc'),
    },
    {
      value: 'skill_engine',
      label: t('taskManagement.taskType.skillEngine'),
      description: t('taskManagement.taskType.skillEngineDesc'),
    },
  ]

  const getCategoryMeta = (value) => {
    const type = TASK_TYPES.find((item) => item.value === value)
    return {
      label: type ? type.label : t('taskManagement.taskType.other'),
      ...(TYPE_STYLES[value] || { bg: 'rgba(148,163,184,0.16)', text: '#64748b' }),
    }
  }

  // Identical to the Dashboard's STATUS_META (DashboardHome.jsx) so a
  // status reads the same wherever it appears in the app.
  const STATUS_META = {
    draft: { label: t('taskManagement.status.draft'), color: '#94a3b8' },
    file_submitted: { label: t('taskManagement.status.fileSubmitted'), color: '#f59e0b' },
    analysis_in_progress: { label: t('taskManagement.status.analysisInProgress'), color: '#3b82f6' },
    waiting_for_support_response: { label: t('taskManagement.status.waitingForSupportResponse'), color: '#eab308' },
    additional_information_required: {
      label: t('taskManagement.status.additionalInformationRequired'),
      color: '#ef4444',
    },
    data_corrected: { label: t('taskManagement.status.dataCorrected'), color: '#8b5cf6' },
    data_validated: { label: t('taskManagement.status.dataValidated'), color: '#14b8a6' },
    script_generated: { label: t('taskManagement.status.scriptGenerated'), color: '#0ea5e9' },
    processing_completed: { label: t('taskManagement.status.processingCompleted'), color: '#16a34a' },
    escalation_required: { label: t('taskManagement.status.escalationRequired'), color: '#dc2626' },
  }
  const statusOf = (status) =>
    STATUS_META[status] || { label: status || t('taskManagement.status.unknown'), color: '#94a3b8' }

  // Urgency, hottest first — identical to the Dashboard so a priority
  // reads the same wherever it appears.
  const PRIORITY_META = {
    high: { label: t('taskManagement.priority.high'), color: '#dc2626' },
    medium: { label: t('taskManagement.priority.medium'), color: '#d97706' },
    low: { label: t('taskManagement.priority.low'), color: '#0284c7' },
  }
  const priorityOf = (priority) =>
    PRIORITY_META[String(priority || 'medium').toLowerCase()] || PRIORITY_META.medium

  const [activeTab, setActiveTab] = useState('requests') // 'requests' | 'templates'

  // Shared toast for both tabs.
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' })
  const handleSnackbarClose = () => setSnackbar((prev) => ({ ...prev, open: false }))

  // ════════════════════════════════════════════════════════════════
  // REQUESTS BOARD — grouped by workflow status (To Do / In Progress /
  // Done), with priority, owner and type, mirroring the Dashboard.
  // ════════════════════════════════════════════════════════════════
  const [requestItems, setRequestItems] = useState([])
  const [isLoadingRequests, setIsLoadingRequests] = useState(true)
  const [requestError, setRequestError] = useState('')

  const loadRequests = useCallback(async () => {
    setIsLoadingRequests(true)
    setRequestError('')
    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetch(`${API_BASE}/api/requests/`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!resp.ok) {
        throw new Error(
          resp.status === 401
            ? t('taskManagement.errors.sessionExpired')
            : t('taskManagement.errors.loadRequestsFailed', { status: resp.status })
        )
      }
      const data = await resp.json()
      setRequestItems(data.items || [])
    } catch (err) {
      setRequestError(err.message || t('taskManagement.errors.loadRequestsGeneric'))
    } finally {
      setIsLoadingRequests(false)
    }
  }, [])

  useEffect(() => {
    loadRequests()
  }, [loadRequests])

  const filteredRequestItems = requestItems.filter((item) => {
    if (!searchTerm) return true
    const term = searchTerm.toLowerCase()
    const priority = priorityOf(item.priority)
    const status = statusOf(item.status)
    return (
      (item.task_name && item.task_name.toLowerCase().includes(term)) ||
      (item.task_description && item.task_description.toLowerCase().includes(term)) ||
      (item.owner?.full_name && item.owner.full_name.toLowerCase().includes(term)) ||
      priority.label.toLowerCase().includes(term) ||
      status.label.toLowerCase().includes(term)
    )
  })

  // ─── Pagination ──────────────────────────────────────────────────
  const [requestsPage, setRequestsPage] = useState(1)
  const [requestsPageSize, setRequestsPageSize] = useState(10)
  const requestsPageCount = Math.max(1, Math.ceil(filteredRequestItems.length / requestsPageSize))
  const pagedRequestItems = filteredRequestItems.slice(
    (requestsPage - 1) * requestsPageSize,
    requestsPage * requestsPageSize
  )

  useEffect(() => {
    setRequestsPage((prev) => Math.min(prev, requestsPageCount))
  }, [requestsPageCount])

  useEffect(() => {
    setRequestsPage(1)
  }, [searchTerm])

  const changeRequestsPageSize = (size) => {
    setRequestsPageSize(size)
    setRequestsPage(1)
  }

  // ─── Selection ─────────────────────────────────────────────────
  const [selectedIds, setSelectedIds] = useState([])
  const pageIds = pagedRequestItems.map((item) => item.id)
  const allOnPageSelected = pageIds.length > 0 && pageIds.every((id) => selectedIds.includes(id))
  const someOnPageSelected = pageIds.some((id) => selectedIds.includes(id))

  const toggleOneSelected = (id) =>
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))

  const toggleAllOnPage = () =>
    setSelectedIds((prev) =>
      allOnPageSelected ? prev.filter((id) => !pageIds.includes(id)) : Array.from(new Set([...prev, ...pageIds]))
    )

  useEffect(() => {
    setSelectedIds((prev) => prev.filter((id) => requestItems.some((item) => item.id === id)))
  }, [requestItems])

  // ─── Delete ────────────────────────────────────────────────────
  const [pendingDelete, setPendingDelete] = useState(null) // array of items
  const [isDeletingRequests, setIsDeletingRequests] = useState(false)

  const confirmDeleteRequests = async () => {
    const targets = pendingDelete || []
    if (targets.length === 0) return
    setIsDeletingRequests(true)
    try {
      const token = localStorage.getItem('brainopx_token')
      const headers = { Authorization: `Bearer ${token}` }
      let message

      if (targets.length === 1) {
        const resp = await fetch(`${API_BASE}/api/requests/${targets[0].id}`, { method: 'DELETE', headers })
        if (!resp.ok) {
          const body = await resp.json().catch(() => ({}))
          throw new Error(
            body.detail ||
              (resp.status === 403
                ? t('taskManagement.errors.deleteOwnOnly')
                : t('taskManagement.errors.deleteRequestFailed', { status: resp.status }))
          )
        }
        message = { open: true, message: t('taskManagement.messages.requestDeleted'), severity: 'success' }
      } else {
        const resp = await fetch(`${API_BASE}/api/requests/bulk-delete`, {
          method: 'POST',
          headers: { ...headers, 'Content-Type': 'application/json' },
          body: JSON.stringify({ ids: targets.map((item) => item.id) }),
        })
        if (!resp.ok) {
          const body = await resp.json().catch(() => ({}))
          throw new Error(body.detail || t('taskManagement.errors.deleteSelectedFailed', { status: resp.status }))
        }
        const result = await resp.json()
        const refused = (result.forbidden || []).length
        message = refused
          ? {
              open: true,
              severity: 'warning',
              message: t('taskManagement.messages.bulkDeletePartial', {
                deleted: result.deleted_count,
                refused,
              }),
            }
          : {
              open: true,
              severity: 'success',
              message: t('taskManagement.messages.bulkDeleteSuccess', { count: result.deleted_count }),
            }
      }

      setPendingDelete(null)
      setSelectedIds([])
      setSnackbar(message)
      await loadRequests()
    } catch (err) {
      setSnackbar({ open: true, message: err.message || t('taskManagement.errors.deleteGeneric'), severity: 'error' })
    } finally {
      setIsDeletingRequests(false)
    }
  }

  // ─── Priority ──────────────────────────────────────────────────
  const [priorityMenu, setPriorityMenu] = useState(null) // { anchorEl, item }

  const changePriority = async (item, priority) => {
    setPriorityMenu(null)
    if (priority === item.priority) return
    setRequestItems((prev) => prev.map((row) => (row.id === item.id ? { ...row, priority } : row)))
    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetch(`${API_BASE}/api/requests/${item.id}/priority`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ priority }),
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(
          body.detail ||
            (resp.status === 403
              ? t('taskManagement.errors.changeOwnOnly')
              : t('taskManagement.errors.changePriorityFailed', { status: resp.status }))
        )
      }
    } catch (err) {
      setRequestItems((prev) => prev.map((row) => (row.id === item.id ? { ...row, priority: item.priority } : row)))
      setSnackbar({ open: true, message: err.message || t('taskManagement.errors.changePriorityGeneric'), severity: 'error' })
    }
  }

  // ─── Mark complete ─────────────────────────────────────────────
  const markComplete = async (item) => {
    setRowMenu(null)
    if (item.status === 'processing_completed') return
    const previousStatus = item.status
    setRequestItems((prev) =>
      prev.map((row) => (row.id === item.id ? { ...row, status: 'processing_completed' } : row))
    )
    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetch(`${API_BASE}/api/requests/${item.id}/complete`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(body.detail || t('taskManagement.errors.markCompleteFailed', { status: resp.status }))
      }
      setSnackbar({ open: true, message: t('taskManagement.messages.taskMarkedCompleted'), severity: 'success' })
      // Reload so bucket/progress (which the Dashboard's Graph Analysis
      // tab keys off) come back in sync with the server.
      await loadRequests()
    } catch (err) {
      setRequestItems((prev) =>
        prev.map((row) => (row.id === item.id ? { ...row, status: previousStatus } : row))
      )
      setSnackbar({ open: true, message: err.message || t('taskManagement.errors.markCompleteGeneric'), severity: 'error' })
    }
  }

  // ─── Row "..." menu ────────────────────────────────────────────
  const [rowMenu, setRowMenu] = useState(null) // { anchorEl, item }

  // ════════════════════════════════════════════════════════════════
  // TASK TEMPLATES — the admin-defined Excel/rules definitions, grouped
  // by type, unchanged from before but shown as a secondary tab.
  // ════════════════════════════════════════════════════════════════
  const [tasks, setTasks] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogMode, setDialogMode] = useState('create') // 'create' or 'edit'
  const [editingTaskId, setEditingTaskId] = useState(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('report_analyses')
  const [file, setFile] = useState(null)
  const [submitError, setSubmitError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [taskToDelete, setTaskToDelete] = useState(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const filteredTasks = tasks.filter((task) => {
    const searchLower = searchTerm.toLowerCase()
    return (
      !searchTerm ||
      task.name.toLowerCase().includes(searchLower) ||
      (task.description && task.description.toLowerCase().includes(searchLower)) ||
      (task.category && task.category.toLowerCase().includes(searchLower))
    )
  })

  const [collapsedTemplateGroups, setCollapsedTemplateGroups] = useState({})
  const toggleTemplateGroup = (value) =>
    setCollapsedTemplateGroups((prev) => ({ ...prev, [value]: !prev[value] }))

  const groupedTasks = TASK_TYPES.map((type) => ({
    ...type,
    items: filteredTasks.filter((task) => (task.category || 'report_analyses') === type.value),
  }))

  const [templateActionMenu, setTemplateActionMenu] = useState({ anchorEl: null, task: null })
  const openTemplateActionMenu = (event, task) => setTemplateActionMenu({ anchorEl: event.currentTarget, task })
  const closeTemplateActionMenu = () => setTemplateActionMenu({ anchorEl: null, task: null })

  const fetchTasks = useCallback(async () => {
    setIsLoading(true)
    setLoadError('')
    try {
      const data = await listTasks()
      setTasks(data)
    } catch (err) {
      setLoadError(err?.message || t('taskManagement.errors.loadTasksFailed'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTasks()
  }, [fetchTasks])

  const resetForm = () => {
    setName('')
    setDescription('')
    setCategory('report_analyses')
    setFile(null)
    setSubmitError('')
    setEditingTaskId(null)
  }

  const handleOpenCreateDialog = () => {
    resetForm()
    setDialogMode('create')
    setDialogOpen(true)
  }

  const handleOpenEditDialog = (task) => {
    setName(task.name)
    setDescription(task.description || '')
    setCategory(task.category || 'report_analyses')
    setFile(null)
    setEditingTaskId(task.id)
    setDialogMode('edit')
    setSubmitError('')
    setDialogOpen(true)
  }

  const handleCloseDialog = () => {
    if (isSubmitting) return
    setDialogOpen(false)
    resetForm()
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSubmitError('')

    if (!name.trim()) {
      setSubmitError(t('taskManagement.errors.taskNameRequired'))
      return
    }

    const fileExt = file ? file.name.toLowerCase().split('.').pop() : ''
    const isReportAnalyses = category === 'report_analyses'

    if (dialogMode === 'create' && !file) {
      setSubmitError(
        isReportAnalyses
          ? t('taskManagement.errors.selectExcelFile')
          : t('taskManagement.errors.selectRulesFile')
      )
      return
    }

    if (file) {
      const allowedExts = isReportAnalyses ? ['xlsx'] : ['txt', 'pdf', 'doc', 'docx']
      if (!allowedExts.includes(fileExt)) {
        setSubmitError(
          isReportAnalyses
            ? t('taskManagement.errors.onlyXlsxSupported')
            : t('taskManagement.errors.onlyRulesFormatsSupported')
        )
        return
      }
    }

    setIsSubmitting(true)
    try {
      const taskData = { name, description, category, file }
      if (dialogMode === 'create') {
        await createTask(taskData)
        setSnackbar({ open: true, message: t('taskManagement.messages.taskCreated'), severity: 'success' })
      } else {
        await updateTask(editingTaskId, taskData)
        setSnackbar({ open: true, message: t('taskManagement.messages.taskUpdated'), severity: 'success' })
      }
      setDialogOpen(false)
      resetForm()
      fetchTasks()
    } catch (err) {
      setSubmitError(err?.message || t('taskManagement.errors.saveTaskFailed'))
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDeleteClick = (task) => {
    setTaskToDelete(task)
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!taskToDelete) return
    setIsDeleting(true)
    try {
      await deleteTask(taskToDelete.id)
      setSnackbar({
        open: true,
        message: t('taskManagement.messages.taskDeleted', { name: taskToDelete.name }),
        severity: 'success',
      })
      setDeleteDialogOpen(false)
      setTaskToDelete(null)
      await fetchTasks()
    } catch (err) {
      setSnackbar({
        open: true,
        message: err?.message || t('taskManagement.errors.deleteTaskFailed'),
        severity: 'error',
      })
    } finally {
      setIsDeleting(false)
    }
  }

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false)
    setTaskToDelete(null)
  }

  const getFileAccept = (type) => (type === 'skill_engine' ? '.txt,.pdf,.doc,.docx' : '.xlsx')

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ width: '100%' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
          <Box>
            <Typography variant="h4" sx={{ fontWeight: 700, mb: 1, color: 'text.primary' }}>
              {t('taskManagement.title')}
            </Typography>
            <Typography variant="body1" sx={{ color: 'text.secondary' }}>
              {activeTab === 'requests'
                ? t('taskManagement.subtitle.requests')
                : t('taskManagement.subtitle.templates')}
            </Typography>
          </Box>
          {activeTab === 'requests' ? (
            <Tooltip title={t('taskManagement.refresh')}>
              <span>
                <IconButton onClick={loadRequests} disabled={isLoadingRequests}>
                  <RefreshIcon />
                </IconButton>
              </span>
            </Tooltip>
          ) : (
            <Tooltip title={isAdmin ? '' : t('taskManagement.onlyAdminCreate')}>
              <span>
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  onClick={handleOpenCreateDialog}
                  disabled={!isAdmin}
                  sx={{ borderRadius: 3, textTransform: 'none', px: 3, background: GRADIENT }}
                >
                  {t('taskManagement.newTask')}
                </Button>
              </span>
            </Tooltip>
          )}
        </Box>

        {/* Tab toggle */}
        <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
          {[
            { value: 'requests', label: t('taskManagement.tabs.requestsBoard') },
            { value: 'templates', label: t('taskManagement.tabs.taskTemplates') },
          ].map((tab) => (
            <Button
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              variant={activeTab === tab.value ? 'contained' : 'outlined'}
              sx={{
                borderRadius: 3,
                textTransform: 'none',
                px: 2.5,
                ...(activeTab === tab.value
                  ? { background: GRADIENT }
                  : { borderColor: (theme) => (theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.2)' : '#e5e7eb'), color: 'text.secondary' }),
              }}
            >
              {tab.label}
            </Button>
          ))}
        </Box>

        {/* ══════════════════════════ REQUESTS BOARD ══════════════════════════ */}
        {activeTab === 'requests' && (
          <Box>
            {requestError && <Alert severity="error" sx={{ mb: 3 }}>{requestError}</Alert>}

            {isLoadingRequests ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
                <CircularProgress />
              </Box>
            ) : filteredRequestItems.length === 0 ? (
              <Paper
                sx={{
                  p: 6,
                  textAlign: 'center',
                  background: (theme) => (theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : '#ffffff'),
                  border: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
                  borderRadius: 3,
                }}
              >
                <DescriptionIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                <Typography variant="h6" sx={{ color: 'text.primary', mb: 1 }}>
                  {searchTerm ? t('taskManagement.emptyState.noRequestsMatch') : t('taskManagement.emptyState.noRequestsYet')}
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  {searchTerm
                    ? t('taskManagement.emptyState.tryAdjusting', { term: searchTerm })
                    : t('taskManagement.emptyState.requestsAppearHere')}
                </Typography>
              </Paper>
            ) : (
              <Paper
                sx={{
                  borderRadius: 3,
                  overflow: 'hidden',
                  background: (theme) => (theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : '#ffffff'),
                  border: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
                }}
              >
                {selectedIds.length > 0 && (
                  <Stack
                    direction="row"
                    alignItems="center"
                    justifyContent="space-between"
                    sx={{
                      px: 2,
                      py: 1.25,
                      bgcolor: 'rgba(79,70,229,0.06)',
                      borderBottom: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
                    }}
                  >
                    <Typography variant="body2" sx={{ fontWeight: 700 }}>
                      {t('taskManagement.selection.selectedCount', { count: selectedIds.length })}
                    </Typography>
                    <Stack direction="row" spacing={1}>
                      <Button size="small" onClick={() => setSelectedIds([])} sx={{ textTransform: 'none' }}>
                        {t('taskManagement.selection.clear')}
                      </Button>
                      <Button
                        size="small"
                        variant="contained"
                        color="error"
                        startIcon={<DeleteOutlineIcon />}
                        onClick={() => setPendingDelete(requestItems.filter((i) => selectedIds.includes(i.id)))}
                        sx={{ textTransform: 'none', borderRadius: 2 }}
                      >
                        {t('taskManagement.selection.deleteSelected')}
                      </Button>
                    </Stack>
                  </Stack>
                )}

                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow
                        sx={{
                          '& th': {
                            fontWeight: 700,
                            color: 'text.secondary',
                            fontSize: 12,
                            textTransform: 'uppercase',
                            letterSpacing: 0.4,
                            borderBottom: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
                            py: 1.5,
                          },
                        }}
                      >
                        <TableCell padding="checkbox">
                          <Checkbox
                            size="small"
                            disabled={pageIds.length === 0}
                            checked={allOnPageSelected}
                            indeterminate={someOnPageSelected && !allOnPageSelected}
                            onChange={toggleAllOnPage}
                            inputProps={{ 'aria-label': t('taskManagement.table.selectAllAria') }}
                          />
                        </TableCell>
                        <TableCell>{t('taskManagement.table.columnTaskName')}</TableCell>
                        <TableCell>{t('taskManagement.table.columnProject')}</TableCell>
                        <TableCell>{t('taskManagement.table.columnAssignee')}</TableCell>
                        <TableCell>{t('taskManagement.table.columnPriority')}</TableCell>
                        <TableCell>{t('taskManagement.table.columnStatus')}</TableCell>
                        <TableCell>{t('taskManagement.table.columnDate')}</TableCell>
                        <TableCell align="right" sx={{ width: 56 }} />
                      </TableRow>
                    </TableHead>

                    <TableBody>
                      {pagedRequestItems.map((item) => {
                        const categoryMeta = getCategoryMeta(item.task_category)
                        const priority = priorityOf(item.priority)
                        const status = statusOf(item.status)
                        return (
                          <TableRow
                            key={item.id}
                            hover
                            selected={selectedIds.includes(item.id)}
                            sx={{
                              '& td': {
                                borderBottom: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : '#f1f3f7'}`,
                                py: 1.25,
                              },
                            }}
                          >
                            <TableCell padding="checkbox">
                              <Checkbox
                                size="small"
                                checked={selectedIds.includes(item.id)}
                                onChange={() => toggleOneSelected(item.id)}
                                inputProps={{ 'aria-label': t('taskManagement.table.selectRowAria', { name: item.task_name }) }}
                              />
                            </TableCell>

                            <TableCell>
                              <Typography
                                variant="body2"
                                sx={{ fontFamily: "'Nunito', 'Inter', 'Roboto', sans-serif", fontWeight: 700, color: 'text.primary' }}
                              >
                                {item.task_name}
                              </Typography>
                            </TableCell>

                            <TableCell>
                              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                                {categoryMeta.label}
                              </Typography>
                            </TableCell>

                            <TableCell>
                              <Stack direction="row" alignItems="center" spacing={1}>
                                <Avatar
                                  src={profileUrlOf(item.owner)}
                                  alt={item.owner?.full_name || t('taskManagement.table.unassigned')}
                                  sx={{
                                    width: 26,
                                    height: 26,
                                    fontSize: 11,
                                    fontWeight: 700,
                                    bgcolor: item.owner ? 'primary.main' : 'action.disabledBackground',
                                    color: item.owner ? '#fff' : 'text.disabled',
                                  }}
                                >
                                  {initialsOf(item.owner?.full_name)}
                                </Avatar>
                                <Typography variant="body2" sx={{ whiteSpace: 'nowrap' }}>
                                  {item.owner?.full_name || t('taskManagement.table.unassigned')}
                                </Typography>
                              </Stack>
                            </TableCell>

                            <TableCell>
                              <Tooltip title={t('taskManagement.table.clickToChangePriority')}>
                                <Typography
                                  variant="body2"
                                  onClick={(event) => setPriorityMenu({ anchorEl: event.currentTarget, item })}
                                  sx={{
                                    display: 'inline-block',
                                    fontFamily: "'Nunito', 'Inter', 'Roboto', sans-serif",
                                    fontWeight: 700,
                                    cursor: 'pointer',
                                    color: priority.color,
                                  }}
                                >
                                  {priority.label}
                                </Typography>
                              </Tooltip>
                            </TableCell>

                            <TableCell>
                              <Chip
                                size="small"
                                label={status.label}
                                sx={{ fontWeight: 700, fontSize: 11.5, color: status.color, bgcolor: `${status.color}1F`, border: 'none' }}
                              />
                            </TableCell>

                            <TableCell>
                              <Typography variant="body2" sx={{ color: 'text.secondary', whiteSpace: 'nowrap' }}>
                                {dateOf(item.updated_at || item.created_at)}
                              </Typography>
                            </TableCell>

                            <TableCell align="right">
                              <IconButton
                                size="small"
                                onClick={(event) => setRowMenu({ anchorEl: event.currentTarget, item })}
                                sx={{ color: 'text.disabled' }}
                              >
                                <MoreVertIcon sx={{ fontSize: 19 }} />
                              </IconButton>
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </TableContainer>

                <PaginationBar
                  page={requestsPage}
                  pageSize={requestsPageSize}
                  totalRecords={filteredRequestItems.length}
                  onPageChange={setRequestsPage}
                  onPageSizeChange={changeRequestsPageSize}
                  pageSizeOptions={REQUEST_PAGE_SIZE_OPTIONS}
                  recordLabel={t('taskManagement.table.recordLabel')}
                />
              </Paper>
            )}

            {/* Row "..." menu */}
            <Menu
              anchorEl={rowMenu?.anchorEl || null}
              open={Boolean(rowMenu)}
              onClose={() => setRowMenu(null)}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
              transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            >
              {rowMenu?.item && rowMenu.item.status !== 'processing_completed' && (
                <MenuItem
                  disabled={rowMenu.item.progress < 100}
                  onClick={() => markComplete(rowMenu.item)}
                >
                  <CheckCircleOutlineIcon fontSize="small" sx={{ mr: 1.5 }} />
                  {rowMenu.item.progress < 100
                    ? t('taskManagement.menu.finishStepsFirst')
                    : t('taskManagement.menu.markCompleted')}
                </MenuItem>
              )}
              <MenuItem
                onClick={() => {
                  setPendingDelete([rowMenu.item])
                  setRowMenu(null)
                }}
                sx={{ color: 'error.main' }}
              >
                <DeleteIcon fontSize="small" sx={{ mr: 1.5 }} />
                {t('taskManagement.menu.delete')}
              </MenuItem>
            </Menu>

            {/* Priority menu */}
            <Menu
              anchorEl={priorityMenu?.anchorEl || null}
              open={Boolean(priorityMenu)}
              onClose={() => setPriorityMenu(null)}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
              transformOrigin={{ vertical: 'top', horizontal: 'left' }}
            >
              {PRIORITY_ORDER.map((key) => {
                const meta = PRIORITY_META[key]
                const current = String(priorityMenu?.item?.priority || 'medium').toLowerCase()
                return (
                  <MenuItem
                    key={key}
                    selected={current === key}
                    onClick={() => changePriority(priorityMenu.item, key)}
                    sx={{ fontSize: 13, gap: 1.25, minWidth: 150 }}
                  >
                    <Box sx={{ width: 9, height: 9, borderRadius: '50%', bgcolor: meta.color, flexShrink: 0 }} />
                    {meta.label}
                  </MenuItem>
                )
              })}
            </Menu>

            {/* Confirm deletion */}
            <Dialog
              open={Boolean(pendingDelete && pendingDelete.length)}
              onClose={() => !isDeletingRequests && setPendingDelete(null)}
              maxWidth="sm"
              fullWidth
            >
              <DialogTitle sx={{ fontWeight: 700 }}>
                {pendingDelete?.length > 1
                  ? t('taskManagement.dialog.deleteRequestsTitle', { count: pendingDelete.length })
                  : t('taskManagement.dialog.deleteRequestTitle')}
              </DialogTitle>
              <DialogContent>
                {pendingDelete?.length === 1 ? (
                  <Typography variant="body2" sx={{ mb: 1.5 }}>
                    <Box component="span" sx={{ fontWeight: 700 }}>
                      {pendingDelete[0].task_name}
                    </Box>
                    {pendingDelete[0].uploaded_filename ? ` (${pendingDelete[0].uploaded_filename})` : ''}{' '}
                    {t('taskManagement.dialog.willBeRemoved')}
                  </Typography>
                ) : (
                  <Box sx={{ mb: 1.5, maxHeight: 168, overflowY: 'auto', pl: 2 }}>
                    {pendingDelete?.map((item) => (
                      <Typography key={item.id} variant="body2" sx={{ fontWeight: 600, listStyle: 'disc', display: 'list-item' }}>
                        {item.task_name}
                      </Typography>
                    ))}
                  </Box>
                )}
                <Alert severity="warning" sx={{ borderRadius: 2 }}>
                  {t('taskManagement.dialog.deleteRequestWarning')}
                </Alert>
              </DialogContent>
              <DialogActions sx={{ px: 3, pb: 3 }}>
                <Button onClick={() => setPendingDelete(null)} disabled={isDeletingRequests} sx={{ textTransform: 'none' }}>
                  {t('taskManagement.dialog.cancel')}
                </Button>
                <Button
                  onClick={confirmDeleteRequests}
                  variant="contained"
                  color="error"
                  disabled={isDeletingRequests}
                  startIcon={isDeletingRequests ? <CircularProgress size={16} /> : <DeleteIcon />}
                  sx={{ textTransform: 'none' }}
                >
                  {isDeletingRequests
                    ? t('taskManagement.dialog.deleting')
                    : pendingDelete?.length > 1
                    ? t('taskManagement.dialog.deleteCount', { count: pendingDelete.length })
                    : t('taskManagement.menu.delete')}
                </Button>
              </DialogActions>
            </Dialog>
          </Box>
        )}

        {/* ══════════════════════════ TASK TEMPLATES ══════════════════════════ */}
        {activeTab === 'templates' && (
          <Box>
            {loadError && <Alert severity="error" sx={{ mb: 3 }}>{loadError}</Alert>}

            {isLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
                <CircularProgress />
              </Box>
            ) : filteredTasks.length === 0 ? (
              <Paper
                sx={{
                  p: 6,
                  textAlign: 'center',
                  background: (theme) => (theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : '#ffffff'),
                  border: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
                  borderRadius: 3,
                }}
              >
                <DescriptionIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                <Typography variant="h6" sx={{ color: 'text.primary', mb: 1 }}>
                  {searchTerm ? t('taskManagement.emptyState.noTasksMatch') : t('taskManagement.emptyState.noTasksYet')}
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  {searchTerm
                    ? t('taskManagement.emptyState.tryAdjusting', { term: searchTerm })
                    : isAdmin
                    ? t('taskManagement.emptyState.clickNewTask')
                    : t('taskManagement.emptyState.adminHasNotDefined')}
                </Typography>
              </Paper>
            ) : (
              <Box>
                <Typography variant="body2" sx={{ color: 'text.secondary', px: 1, mb: 2 }}>
                  {searchTerm
                    ? t('taskManagement.tasksFoundSearch', { count: filteredTasks.length, term: searchTerm })
                    : t('taskManagement.tasksFound', { count: filteredTasks.length })}
                </Typography>

                {groupedTasks.map((group, groupIndex) => {
                  const style = TYPE_STYLES[group.value] || TYPE_STYLES.report_analyses
                  const isCollapsed = !!collapsedTemplateGroups[group.value]
                  return (
                    <Box key={group.value} sx={{ mt: groupIndex === 0 ? 0 : 3 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5, px: 0.5 }}>
                        <IconButton size="small" onClick={() => toggleTemplateGroup(group.value)} sx={{ color: 'text.secondary' }}>
                          {isCollapsed ? <ChevronRightIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                        </IconButton>
                        <Chip
                          label={group.label}
                          size="small"
                          sx={{ bgcolor: style.bg, color: style.text, fontWeight: 700, fontSize: '0.75rem' }}
                        />
                        <Chip
                          label={group.items.length}
                          size="small"
                          sx={{
                            bgcolor: (theme) => (theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : '#f1f1f4'),
                            color: 'text.secondary',
                            fontWeight: 700,
                            minWidth: 28,
                          }}
                        />
                      </Box>

                      {!isCollapsed &&
                        (group.items.length === 0 ? (
                          <Paper
                            sx={{
                              p: 3,
                              textAlign: 'center',
                              border: (theme) => `1px dashed ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.15)' : '#e5e7eb'}`,
                              borderRadius: 3,
                              boxShadow: 'none',
                              background: 'transparent',
                            }}
                          >
                            <Typography variant="body2" sx={{ color: 'text.disabled' }}>
                              {searchTerm
                                ? t('taskManagement.emptyState.noGroupTasksSearch', { group: group.label.toLowerCase() })
                                : t('taskManagement.emptyState.noGroupTasksYet', { group: group.label.toLowerCase() })}
                            </Typography>
                          </Paper>
                        ) : (
                          <Paper
                            sx={{
                              borderRadius: 3,
                              overflow: 'hidden',
                              border: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
                              boxShadow: 'none',
                            }}
                          >
                            <TableContainer
                              sx={{
                                '& .MuiTableHead-root .MuiTableCell-root': {
                                  fontWeight: 700,
                                  color: 'text.secondary',
                                  fontSize: '0.75rem',
                                  textTransform: 'uppercase',
                                  letterSpacing: '0.5px',
                                  borderBottom: (theme) => `2px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
                                  bgcolor: (theme) => (theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : '#f8fafc'),
                                },
                                '& .MuiTableBody-root .MuiTableRow-root:hover': {
                                  bgcolor: (theme) => (theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : '#f8fafc'),
                                },
                                '& .MuiTableBody-root .MuiTableCell-root': {
                                  borderBottom: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : '#f0f0f0'}`,
                                  py: 1.5,
                                },
                              }}
                            >
                              <Table sx={{ minWidth: 700 }}>
                                <TableHead>
                                  <TableRow>
                                    <TableCell sx={{ width: 220 }}>{t('taskManagement.table.columnTaskName')}</TableCell>
                                    <TableCell>{t('taskManagement.table.columnDescription')}</TableCell>
                                    <TableCell sx={{ width: 220 }}>{t('taskManagement.table.columnTemplateRules')}</TableCell>
                                    <TableCell sx={{ width: 120 }}>{t('taskManagement.table.columnCreated')}</TableCell>
                                    <TableCell sx={{ width: 70, textAlign: 'center' }}>{t('taskManagement.table.columnActions')}</TableCell>
                                  </TableRow>
                                </TableHead>
                                <TableBody>
                                  {group.items.map((task) => (
                                    <TableRow key={task.id} hover>
                                      <TableCell>
                                        <Stack direction="row" alignItems="center" spacing={0.75}>
                                          <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>
                                            {task.name}
                                          </Typography>
                                          {task.validation_report?.issue_count > 0 && (
                                            <Tooltip
                                              title={
                                                <Box>
                                                  <Typography variant="caption" sx={{ display: 'block', mb: 0.5 }}>
                                                    {t('taskManagement.validation.tooltipIntro')}
                                                  </Typography>
                                                  {task.validation_report.issues.map((issue) => (
                                                    <Typography key={issue.step} variant="caption" sx={{ display: 'block' }}>
                                                      • {issue.rule_name}
                                                    </Typography>
                                                  ))}
                                                </Box>
                                              }
                                            >
                                              <Chip
                                                size="small"
                                                icon={<WarningAmberIcon sx={{ fontSize: '14px !important' }} />}
                                                label={t('taskManagement.validation.needsReview', {
                                                  count: task.validation_report.issue_count,
                                                })}
                                                sx={{
                                                  height: 20,
                                                  fontSize: 11,
                                                  fontWeight: 700,
                                                  color: '#b45309',
                                                  bgcolor: 'rgba(217,119,6,0.14)',
                                                  '& .MuiChip-icon': { color: '#b45309' },
                                                }}
                                              />
                                            </Tooltip>
                                          )}
                                        </Stack>
                                      </TableCell>

                                      <TableCell>
                                        <Typography
                                          variant="body2"
                                          sx={{
                                            color: 'text.secondary',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            display: '-webkit-box',
                                            WebkitLineClamp: 2,
                                            WebkitBoxOrient: 'vertical',
                                          }}
                                        >
                                          {task.description || (
                                            <Box component="span" sx={{ fontStyle: 'italic', color: 'text.disabled' }}>
                                              {t('taskManagement.table.noDescription')}
                                            </Box>
                                          )}
                                        </Typography>
                                      </TableCell>

                                      <TableCell>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                          <DescriptionIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                                          <Typography variant="caption" sx={{ color: 'text.primary', fontWeight: 500 }}>
                                            {task.template_filename}
                                          </Typography>
                                        </Box>
                                      </TableCell>

                                      <TableCell>
                                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                          {dateOf(task.created_at)}
                                        </Typography>
                                      </TableCell>

                                      <TableCell>
                                        <Box sx={{ display: 'flex', justifyContent: 'center' }}>
                                          <Tooltip title={isAdmin ? '' : t('taskManagement.onlyAdminEditDelete')}>
                                            <span>
                                              <IconButton
                                                size="small"
                                                onClick={(e) => openTemplateActionMenu(e, task)}
                                                disabled={!isAdmin}
                                                sx={{ color: 'text.secondary' }}
                                              >
                                                <MoreVertIcon fontSize="small" />
                                              </IconButton>
                                            </span>
                                          </Tooltip>
                                        </Box>
                                      </TableCell>
                                    </TableRow>
                                  ))}
                                </TableBody>
                              </Table>
                            </TableContainer>
                          </Paper>
                        ))}
                    </Box>
                  )
                })}
              </Box>
            )}

            <Menu anchorEl={templateActionMenu.anchorEl} open={Boolean(templateActionMenu.anchorEl)} onClose={closeTemplateActionMenu}>
              <MenuItem
                onClick={() => {
                  handleOpenEditDialog(templateActionMenu.task)
                  closeTemplateActionMenu()
                }}
              >
                <EditIcon fontSize="small" sx={{ mr: 1.5, color: 'primary.main' }} />
                {t('taskManagement.menu.edit')}
              </MenuItem>
              <MenuItem
                onClick={() => {
                  handleDeleteClick(templateActionMenu.task)
                  closeTemplateActionMenu()
                }}
                sx={{ color: 'error.main' }}
              >
                <DeleteIcon fontSize="small" sx={{ mr: 1.5 }} />
                {t('taskManagement.menu.delete')}
              </MenuItem>
            </Menu>

            {/* Create/Edit Dialog */}
            <Dialog open={dialogOpen} onClose={handleCloseDialog} fullWidth maxWidth="sm">
              <DialogTitle>
                {dialogMode === 'create'
                  ? t('taskManagement.dialog.createTitle')
                  : t('taskManagement.dialog.editTitle')}
              </DialogTitle>
              <Box component="form" onSubmit={handleSubmit}>
                <DialogContent>
                  {submitError && <Alert severity="error" sx={{ mb: 2 }}>{submitError}</Alert>}

                  <FormControl fullWidth sx={{ mb: 3 }}>
                    <InputLabel id="task-type-label">{t('taskManagement.dialog.taskType')}</InputLabel>
                    <Select
                      labelId="task-type-label"
                      label={t('taskManagement.dialog.taskType')}
                      value={category}
                      onChange={(e) => {
                        setCategory(e.target.value)
                        setFile(null)
                      }}
                    >
                      {TASK_TYPES.map((type) => (
                        <MenuItem key={type.value} value={type.value}>
                          {type.label}
                        </MenuItem>
                      ))}
                    </Select>
                    <Typography variant="caption" sx={{ color: 'text.secondary', mt: 1 }}>
                      {TASK_TYPES.find((item) => item.value === category)?.description}
                    </Typography>
                  </FormControl>

                  <TextField
                    fullWidth
                    required
                    label={t('taskManagement.dialog.taskNameLabel')}
                    placeholder={t('taskManagement.dialog.taskNamePlaceholder')}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    sx={{ mb: 3 }}
                  />
                  <TextField
                    fullWidth
                    multiline
                    minRows={3}
                    label={t('taskManagement.dialog.descriptionLabel')}
                    placeholder={t('taskManagement.dialog.descriptionPlaceholder')}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    sx={{ mb: 3 }}
                  />
                  <Button component="label" variant="outlined" startIcon={<UploadFileIcon />} sx={{ textTransform: 'none', py: 1.5, borderRadius: 2 }}>
                    {file
                      ? file.name
                      : dialogMode === 'edit'
                      ? t('taskManagement.dialog.keepExistingFile')
                      : category === 'skill_engine'
                      ? t('taskManagement.dialog.chooseRulesFile')
                      : t('taskManagement.dialog.chooseExcelFile')}
                    <input type="file" accept={getFileAccept(category)} hidden onChange={(e) => setFile(e.target.files?.[0] || null)} />
                  </Button>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 1 }}>
                    {dialogMode === 'edit'
                      ? t('taskManagement.dialog.replaceFileHint')
                      : category === 'skill_engine'
                      ? t('taskManagement.dialog.rulesFileHint')
                      : t('taskManagement.dialog.excelFileHint')}
                  </Typography>
                </DialogContent>
                <DialogActions sx={{ px: 3, pb: 3 }}>
                  <Button onClick={handleCloseDialog} disabled={isSubmitting} sx={{ textTransform: 'none' }}>
                    {t('taskManagement.dialog.cancel')}
                  </Button>
                  <Button type="submit" variant="contained" disabled={isSubmitting} sx={{ textTransform: 'none', background: GRADIENT }}>
                    {isSubmitting
                      ? t('taskManagement.dialog.saving')
                      : dialogMode === 'create'
                      ? t('taskManagement.dialog.createTask')
                      : t('taskManagement.dialog.updateTask')}
                  </Button>
                </DialogActions>
              </Box>
            </Dialog>

            {/* Delete Confirmation Dialog */}
            <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel} maxWidth="sm" fullWidth>
              <DialogTitle>{t('taskManagement.dialog.deleteTaskTitle')}</DialogTitle>
              <DialogContent>
                <Typography variant="body1" sx={{ color: 'text.primary', mb: 2 }}>
                  <Trans i18nKey="taskManagement.dialog.deleteTaskConfirm" ns="pages" values={{ taskName: taskToDelete?.name }}>
                    Are you sure you want to delete the task <strong>"{'{{taskName}}'}"</strong>?
                  </Trans>
                </Typography>
                <Alert severity="warning" sx={{ borderRadius: 2 }}>
                  {t('taskManagement.dialog.deleteTaskWarning')}
                </Alert>
              </DialogContent>
              <DialogActions sx={{ px: 3, pb: 3 }}>
                <Button onClick={handleDeleteCancel} disabled={isDeleting} sx={{ textTransform: 'none' }}>
                  {t('taskManagement.dialog.cancel')}
                </Button>
                <Button
                  onClick={handleDeleteConfirm}
                  variant="contained"
                  color="error"
                  disabled={isDeleting}
                  startIcon={isDeleting ? <CircularProgress size={16} /> : <DeleteIcon />}
                  sx={{ textTransform: 'none' }}
                >
                  {isDeleting ? t('taskManagement.dialog.deleting') : t('taskManagement.menu.delete')}
                </Button>
              </DialogActions>
            </Dialog>
          </Box>
        )}

        {/* Shared toast */}
        <Snackbar open={snackbar.open} autoHideDuration={4000} onClose={handleSnackbarClose} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}>
          <Alert onClose={handleSnackbarClose} severity={snackbar.severity} sx={{ width: '100%', borderRadius: 2 }}>
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Box>
    </Box>
  )
}

export default TaskManagement
