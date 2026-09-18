import { useEffect, useRef, useState } from 'react'
import {
  Box,
  Typography,
  Paper,
  IconButton,
  Button,
  Avatar,
  Tabs,
  Tab,
  CircularProgress,
} from '@mui/material'
import ArrowBackIconImport from '@mui/icons-material/ArrowBack'
import NotificationsIconImport from '@mui/icons-material/Notifications'
import OpenInNewIconImport from '@mui/icons-material/OpenInNew'
import DeleteOutlineIconImport from '@mui/icons-material/DeleteOutline'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useNotifications } from '../context/NotificationContext.jsx'
import { notificationTypeConfig } from './notificationTypes.jsx'

const ArrowBackIcon = ArrowBackIconImport?.default || ArrowBackIconImport
const NotificationsIcon = NotificationsIconImport?.default || NotificationsIconImport
const OpenInNewIcon = OpenInNewIconImport?.default || OpenInNewIconImport
const DeleteOutlineIcon = DeleteOutlineIconImport?.default || DeleteOutlineIconImport

// The notification panel body. Positioning is left to the caller
// (topbar dropdown wrapper or sidebar popover), so this component can
// be reused in both places.
const NotificationsPanelContent = ({ onClose, width = 400, maxHeight = 560 }) => {
  const { t } = useTranslation('components')
  const {
    notifications,
    unreadCount,
    loading,
    refreshNotifications,
    markNotificationRead,
    markAllRead,
    deleteNotification,
  } = useNotifications()
  const [tab, setTab] = useState('all')
  const [selected, setSelected] = useState(null)
  const panelRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    refreshNotifications()
    setTab('all')
    setSelected(null)
  }, [refreshNotifications])

  useEffect(() => {
    if (!onClose) return
    const handleClickOutside = (event) => {
      if (panelRef.current && !panelRef.current.contains(event.target)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose])

  const filtered = tab === 'unread' ? notifications.filter((n) => !n.is_read) : notifications

  const selectedConfig = selected
    ? notificationTypeConfig[selected.type] || notificationTypeConfig.info
    : null

  const handleOpenDetail = (notification) => {
    if (!notification.is_read) {
      markNotificationRead(notification.id)
    }
    setSelected(notification)
  }

  const handleDeleteNotification = (notification) => {
    deleteNotification(notification.id)
    if (selected?.id === notification.id) {
      setSelected(null)
    }
  }

  const formatTime = (dateStr) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return t('notificationsPanel.justNow')
    if (diffMins < 60) return t('notificationsPanel.minutesAgo', { count: diffMins })
    if (diffHours < 24) return t('notificationsPanel.hoursAgo', { count: diffHours })
    if (diffDays < 7) return t('notificationsPanel.daysAgo', { count: diffDays })
    return date.toLocaleDateString()
  }

  return (
    <Paper
      ref={panelRef}
      elevation={8}
      sx={{
        width,
        maxHeight,
        display: 'flex',
        flexDirection: 'column',
        borderRadius: 3,
        overflow: 'hidden',
        bgcolor: (theme) => theme.palette.background.paper,
        border: (theme) =>
          `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
      }}
    >
      {/* Tabs + mark all read */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          borderBottom: (theme) => `1px solid ${theme.palette.divider}`,
        }}
      >
        <Tabs
          value={tab}
          onChange={(event, value) => setTab(value)}
          variant="fullWidth"
          sx={{
            flex: 1,
            minHeight: 40,
            '& .MuiTabs-indicator': {
              backgroundColor: '#3b66ff',
              height: 2,
              borderRadius: '2px 2px 0 0',
            },
            '& .MuiTab-root': {
              minHeight: 40,
              color: 'text.secondary',
              fontWeight: 600,
              fontSize: 13,
              textTransform: 'none',
            },
            '& .Mui-selected': { color: '#3b66ff' },
          }}
        >
          <Tab label={t('notificationsPanel.all')} value="all" />
          <Tab label={`${t('notificationsPanel.unread')} (${unreadCount})`} value="unread" />
        </Tabs>

        {notifications.some((n) => !n.is_read) && (
          <Button
            onClick={markAllRead}
            sx={{
              textTransform: 'none',
              fontSize: 12,
              color: 'primary.main',
              minWidth: 'auto',
              px: 2,
              flexShrink: 0,
            }}
          >
            {t('notificationsPanel.markAllRead')}
          </Button>
        )}
      </Box>

      {/* Body */}
      <Box sx={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {selected ? (
          <Box>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                px: 2,
                py: 1,
                borderBottom: (theme) => `1px solid ${theme.palette.divider}`,
              }}
            >
              <IconButton size="small" onClick={() => setSelected(null)}>
                <ArrowBackIcon fontSize="small" />
              </IconButton>
              <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                {t('notificationsPanel.back')}
              </Typography>
              <Box sx={{ flex: 1 }} />
              <IconButton
                size="small"
                aria-label={t('notificationsPanel.delete')}
                title={t('notificationsPanel.delete')}
                onClick={() => handleDeleteNotification(selected)}
                sx={{ color: 'text.disabled', '&:hover': { color: 'error.main' } }}
              >
                <DeleteOutlineIcon fontSize="small" />
              </IconButton>
            </Box>

            <Box sx={{ px: 3, py: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Avatar
                  sx={{
                    width: 46,
                    height: 46,
                    flexShrink: 0,
                    bgcolor: selectedConfig.color,
                    color: '#fff',
                    fontSize: 18,
                    fontWeight: 700,
                  }}
                >
                  {selected.title.charAt(0).toUpperCase()}
                </Avatar>
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                    {selected.title}
                  </Typography>
                  <Typography variant="caption" color="text.disabled">
                    {formatTime(selected.created_at)}
                  </Typography>
                </Box>
              </Box>

              {selected.message && (
                <Typography
                  variant="body2"
                  sx={{
                    mt: 2.5,
                    color: 'text.secondary',
                    whiteSpace: 'normal',
                    wordBreak: 'break-word',
                    lineHeight: 1.6,
                  }}
                >
                  {selected.message}
                </Typography>
              )}

              {selected.link && (
                <Button
                  variant="contained"
                  size="small"
                  endIcon={<OpenInNewIcon fontSize="small" />}
                  onClick={() => {
                    navigate(selected.link)
                    if (onClose) onClose()
                  }}
                  sx={{ mt: 3, textTransform: 'none', borderRadius: 2 }}
                >
                  {t('notificationsPanel.open')}
                </Button>
              )}
            </Box>
          </Box>
        ) : loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={24} />
          </Box>
        ) : filtered.length === 0 ? (
          <Box sx={{ py: 6, textAlign: 'center', px: 3 }}>
            <NotificationsIcon sx={{ fontSize: 40, color: 'text.disabled', mb: 1 }} />
            <Typography variant="body2" color="text.secondary">
              {t('notificationsPanel.noNotifications')}
            </Typography>
          </Box>
        ) : (
          filtered.map((notification, index) => {
            const config =
              notificationTypeConfig[notification.type] || notificationTypeConfig.info
            return (
              <Box
                key={notification.id}
                onClick={() => handleOpenDetail(notification)}
                sx={{
                  display: 'flex',
                  alignItems: 'stretch',
                  cursor: 'pointer',
                  borderBottom: index < filtered.length - 1
                    ? (theme) => `1px solid ${theme.palette.divider}`
                    : 'none',
                  '&:hover': { bgcolor: 'action.hover' },
                }}
              >
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 1.5,
                    px: 2,
                    py: 1.75,
                    flex: 1,
                    minWidth: 0,
                  }}
                >
                  <Avatar
                    sx={{
                      width: 40,
                      height: 40,
                      flexShrink: 0,
                      bgcolor: config.color,
                      color: '#fff',
                      fontSize: 16,
                      fontWeight: 700,
                    }}
                  >
                    {notification.title.charAt(0).toUpperCase()}
                  </Avatar>

                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography
                      variant="body2"
                      sx={{
                        color: 'text.primary',
                        lineHeight: 1.4,
                        wordBreak: 'break-word',
                      }}
                    >
                      <Box
                        component="span"
                        sx={{ fontWeight: notification.is_read ? 600 : 700 }}
                      >
                        {notification.title}
                      </Box>
                      {notification.message && ` ${notification.message}`}
                    </Typography>
                  </Box>

                  <Typography
                    variant="caption"
                    sx={{ color: 'text.disabled', flexShrink: 0, lineHeight: 1.4 }}
                  >
                    {formatTime(notification.created_at)}
                  </Typography>
                </Box>

                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    px: 0.5,
                  }}
                >
                  <IconButton
                    size="small"
                    aria-label={t('notificationsPanel.delete')}
                    title={t('notificationsPanel.delete')}
                    onClick={(event) => {
                      event.stopPropagation()
                      handleDeleteNotification(notification)
                    }}
                    sx={{ color: 'text.disabled', '&:hover': { color: 'error.main' } }}
                  >
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                </Box>

                <Box
                  sx={{
                    width: 3,
                    flexShrink: 0,
                    bgcolor: notification.is_read
                      ? (theme) =>
                          theme.palette.mode === 'dark'
                            ? 'rgba(255,255,255,0.08)'
                            : 'rgba(0,0,0,0.08)'
                      : '#3b66ff',
                  }}
                />
              </Box>
            )
          })
        )}
      </Box>
    </Paper>
  )
}

export default NotificationsPanelContent
