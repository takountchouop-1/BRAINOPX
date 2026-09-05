import React, { useCallback, useEffect, useState } from 'react'
import {
  Avatar,
  AvatarGroup,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Grid,
  IconButton,
  LinearProgress,
  Menu,
  MenuItem,
  Paper,
  Snackbar,
  Alert,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tab,
  Tabs,
  Tooltip,
  Typography,
} from '@mui/material'

import RefreshIconImport from '@mui/icons-material/Refresh'
import InboxIconImport from '@mui/icons-material/Inbox'
import DeleteOutlineIconImport from '@mui/icons-material/DeleteOutline'
import MoreVertIconImport from '@mui/icons-material/MoreVert'
import AssignmentOutlinedIconImport from '@mui/icons-material/AssignmentOutlined'
import AccessTimeIconImport from '@mui/icons-material/AccessTime'
import CheckCircleOutlineIconImport from '@mui/icons-material/CheckCircleOutline'
import HourglassEmptyIconImport from '@mui/icons-material/HourglassEmpty'
import PaginationBar from '../components/PaginationBar.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import GraphAnalysis from './GraphAnalysis.jsx'
import { useTranslation } from 'react-i18next'

const RefreshIcon = RefreshIconImport?.default || RefreshIconImport
const InboxIcon = InboxIconImport?.default || InboxIconImport
const DeleteOutlineIcon = DeleteOutlineIconImport?.default || DeleteOutlineIconImport
const MoreVertIcon = MoreVertIconImport?.default || MoreVertIconImport
const AssignmentOutlinedIcon = AssignmentOutlinedIconImport?.default || AssignmentOutlinedIconImport
const AccessTimeIcon = AccessTimeIconImport?.default || AccessTimeIconImport
const CheckCircleOutlineIcon = CheckCircleOutlineIconImport?.default || CheckCircleOutlineIconImport
const HourglassEmptyIcon = HourglassEmptyIconImport?.default || HourglassEmptyIconImport

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// ─── STATUS ──────────────────────────────────────────────────────────────────
// Same vocabulary the configuration page uses, so a status reads the
// same wherever it appears.

// Each status carries its own colour — previously several shared
// warning.main / success.main, so "In progress" and "Awaiting
// response" were indistinguishable at a glance, which is the whole
// point of a status column.
// Labels are translation keys (resolved with `t` at the call site via
// statusOf/priorityOf below) so this table can be shared by both
// DashboardHome and GraphAnalysis without baking in one language.
export const STATUS_META = {
  draft:                           { labelKey: 'dashboardHome.status.draft',                           color: '#94a3b8' }, // slate
  file_submitted:                  { labelKey: 'dashboardHome.status.fileSubmitted',                    color: '#f59e0b' }, // amber
  analysis_in_progress:            { labelKey: 'dashboardHome.status.analysisInProgress',                color: '#3b82f6' }, // blue
  waiting_for_support_response:    { labelKey: 'dashboardHome.status.waitingForSupportResponse',         color: '#eab308' }, // yellow
  additional_information_required: { labelKey: 'dashboardHome.status.additionalInformationRequired',     color: '#ef4444' }, // red
  data_corrected:                  { labelKey: 'dashboardHome.status.dataCorrected',                     color: '#8b5cf6' }, // violet
  data_validated:                  { labelKey: 'dashboardHome.status.dataValidated',                     color: '#14b8a6' }, // teal
  script_generated:                { labelKey: 'dashboardHome.status.scriptGenerated',                   color: '#0ea5e9' }, // sky
  processing_completed:            { labelKey: 'dashboardHome.status.processingCompleted',                color: '#16a34a' }, // green
  escalation_required:             { labelKey: 'dashboardHome.status.escalationRequired',                 color: '#dc2626' }, // deep red
}

export const statusOf = (status, t) => {
  const meta = STATUS_META[status]
  if (meta) return { label: t(meta.labelKey), color: meta.color }
  return { label: status || t('dashboardHome.status.unknown'), color: '#94a3b8' }
}

// Urgency, hottest first. Deliberately clear of the status palette
// above so a red priority is never mistaken for a red status.
export const PRIORITY_META = {
  high:   { labelKey: 'dashboardHome.priority.high',   color: '#dc2626', bg: 'rgba(220,38,38,0.12)' },
  medium: { labelKey: 'dashboardHome.priority.medium', color: '#d97706', bg: 'rgba(217,119,6,0.14)' },
  low:    { labelKey: 'dashboardHome.priority.low',    color: '#0284c7', bg: 'rgba(2,132,199,0.12)' },
}

const PRIORITY_ORDER = ['high', 'medium', 'low']

export const priorityOf = (priority, t) => {
  const meta = PRIORITY_META[String(priority || 'medium').toLowerCase()] || PRIORITY_META.medium
  return { label: t(meta.labelKey), color: meta.color, bg: meta.bg }
}

export const initialsOf = (fullName) =>
  fullName
    ? fullName.split(' ').filter(Boolean).slice(0, 2)
        .map((part) => part[0].toUpperCase()).join('')
    : '?'

export const profileUrlOf = (owner) =>
  owner?.profile_picture
    ? `${API_BASE}/uploads/profiles/${owner.profile_picture}`
    : undefined

export const dateOf = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

// ─── STAT CARD ───────────────────────────────────────────────────────────────

/**
 * A summary tile: coloured icon badge, a menu affordance, the figure,
 * and a one-line subtitle underneath — as in the reference dashboard.
 */
export const StatCard = ({ icon: Icon, iconColor, iconBg, label, value, subtitle }) => (
  <Paper
    sx={{
      p: 2.5,
      borderRadius: 3,
      height: '100%',
      background: (theme) =>
        theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : '#ffffff',
      border: (theme) =>
        `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
    }}
  >
    <Stack direction="row" alignItems="flex-start" justifyContent="space-between">
      <Box
        sx={{
          width: 40,
          height: 40,
          borderRadius: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: iconBg,
          color: iconColor,
        }}
      >
        <Icon fontSize="small" />
      </Box>
      <IconButton size="small" sx={{ color: 'text.disabled', mt: -0.5, mr: -0.5 }}>
        <MoreVertIcon fontSize="small" />
      </IconButton>
    </Stack>

    <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.secondary', mt: 1.75 }}>
      {label}
    </Typography>
    <Typography variant="h4" sx={{ fontWeight: 700, color: 'text.primary', mt: 0.25 }}>
      {value}
    </Typography>
    <Typography variant="caption" sx={{ color: 'text.disabled' }}>
      {subtitle}
    </Typography>
  </Paper>
)

// ─── DASHBOARD ───────────────────────────────────────────────────────────────

const DashboardHome = ({ searchTerm = '' } = {}) => {
  const { user } = useAuth()
  const { t } = useTranslation('layout')
  const [summary, setSummary] = useState(null)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState(0)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetch(`${API_BASE}/api/requests/`, {
        headers: { Authorization: `Bearer ${token}` },
      })

      if (!resp.ok) {
        throw new Error(
          resp.status === 401
            ? t('dashboardHome.errors.sessionExpired')
            : t('dashboardHome.errors.couldNotLoadTasksWithStatus', { status: resp.status })
        )
      }

      const data = await resp.json()
      setSummary(data.summary || null)
      setItems(data.items || [])
    } catch (err) {
      setError(err.message || t('dashboardHome.errors.couldNotLoadTasks'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    load()
  }, [load])

  // ─── DELETING ──────────────────────────────────────────────────
  // Held in state so the confirmation names the task being removed;
  // deleting is not reversible, so it is never one click.

  // `pendingDelete` holds the rows a confirmation is open for — one
  // from a row's bin icon, several from the selection toolbar. One
  // dialog serves both.
  const [pendingDelete, setPendingDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [notice, setNotice] = useState(null)
  const [selected, setSelected] = useState([])

  // ─── SEARCH ────────────────────────────────────────────────────
  // The topbar search box drives this — task name, requester, status
  // and priority are all fair game, since those are exactly the
  // things this table is organised by.
  const filteredItems = items.filter((item) => {
    if (!searchTerm) return true
    const term = searchTerm.toLowerCase()
    const status = statusOf(item.status, t)
    const priority = priorityOf(item.priority, t)
    return (
      (item.task_name && item.task_name.toLowerCase().includes(term)) ||
      (item.owner?.full_name && item.owner.full_name.toLowerCase().includes(term)) ||
      status.label.toLowerCase().includes(term) ||
      priority.label.toLowerCase().includes(term)
    )
  })

  // ─── PAGING ────────────────────────────────────────────────────
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  const pageCount = Math.max(1, Math.ceil(filteredItems.length / pageSize))
  const pagedItems = filteredItems.slice((page - 1) * pageSize, page * pageSize)

  // If a delete (or a reload) shrinks the list enough that the
  // current page no longer exists, land on the new last page rather
  // than showing an empty table.
  useEffect(() => {
    setPage((prev) => Math.min(prev, pageCount))
  }, [pageCount])

  // A search that matches something different deserves to start from
  // the top, not wherever paging happened to be left.
  useEffect(() => {
    setPage(1)
  }, [searchTerm])

  const changePageSize = (size) => {
    setPageSize(size)
    setPage(1)
  }

  // ─── ROW MENU ──────────────────────────────────────────────────
  const [rowMenu, setRowMenu] = useState(null)

  // ─── PRIORITY ──────────────────────────────────────────────────
  const [priorityMenu, setPriorityMenu] = useState(null)

  const changePriority = async (item, priority) => {
    setPriorityMenu(null)

    if (priority === item.priority) return

    // Updated locally first so the chip responds immediately; the
    // reload below reconciles it, and a failure puts it back.
    setItems((prev) =>
      prev.map((row) => (row.id === item.id ? { ...row, priority } : row))
    )

    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetch(`${API_BASE}/api/requests/${item.id}/priority`, {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ priority }),
      })

      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(
          body.detail ||
            (resp.status === 403
              ? t('dashboardHome.errors.onlyChangeOwnRequests')
              : t('dashboardHome.errors.couldNotChangePriorityWithStatus', { status: resp.status }))
        )
      }
    } catch (err) {
      setItems((prev) =>
        prev.map((row) =>
          row.id === item.id ? { ...row, priority: item.priority } : row
        )
      )
      setNotice({ severity: 'error', text: err.message || t('dashboardHome.errors.couldNotChangePriority') })
    }
  }

  const markComplete = async (item) => {
    setRowMenu(null)
    if (item.status === 'processing_completed') return
    const previousStatus = item.status
    setItems((prev) =>
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
        throw new Error(body.detail || t('dashboardHome.errors.couldNotCompleteTaskWithStatus', { status: resp.status }))
      }
      setNotice({ severity: 'success', text: t('dashboardHome.notices.taskCompleted') })
      // Reload so summary.completed and each item's bucket (which the
      // Graph Analysis tab keys its charts on) come back in sync with
      // the server — the optimistic status patch above doesn't touch
      // either of those.
      await load()
    } catch (err) {
      setItems((prev) =>
        prev.map((row) => (row.id === item.id ? { ...row, status: previousStatus } : row))
      )
      setNotice({ severity: 'error', text: err.message || t('dashboardHome.errors.couldNotCompleteTask') })
    }
  }

  const pageIds = pagedItems.map((item) => item.id)
  const allOnPageSelected = pageIds.length > 0 && pageIds.every((id) => selected.includes(id))
  const someOnPageSelected = pageIds.some((id) => selected.includes(id))

  const toggleOne = (id) =>
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    )

  // Selects the current page only — with 65 rows across 7 pages, a
  // "select all" that silently reached past what is on screen would
  // be an easy way to bulk-delete far more than intended. Selections
  // on other pages are left alone, so picking rows across several
  // pages before deleting still works.
  const toggleAll = () =>
    setSelected((prev) =>
      allOnPageSelected
        ? prev.filter((id) => !pageIds.includes(id))
        : Array.from(new Set([...prev, ...pageIds]))
    )

  // Selections must not survive the rows they point at.
  useEffect(() => {
    setSelected((prev) => prev.filter((id) => items.some((item) => item.id === id)))
  }, [items])

  const confirmDelete = async () => {
    const targets = pendingDelete || []
    if (targets.length === 0) return

    setDeleting(true)
    try {
      const token = localStorage.getItem('brainopx_token')
      const headers = { Authorization: `Bearer ${token}` }

      let message

      if (targets.length === 1) {
        const resp = await fetch(`${API_BASE}/api/requests/${targets[0].id}`, {
          method: 'DELETE',
          headers,
        })

        if (!resp.ok) {
          const body = await resp.json().catch(() => ({}))
          throw new Error(
            body.detail ||
              (resp.status === 403
                ? t('dashboardHome.errors.onlyDeleteOwnRequests')
                : t('dashboardHome.errors.couldNotDeleteTaskWithStatus', { status: resp.status }))
          )
        }

        message = { severity: 'success', text: t('dashboardHome.notices.taskDeleted') }
      } else {
        const resp = await fetch(`${API_BASE}/api/requests/bulk-delete`, {
          method: 'POST',
          headers: { ...headers, 'Content-Type': 'application/json' },
          body: JSON.stringify({ ids: targets.map((t) => t.id) }),
        })

        if (!resp.ok) {
          const body = await resp.json().catch(() => ({}))
          throw new Error(body.detail || t('dashboardHome.errors.couldNotDeleteTasksWithStatus', { status: resp.status }))
        }

        const result = await resp.json()
        const refused = (result.forbidden || []).length

        // A partial result is reported as such rather than as success.
        message = refused
          ? {
              severity: 'warning',
              text: t('dashboardHome.notices.partialDelete', { count: result.deleted_count, refused }),
            }
          : { severity: 'success', text: t('dashboardHome.notices.bulkDeleted', { count: result.deleted_count }) }
      }

      setPendingDelete(null)
      setSelected([])
      setNotice(message)
      await load()
    } catch (err) {
      setNotice({ severity: 'error', text: err.message || t('dashboardHome.errors.couldNotDelete') })
    } finally {
      setDeleting(false)
    }
  }

  const total = summary?.total || 0

  // Real counts behind the card subtitles — no invented trend
  // percentages, since the API has no historical snapshots to
  // compute a week-over-week change from.
  const COMPLETED_STATUSES = new Set(['script_generated', 'processing_completed'])
  const now = new Date()
  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1)
  const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)

  const createdThisMonth = items.filter(
    (item) => item.created_at && new Date(item.created_at) >= startOfMonth
  ).length

  const completedThisWeek = items.filter((item) => {
    if (!COMPLETED_STATUSES.has(item.status)) return false
    const when = new Date(item.updated_at || item.created_at)
    return !Number.isNaN(when.getTime()) && when >= sevenDaysAgo
  }).length

  // Everyone currently working on something.
  const contributors = Array.from(
    new Map(
      items
        .filter((item) => item.owner)
        .map((item) => [item.owner.id, item.owner])
    ).values()
  )

  return (
    <Box sx={{ p: 4 }}>
      <Box sx={{ maxWidth: 1400, mx: 'auto' }}>

        <Stack
          direction="row"
          alignItems="flex-start"
          justifyContent="space-between"
          sx={{ mb: 3 }}
        >
          <Box>
            <Typography variant="h4" sx={{ fontWeight: 700, mb: 0.5, color: 'text.primary' }}>
              {t('dashboardHome.title')}
            </Typography>
            <Typography variant="body1" sx={{ color: 'text.secondary' }}>
              {t('dashboardHome.subtitle')}
            </Typography>
          </Box>

          <Stack direction="row" spacing={1.5} alignItems="center">
            {contributors.length > 0 && (
              <AvatarGroup
                max={5}
                sx={{ '& .MuiAvatar-root': { width: 32, height: 32, fontSize: 12 } }}
              >
                {contributors.map((owner) => (
                  <Tooltip key={owner.id} title={owner.full_name || t('dashboardHome.user')}>
                    <Avatar src={profileUrlOf(owner)} alt={owner.full_name}>
                      {initialsOf(owner.full_name)}
                    </Avatar>
                  </Tooltip>
                ))}
              </AvatarGroup>
            )}
            <Tooltip title={t('dashboardHome.refresh')}>
              <span>
                <IconButton onClick={load} disabled={loading}>
                  <RefreshIcon />
                </IconButton>
              </span>
            </Tooltip>
          </Stack>
        </Stack>

        {/* ── Overview / Graph Analysis ───────────────────────────── */}
        <Tabs
          value={activeTab}
          onChange={(_e, value) => setActiveTab(value)}
          sx={{
            mb: 3,
            minHeight: 40,
            borderBottom: (theme) =>
              `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
            '& .MuiTab-root': {
              textTransform: 'none',
              fontWeight: 700,
              minHeight: 40,
              fontSize: 14,
            },
          }}
        >
          <Tab label={t('dashboardHome.tabs.overview')} />
          <Tab label={t('dashboardHome.tabs.graphAnalysis')} />
        </Tabs>

        {activeTab === 1 && <GraphAnalysis items={items} loading={loading} />}

        {activeTab !== 1 && (
        <>
        {/* ── Your account ────────────────────────────────────────── */}
        {user && (
          <Paper
            sx={{
              p: 2.5,
              mb: 3,
              borderRadius: 3,
              display: 'flex',
              alignItems: 'center',
              gap: 2,
            }}
          >
            <Avatar
              src={profileUrlOf(user)}
              alt={user.full_name}
              sx={{ width: 56, height: 56, fontSize: 20 }}
            >
              {initialsOf(user.full_name)}
            </Avatar>
            <Box sx={{ flexGrow: 1, minWidth: 0 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, color: 'text.primary' }} noWrap>
                {user.full_name || t('dashboardHome.welcome')}
              </Typography>
              <Typography variant="body2" sx={{ color: 'text.secondary' }} noWrap>
                {user.email}
              </Typography>
            </Box>
            <Chip
              label={user.role === 'admin' ? t('dashboardHome.administrator') : t('dashboardHome.member')}
              size="small"
              sx={{
                textTransform: 'capitalize',
                fontWeight: 600,
                bgcolor: user.role === 'admin' ? 'rgba(79,70,229,0.12)' : 'rgba(100,116,139,0.12)',
                color: user.role === 'admin' ? '#4f46e5' : '#475569',
              }}
            />
          </Paper>
        )}

        {error && (
          <Paper
            sx={{
              p: 2,
              mb: 3,
              borderRadius: 3,
              border: '1px solid rgba(211,47,47,0.3)',
              bgcolor: 'rgba(211,47,47,0.04)',
            }}
          >
            <Typography variant="body2" sx={{ color: 'error.main' }}>{error}</Typography>
          </Paper>
        )}

        {/* ── Summary cards ───────────────────────────────────────── */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              icon={AssignmentOutlinedIcon}
              iconColor="#4f46e5"
              iconBg="rgba(79,70,229,0.12)"
              label={t('dashboardHome.stats.totalTasks')}
              value={total}
              subtitle={t('dashboardHome.stats.createdThisMonth', { count: createdThisMonth })}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              icon={AccessTimeIcon}
              iconColor="#3b82f6"
              iconBg="rgba(59,130,246,0.12)"
              label={t('dashboardHome.stats.inProgress')}
              value={summary?.pending || 0}
              subtitle={t('dashboardHome.stats.currentlyBeingWorkedOn')}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              icon={CheckCircleOutlineIcon}
              iconColor="#16a34a"
              iconBg="rgba(22,163,74,0.12)"
              label={t('dashboardHome.stats.completed')}
              value={summary?.completed || 0}
              subtitle={t('dashboardHome.stats.finishedThisWeek', { count: completedThisWeek })}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              icon={HourglassEmptyIcon}
              iconColor="#f59e0b"
              iconBg="rgba(245,158,11,0.12)"
              label={t('dashboardHome.stats.notStarted')}
              value={summary?.not_started || 0}
              subtitle={t('dashboardHome.stats.waitingToBePickedUp')}
            />
          </Grid>
        </Grid>

        {/* ── Task table ──────────────────────────────────────────── */}
        <Paper
          sx={{
            borderRadius: 3,
            overflow: 'hidden',
            background: (theme) =>
              theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : '#ffffff',
            border: (theme) =>
              `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
          }}
        >
          {loading && <LinearProgress />}

          {/* Replaces the header row's meaning while rows are picked,
              so the destructive action is only present when it applies. */}
          {selected.length > 0 && (
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="space-between"
              sx={{
                px: 2,
                py: 1.25,
                bgcolor: 'rgba(79,70,229,0.06)',
                borderBottom: (theme) =>
                  `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
              }}
            >
              <Typography variant="body2" sx={{ fontWeight: 700 }}>
                {t('dashboardHome.selection.selectedCount', { count: selected.length })}
              </Typography>

              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  onClick={() => setSelected([])}
                  sx={{ textTransform: 'none' }}
                >
                  {t('dashboardHome.selection.clear')}
                </Button>
                <Button
                  size="small"
                  variant="contained"
                  color="error"
                  startIcon={<DeleteOutlineIcon />}
                  onClick={() =>
                    setPendingDelete(items.filter((i) => selected.includes(i.id)))
                  }
                  sx={{ textTransform: 'none', borderRadius: 2 }}
                >
                  {t('dashboardHome.selection.deleteSelected')}
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
                      borderBottom: (theme) =>
                        `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
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
                      onChange={toggleAll}
                      inputProps={{ 'aria-label': t('dashboardHome.table.selectAllAria') }}
                    />
                  </TableCell>
                  <TableCell>{t('dashboardHome.table.taskName')}</TableCell>
                  <TableCell>{t('dashboardHome.table.assignee')}</TableCell>
                  <TableCell>{t('dashboardHome.table.priority')}</TableCell>
                  <TableCell>{t('dashboardHome.table.status')}</TableCell>
                  <TableCell>{t('dashboardHome.table.updated')}</TableCell>
                  <TableCell align="right" sx={{ width: 60 }} />
                </TableRow>
              </TableHead>

              <TableBody>
                {!loading && filteredItems.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} sx={{ border: 0, py: 8 }}>
                      <Stack alignItems="center" spacing={1} sx={{ color: 'text.disabled' }}>
                        <InboxIcon sx={{ fontSize: 36, opacity: 0.4 }} />
                        <Typography variant="body2">
                          {items.length === 0
                            ? t('dashboardHome.table.noTasksYet')
                            : t('dashboardHome.table.noTasksMatch', { term: searchTerm })}
                        </Typography>
                      </Stack>
                    </TableCell>
                  </TableRow>
                )}

                {pagedItems.map((item) => {
                  const meta = statusOf(item.status, t)

                  return (
                    <TableRow
                      key={item.id}
                      hover
                      selected={selected.includes(item.id)}
                      sx={{
                        '& td': {
                          borderBottom: (theme) =>
                            `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : '#f1f3f7'}`,
                          py: 1.5,
                        },
                      }}
                    >
                      <TableCell padding="checkbox">
                        <Checkbox
                          size="small"
                          checked={selected.includes(item.id)}
                          onChange={() => toggleOne(item.id)}
                          inputProps={{ 'aria-label': t('dashboardHome.table.selectRowAria', { name: item.task_name }) }}
                        />
                      </TableCell>

                      <TableCell>
                        <Typography
                          variant="body2"
                          sx={{ fontFamily: "'Nunito', 'Inter', 'Roboto', sans-serif", fontWeight: 700 }}
                        >
                          {item.task_name}
                        </Typography>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          {item.uploaded_filename || t('dashboardHome.table.noFileUploaded')}
                        </Typography>
                      </TableCell>

                      <TableCell>
                        <Stack direction="row" alignItems="center" spacing={1}>
                          <Avatar
                            src={profileUrlOf(item.owner)}
                            alt={item.owner?.full_name || t('dashboardHome.table.unassigned')}
                            sx={{
                              width: 28,
                              height: 28,
                              fontSize: 11,
                              fontWeight: 700,
                              bgcolor: item.owner ? 'primary.main' : 'action.disabledBackground',
                              color: item.owner ? '#fff' : 'text.disabled',
                            }}
                          >
                            {initialsOf(item.owner?.full_name)}
                          </Avatar>
                          <Typography variant="body2" sx={{ whiteSpace: 'nowrap' }}>
                            {item.owner?.full_name || t('dashboardHome.table.unassigned')}
                          </Typography>
                        </Stack>
                      </TableCell>

                      <TableCell>
                        <Tooltip title={t('dashboardHome.table.clickToChangePriority')}>
                          <Typography
                            variant="body2"
                            onClick={(event) => setPriorityMenu({
                              anchor: event.currentTarget,
                              item,
                            })}
                            sx={{
                              display: 'inline-block',
                              fontFamily: "'Nunito', 'Inter', 'Roboto', sans-serif",
                              fontWeight: 700,
                              cursor: 'pointer',
                              color: priorityOf(item.priority, t).color,
                            }}
                          >
                            {priorityOf(item.priority, t).label}
                          </Typography>
                        </Tooltip>
                      </TableCell>

                      <TableCell>
                        <Chip
                          size="small"
                          label={meta.label}
                          sx={{
                            fontWeight: 700,
                            fontSize: 11.5,
                            color: meta.color,
                            bgcolor: `${meta.color}1F`,
                            border: 'none',
                          }}
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
                          onClick={(event) =>
                            setRowMenu({ anchor: event.currentTarget, item })
                          }
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
            page={page}
            pageSize={pageSize}
            totalRecords={items.length}
            onPageChange={setPage}
            onPageSizeChange={changePageSize}
            recordLabel={t('dashboardHome.table.recordsLabel')}
          />
        </Paper>

        {/* ── Row actions ──────────────────────────────────────────── */}
        <Menu
          anchorEl={rowMenu?.anchor || null}
          open={Boolean(rowMenu)}
          onClose={() => setRowMenu(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        >
          {rowMenu?.item && rowMenu.item.status !== 'processing_completed' && (
            <MenuItem
              disabled={rowMenu.item.progress < 100}
              onClick={() => markComplete(rowMenu.item)}
              sx={{ fontSize: 13, gap: 1.25 }}
            >
              <CheckCircleOutlineIcon sx={{ fontSize: 18 }} />
              {rowMenu.item.progress < 100
                ? t('dashboardHome.rowMenu.finishAllStepsFirst')
                : t('dashboardHome.rowMenu.markAsCompleted')}
            </MenuItem>
          )}
          <MenuItem
            onClick={() => {
              setPendingDelete([rowMenu.item])
              setRowMenu(null)
            }}
            sx={{ fontSize: 13, gap: 1.25, color: 'error.main' }}
          >
            <DeleteOutlineIcon sx={{ fontSize: 18 }} />
            {t('dashboardHome.rowMenu.delete')}
          </MenuItem>
        </Menu>

        {/* ── Change priority ─────────────────────────────────────── */}
        <Menu
          anchorEl={priorityMenu?.anchor || null}
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
                <Box
                  sx={{
                    width: 9,
                    height: 9,
                    borderRadius: '50%',
                    bgcolor: meta.color,
                    flexShrink: 0,
                  }}
                />
                {t(meta.labelKey)}
              </MenuItem>
            )
          })}
        </Menu>

        {/* ── Confirm deletion ────────────────────────────────────── */}
        <Dialog
          open={Boolean(pendingDelete && pendingDelete.length)}
          onClose={() => !deleting && setPendingDelete(null)}
          PaperProps={{ sx: { borderRadius: 3, maxWidth: 460 } }}
        >
          <DialogTitle sx={{ fontWeight: 700 }}>
            {pendingDelete?.length > 1
              ? t('dashboardHome.deleteDialog.titlePlural', { count: pendingDelete.length })
              : t('dashboardHome.deleteDialog.titleSingle')}
          </DialogTitle>

          <DialogContent>
            <DialogContentText component="div">
              {pendingDelete?.length === 1 ? (
                <Typography variant="body2" sx={{ mb: 1.5 }}>
                  <Box component="span" sx={{ fontWeight: 700 }}>
                    {pendingDelete[0].task_name}
                  </Box>
                  {pendingDelete[0].uploaded_filename
                    ? ` (${pendingDelete[0].uploaded_filename})`
                    : ''}{' '}
                  {t('dashboardHome.deleteDialog.willBeRemoved')}
                </Typography>
              ) : (
                // Naming them makes an accidental selection obvious
                // before it is acted on.
                <Box
                  sx={{
                    mb: 1.5,
                    maxHeight: 168,
                    overflowY: 'auto',
                    pl: 2,
                  }}
                >
                  {pendingDelete?.map((item) => (
                    <Typography
                      key={item.id}
                      variant="body2"
                      sx={{ fontWeight: 600, listStyle: 'disc', display: 'list-item' }}
                    >
                      {item.task_name}
                    </Typography>
                  ))}
                </Box>
              )}

              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                {pendingDelete?.length > 1
                  ? t('dashboardHome.deleteDialog.consequencePlural')
                  : t('dashboardHome.deleteDialog.consequenceSingular')}
              </Typography>
            </DialogContentText>
          </DialogContent>

          <DialogActions sx={{ px: 3, pb: 2.5 }}>
            <Button
              onClick={() => setPendingDelete(null)}
              disabled={deleting}
              sx={{ textTransform: 'none' }}
            >
              {t('dashboardHome.deleteDialog.cancel')}
            </Button>
            <Button
              onClick={confirmDelete}
              disabled={deleting}
              variant="contained"
              color="error"
              startIcon={
                deleting
                  ? <CircularProgress size={15} color="inherit" />
                  : <DeleteOutlineIcon />
              }
              sx={{ textTransform: 'none', borderRadius: 2 }}
            >
              {deleting
                ? t('dashboardHome.deleteDialog.deleting')
                : pendingDelete?.length > 1
                ? t('dashboardHome.deleteDialog.deleteCount', { count: pendingDelete.length })
                : t('dashboardHome.deleteDialog.delete')}
            </Button>
          </DialogActions>
        </Dialog>

        <Snackbar
          open={Boolean(notice)}
          autoHideDuration={4000}
          onClose={() => setNotice(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        >
          {notice ? (
            <Alert
              severity={notice.severity}
              variant="filled"
              onClose={() => setNotice(null)}
              sx={{ borderRadius: 2 }}
            >
              {notice.text}
            </Alert>
          ) : undefined}
        </Snackbar>
        </>
        )}
      </Box>
    </Box>
  )
}

export default DashboardHome
