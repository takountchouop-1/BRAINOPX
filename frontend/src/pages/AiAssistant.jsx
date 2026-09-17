import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  InputBase,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Popover,
  Snackbar,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material'

import AddIconImport from '@mui/icons-material/Add'
import ArrowUpwardIconImport from '@mui/icons-material/ArrowUpward'
import AutoAwesomeIconImport from '@mui/icons-material/AutoAwesome'
import HistoryIconImport from '@mui/icons-material/HistoryOutlined'
import ChatBubbleOutlineIconImport from '@mui/icons-material/ChatBubbleOutline'
import DeleteOutlineIconImport from '@mui/icons-material/DeleteOutline'
import AttachFileIconImport from '@mui/icons-material/AttachFile'
import CloseIconImport from '@mui/icons-material/Close'
import InsertDriveFileIconImport from '@mui/icons-material/InsertDriveFileOutlined'
import DownloadIconImport from '@mui/icons-material/DownloadOutlined'
import PictureAsPdfIconImport from '@mui/icons-material/PictureAsPdfOutlined'
import DescriptionIconImport from '@mui/icons-material/DescriptionOutlined'
import SearchIconImport from '@mui/icons-material/Search'
import CheckIconImport from '@mui/icons-material/Check'
import ExpandMoreIconImport from '@mui/icons-material/ExpandMore'

import { useAuth } from '../context/AuthContext.jsx'
import ChatMessage, { TypingIndicator, conversationBackground, composerBackground } from '../components/ChatMessage.jsx'
import {
  sendAssistantMessage,
  listAssistantConversations,
  getAssistantConversation,
  clearAssistantConversations,
  uploadAssistantAttachment,
  downloadAssistantExport,
} from '../services/assistantService.js'
import { listTasks } from '../services/taskService.js'
import taskIconImg from '../assets/taskicon.jpg'

const AddIcon = AddIconImport?.default || AddIconImport
const ArrowUpwardIcon = ArrowUpwardIconImport?.default || ArrowUpwardIconImport
const AutoAwesomeIcon = AutoAwesomeIconImport?.default || AutoAwesomeIconImport
const HistoryIcon = HistoryIconImport?.default || HistoryIconImport
const ChatBubbleOutlineIcon = ChatBubbleOutlineIconImport?.default || ChatBubbleOutlineIconImport
const DeleteOutlineIcon = DeleteOutlineIconImport?.default || DeleteOutlineIconImport
const AttachFileIcon = AttachFileIconImport?.default || AttachFileIconImport
const CloseIcon = CloseIconImport?.default || CloseIconImport
const InsertDriveFileIcon = InsertDriveFileIconImport?.default || InsertDriveFileIconImport
const DownloadIcon = DownloadIconImport?.default || DownloadIconImport
const PictureAsPdfIcon = PictureAsPdfIconImport?.default || PictureAsPdfIconImport
const DescriptionIcon = DescriptionIconImport?.default || DescriptionIconImport
const SearchIcon = SearchIconImport?.default || SearchIconImport
const CheckIcon = CheckIconImport?.default || CheckIconImport
const ExpandMoreIcon = ExpandMoreIconImport?.default || ExpandMoreIconImport

const ATTACHMENT_ACCEPT = '.pdf,.docx,.doc,.txt,.xlsx,.xls,.csv'

const formatFileSize = (bytes, t) => {
  if (!bytes && bytes !== 0) return ''
  if (bytes < 1024) return t('aiAssistant.fileSizeBytes', { size: bytes })
  if (bytes < 1024 * 1024) return t('aiAssistant.fileSizeKB', { size: (bytes / 1024).toFixed(1) })
  return t('aiAssistant.fileSizeMB', { size: (bytes / (1024 * 1024)).toFixed(1) })
}

// "Today" / "Yesterday" / a full date — used to separate message groups by day.
const dayLabelFor = (timestamp, t) => {
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return ''

  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const today = startOfDay(new Date())
  const target = startOfDay(date)
  const diffDays = Math.round((today - target) / 86400000)

  if (diffDays === 0) return t('aiAssistant.today')
  if (diffDays === 1) return t('aiAssistant.yesterday')
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })
}

const greetingKeyFor = (hour) => {
  if (hour < 12) return 'aiAssistant.greetingMorning'
  if (hour < 18) return 'aiAssistant.greetingAfternoon'
  return 'aiAssistant.greetingEvening'
}

const CONTEXT_PREVIEW_COUNT = 3

// ─── PAGE ────────────────────────────────────────────────────────────────────

const AiAssistant = () => {
  const { t } = useTranslation('pages')
  const { user } = useAuth()

  const SUGGESTIONS = t('aiAssistant.suggestions', { returnObjects: true })

  const CONTEXT_CATEGORY_META = {
    report_analyses: { label: t('aiAssistant.contextCategoryReport') },
    skill_engine: { label: t('aiAssistant.contextCategorySkillEngine') },
  }

  const firstName = (user?.full_name || t('aiAssistant.firstNameFallback')).split(' ')[0]

  const [conversations, setConversations] = useState([])
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)

  const [tasks, setTasks] = useState([])
  const [selectedTask, setSelectedTask] = useState(null)
  const [contextAnchor, setContextAnchor] = useState(null)
  const [contextSearch, setContextSearch] = useState('')
  const [contextExpanded, setContextExpanded] = useState(false)
  const contextCloseTimerRef = useRef(null)

  const [historyAnchor, setHistoryAnchor] = useState(null)
  const [historySearch, setHistorySearch] = useState('')

  const [pendingAttachments, setPendingAttachments] = useState([])
  const [uploadingAttachment, setUploadingAttachment] = useState(false)
  const [exportAnchor, setExportAnchor] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [notice, setNotice] = useState(null) // { severity, message } | null

  const scrollAnchorRef = useRef(null)
  const attachFileInputRef = useRef(null)
  // Whether the message list was scrolled to (or near) the bottom before
  // this update — read in the effect below to decide whether a new
  // message should pull the view down, or leave the user's scroll
  // position alone while they're reading earlier messages.
  const isAtBottomRef = useRef(true)

  const panel = (theme) =>
    theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : '#ffffff'

  const hairline = (theme) =>
    theme.palette.mode === 'dark'
      ? '1px solid rgba(255,255,255,0.10)'
      : '1px solid rgba(79,70,229,0.16)'

  const loadConversations = async () => {
    try {
      const list = await listAssistantConversations()
      setConversations(list)
    } catch {
      // Recent row just stays empty if this fails.
    }
  }

  useEffect(() => {
    loadConversations()
    listTasks().then(setTasks).catch(() => {})
  }, [])

  useEffect(() => {
    const lastMessage = messages[messages.length - 1]
    // Always follow the user's own message; for an incoming assistant
    // reply, only auto-scroll if they hadn't scrolled up to read history.
    if (isAtBottomRef.current || lastMessage?.role === 'user') {
      scrollAnchorRef.current?.scrollIntoView({ behavior: 'smooth' })
      isAtBottomRef.current = true
    }
  }, [messages, sending])

  const NEAR_BOTTOM_THRESHOLD_PX = 80
  const handleMessagesScroll = (e) => {
    const el = e.currentTarget
    isAtBottomRef.current =
      el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_THRESHOLD_PX
  }

  useEffect(() => () => clearTimeout(contextCloseTimerRef.current), [])

  const startNewChat = () => {
    setConversationId(null)
    setMessages([])
    setSelectedTask(null)
  }

  const openConversation = async (conversation) => {
    try {
      const msgs = await getAssistantConversation(conversation.id)
      setConversationId(conversation.id)
      setMessages(msgs)
      setSelectedTask(null)
    } catch {
      // Leave the current view as-is if the thread can't be loaded.
    }
  }

  const closeHistory = () => {
    setHistoryAnchor(null)
    setHistorySearch('')
  }

  const handleSelectConversation = (conversation) => {
    openConversation(conversation)
    closeHistory()
  }

  const handleClearConversations = async () => {
    if (conversations.length === 0) return
    try {
      await clearAssistantConversations()
      setConversations([])
      startNewChat()
    } catch {
      // If this fails the list just stays as it was.
    }
    closeHistory()
  }

  const filteredConversations = conversations.filter((conversation) => {
    const label = (conversation.title || conversation.last_message_preview || t('aiAssistant.untitledChat')).toLowerCase()
    return label.includes(historySearch.trim().toLowerCase())
  })

  const openContextMenu = (e) => {
    clearTimeout(contextCloseTimerRef.current)
    setContextAnchor(e.currentTarget)
  }

  const closeContextMenu = () => {
    setContextAnchor(null)
    setContextSearch('')
    setContextExpanded(false)
  }

  const scheduleCloseContextMenu = () => {
    clearTimeout(contextCloseTimerRef.current)
    contextCloseTimerRef.current = setTimeout(closeContextMenu, 200)
  }

  const cancelCloseContextMenu = () => clearTimeout(contextCloseTimerRef.current)

  const handleSelectContext = (task) => {
    setSelectedTask(task)
    closeContextMenu()
  }

  const handleClearContext = () => {
    setSelectedTask(null)
    closeContextMenu()
  }

  const contextSearchLower = contextSearch.trim().toLowerCase()
  const filteredContextItems = tasks.filter((task) => {
    if (!contextSearchLower) return true
    const categoryLabel = CONTEXT_CATEGORY_META[task.category]?.label || ''
    return (
      task.name.toLowerCase().includes(contextSearchLower) ||
      categoryLabel.toLowerCase().includes(contextSearchLower)
    )
  })
  const contextItemsToShow =
    contextExpanded || contextSearchLower
      ? filteredContextItems
      : filteredContextItems.slice(0, CONTEXT_PREVIEW_COUNT)
  const hasMoreContextItems =
    !contextExpanded && !contextSearchLower && filteredContextItems.length > CONTEXT_PREVIEW_COUNT

  const handleAttachClick = () => attachFileInputRef.current?.click()

  const handleFileSelected = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = '' // allow re-selecting the same file later
    if (!file) return

    setUploadingAttachment(true)
    try {
      const attachment = await uploadAssistantAttachment({ file, conversationId })
      setPendingAttachments((prev) => [...prev, attachment])
      if (!attachment.extractable) {
        setNotice({
          severity: 'warning',
          message: t('aiAssistant.attachmentUnreadableNotice', { filename: attachment.filename }),
        })
      }
    } catch (err) {
      setNotice({ severity: 'error', message: err.message || t('aiAssistant.uploadFailedDefault') })
    } finally {
      setUploadingAttachment(false)
    }
  }

  const removePendingAttachment = (id) => {
    setPendingAttachments((prev) => prev.filter((a) => a.id !== id))
  }

  const handleExport = async (format) => {
    setExportAnchor(null)
    if (!conversationId) return

    setExporting(true)
    try {
      await downloadAssistantExport({ conversationId, format })
    } catch (err) {
      setNotice({ severity: 'error', message: err.message || t('aiAssistant.exportFailedDefault') })
    } finally {
      setExporting(false)
    }
  }

  const sendMessage = async (rawText) => {
    const text = (rawText ?? input).trim()
    console.log('sendMessage value:', text, 'type:', typeof text)
    if (!text || sending) return

    setInput('')
    const attachmentsForMessage = pendingAttachments
    const localUserMessage = {
      id: `local-${Date.now()}`,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
      attachments: attachmentsForMessage,
    }
    setMessages((prev) => [...prev, localUserMessage])
    setSending(true)

    try {
      const res = await sendAssistantMessage({
        message: text,
        conversationId,
        taskId: selectedTask?.id ?? null,
        attachmentIds: attachmentsForMessage.map((a) => a.id),
      })
      setConversationId(res.conversation_id)
      setMessages((prev) => [...prev, { ...res.reply, _animate: true }])
      setPendingAttachments([])
      loadConversations()
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: t('aiAssistant.assistantErrorMessage', { error: err.message }),
          created_at: new Date().toISOString(),
          _animate: true,
        },
      ])
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const hasMessages = messages.length > 0
  const lastMessage = messages[messages.length - 1]

  const composer = (
    <Box
      sx={{
        position: 'relative',
        width: '100%',
        maxWidth: 760,
        mx: 'auto',
        borderRadius: '24px',
        p: '2px',
        overflow: 'hidden',
        transition: 'transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.25s ease',
        boxShadow: (theme) =>
          theme.palette.mode === 'dark'
            ? '0 10px 30px rgba(0,0,0,0.36), 0 0 44px rgba(124,58,237,0.38), 0 0 18px rgba(34,211,238,0.20)'
            : '0 12px 34px rgba(79,70,229,0.16), 0 0 40px rgba(124,58,237,0.24), 0 2px 6px rgba(16,24,40,0.04)',
        '&:focus-within': {
          transform: 'scale(1.015)',
          boxShadow: (theme) =>
            theme.palette.mode === 'dark'
              ? '0 16px 40px rgba(0,0,0,0.45), 0 0 64px rgba(124,58,237,0.55), 0 0 26px rgba(34,211,238,0.32)'
              : '0 18px 44px rgba(79,70,229,0.22), 0 0 60px rgba(124,58,237,0.34), 0 2px 8px rgba(16,24,40,0.06)',
        },
        '&::before': {
          content: '""',
          position: 'absolute',
          top: '50%',
          left: '50%',
          width: '160%',
          aspectRatio: '1',
          background:
            'conic-gradient(from 0deg, #4f46e5, #7c3aed, #22d3ee, #3b66ff, #4f46e5)',
          filter: 'saturate(1.35) brightness(1.08)',
          animation: 'composerSpin 5s linear infinite',
        },
        '@keyframes composerSpin': {
          from: { transform: 'translate(-50%, -50%) rotate(0deg)' },
          to: { transform: 'translate(-50%, -50%) rotate(360deg)' },
        },
        '@media (prefers-reduced-motion: reduce)': {
          '&::before': { animation: 'none' },
          '&:focus-within': { transform: 'none' },
        },
      }}
    >
      <Box
        sx={{
          position: 'relative',
          zIndex: 1,
          borderRadius: '22px',
          bgcolor: panel,
          px: 2.5,
          pt: 2.25,
          pb: 1.5,
          minHeight: hasMessages ? 'auto' : 168,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Stack direction="row" alignItems="flex-start" spacing={1} sx={{ flex: 1 }}>
          <AutoAwesomeIcon sx={{ fontSize: 19, color: '#4f46e5', mt: 0.3 }} />
          <InputBase
            fullWidth
            multiline
            maxRows={10}
            placeholder={t('aiAssistant.askAnythingPlaceholder')}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={sending}
            sx={{ fontSize: 16, lineHeight: 1.6, p: 0, alignItems: 'flex-start' }}
          />
        </Stack>

        {pendingAttachments.length > 0 && (
          <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap', gap: 0.75, mt: 1.25 }}>
            {pendingAttachments.map((attachment) => (
              <Chip
                key={attachment.id}
                size="small"
                icon={<InsertDriveFileIcon sx={{ fontSize: 15 }} />}
                label={`${attachment.filename}${
                  attachment.size_bytes != null ? ` · ${formatFileSize(attachment.size_bytes, t)}` : ''
                }${attachment.extractable === false ? ` · ${t('aiAssistant.attachmentChipUnreadable')}` : ''}`}
                onDelete={() => removePendingAttachment(attachment.id)}
                deleteIcon={<CloseIcon sx={{ fontSize: 14 }} />}
                sx={{
                  borderRadius: '999px',
                  fontSize: 12,
                  fontWeight: 600,
                  bgcolor: attachment.extractable === false ? 'rgba(220,38,38,0.08)' : 'rgba(79,70,229,0.08)',
                  color: attachment.extractable === false ? '#dc2626' : '#4f46e5',
                }}
              />
            ))}
          </Stack>
        )}

        <input
          ref={attachFileInputRef}
          type="file"
          accept={ATTACHMENT_ACCEPT}
          hidden
          onChange={handleFileSelected}
        />

        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          sx={{ mt: 1.5 }}
        >
          <Stack direction="row" alignItems="center" spacing={0.5}>
            <Tooltip title={t('aiAssistant.attachTooltip')}>
              <span>
                <IconButton
                  onClick={handleAttachClick}
                  disabled={sending || uploadingAttachment}
                  sx={{
                    width: 34,
                    height: 34,
                    color: 'text.secondary',
                  }}
                >
                  {uploadingAttachment ? (
                    <CircularProgress size={16} />
                  ) : (
                    <AttachFileIcon sx={{ fontSize: 18 }} />
                  )}
                </IconButton>
              </span>
            </Tooltip>

            <Tooltip title={t('aiAssistant.contextTooltip')}>
              <IconButton
                onMouseEnter={openContextMenu}
                onClick={openContextMenu}
                sx={{
                  width: 34,
                  height: 34,
                  color: '#4f46e5',
                  background: selectedTask
                    ? 'linear-gradient(135deg, #e0edff 0%, #c7dbff 100%)'
                    : 'linear-gradient(135deg, #ffffff 0%, #e8f1ff 100%)',
                  border: '1px solid rgba(79,70,229,0.14)',
                  '&:hover': {
                    background: 'linear-gradient(135deg, #f0f6ff 0%, #d6e6ff 100%)',
                  },
                }}
              >
                <AddIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Tooltip>

            <Popover
              open={Boolean(contextAnchor)}
              anchorEl={contextAnchor}
              onClose={closeContextMenu}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
              transformOrigin={{ vertical: 'top', horizontal: 'left' }}
              disableRestoreFocus
              PaperProps={{
                onMouseEnter: cancelCloseContextMenu,
                onMouseLeave: scheduleCloseContextMenu,
                sx: {
                  width: 300,
                  maxHeight: 380,
                  mt: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  borderRadius: '16px',
                  bgcolor: panel,
                  border: hairline,
                  boxShadow: (theme) =>
                    theme.palette.mode === 'dark'
                      ? '0 16px 40px rgba(0,0,0,0.45)'
                      : '0 16px 40px rgba(16,24,40,0.14)',
                },
              }}
            >
              <Box sx={{ px: 1.5, pt: 1.5, pb: 1 }}>
                <Stack
                  direction="row"
                  alignItems="center"
                  spacing={0.75}
                  sx={{
                    px: 1.25,
                    py: 0.65,
                    borderRadius: '10px',
                    bgcolor: (theme) =>
                      theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
                    border: hairline,
                  }}
                >
                  <SearchIcon sx={{ fontSize: 16, color: 'text.disabled' }} />
                  <InputBase
                    fullWidth
                    autoFocus
                    placeholder={t('aiAssistant.contextSearchPlaceholder')}
                    value={contextSearch}
                    onChange={(e) => {
                      setContextSearch(e.target.value)
                      setContextExpanded(false)
                    }}
                    sx={{ fontSize: 13 }}
                  />
                </Stack>
              </Box>

              <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto', px: 0.75, py: 0.5 }}>
                <MenuItem
                  selected={!selectedTask}
                  onClick={handleClearContext}
                  sx={{ borderRadius: '10px', mx: 0.5, my: 0.25, fontSize: 13 }}
                >
                  <ListItemIcon sx={{ minWidth: 30 }}>
                    <AutoAwesomeIcon sx={{ fontSize: 16, color: '#4f46e5' }} />
                  </ListItemIcon>
                  <ListItemText
                    primary={t('aiAssistant.generalAssistant')}
                    primaryTypographyProps={{ fontSize: 13 }}
                  />
                  {!selectedTask && <CheckIcon sx={{ fontSize: 16, color: '#4f46e5' }} />}
                </MenuItem>

                <Divider sx={{ my: 0.5 }} />

                {filteredContextItems.length === 0 ? (
                  <Typography
                    sx={{ fontSize: 12.5, color: 'text.disabled', textAlign: 'center', py: 3 }}
                  >
                    {tasks.length === 0 ? t('aiAssistant.nothingToBringInYet') : t('aiAssistant.noMatchesFound')}
                  </Typography>
                ) : (
                  contextItemsToShow.map((task) => {
                    const meta = CONTEXT_CATEGORY_META[task.category] || { label: t('aiAssistant.contextCategoryOther') }
                    const isSelected = selectedTask?.id === task.id
                    return (
                      <MenuItem
                        key={task.id}
                        selected={isSelected}
                        onClick={() => handleSelectContext(task)}
                        sx={{ borderRadius: '10px', mx: 0.5, my: 0.25 }}
                      >
                        <ListItemIcon sx={{ minWidth: 30 }}>
                          <Box
                            component="img"
                            src={taskIconImg}
                            alt=""
                            sx={{ width: 18, height: 18, borderRadius: '5px', objectFit: 'cover' }}
                          />
                        </ListItemIcon>
                        <ListItemText
                          primary={task.name}
                          secondary={meta.label}
                          primaryTypographyProps={{ noWrap: true, fontSize: 13 }}
                          secondaryTypographyProps={{ fontSize: 11 }}
                        />
                        {isSelected && <CheckIcon sx={{ fontSize: 16, color: '#4f46e5', flexShrink: 0 }} />}
                      </MenuItem>
                    )
                  })
                )}

                {hasMoreContextItems && (
                  <MenuItem
                    onClick={() => setContextExpanded(true)}
                    sx={{ borderRadius: '10px', mx: 0.5, my: 0.25, justifyContent: 'center' }}
                  >
                    <Typography sx={{ fontSize: 12.5, fontWeight: 600, color: '#4f46e5' }}>
                      {t('aiAssistant.seeMore')}
                    </Typography>
                    <ExpandMoreIcon sx={{ fontSize: 16, color: '#4f46e5', ml: 0.5 }} />
                  </MenuItem>
                )}
              </Box>
            </Popover>
          </Stack>

          <Tooltip title={t('aiAssistant.sendTooltip')}>
            <span>
              <IconButton
                onClick={() => sendMessage()}
                disabled={sending || !input.trim()}
                sx={{
                  bgcolor: '#4f46e5',
                  color: '#fff',
                  width: 34,
                  height: 34,
                  '&:hover': { bgcolor: '#4338ca' },
                  '&.Mui-disabled': { bgcolor: 'rgba(79,70,229,0.35)', color: '#fff' },
                }}
              >
                <ArrowUpwardIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </span>
          </Tooltip>
        </Stack>
      </Box>
    </Box>
  )

  return (
    <Box
      sx={{
        height: 'calc(100vh - 64px)',
        display: 'flex',
        flexDirection: 'column',
        background: conversationBackground,
      }}
    >
      {/* ── Slim header ───────────────────────────────────────────── */}
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="flex-end"
        sx={{ px: 3, py: 2, flexShrink: 0 }}
      >
        <Stack direction="row" alignItems="center" spacing={1}>
          <Tooltip title={hasMessages ? t('aiAssistant.exportTooltipEnabled') : t('aiAssistant.exportTooltipDisabled')}>
            <span>
              <IconButton
                onClick={(e) => setExportAnchor(e.currentTarget)}
                disabled={!hasMessages || exporting}
                sx={{
                  width: 36,
                  height: 36,
                  bgcolor: panel,
                  border: hairline,
                  color: 'text.secondary',
                }}
              >
                {exporting ? <CircularProgress size={16} /> : <DownloadIcon sx={{ fontSize: 18 }} />}
              </IconButton>
            </span>
          </Tooltip>

          <Menu
            anchorEl={exportAnchor}
            open={Boolean(exportAnchor)}
            onClose={() => setExportAnchor(null)}
          >
            <MenuItem onClick={() => handleExport('pdf')}>
              <ListItemIcon>
                <PictureAsPdfIcon sx={{ fontSize: 18 }} />
              </ListItemIcon>
              {t('aiAssistant.exportAsPdf')}
            </MenuItem>
            <MenuItem onClick={() => handleExport('docx')}>
              <ListItemIcon>
                <DescriptionIcon sx={{ fontSize: 18 }} />
              </ListItemIcon>
              {t('aiAssistant.exportAsWord')}
            </MenuItem>
          </Menu>

          <Tooltip title={t('aiAssistant.chatHistory')}>
            <IconButton
              onClick={(e) => setHistoryAnchor(e.currentTarget)}
              sx={{
                width: 36,
                height: 36,
                bgcolor: panel,
                border: hairline,
                color: 'text.secondary',
              }}
            >
              <HistoryIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Tooltip>

          <Button
            startIcon={<AddIcon />}
            onClick={startNewChat}
            sx={{
              textTransform: 'none',
              borderRadius: '999px',
              px: 2.25,
              py: 0.7,
              bgcolor: '#4f46e5',
              color: '#fff',
              fontWeight: 700,
              fontSize: 13,
              boxShadow: '0 6px 16px rgba(79,70,229,0.24)',
              '&:hover': { bgcolor: '#4338ca' },
            }}
          >
            {t('aiAssistant.newChat')}
          </Button>
        </Stack>
      </Stack>

      <Popover
        open={Boolean(historyAnchor)}
        anchorEl={historyAnchor}
        onClose={closeHistory}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        PaperProps={{
          sx: {
            width: 300,
            maxHeight: 440,
            mt: 1,
            display: 'flex',
            flexDirection: 'column',
            borderRadius: '16px',
            bgcolor: panel,
            border: hairline,
            boxShadow: (theme) =>
              theme.palette.mode === 'dark'
                ? '0 16px 40px rgba(0,0,0,0.45)'
                : '0 16px 40px rgba(16,24,40,0.14)',
          },
        }}
      >
        <Box sx={{ px: 1.75, pt: 1.75, pb: 1 }}>
          <Typography sx={{ fontSize: 12.5, fontWeight: 700, mb: 1 }}>
            {t('aiAssistant.chatHistory')}
          </Typography>
          <InputBase
            fullWidth
            autoFocus
            placeholder={t('aiAssistant.historySearchPlaceholder')}
            value={historySearch}
            onChange={(e) => setHistorySearch(e.target.value)}
            sx={{
              fontSize: 13,
              px: 1.25,
              py: 0.65,
              borderRadius: '10px',
              bgcolor: (theme) =>
                theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
              border: hairline,
            }}
          />
        </Box>

        <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto', px: 0.75, py: 0.5 }}>
          {filteredConversations.length === 0 ? (
            <Typography
              sx={{ fontSize: 12.5, color: 'text.disabled', textAlign: 'center', py: 3 }}
            >
              {conversations.length === 0 ? t('aiAssistant.noConversationsYet') : t('aiAssistant.noMatchesFound')}
            </Typography>
          ) : (
            <List dense disablePadding>
              {filteredConversations.map((conversation) => (
                <ListItemButton
                  key={conversation.id}
                  selected={conversation.id === conversationId}
                  onClick={() => handleSelectConversation(conversation)}
                  sx={{ borderRadius: '10px', mx: 0.5, my: 0.25 }}
                >
                  <ListItemIcon sx={{ minWidth: 30 }}>
                    <ChatBubbleOutlineIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                  </ListItemIcon>
                  <ListItemText
                    primary={conversation.title || conversation.last_message_preview || t('aiAssistant.untitledChat')}
                    primaryTypographyProps={{ noWrap: true, fontSize: 13 }}
                  />
                </ListItemButton>
              ))}
            </List>
          )}
        </Box>

        <Divider />

        <Box
          onClick={handleClearConversations}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            px: 1.75,
            py: 1.25,
            flexShrink: 0,
            cursor: conversations.length ? 'pointer' : 'default',
            opacity: conversations.length ? 1 : 0.4,
            color: '#dc2626',
            '&:hover': conversations.length ? { bgcolor: 'rgba(220,38,38,0.08)' } : undefined,
          }}
        >
          <DeleteOutlineIcon sx={{ fontSize: 17 }} />
          <Typography sx={{ fontSize: 12.5, fontWeight: 600 }}>{t('aiAssistant.clearConversations')}</Typography>
        </Box>
      </Popover>

      {!hasMessages ? (
        // ── Greeting and composer ─────────────────────────────────── */}
        <Box
          sx={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            px: 3,
            pb: 4,
          }}
        >
          <Typography
            align="center"
            sx={{ fontWeight: 700, fontSize: { xs: 22, md: 28 }, lineHeight: 1.3 }}
          >
            {t(greetingKeyFor(new Date().getHours()), { name: firstName })}
          </Typography>

          <Typography
            align="center"
            sx={{
              fontWeight: 700,
              fontSize: { xs: 22, md: 28 },
              lineHeight: 1.3,
              mb: 4,
            }}
          >
            {t('aiAssistant.howCanIHelpPrefix')}{' '}
            <Box component="span" sx={{ color: '#4f46e5' }}>
              {t('aiAssistant.howCanIHelpHighlight')}
            </Box>
          </Typography>

          {composer}

          <Typography
            sx={{ mt: 3, mb: 1.25, fontSize: 12.5, color: 'text.secondary', fontWeight: 600 }}
          >
            {t('aiAssistant.tryOneOfThese')}
          </Typography>

          <Stack
            direction="row"
            spacing={1}
            sx={{ flexWrap: 'wrap', gap: 1, justifyContent: 'center', maxWidth: 760 }}
          >
            {SUGGESTIONS.map((suggestion) => (
              <Chip
                key={suggestion}
                label={suggestion}
                variant="outlined"
                onClick={() => sendMessage(suggestion)}
                sx={{
                  borderRadius: '999px',
                  fontSize: 12.5,
                  bgcolor: panel,
                  cursor: 'pointer',
                  borderColor: (theme) =>
                    theme.palette.mode === 'dark'
                      ? 'rgba(255,255,255,0.12)'
                      : 'rgba(0,0,0,0.10)',
                  '&:hover': {
                    borderColor: 'rgba(79,70,229,0.45)',
                    bgcolor: 'rgba(79,70,229,0.05)',
                  },
                }}
              />
            ))}
          </Stack>

          {conversations.length > 0 && (
            <Stack
              direction="row"
              alignItems="center"
              spacing={1}
              sx={{ mt: 3.5, flexWrap: 'wrap', gap: 1, justifyContent: 'center', maxWidth: 760 }}
            >
              <Stack direction="row" alignItems="center" spacing={0.5} sx={{ color: 'text.disabled' }}>
                <HistoryIcon sx={{ fontSize: 16 }} />
                <Typography sx={{ fontSize: 12, fontWeight: 600 }}>{t('aiAssistant.recent')}</Typography>
              </Stack>

              {conversations.slice(0, 6).map((conversation) => (
                <Typography
                  key={conversation.id}
                  noWrap
                  onClick={() => openConversation(conversation)}
                  sx={{
                    fontSize: 12.5,
                    color: 'text.secondary',
                    cursor: 'pointer',
                    px: 1,
                    py: 0.4,
                    borderRadius: '8px',
                    maxWidth: 220,
                    '&:hover': { color: '#4f46e5', bgcolor: 'rgba(79,70,229,0.06)' },
                  }}
                >
                  {conversation.title || conversation.last_message_preview || t('aiAssistant.untitledChat')}
                </Typography>
              ))}
            </Stack>
          )}
        </Box>
      ) : (
        // ── Active conversation ───────────────────────────────────── */}
        <>
          <Box
            onScroll={handleMessagesScroll}
            sx={{
              flex: 1,
              minHeight: 0,
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
              px: 3,
              py: 2,
            }}
          >
            {messages.map((message, index) => {
              const previous = messages[index - 1]
              const showDaySeparator =
                !previous || dayLabelFor(message.created_at, t) !== dayLabelFor(previous.created_at, t)

              return (
                <Box key={message.id}>
                  {showDaySeparator && (
                    <Stack direction="row" alignItems="center" spacing={1.5} sx={{ my: 1.5 }}>
                      <Divider sx={{ flex: 1 }} />
                      <Typography sx={{ fontSize: 11.5, fontWeight: 700, color: 'text.disabled' }}>
                        {dayLabelFor(message.created_at, t)}
                      </Typography>
                      <Divider sx={{ flex: 1 }} />
                    </Stack>
                  )}
                  <ChatMessage
                    sender={message.role === 'user' ? 'user' : 'assistant'}
                    text={message.content}
                    timestamp={message.created_at}
                    user={user}
                    attachments={message.attachments || []}
                    animate={Boolean(message._animate)}
                  />
                </Box>
              )
            })}
            {sending && <TypingIndicator />}

            {!sending && lastMessage?.role === 'assistant' && lastMessage.suggestions?.length > 0 && (
              <Stack spacing={0.75} sx={{ pl: { xs: 0, sm: 5 } }}>
                <Typography sx={{ fontSize: 11.5, fontWeight: 600, color: 'text.disabled' }}>
                  {t('aiAssistant.followUpSuggestions')}
                </Typography>
                <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
                {lastMessage.suggestions.map((suggestion) => (
                  <Chip
                    key={suggestion}
                    label={suggestion}
                    variant="outlined"
                    onClick={() => sendMessage(suggestion)}
                    sx={{
                      borderRadius: '999px',
                      fontSize: 12.5,
                      bgcolor: panel,
                      cursor: 'pointer',
                      borderColor: (theme) =>
                        theme.palette.mode === 'dark'
                          ? 'rgba(255,255,255,0.12)'
                          : 'rgba(0,0,0,0.10)',
                      '&:hover': {
                        borderColor: 'rgba(79,70,229,0.45)',
                        bgcolor: 'rgba(79,70,229,0.05)',
                      },
                    }}
                  />
                ))}
                </Stack>
              </Stack>
            )}

            <div ref={scrollAnchorRef} />
          </Box>

          <Box sx={{ flexShrink: 0, px: 3, pb: 3, pt: 1, background: composerBackground }}>
            {composer}
          </Box>
        </>
      )}

      <Snackbar
        open={Boolean(notice)}
        autoHideDuration={5000}
        onClose={() => setNotice(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        {notice ? (
          <Alert severity={notice.severity} onClose={() => setNotice(null)} sx={{ borderRadius: '12px' }}>
            {notice.message}
          </Alert>
        ) : undefined}
      </Snackbar>
    </Box>
  )
}

export default AiAssistant
