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
const STATUS_META = {
  draft:                           { label: 'Not started',       color: '#94a3b8' }, // slate
  file_submitted:                  { label: 'Pending',           color: '#f59e0b' }, // amber
  analysis_in_progress:            { label: 'In progress',       color: '#3b82f6' }, // blue
  waiting_for_support_response:    { label: 'Awaiting response', color: '#eab308' }, // yellow
  additional_information_required: { label: 'Needs information', color: '#ef4444' }, // red
  data_corrected:                  { label: 'Corrected',         color: '#8b5cf6' }, // violet
  data_validated:                  { label: 'Validated',         color: '#14b8a6' }, // teal
  script_generated:                { label: 'Script generated',  color: '#0ea5e9' }, // sky
  processing_completed:            { label: 'Completed',         color: '#16a34a' }, // green
  escalation_required:             { label: 'Escalated',         color: '#dc2626' }, // deep red
}

const statusOf = (status) =>
  STATUS_META[status] || { label: status || 'Unknown', color: '#94a3b8' }

// Urgency, hottest first. Deliberately clear of the status palette
// above so a red priority is never mistaken for a red status.
const PRIORITY_META = {
  high:   { label: 'High',   color: '#dc2626', bg: 'rgba(220,38,38,0.12)' },
  medium: { label: 'Medium', color: '#d97706', bg: 'rgba(217,119,6,0.14)' },
  low:    { label: 'Low',    color: '#0284c7', bg: 'rgba(2,132,199,0.12)' },
}

const PRIORITY_ORDER = ['high', 'medium', 'low']

const priorityOf = (priority) =>
  PRIORITY_META[String(priority || 'medium').toLowerCase()] || PRIORITY_META.medium

const initialsOf = (fullName) =>
  fullName
    ? fullName.split(' ').filter(Boolean).slice(0, 2)
        .map((part) => part[0].toUpperCase()).join('')
    : '?'

const profileUrlOf = (owner) =>
  owner?.profile_picture
    ? `${API_BASE}/uploads/profiles/${owner.profile_picture}`
    : undefined

const dateOf = (value) => {
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
const StatCard = ({ icon: Icon, iconColor, iconBg, label, value, subtitle }) => (
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
  const [summary, setSummary] = useState(null)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

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
            ? 'Your session has expired. Please sign in again.'
            : `Could not load tasks (${resp.status}).`
        )
      }

      const data = await resp.json()
      setSummary(data.summary || null)
      setItems(data.items || [])
    } catch (err) {
      setError(err.message || 'Could not load tasks.')
    } finally {
      setLoading(false)
    }
  }, [])

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
    const status = statusOf(item.status)
    const priority = priorityOf(item.priority)
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
              ? 'You can only change your own requests.'
              : `Could not change the priority (${resp.status}).`)
        )
      }
    } catch (err) {
      setItems((prev) =>
        prev.map((row) =>
          row.id === item.id ? { ...row, priority: item.priority } : row
        )
      )
      setNotice({ severity: 'error', text: err.message || 'Could not change the priority.' })
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
                ? 'You can only delete your own requests.'
                : `Could not delete this task (${resp.status}).`)
          )
        }

        message = { severity: 'success', text: 'Task deleted.' }
      } else {
        const resp = await fetch(`${API_BASE}/api/requests/bulk-delete`, {
          method: 'POST',
          headers: { ...headers, 'Content-Type': 'application/json' },
          body: JSON.stringify({ ids: targets.map((t) => t.id) }),
        })

        if (!resp.ok) {
          const body = await resp.json().catch(() => ({}))
          throw new Error(body.detail || `Could not delete the selected tasks (${resp.status}).`)
        }

        const result = await resp.json()
        const refused = (result.forbidden || []).length

        // A partial result is reported as such rather than as success.
        message = refused
          ? {
              severity: 'warning',
              text: `${result.deleted_count} deleted. ${refused} could not be — you can only delete your own requests.`,
            }
          : { severity: 'success', text: `${result.deleted_count} tasks deleted.` }
      }

      setPendingDelete(null)
      setSelected([])
      setNotice(message)
      await load()
    } catch (err) {
      setNotice({ severity: 'error', text: err.message || 'Could not delete.' })
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
              Dashboard
            </Typography>
            <Typography variant="body1" sx={{ color: 'text.secondary' }}>
              Progress across every configuration task, and who is working on it.
            </Typography>
          </Box>

          <Stack direction="row" spacing={1.5} alignItems="center">
            {contributors.length > 0 && (
              <AvatarGroup
                max={5}
                sx={{ '& .MuiAvatar-root': { width: 32, height: 32, fontSize: 12 } }}
              >
                {contributors.map((owner) => (
                  <Tooltip key={owner.id} title={owner.full_name || 'User'}>
                    <Avatar src={profileUrlOf(owner)} alt={owner.full_name}>
                      {initialsOf(owner.full_name)}
                    </Avatar>
                  </Tooltip>
                ))}
              </AvatarGroup>
            )}
            <Tooltip title="Refresh">
              <span>
                <IconButton onClick={load} disabled={loading}>
                  <RefreshIcon />
                </IconButton>
              </span>
            </Tooltip>
          </Stack>
        </Stack>

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
              label="Total Tasks"
              value={total}
              subtitle={`${createdThisMonth} created this month`}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              icon={AccessTimeIcon}
              iconColor="#3b82f6"
              iconBg="rgba(59,130,246,0.12)"
              label="In Progress"
              value={summary?.pending || 0}
              subtitle="Currently being worked on"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              icon={CheckCircleOutlineIcon}
              iconColor="#16a34a"
              iconBg="rgba(22,163,74,0.12)"
              label="Completed"
              value={summary?.completed || 0}
              subtitle={`${completedThisWeek} finished this week`}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              icon={HourglassEmptyIcon}
              iconColor="#f59e0b"
              iconBg="rgba(245,158,11,0.12)"
              label="Not Started"
              value={summary?.not_started || 0}
              subtitle="Waiting to be picked up"
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
                {selected.length} selected
              </Typography>

              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  onClick={() => setSelected([])}
                  sx={{ textTransform: 'none' }}
                >
                  Clear
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
                  Delete selected
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
                      inputProps={{ 'aria-label': 'Select all tasks on this page' }}
                    />
                  </TableCell>
                  <TableCell>Task Name</TableCell>
                  <TableCell>Assignee</TableCell>
                  <TableCell>Priority</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Updated</TableCell>
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
                            ? 'No configuration tasks yet.'
                            : `No tasks match "${searchTerm}".`}
                        </Typography>
                      </Stack>
                    </TableCell>
                  </TableRow>
                )}

                {pagedItems.map((item) => {
                  const meta = statusOf(item.status)

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
                          inputProps={{ 'aria-label': `Select ${item.task_name}` }}
                        />
                      </TableCell>

                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 700 }}>
                          {item.task_name}
                        </Typography>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          {item.uploaded_filename || 'No file uploaded'}
                        </Typography>
                      </TableCell>

                      <TableCell>
                        <Stack direction="row" alignItems="center" spacing={1}>
                          <Avatar
                            src={profileUrlOf(item.owner)}
                            alt={item.owner?.full_name || 'Unassigned'}
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
                            {item.owner?.full_name || 'Unassigned'}
                          </Typography>
                        </Stack>
                      </TableCell>

                      <TableCell>
                        <Tooltip title="Click to change priority">
                          <Typography
                            variant="body2"
                            onClick={(event) => setPriorityMenu({
                              anchor: event.currentTarget,
                              item,
                            })}
                            sx={{
                              display: 'inline-block',
                              fontWeight: 700,
                              cursor: 'pointer',
                              color: priorityOf(item.priority).color,
                            }}
                          >
                            {priorityOf(item.priority).label}
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
            recordLabel="records"
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
          <MenuItem
            onClick={() => {
              setPendingDelete([rowMenu.item])
              setRowMenu(null)
            }}
            sx={{ fontSize: 13, gap: 1.25, color: 'error.main' }}
          >
            <DeleteOutlineIcon sx={{ fontSize: 18 }} />
            Delete
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
                {meta.label}
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
              ? `Delete ${pendingDelete.length} tasks?`
              : 'Delete this task?'}
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
                  will be removed.
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
                {pendingDelete?.length > 1 ? 'Their' : 'Its'} conversation,
                progress and uploaded file go with{' '}
                {pendingDelete?.length > 1 ? 'them' : 'it'}. This cannot be
                undone. The task template{pendingDelete?.length > 1 ? 's are' : ' itself is'}{' '}
                kept, so a new request can be started from{' '}
                {pendingDelete?.length > 1 ? 'them' : 'it'}.
              </Typography>
            </DialogContentText>
          </DialogContent>

          <DialogActions sx={{ px: 3, pb: 2.5 }}>
            <Button
              onClick={() => setPendingDelete(null)}
              disabled={deleting}
              sx={{ textTransform: 'none' }}
            >
              Cancel
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
                ? 'Deleting...'
                : pendingDelete?.length > 1
                ? `Delete ${pendingDelete.length}`
                : 'Delete'}
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
      </Box>
    </Box>
  )
}

export default DashboardHome
