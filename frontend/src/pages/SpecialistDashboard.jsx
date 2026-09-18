import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  Alert,
  Avatar,
  Badge,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  InputBase,
  List,
  ListItem,
  ListItemButton,
  Paper,
  Snackbar,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import LogoutIconImport from '@mui/icons-material/Logout'
import SearchIconImport from '@mui/icons-material/Search'
import SendIconImport from '@mui/icons-material/Send'
import CheckCircleIconImport from '@mui/icons-material/CheckCircle'
import ReplayIconImport from '@mui/icons-material/Replay'
import AssignmentIndIconImport from '@mui/icons-material/AssignmentInd'
import InboxIconImport from '@mui/icons-material/Inbox'
import { useAuth } from '../context/AuthContext.jsx'
import { useNavigate } from 'react-router-dom'
import {
  listSpecialistTickets,
  getSpecialistTicket,
  sendSpecialistReply,
  claimTicket,
  resolveTicket,
  reopenTicket,
} from '../services/supportService.js'

const LogoutIcon = LogoutIconImport?.default || LogoutIconImport
const SearchIcon = SearchIconImport?.default || SearchIconImport
const SendIcon = SendIconImport?.default || SendIconImport
const CheckCircleIcon = CheckCircleIconImport?.default || CheckCircleIconImport
const ReplayIcon = ReplayIconImport?.default || ReplayIconImport
const AssignmentIndIcon = AssignmentIndIconImport?.default || AssignmentIndIconImport
const InboxIcon = InboxIconImport?.default || InboxIconImport

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const STATUS_META = {
  open: { label: 'Open', color: '#f59e0b', bg: 'rgba(245,158,11,0.14)' },
  claimed: { label: 'Claimed', color: '#3b66ff', bg: 'rgba(59,102,255,0.14)' },
  resolved: { label: 'Resolved', color: '#10b981', bg: 'rgba(16,185,129,0.14)' },
}

const FILTERS = [
  { key: '', label: 'All' },
  { key: 'open', label: 'Open' },
  { key: 'claimed', label: 'Claimed' },
  { key: 'resolved', label: 'Resolved' },
]

const timeAgo = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const mins = Math.floor((Date.now() - date.getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return date.toLocaleDateString()
}

const initialsOf = (name) =>
  name
    ? name.split(' ').filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('')
    : '?'

const SpecialistDashboard = () => {
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  const [tickets, setTickets] = useState([])
  const [filter, setFilter] = useState('')
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const [thread, setThread] = useState(null)
  const [loadingList, setLoadingList] = useState(true)
  const [loadingThread, setLoadingThread] = useState(false)
  const [reply, setReply] = useState('')
  const [sending, setSending] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const messagesEndRef = useRef(null)

  const loadList = useCallback(async () => {
    try {
      const data = await listSpecialistTickets(filter)
      setTickets(data)
    } catch (err) {
      setError(err.message || 'Could not load tickets.')
    } finally {
      setLoadingList(false)
    }
  }, [filter])

  useEffect(() => {
    loadList()
    const interval = setInterval(loadList, 20000)
    return () => clearInterval(interval)
  }, [loadList])

  const loadThread = useCallback(async (id) => {
    setLoadingThread(true)
    try {
      const data = await getSpecialistTicket(id)
      setThread(data)
      // The thread's unread count just reset — refresh the list badge.
      loadList()
    } catch (err) {
      setError(err.message || 'Could not load this request.')
    } finally {
      setLoadingThread(false)
    }
  }, [loadList])

  useEffect(() => {
    if (selectedId != null) {
      loadThread(selectedId)
    }
  }, [selectedId, loadThread])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [thread?.messages?.length])

  const handleSelect = (ticket) => {
    setSelectedId(ticket.id)
  }

  const handleSend = async () => {
    const body = reply.trim()
    if (!body || selectedId == null) return

    setSending(true)
    try {
      await sendSpecialistReply(selectedId, body)
      setReply('')
      await loadThread(selectedId)
    } catch (err) {
      setError(err.message || 'Could not send reply.')
    } finally {
      setSending(false)
    }
  }

  const handleClaim = async () => {
    if (selectedId == null) return
    try {
      await claimTicket(selectedId)
      setNotice('Request claimed.')
      await loadThread(selectedId)
    } catch (err) {
      setError(err.message || 'Could not claim.')
    }
  }

  const handleResolve = async () => {
    if (selectedId == null) return
    try {
      await resolveTicket(selectedId)
      setNotice('Request resolved.')
      await loadThread(selectedId)
    } catch (err) {
      setError(err.message || 'Could not resolve.')
    }
  }

  const handleReopen = async () => {
    if (selectedId == null) return
    try {
      await reopenTicket(selectedId)
      setNotice('Request reopened.')
      await loadThread(selectedId)
    } catch (err) {
      setError(err.message || 'Could not reopen.')
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/specialist/login')
  }

  const term = search.trim().toLowerCase()
  const filteredTickets = tickets.filter((t) => {
    if (!term) return true
    const haystack = `${t.subject} ${t.user_name || ''} ${t.user_email || ''}`.toLowerCase()
    return haystack.includes(term)
  })

  const totalUnread = tickets.reduce((sum, t) => sum + (t.unread_count || 0), 0)
  const selectedTicket = tickets.find((t) => t.id === selectedId) || thread?.ticket

  return (
    <Box sx={{ display: 'flex', height: '100vh', bgcolor: '#f4f6fb' }}>
      {/* ── Left: inbox ─────────────────────────────────── */}
      <Box
        sx={{
          width: 360,
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          bgcolor: '#fff',
          borderRight: '1px solid #e5e7eb',
        }}
      >
        <Box sx={{ px: 3, py: 2.5, borderBottom: '1px solid #eef0f4' }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 800, color: '#1e293b' }}>
                Specialist Portal
              </Typography>
              <Typography variant="caption" sx={{ color: '#64748b' }}>
                {totalUnread} unread request{totalUnread === 1 ? '' : 's'}
              </Typography>
            </Box>
            <IconButton onClick={handleLogout} title="Sign out" sx={{ color: '#64748b' }}>
              <LogoutIcon fontSize="small" />
            </IconButton>
          </Stack>

          <Paper
            sx={{
              display: 'flex',
              alignItems: 'center',
              mt: 2,
              px: 1.5,
              py: 0.5,
              borderRadius: 2.5,
              border: '1px solid #e5e7eb',
              boxShadow: 'none',
            }}
          >
            <SearchIcon fontSize="small" sx={{ color: '#94a3b8', mr: 1 }} />
            <InputBase
              placeholder="Search requests…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              fullWidth
              sx={{ fontSize: 14 }}
            />
          </Paper>

          <Stack direction="row" spacing={0.5} sx={{ mt: 1.5 }}>
            {FILTERS.map((f) => (
              <Chip
                key={f.key || 'all'}
                label={f.label}
                size="small"
                onClick={() => setFilter(f.key)}
                variant={filter === f.key ? 'filled' : 'outlined'}
                sx={{
                  fontWeight: 600,
                  ...(filter === f.key
                    ? { bgcolor: '#3b66ff', color: '#fff', '&:hover': { bgcolor: '#2f56e0' } }
                    : { color: '#475569', borderColor: '#e2e8f0' }),
                }}
              />
            ))}
          </Stack>
        </Box>

        <List sx={{ flex: 1, overflowY: 'auto', py: 1 }}>
          {loadingList ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress size={24} />
            </Box>
          ) : filteredTickets.length === 0 ? (
            <Box sx={{ py: 6, textAlign: 'center', px: 3 }}>
              <InboxIcon sx={{ fontSize: 40, color: '#cbd5e1', mb: 1 }} />
              <Typography variant="body2" color="text.secondary">
                No requests match this view.
              </Typography>
            </Box>
          ) : (
            filteredTickets.map((ticket) => {
              const meta = STATUS_META[ticket.status] || STATUS_META.open
              const active = ticket.id === selectedId
              return (
                <ListItem key={ticket.id} disablePadding sx={{ px: 1.5, mb: 0.5 }}>
                  <ListItemButton
                    onClick={() => handleSelect(ticket)}
                    sx={{
                      borderRadius: 2.5,
                      px: 1.5,
                      py: 1.25,
                      bgcolor: active ? 'rgba(59,102,255,0.08)' : 'transparent',
                      '&:hover': { bgcolor: 'rgba(59,102,255,0.06)' },
                    }}
                  >
                    <Avatar sx={{ width: 34, height: 34, fontSize: 13, bgcolor: '#3b66ff', mr: 1.5 }}>
                      {initialsOf(ticket.user_name)}
                    </Avatar>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
                        <Typography
                          variant="body2"
                          noWrap
                          sx={{
                            fontWeight: ticket.unread_count ? 700 : 600,
                            color: '#1e293b',
                          }}
                        >
                          {ticket.subject}
                        </Typography>
                        {ticket.unread_count > 0 && (
                          <Badge badgeContent={ticket.unread_count} color="error" sx={{ flexShrink: 0 }} />
                        )}
                      </Stack>
                      <Typography
                        variant="caption"
                        noWrap
                        sx={{ display: 'block', color: '#64748b', mt: 0.25 }}
                      >
                        {ticket.user_name || ticket.user_email}
                      </Typography>
                      <Stack direction="row" alignItems="center" spacing={1} sx={{ mt: 0.5 }}>
                        <Chip
                          label={meta.label}
                          size="small"
                          sx={{
                            height: 18,
                            fontSize: 10,
                            fontWeight: 700,
                            color: meta.color,
                            bgcolor: meta.bg,
                          }}
                        />
                        <Typography variant="caption" sx={{ color: '#94a3b8' }}>
                          {timeAgo(ticket.last_message_at || ticket.updated_at)}
                        </Typography>
                      </Stack>
                    </Box>
                  </ListItemButton>
                </ListItem>
              )
            })
          )}
        </List>
      </Box>

      {/* ── Right: thread ───────────────────────────────── */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {loadingThread ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flex: 1 }}>
            <CircularProgress size={28} />
          </Box>
        ) : !selectedTicket || !thread ? (
          <Box
            sx={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#94a3b8',
            }}
          >
            <InboxIcon sx={{ fontSize: 56, mb: 2, color: '#cbd5e1' }} />
            <Typography variant="body1" sx={{ fontWeight: 600, color: '#64748b' }}>
              Select a request
            </Typography>
            <Typography variant="body2">Choose a request on the left to view and respond.</Typography>
          </Box>
        ) : (
          <>
            {/* Header */}
            <Box
              sx={{
                px: 3,
                py: 2,
                bgcolor: '#fff',
                borderBottom: '1px solid #eef0f4',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 2,
              }}
            >
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="h6" noWrap sx={{ fontWeight: 800, color: '#1e293b' }}>
                  {selectedTicket.subject}
                </Typography>
                <Typography variant="caption" sx={{ color: '#64748b' }}>
                  {selectedTicket.user_name || 'Unknown user'}
                  {selectedTicket.user_email ? ` — ${selectedTicket.user_email}` : ''}
                </Typography>
              </Box>
              <Stack direction="row" spacing={1}>
                {selectedTicket.status !== 'resolved' && (
                  <>
                    {selectedTicket.status === 'open' && (
                      <Button
                        size="small"
                        startIcon={<AssignmentIndIcon fontSize="small" />}
                        onClick={handleClaim}
                        sx={{ textTransform: 'none', fontWeight: 700 }}
                      >
                        Claim
                      </Button>
                    )}
                    <Button
                      size="small"
                      variant="contained"
                      color="success"
                      startIcon={<CheckCircleIcon fontSize="small" />}
                      onClick={handleResolve}
                      sx={{ textTransform: 'none', fontWeight: 700 }}
                    >
                      Resolve
                    </Button>
                  </>
                )}
                {selectedTicket.status === 'resolved' && (
                  <Button
                    size="small"
                    startIcon={<ReplayIcon fontSize="small" />}
                    onClick={handleReopen}
                    sx={{ textTransform: 'none', fontWeight: 700 }}
                  >
                    Reopen
                  </Button>
                )}
              </Stack>
            </Box>

            {/* Messages */}
            <Box sx={{ flex: 1, overflowY: 'auto', px: 3, py: 3 }}>
              <Stack spacing={1.5}>
                {thread.messages.map((message) => {
                  const role = message.sender_role
                  const isSpecialist = role === 'specialist'
                  const isAssistant = role === 'assistant'
                  const isSystem = role === 'system'

                  if (isSystem) {
                    return (
                      <Box key={message.id} sx={{ display: 'flex', justifyContent: 'center', py: 0.5 }}>
                        <Paper
                          elevation={0}
                          sx={{
                            maxWidth: '80%',
                            px: 2,
                            py: 0.75,
                            borderRadius: 2,
                            bgcolor: 'rgba(245,158,11,0.12)',
                            color: '#92400e',
                            border: '1px dashed rgba(245,158,11,0.5)',
                          }}
                        >
                          <Typography
                            variant="caption"
                            sx={{ fontWeight: 700, whiteSpace: 'pre-wrap', lineHeight: 1.5, display: 'block' }}
                          >
                            {message.body}
                          </Typography>
                          <Typography
                            variant="caption"
                            sx={{ display: 'block', textAlign: 'center', color: 'rgba(146,64,14,0.7)', mt: 0.25 }}
                          >
                            {timeAgo(message.created_at)}
                          </Typography>
                        </Paper>
                      </Box>
                    )
                  }

                  const alignRight = isSpecialist
                  const bgcolor = isSpecialist ? '#3b66ff' : isAssistant ? '#eef2ff' : '#fff'
                  const color = isSpecialist ? '#fff' : isAssistant ? '#334155' : '#1e293b'
                  const border = isSpecialist ? 'none' : '1px solid #e5e7eb'
                  const labelColor = isSpecialist
                    ? 'rgba(255,255,255,0.8)'
                    : isAssistant
                      ? '#6366f1'
                      : '#3b66ff'
                  const label = isSpecialist
                    ? 'You'
                    : isAssistant
                      ? 'BRAINOPX AI Assistant'
                      : message.sender_name || 'User'

                  return (
                    <Box
                      key={message.id}
                      sx={{
                        display: 'flex',
                        justifyContent: alignRight ? 'flex-end' : 'flex-start',
                      }}
                    >
                      <Paper
                        elevation={0}
                        sx={{
                          maxWidth: '70%',
                          px: 2,
                          py: 1.25,
                          borderRadius: 3,
                          bgcolor,
                          color,
                          border,
                        }}
                      >
                        <Typography
                          variant="caption"
                          sx={{
                            display: 'block',
                            fontWeight: 700,
                            color: labelColor,
                            mb: 0.25,
                          }}
                        >
                          {label}
                        </Typography>
                        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
                          {message.body}
                        </Typography>
                        <Typography
                          variant="caption"
                          sx={{
                            display: 'block',
                            mt: 0.5,
                            textAlign: 'right',
                            color: isSpecialist ? 'rgba(255,255,255,0.7)' : '#94a3b8',
                          }}
                        >
                          {timeAgo(message.created_at)}
                        </Typography>
                      </Paper>
                    </Box>
                  )
                })}
                <div ref={messagesEndRef} />
              </Stack>
            </Box>

            {/* Composer */}
            <Box sx={{ px: 3, py: 2, bgcolor: '#fff', borderTop: '1px solid #eef0f4' }}>
              <Stack direction="row" spacing={1.5} alignItems="flex-end">
                <TextField
                  fullWidth
                  multiline
                  minRows={1}
                  maxRows={5}
                  placeholder={
                    selectedTicket.status === 'resolved'
                      ? 'Reopen the request to reply…'
                      : 'Write a reply…'
                  }
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSend()
                    }
                  }}
                  disabled={selectedTicket.status === 'resolved'}
                  sx={{ '& .MuiOutlinedInput-root': { borderRadius: 2.5 } }}
                />
                <Button
                  variant="contained"
                  disabled={sending || !reply.trim() || selectedTicket.status === 'resolved'}
                  onClick={handleSend}
                  sx={{
                    minWidth: 48,
                    height: 48,
                    px: 0,
                    borderRadius: 2.5,
                    background: 'linear-gradient(120deg, #3b66ff 0%, #2563eb 100%)',
                    '&:hover': { filter: 'brightness(1.05)' },
                  }}
                >
                  {sending ? <CircularProgress size={20} sx={{ color: '#fff' }} /> : <SendIcon />}
                </Button>
              </Stack>
            </Box>
          </>
        )}
      </Box>

      <Snackbar
        open={!!error || !!notice}
        autoHideDuration={4000}
        onClose={() => {
          setError('')
          setNotice('')
        }}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity={error ? 'error' : 'success'}
          onClose={() => {
            setError('')
            setNotice('')
          }}
          sx={{ width: '100%' }}
        >
          {error || notice}
        </Alert>
      </Snackbar>
    </Box>
  )
}

export default SpecialistDashboard
