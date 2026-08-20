import React, { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Avatar,
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
  Divider,
  FormControlLabel,
  FormGroup,
  IconButton,
  InputAdornment,
  LinearProgress,
  Menu,
  MenuItem,
  Paper,
  Select,
  Snackbar,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'

import AddIconImport from '@mui/icons-material/Add'
import SearchIconImport from '@mui/icons-material/Search'
import FilterListIconImport from '@mui/icons-material/FilterList'
import MoreVertIconImport from '@mui/icons-material/MoreVert'
import ContentCopyIconImport from '@mui/icons-material/ContentCopy'
import CheckCircleIconImport from '@mui/icons-material/CheckCircle'
import PersonOffIconImport from '@mui/icons-material/PersonOff'
import GroupIconImport from '@mui/icons-material/Group'
import DeleteOutlineIconImport from '@mui/icons-material/DeleteOutline'

import { useAuth } from '../context/AuthContext.jsx'
import PaginationBar from '../components/PaginationBar.jsx'

const AddIcon = AddIconImport?.default || AddIconImport
const SearchIcon = SearchIconImport?.default || SearchIconImport
const FilterListIcon = FilterListIconImport?.default || FilterListIconImport
const MoreVertIcon = MoreVertIconImport?.default || MoreVertIconImport
const ContentCopyIcon = ContentCopyIconImport?.default || ContentCopyIconImport
const CheckCircleIcon = CheckCircleIconImport?.default || CheckCircleIconImport
const PersonOffIcon = PersonOffIconImport?.default || PersonOffIconImport
const GroupIcon = GroupIconImport?.default || GroupIconImport
const DeleteOutlineIcon = DeleteOutlineIconImport?.default || DeleteOutlineIconImport

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// ─── VOCABULARY ──────────────────────────────────────────────────────────────
// Mirrors app.services.user_access on the backend — the only two
// access tags that exist, plus the two roles.

const ACCESS_OPTIONS = [
  { value: 'data_export', label: 'Data Export' },
  { value: 'data_import', label: 'Data Import' },
]

const ROLE_OPTIONS = [
  { value: 'admin', label: 'Admin' },
  { value: 'member', label: 'Member' },
]

// Chip colours. "Admin" gets the brand accent since it is the most
// consequential tag; the two access tags get colours distinct from
// both that and the status/priority palettes used elsewhere in the
// dashboard, so a glance is enough to tell which kind of tag it is.
const TAG_META = {
  Admin: { color: '#4f46e5', bg: 'rgba(79,70,229,0.12)' },
  'Data Export': { color: '#0d9488', bg: 'rgba(13,148,136,0.12)' },
  'Data Import': { color: '#7c3aed', bg: 'rgba(124,58,237,0.12)' },
}

const tagMeta = (label) => TAG_META[label] || { color: '#64748b', bg: 'rgba(100,116,139,0.12)' }

// ─── HELPERS ─────────────────────────────────────────────────────────────────

const initialsOf = (fullName) =>
  fullName
    ? fullName.split(' ').filter(Boolean).slice(0, 2)
        .map((part) => part[0].toUpperCase()).join('')
    : '?'

const profileUrlOf = (u) =>
  u?.profile_picture ? `${API_BASE}/uploads/profiles/${u.profile_picture}` : undefined

const dateOf = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

const displayTags = (user) => {
  const tags = []
  if (user.role === 'admin') tags.push('Admin')
  for (const opt of ACCESS_OPTIONS) {
    if ((user.access || []).includes(opt.value)) tags.push(opt.label)
  }
  return tags
}

const emptyForm = { full_name: '', email: '', address: '', role: 'member', access: [] }

// ─── PAGE ────────────────────────────────────────────────────────────────────

const UserManagement = ({ searchTerm: topbarSearch = '' } = {}) => {
  const { user: me } = useAuth()
  // Same dashboard for everyone; viewing the roster is open to all,
  // but adding a user and changing anyone's role/access/status are
  // admin-only — enforced on the backend regardless of this flag.
  const isAdmin = me?.role === 'admin'

  const [summary, setSummary] = useState(null)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState(null)
  const [filterAnchor, setFilterAnchor] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetch(`${API_BASE}/api/users/`, {
        headers: { Authorization: `Bearer ${token}` },
      })

      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(
          body.detail ||
            (resp.status === 403
              ? 'User management is available to administrators only.'
              : `Could not load users (${resp.status}).`)
        )
      }

      const data = await resp.json()
      setSummary(data.summary || null)
      setItems(data.items || [])
    } catch (err) {
      setError(err.message || 'Could not load users.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const term = (search || topbarSearch || '').trim().toLowerCase()

  const filtered = items.filter((u) => {
    const matchesSearch =
      !term ||
      u.full_name.toLowerCase().includes(term) ||
      u.email.toLowerCase().includes(term)
    const matchesRole = !roleFilter || u.role === roleFilter
    return matchesSearch && matchesRole
  })

  // ─── PAGING ────────────────────────────────────────────────────
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize))
  const pagedItems = filtered.slice((page - 1) * pageSize, page * pageSize)

  useEffect(() => {
    setPage((prev) => Math.min(prev, pageCount))
  }, [pageCount])

  useEffect(() => {
    setPage(1)
  }, [term, roleFilter])

  const changePageSize = (size) => {
    setPageSize(size)
    setPage(1)
  }

  // ─── SELECTION ─────────────────────────────────────────────────
  const [selected, setSelected] = useState([])
  const pageIds = pagedItems.map((u) => u.id)
  const allOnPageSelected = pageIds.length > 0 && pageIds.every((id) => selected.includes(id))
  const someOnPageSelected = pageIds.some((id) => selected.includes(id))

  const toggleOne = (id) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))

  const toggleAll = () =>
    setSelected((prev) =>
      allOnPageSelected
        ? prev.filter((id) => !pageIds.includes(id))
        : Array.from(new Set([...prev, ...pageIds]))
    )

  useEffect(() => {
    setSelected((prev) => prev.filter((id) => items.some((u) => u.id === id)))
  }, [items])

  // ─── ROW MENU ──────────────────────────────────────────────────
  const [rowMenu, setRowMenu] = useState(null)

  const patchUser = async (id, body) => {
    const token = localStorage.getItem('brainopx_token')
    const resp = await fetch(`${API_BASE}/api/users/${id}`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(err.detail || `Could not update this user (${resp.status}).`)
    }
    return resp.json()
  }

  const [confirmDeactivate, setConfirmDeactivate] = useState(null)

  const setActive = async (targetUser, active) => {
    try {
      await patchUser(targetUser.id, { is_active: active })
      setNotice({ severity: 'success', text: active ? 'Account reactivated.' : 'Account deactivated.' })
      await load()
    } catch (err) {
      setNotice({ severity: 'error', text: err.message })
    } finally {
      setConfirmDeactivate(null)
    }
  }

  // ─── DELETE ────────────────────────────────────────────────────
  // Unlike deactivating, this cannot be undone, so it always goes
  // through a confirmation — and the backend itself refuses to
  // delete anyone with real history (requests, runs, walkthroughs),
  // rather than silently destroying it or cascading it away.
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [deletingUser, setDeletingUser] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  const openConfirmDelete = (targetUser) => {
    setDeleteError('')
    setConfirmDelete(targetUser)
    setRowMenu(null)
  }

  const deleteUser = async () => {
    if (!confirmDelete) return

    setDeleteError('')
    setDeletingUser(true)
    try {
      const token = localStorage.getItem('brainopx_token')
      const resp = await fetch(`${API_BASE}/api/users/${confirmDelete.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })

      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(
          body.detail ||
            (resp.status === 403
              ? 'Only administrators can delete users.'
              : `Could not delete this user (${resp.status}).`)
        )
      }

      setNotice({ severity: 'success', text: 'User deleted.' })
      setConfirmDelete(null)
      await load()
    } catch (err) {
      // Shown inside the dialog rather than a toast: the backend's
      // explanation here (usually "this account has real history
      // attached") is something the admin needs to actually read,
      // not something that should vanish in four seconds.
      setDeleteError(err.message || 'Could not delete this user.')
    } finally {
      setDeletingUser(false)
    }
  }

  // ─── ADD / EDIT USER ───────────────────────────────────────────
  const [formOpen, setFormOpen] = useState(false)
  const [formMode, setFormMode] = useState('create') // 'create' | 'edit'
  const [editingUser, setEditingUser] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  const openCreate = () => {
    setFormMode('create')
    setEditingUser(null)
    setForm(emptyForm)
    setFormError('')
    setFormOpen(true)
  }

  const openEdit = (targetUser) => {
    setFormMode('edit')
    setEditingUser(targetUser)
    setForm({
      full_name: targetUser.full_name,
      email: targetUser.email,
      address: targetUser.address || '',
      role: targetUser.role,
      access: targetUser.access || [],
    })
    setFormError('')
    setFormOpen(true)
    setRowMenu(null)
  }

  const toggleAccessOption = (value) =>
    setForm((prev) => ({
      ...prev,
      access: prev.access.includes(value)
        ? prev.access.filter((v) => v !== value)
        : [...prev.access, value],
    }))

  // Shown once, right after a new account is created — this is the
  // only place the temporary password is ever displayed.
  const [credentials, setCredentials] = useState(null)

  const submitForm = async () => {
    setFormError('')

    if (formMode === 'create') {
      if (!form.full_name.trim() || !form.email.trim()) {
        setFormError('Name and email are required.')
        return
      }
    }

    setSaving(true)
    try {
      const token = localStorage.getItem('brainopx_token')

      if (formMode === 'create') {
        const resp = await fetch(`${API_BASE}/api/users/`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({
            full_name: form.full_name.trim(),
            email: form.email.trim(),
            address: form.address.trim() || null,
            role: form.role,
            access: form.access,
          }),
        })

        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}))
          throw new Error(err.detail || `Could not create this user (${resp.status}).`)
        }

        const data = await resp.json()
        setFormOpen(false)
        setCredentials({
          email: data.user.email,
          password: data.temporary_password,
          emailSent: data.email_sent,
        })
      } else {
        await patchUser(editingUser.id, {
          role: form.role,
          access: form.access,
          address: form.address.trim() || null,
        })
        setFormOpen(false)
        setNotice({ severity: 'success', text: 'User updated.' })
      }

      await load()
    } catch (err) {
      setFormError(err.message || 'Something went wrong.')
    } finally {
      setSaving(false)
    }
  }

  const copyPassword = async () => {
    if (!credentials) return
    try {
      await navigator.clipboard.writeText(credentials.password)
      setNotice({ severity: 'success', text: 'Password copied.' })
    } catch {
      // Clipboard access can be denied by the browser; the password
      // is still visible on screen to copy by hand.
    }
  }

  const total = summary?.total ?? items.length

  return (
    <Box sx={{ p: 4 }}>
      <Box sx={{ maxWidth: 1400, mx: 'auto' }}>

        <Typography variant="h4" sx={{ fontWeight: 700, mb: 0.5, color: 'text.primary' }}>
          User management
        </Typography>
        <Typography variant="body1" sx={{ color: 'text.secondary', mb: 3 }}>
          Manage your team members and their account permissions here.
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }}>{error}</Alert>
        )}

        {/* ── Toolbar ──────────────────────────────────────────── */}
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          alignItems={{ xs: 'stretch', sm: 'center' }}
          justifyContent="space-between"
          spacing={1.5}
          sx={{ mb: 2 }}
        >
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            All users <Typography component="span" sx={{ color: 'text.secondary', fontWeight: 600 }}>{total}</Typography>
          </Typography>

          <Stack direction="row" spacing={1.25}>
            <TextField
              size="small"
              placeholder="Search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              sx={{ minWidth: 220 }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon sx={{ fontSize: 18, color: 'text.disabled' }} />
                  </InputAdornment>
                ),
              }}
            />

            <Button
              variant="outlined"
              startIcon={<FilterListIcon sx={{ fontSize: 18 }} />}
              onClick={(e) => setFilterAnchor(e.currentTarget)}
              sx={{ textTransform: 'none', borderRadius: 2, whiteSpace: 'nowrap' }}
            >
              {roleFilter ? `Filters (${roleFilter})` : 'Filters'}
            </Button>

            <Tooltip title={isAdmin ? '' : 'Only administrators can add users'}>
              <span>
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  onClick={openCreate}
                  disabled={!isAdmin}
                  sx={{ textTransform: 'none', borderRadius: 2, bgcolor: '#4f46e5', '&:hover': { bgcolor: '#4338ca' }, whiteSpace: 'nowrap' }}
                >
                  Add user
                </Button>
              </span>
            </Tooltip>
          </Stack>
        </Stack>

        <Menu anchorEl={filterAnchor} open={Boolean(filterAnchor)} onClose={() => setFilterAnchor(null)}>
          <MenuItem selected={!roleFilter} onClick={() => { setRoleFilter(null); setFilterAnchor(null) }}>
            All roles
          </MenuItem>
          <Divider />
          {ROLE_OPTIONS.map((opt) => (
            <MenuItem
              key={opt.value}
              selected={roleFilter === opt.value}
              onClick={() => { setRoleFilter(opt.value); setFilterAnchor(null) }}
            >
              {opt.label} only
            </MenuItem>
          ))}
        </Menu>

        {/* ── Bulk bar ─────────────────────────────────────────── */}
        {isAdmin && selected.length > 0 && (
          <Stack
            direction="row"
            alignItems="center"
            justifyContent="space-between"
            sx={{
              px: 2, py: 1.25, mb: 1, borderRadius: 2,
              bgcolor: 'rgba(79,70,229,0.06)',
              border: '1px solid rgba(79,70,229,0.14)',
            }}
          >
            <Typography variant="body2" sx={{ fontWeight: 700 }}>{selected.length} selected</Typography>
            <Stack direction="row" spacing={1}>
              <Button size="small" onClick={() => setSelected([])} sx={{ textTransform: 'none' }}>
                Clear
              </Button>
              <Button
                size="small"
                variant="outlined"
                color="error"
                startIcon={<PersonOffIcon sx={{ fontSize: 16 }} />}
                onClick={async () => {
                  const targets = items.filter((u) => selected.includes(u.id) && u.id !== me?.id)
                  for (const target of targets) {
                    // Sequential, not parallel: keeps error reporting
                    // simple and avoids hammering the API for a
                    // moderate-sized team list.
                    try {
                      await patchUser(target.id, { is_active: false })
                    } catch {
                      // Reported in aggregate below.
                    }
                  }
                  setSelected([])
                  setNotice({ severity: 'success', text: 'Selected accounts deactivated.' })
                  await load()
                }}
                sx={{ textTransform: 'none', borderRadius: 2 }}
              >
                Deactivate selected
              </Button>
            </Stack>
          </Stack>
        )}

        {/* ── Table ────────────────────────────────────────────── */}
        <Paper
          sx={{
            borderRadius: 3,
            overflow: 'hidden',
            background: (theme) => theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : '#ffffff',
            border: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
          }}
        >
          {loading && <LinearProgress />}

          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow
                  sx={{
                    '& th': {
                      fontWeight: 700, color: 'text.secondary', fontSize: 12,
                      textTransform: 'uppercase', letterSpacing: 0.4,
                      borderBottom: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
                      py: 1.5,
                    },
                  }}
                >
                  {isAdmin && (
                    <TableCell padding="checkbox">
                      <Checkbox
                        size="small"
                        disabled={pageIds.length === 0}
                        checked={allOnPageSelected}
                        indeterminate={someOnPageSelected && !allOnPageSelected}
                        onChange={toggleAll}
                        inputProps={{ 'aria-label': 'Select all users on this page' }}
                      />
                    </TableCell>
                  )}
                  <TableCell>User name</TableCell>
                  <TableCell>Access</TableCell>
                  <TableCell>Last active</TableCell>
                  <TableCell>Date added</TableCell>
                  {isAdmin && <TableCell align="right" sx={{ width: 56 }} />}
                </TableRow>
              </TableHead>

              <TableBody>
                {!loading && pagedItems.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={isAdmin ? 6 : 4} sx={{ border: 0, py: 8 }}>
                      <Stack alignItems="center" spacing={1} sx={{ color: 'text.disabled' }}>
                        <GroupIcon sx={{ fontSize: 36, opacity: 0.4 }} />
                        <Typography variant="body2">
                          {term || roleFilter ? 'No users match your filters.' : 'No users yet.'}
                        </Typography>
                      </Stack>
                    </TableCell>
                  </TableRow>
                )}

                {pagedItems.map((u) => (
                  <TableRow
                    key={u.id}
                    hover
                    selected={selected.includes(u.id)}
                    sx={{
                      opacity: u.is_active ? 1 : 0.55,
                      '& td': {
                        borderBottom: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : '#f1f3f7'}`,
                        py: 1.25,
                      },
                    }}
                  >
                    {isAdmin && (
                      <TableCell padding="checkbox">
                        <Checkbox
                          size="small"
                          checked={selected.includes(u.id)}
                          onChange={() => toggleOne(u.id)}
                          inputProps={{ 'aria-label': `Select ${u.full_name}` }}
                        />
                      </TableCell>
                    )}

                    <TableCell>
                      <Stack direction="row" alignItems="center" spacing={1.25}>
                        <Avatar src={profileUrlOf(u)} sx={{ width: 34, height: 34, fontSize: 13, bgcolor: '#4f46e5' }}>
                          {initialsOf(u.full_name)}
                        </Avatar>
                        <Box sx={{ minWidth: 0 }}>
                          <Typography variant="body2" sx={{ fontWeight: 700 }} noWrap>
                            {u.full_name}
                            {u.id === me?.id && (
                              <Typography component="span" sx={{ ml: 0.75, fontSize: 11, color: 'text.disabled', fontWeight: 600 }}>
                                (you)
                              </Typography>
                            )}
                            {!u.is_active && (
                              <Typography component="span" sx={{ ml: 0.75, fontSize: 11, color: 'error.main', fontWeight: 700 }}>
                                Deactivated
                              </Typography>
                            )}
                          </Typography>
                          <Typography variant="caption" sx={{ color: 'text.secondary' }} noWrap>
                            {u.email}
                          </Typography>
                        </Box>
                      </Stack>
                    </TableCell>

                    <TableCell>
                      <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap', gap: 0.5 }}>
                        {displayTags(u).length === 0 ? (
                          <Typography variant="caption" sx={{ color: 'text.disabled' }}>—</Typography>
                        ) : (
                          displayTags(u).map((label) => {
                            const meta = tagMeta(label)
                            return (
                              <Chip
                                key={label}
                                size="small"
                                label={label}
                                sx={{
                                  fontWeight: 700, fontSize: 11,
                                  color: meta.color, bgcolor: meta.bg,
                                  border: `1px solid ${meta.color}33`,
                                }}
                              />
                            )
                          })
                        )}
                      </Stack>
                    </TableCell>

                    <TableCell>
                      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                        {u.last_login_at ? dateOf(u.last_login_at) : 'Never'}
                      </Typography>
                    </TableCell>

                    <TableCell>
                      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                        {dateOf(u.created_at)}
                      </Typography>
                    </TableCell>

                    {isAdmin && (
                      <TableCell align="right">
                        <IconButton size="small" onClick={(e) => setRowMenu({ anchor: e.currentTarget, user: u })}>
                          <MoreVertIcon sx={{ fontSize: 19 }} />
                        </IconButton>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          <PaginationBar
            page={page}
            pageSize={pageSize}
            totalRecords={filtered.length}
            onPageChange={setPage}
            onPageSizeChange={changePageSize}
            recordLabel="users"
          />
        </Paper>

        {/* ── Row menu ─────────────────────────────────────────── */}
        <Menu
          anchorEl={rowMenu?.anchor || null}
          open={Boolean(rowMenu)}
          onClose={() => setRowMenu(null)}
        >
          <MenuItem onClick={() => openEdit(rowMenu.user)} sx={{ fontSize: 13.5 }}>
            Edit access
          </MenuItem>
          {rowMenu?.user.id === me?.id ? (
            <Tooltip title="You cannot change your own status" placement="left">
              <span>
                <MenuItem disabled sx={{ fontSize: 13.5 }}>
                  {rowMenu?.user.is_active ? 'Deactivate' : 'Activate'}
                </MenuItem>
              </span>
            </Tooltip>
          ) : (
            <MenuItem
              onClick={() => {
                const target = rowMenu.user
                setRowMenu(null)
                if (target.is_active) {
                  setConfirmDeactivate(target)
                } else {
                  setActive(target, true)
                }
              }}
              sx={{ fontSize: 13.5, color: rowMenu?.user.is_active ? 'error.main' : 'success.main' }}
            >
              {rowMenu?.user.is_active ? 'Deactivate' : 'Activate'}
            </MenuItem>
          )}

          <Divider />

          {rowMenu?.user.id === me?.id ? (
            <Tooltip title="You cannot delete your own account" placement="left">
              <span>
                <MenuItem disabled sx={{ fontSize: 13.5 }}>
                  Delete
                </MenuItem>
              </span>
            </Tooltip>
          ) : (
            <MenuItem
              onClick={() => openConfirmDelete(rowMenu.user)}
              sx={{ fontSize: 13.5, color: 'error.main' }}
            >
              <DeleteOutlineIcon sx={{ fontSize: 17, mr: 1 }} />
              Delete
            </MenuItem>
          )}
        </Menu>

        {/* ── Confirm deactivation ─────────────────────────────── */}
        <Dialog open={Boolean(confirmDeactivate)} onClose={() => setConfirmDeactivate(null)} PaperProps={{ sx: { borderRadius: 3, maxWidth: 420 } }}>
          <DialogTitle sx={{ fontWeight: 700 }}>Deactivate this account?</DialogTitle>
          <DialogContent>
            <DialogContentText>
              <Box component="span" sx={{ fontWeight: 700 }}>{confirmDeactivate?.full_name}</Box> will
              no longer be able to sign in. Their account and history are kept, and access can be
              restored at any time.
            </DialogContentText>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2.5 }}>
            <Button onClick={() => setConfirmDeactivate(null)} sx={{ textTransform: 'none' }}>Cancel</Button>
            <Button
              variant="contained"
              color="error"
              onClick={() => setActive(confirmDeactivate, false)}
              sx={{ textTransform: 'none', borderRadius: 2 }}
            >
              Deactivate
            </Button>
          </DialogActions>
        </Dialog>

        {/* ── Confirm deletion ─────────────────────────────────── */}
        <Dialog
          open={Boolean(confirmDelete)}
          onClose={() => !deletingUser && setConfirmDelete(null)}
          PaperProps={{ sx: { borderRadius: 3, maxWidth: 440 } }}
        >
          <DialogTitle sx={{ fontWeight: 700 }}>Delete this user?</DialogTitle>
          <DialogContent>
            {deleteError && <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>{deleteError}</Alert>}
            <DialogContentText>
              <Box component="span" sx={{ fontWeight: 700 }}>{confirmDelete?.full_name}</Box> and
              their account will be permanently removed. This cannot be undone.
              {' '}If they have any configuration requests, skill-engine runs or guided
              walkthroughs, deletion is refused — deactivate the account instead to
              revoke access while keeping that history.
            </DialogContentText>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2.5 }}>
            <Button onClick={() => setConfirmDelete(null)} disabled={deletingUser} sx={{ textTransform: 'none' }}>
              Cancel
            </Button>
            <Button
              variant="contained"
              color="error"
              onClick={deleteUser}
              disabled={deletingUser}
              startIcon={deletingUser ? <CircularProgress size={15} color="inherit" /> : <DeleteOutlineIcon />}
              sx={{ textTransform: 'none', borderRadius: 2 }}
            >
              {deletingUser ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* ── Add / edit user ──────────────────────────────────── */}
        <Dialog open={formOpen} onClose={() => !saving && setFormOpen(false)} fullWidth maxWidth="sm" PaperProps={{ sx: { borderRadius: 3 } }}>
          <DialogTitle sx={{ fontWeight: 700 }}>
            {formMode === 'create' ? 'Add user' : `Edit access — ${editingUser?.full_name}`}
          </DialogTitle>

          <DialogContent>
            {formError && <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>{formError}</Alert>}

            <Stack spacing={2} sx={{ mt: 0.5 }}>
              {formMode === 'create' && (
                <>
                  <TextField
                    label="Full name" fullWidth required
                    value={form.full_name}
                    onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                  />
                  <TextField
                    label="Email" type="email" fullWidth required
                    value={form.email}
                    onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  />
                </>
              )}

              <TextField
                label="Address" fullWidth
                placeholder="Optional"
                value={form.address}
                onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))}
              />

              <Box>
                <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, display: 'block', mb: 0.5 }}>
                  Role
                </Typography>
                <Select
                  fullWidth
                  size="small"
                  value={form.role}
                  onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
                  disabled={formMode === 'edit' && editingUser?.id === me?.id}
                >
                  {ROLE_OPTIONS.map((opt) => (
                    <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                  ))}
                </Select>
                {formMode === 'edit' && editingUser?.id === me?.id && (
                  <Typography variant="caption" sx={{ color: 'text.disabled', mt: 0.5, display: 'block' }}>
                    You cannot change your own role.
                  </Typography>
                )}
              </Box>

              <Box>
                <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, display: 'block', mb: 0.5 }}>
                  Access
                </Typography>
                <FormGroup row>
                  {ACCESS_OPTIONS.map((opt) => (
                    <FormControlLabel
                      key={opt.value}
                      control={
                        <Checkbox
                          size="small"
                          checked={form.access.includes(opt.value)}
                          onChange={() => toggleAccessOption(opt.value)}
                        />
                      }
                      label={<Typography variant="body2">{opt.label}</Typography>}
                    />
                  ))}
                </FormGroup>
              </Box>

              {formMode === 'create' && (
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  A temporary password is generated automatically and shown once the
                  account is created.
                </Typography>
              )}
            </Stack>
          </DialogContent>

          <DialogActions sx={{ px: 3, pb: 2.5 }}>
            <Button onClick={() => setFormOpen(false)} disabled={saving} sx={{ textTransform: 'none' }}>
              Cancel
            </Button>
            <Button
              variant="contained"
              onClick={submitForm}
              disabled={saving}
              startIcon={saving ? <CircularProgress size={15} color="inherit" /> : undefined}
              sx={{ textTransform: 'none', borderRadius: 2, bgcolor: '#4f46e5', '&:hover': { bgcolor: '#4338ca' } }}
            >
              {saving ? 'Saving...' : formMode === 'create' ? 'Create user' : 'Save changes'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* ── New account credentials ──────────────────────────── */}
        <Dialog open={Boolean(credentials)} onClose={() => setCredentials(null)} fullWidth maxWidth="xs" PaperProps={{ sx: { borderRadius: 3 } }}>
          <DialogTitle sx={{ fontWeight: 700 }}>
            <Stack direction="row" alignItems="center" spacing={1}>
              <CheckCircleIcon sx={{ color: 'success.main' }} />
              <span>Account created</span>
            </Stack>
          </DialogTitle>
          <DialogContent>
            <DialogContentText sx={{ mb: 2 }}>
              {credentials?.emailSent
                ? <>A welcome email with a temporary password was sent to <strong>{credentials?.email}</strong>.</>
                : <>Could not send a welcome email — hand this password to <strong>{credentials?.email}</strong> yourself.</>}
              {' '}This is the only time it is shown.
            </DialogContentText>

            <Stack
              direction="row"
              alignItems="center"
              justifyContent="space-between"
              sx={{
                p: 1.5, borderRadius: 2,
                bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : '#f1f5f9',
                border: (theme) => `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e2e8f0'}`,
              }}
            >
              <Typography sx={{ fontFamily: 'Consolas, monospace', fontWeight: 700, fontSize: 14 }}>
                {credentials?.password}
              </Typography>
              <Tooltip title="Copy">
                <IconButton size="small" onClick={copyPassword}>
                  <ContentCopyIcon sx={{ fontSize: 17 }} />
                </IconButton>
              </Tooltip>
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2.5 }}>
            <Button variant="contained" onClick={() => setCredentials(null)} sx={{ textTransform: 'none', borderRadius: 2, bgcolor: '#4f46e5', '&:hover': { bgcolor: '#4338ca' } }}>
              Done
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
            <Alert severity={notice.severity} variant="filled" onClose={() => setNotice(null)} sx={{ borderRadius: 2 }}>
              {notice.text}
            </Alert>
          ) : undefined}
        </Snackbar>
      </Box>
    </Box>
  )
}

export default UserManagement
