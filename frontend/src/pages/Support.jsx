import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Paper,
  Snackbar,
  Stack,
  TextField,
  Typography,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material'
import AddIconImport from '@mui/icons-material/Add'
import SendIconImport from '@mui/icons-material/Send'
import SupportAgentIconImport from '@mui/icons-material/SupportAgent'
import { useTranslation } from 'react-i18next'
import {
  listMyTickets,
  getMyTicket,
  sendUserReply,
  createSupportTicket,
} from '../services/supportService.js'

const AddIcon = AddIconImport?.default || AddIconImport
const SendIcon = SendIconImport?.default || SendIconImport
const SupportAgentIcon = SupportAgentIconImport?.default || SupportAgentIconImport

const STATUS_META = {
  open: { label: 'Open', color: '#f59e0b', bg: 'rgba(245,158,11,0.14)' },
  claimed: { label: 'Claimed', color: '#3b66ff', bg: 'rgba(59,102,255,0.14)' },
  resolved: { label: 'Resolved', color: '#10b981', bg: 'rgba(16,185,129,0.14)' },
}

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

const Support = () => {
  const { t } = useTranslation('pages')
  const [tickets, setTickets] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [thread, setThread] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadingThread, setLoadingThread] = useState(false)
  const [reply, setReply] = useState('')
  const [sending, setSending] = useState(false)
  const [composerOpen, setComposerOpen] = useState(false)
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [creating, setCreating] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const messagesEndRef = useRef(null)

  const load = useCallback(async () => {
    try {
      setTickets(await listMyTickets())
    } catch (err) {
      setError(err.message || 'Could not load your requests.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const openThread = useCallback(async (id) => {
    setLoadingThread(true)
    try {
      setThread(await getMyTicket(id))
      load()
    } catch (err) {
      setError(err.message || 'Could not open this request.')
    } finally {
      setLoadingThread(false)
    }
  }, [load])

  useEffect(() => {
    if (selectedId != null) openThread(selectedId)
  }, [selectedId, openThread])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [thread?.messages?.length])

  const handleSend = async () => {
    const text = reply.trim()
    if (!text || selectedId == null) return
    setSending(true)
    try {
      await sendUserReply(selectedId, text)
      setReply('')
      await openThread(selectedId)
    } catch (err) {
      setError(err.message || 'Could not send your reply.')
    } finally {
      setSending(false)
    }
  }

  const handleCreate = async () => {
    if (!subject.trim()) {
      setError('Please give your request a subject.')
      return
    }
    setCreating(true)
    try {
      const created = await createSupportTicket({ subject: subject.trim(), body: body.trim() })
      setComposerOpen(false)
      setSubject('')
      setBody('')
      await load()
      setSelectedId(created.id)
      setNotice('Request opened.')
    } catch (err) {
      setError(err.message || 'Could not open the request.')
    } finally {
      setCreating(false)
    }
  }

  const selectedTicket = tickets.find((tk) => tk.id === selectedId) || thread?.ticket

  return (
    <Box sx={{ px: { xs: 2, md: 4 }, py: 4, maxWidth: 1100, mx: 'auto' }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 3 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 800, color: 'text.primary' }}>
            {t('support.title', 'Support')}
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {t('support.subtitle', 'Talk to a BRAINOPX specialist and track your requests.')}
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setComposerOpen(true)}
          sx={{ textTransform: 'none', fontWeight: 700, borderRadius: 2.5 }}
        >
          {t('support.newRequest', 'New request')}
        </Button>
      </Stack>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress size={28} />
        </Box>
      ) : tickets.length === 0 ? (
        <Paper
          sx={{
            py: 8,
            px: 4,
            textAlign: 'center',
            borderRadius: 3,
            border: '1px dashed',
            borderColor: 'divider',
          }}
          elevation={0}
        >
          <SupportAgentIcon sx={{ fontSize: 52, color: 'text.disabled', mb: 1.5 }} />
          <Typography variant="h6" sx={{ fontWeight: 700, color: 'text.primary' }}>
            {t('support.noRequestsTitle', 'No support requests yet')}
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
            {t('support.noRequestsBody', 'Open a request when you need help from a specialist.')}
          </Typography>
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setComposerOpen(true)}>
            {t('support.newRequest', 'New request')}
          </Button>
        </Paper>
      ) : (
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2.5} alignItems="stretch">
          {/* List */}
          <Paper sx={{ width: { md: 320 }, flexShrink: 0, borderRadius: 3, overflow: 'hidden' }} elevation={1}>
            <Stack divider={<Divider />} sx={{ maxHeight: 560, overflowY: 'auto' }}>
              {tickets.map((ticket) => {
                const meta = STATUS_META[ticket.status] || STATUS_META.open
                const active = ticket.id === selectedId
                return (
                  <Box
                    key={ticket.id}
                    component="button"
                    onClick={() => setSelectedId(ticket.id)}
                    sx={{
                      textAlign: 'left',
                      px: 2,
                      py: 1.75,
                      cursor: 'pointer',
                      border: 'none',
                      background: active ? 'rgba(59,102,255,0.08)' : 'transparent',
                      '&:hover': { background: 'rgba(59,102,255,0.05)' },
                    }}
                  >
                    <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
                      <Typography
                        variant="body2"
                        noWrap
                        sx={{ fontWeight: ticket.unread_count ? 700 : 600, color: 'text.primary' }}
                      >
                        {ticket.subject}
                      </Typography>
                      {ticket.unread_count > 0 && (
                        <Chip
                          label={ticket.unread_count}
                          size="small"
                          sx={{ height: 18, minWidth: 18, fontSize: 10, fontWeight: 700, bgcolor: '#ef4444', color: '#fff' }}
                        />
                      )}
                    </Stack>
                    <Stack direction="row" alignItems="center" spacing={1} sx={{ mt: 0.5 }}>
                      <Chip
                        label={meta.label}
                        size="small"
                        sx={{ height: 18, fontSize: 10, fontWeight: 700, color: meta.color, bgcolor: meta.bg }}
                      />
                      <Typography variant="caption" sx={{ color: 'text.disabled' }}>
                        {timeAgo(ticket.last_message_at || ticket.updated_at)}
                      </Typography>
                    </Stack>
                  </Box>
                )
              })}
            </Stack>
          </Paper>

          {/* Thread */}
          <Paper sx={{ flex: 1, minWidth: 0, borderRadius: 3, display: 'flex', flexDirection: 'column' }} elevation={1}>
            {loadingThread ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
                <CircularProgress size={26} />
              </Box>
            ) : !selectedTicket || !thread ? (
              <Box sx={{ py: 8, textAlign: 'center', color: 'text.secondary' }}>
                <Typography variant="body1">{t('support.selectRequest', 'Select a request to view the conversation.')}</Typography>
              </Box>
            ) : (
              <>
                <Box sx={{ px: 3, py: 2, borderBottom: 1, borderColor: 'divider' }}>
                  <Typography variant="h6" sx={{ fontWeight: 800, color: 'text.primary' }}>
                    {selectedTicket.subject}
                  </Typography>
                  {selectedTicket.status === 'resolved' && (
                    <Chip
                      label={t('support.resolved', 'Resolved')}
                      size="small"
                      sx={{ mt: 0.5, height: 20, fontSize: 11, fontWeight: 700, color: '#10b981', bgcolor: 'rgba(16,185,129,0.14)' }}
                    />
                  )}
                </Box>
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
                                maxWidth: '85%',
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

                      const alignRight = !isSpecialist && !isAssistant
                      const bgcolor = isSpecialist || isAssistant ? '#fff' : '#3b66ff'
                      const color = isSpecialist || isAssistant ? 'text.primary' : '#fff'
                      const border = isSpecialist || isAssistant ? '1px solid' : 'none'
                      const labelColor = isSpecialist ? '#3b66ff' : isAssistant ? '#6366f1' : 'rgba(255,255,255,0.8)'
                      const label = isSpecialist
                        ? (message.sender_name || 'Specialist')
                        : isAssistant
                          ? 'BRAINOPX AI Assistant'
                          : 'You'

                      return (
                        <Box key={message.id} sx={{ display: 'flex', justifyContent: alignRight ? 'flex-end' : 'flex-start' }}>
                          <Paper
                            elevation={0}
                            sx={{
                              maxWidth: '75%',
                              px: 2,
                              py: 1.25,
                              borderRadius: 3,
                              bgcolor,
                              color,
                              border,
                              borderColor: 'divider',
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
                                color: isSpecialist || isAssistant ? 'text.disabled' : 'rgba(255,255,255,0.7)',
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
                <Box sx={{ px: 3, py: 2, borderTop: 1, borderColor: 'divider' }}>
                  <Stack direction="row" spacing={1.5} alignItems="flex-end">
                    <TextField
                      fullWidth
                      multiline
                      minRows={1}
                      maxRows={5}
                      placeholder={
                        selectedTicket.status === 'resolved'
                          ? t('support.resolvedReplyHint', 'This request is resolved — send a message to reopen it.')
                          : t('support.replyPlaceholder', 'Write a reply…')
                      }
                      value={reply}
                      onChange={(e) => setReply(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          handleSend()
                        }
                      }}
                    />
                    <Button
                      variant="contained"
                      disabled={sending || !reply.trim()}
                      onClick={handleSend}
                      sx={{ minWidth: 48, height: 48, px: 0, borderRadius: 2.5 }}
                    >
                      {sending ? <CircularProgress size={20} sx={{ color: '#fff' }} /> : <SendIcon />}
                    </Button>
                  </Stack>
                </Box>
              </>
            )}
          </Paper>
        </Stack>
      )}

      {/* New request dialog */}
      <Dialog open={composerOpen} onClose={() => setComposerOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle sx={{ fontWeight: 700 }}>
          {t('support.newRequestTitle', 'New support request')}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t('support.subjectLabel', 'Subject')}
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              fullWidth
              required
            />
            <TextField
              label={t('support.messageLabel', 'Message')}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              fullWidth
              multiline
              minRows={4}
              placeholder={t('support.messagePlaceholder', 'Describe what you need help with…')}
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setComposerOpen(false)} sx={{ textTransform: 'none' }}>
            {t('support.cancel', 'Cancel')}
          </Button>
          <Button
            variant="contained"
            disabled={creating || !subject.trim()}
            onClick={handleCreate}
            sx={{ textTransform: 'none', fontWeight: 700 }}
          >
            {creating ? t('support.sending', 'Sending…') : t('support.send', 'Send')}
          </Button>
        </DialogActions>
      </Dialog>

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
        >
          {error || notice}
        </Alert>
      </Snackbar>
    </Box>
  )
}

export default Support
