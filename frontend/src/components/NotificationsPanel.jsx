import React, { useState, useEffect, useRef } from 'react'
import {
  Box,
  Typography,
  Paper,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Button,
  Divider,
  CircularProgress,
  Chip,
} from '@mui/material'
import InfoIconImport from '@mui/icons-material/Info'
import CheckCircleIconImport from '@mui/icons-material/CheckCircle'
import WarningIconImport from '@mui/icons-material/Warning'
import ErrorIconImport from '@mui/icons-material/Error'
import CloseIconImport from '@mui/icons-material/Close'
import NotificationsIconImport from '@mui/icons-material/Notifications'
import { useNavigate } from 'react-router-dom'
import { fetchNotifications, markAsRead, markAllAsRead } from '../services/NotificationService'

const InfoIcon = InfoIconImport?.default || InfoIconImport
const CheckCircleIcon = CheckCircleIconImport?.default || CheckCircleIconImport
const WarningIcon = WarningIconImport?.default || WarningIconImport
const ErrorIcon = ErrorIconImport?.default || ErrorIconImport
const CloseIcon = CloseIconImport?.default || CloseIconImport
const NotificationsIcon = NotificationsIconImport?.default || NotificationsIconImport

const typeConfig = {
  info: { icon: <InfoIcon fontSize="small" />, color: '#3b66ff' },
  success: { icon: <CheckCircleIcon fontSize="small" />, color: '#10b981' },
  warning: { icon: <WarningIcon fontSize="small" />, color: '#f59e0b' },
  error: { icon: <ErrorIcon fontSize="small" />, color: '#ef4444' },
}

const NotificationsPanel = ({ open, onClose, onUnreadCountChange }) => {
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(false)
  const panelRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (open) {
      loadNotifications()
    }
  }, [open])

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (panelRef.current && !panelRef.current.contains(event.target)) {
        onClose()
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open, onClose])

  const loadNotifications = async () => {
    setLoading(true)
    try {
      const data = await fetchNotifications()
      setNotifications(data)
      const unreadCount = data.filter((n) => !n.is_read).length
      if (onUnreadCountChange) onUnreadCountChange(unreadCount)
    } catch (err) {
      console.error('Failed to load notifications:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleMarkRead = async (id) => {
    try {
      await markAsRead(id)
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      )
      const unreadCount = notifications.filter((n) => !n.is_read && n.id !== id).length
      if (onUnreadCountChange) onUnreadCountChange(unreadCount)
    } catch (err) {
      console.error('Failed to mark as read:', err)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await markAllAsRead()
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
      if (onUnreadCountChange) onUnreadCountChange(0)
    } catch (err) {
      console.error('Failed to mark all as read:', err)
    }
  }

  const handleNotificationClick = (notification) => {
    if (!notification.is_read) {
      handleMarkRead(notification.id)
    }
    if (notification.link) {
      navigate(notification.link)
      onClose()
    }
  }

  const formatTime = (dateStr) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  return (
    <Paper
      ref={panelRef}
      elevation={8}
      sx={{
        position: 'absolute',
        top: '100%',
        right: 0,
        mt: 1,
        width: 380,
        maxHeight: 480,
        display: 'flex',
        flexDirection: 'column',
        borderRadius: 3,
        overflow: 'hidden',
        zIndex: 1300,
        bgcolor: (theme) => theme.palette.background.paper,
        border: (theme) =>
          `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          py: 1.5,
          borderBottom: (theme) =>
            `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : '#e5e7eb'}`,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <NotificationsIcon fontSize="small" sx={{ color: 'text.secondary' }} />
          <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'text.primary' }}>
            Notifications
          </Typography>
          {notifications.filter((n) => !n.is_read).length > 0 && (
            <Chip
              label={notifications.filter((n) => !n.is_read).length}
              size="small"
              sx={{
                height: 20,
                minWidth: 20,
                fontSize: 11,
                fontWeight: 700,
                bgcolor: '#ef4444',
                color: '#fff',
              }}
            />
          )}
        </Box>
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          {notifications.some((n) => !n.is_read) && (
            <Button
              size="small"
              onClick={handleMarkAllRead}
              sx={{
                textTransform: 'none',
                fontSize: 12,
                color: 'primary.main',
                minWidth: 'auto',
              }}
            >
              Mark all read
            </Button>
          )}
          <IconButton size="small" onClick={onClose}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>

      {/* List */}
      <Box sx={{ flex: 1, overflowY: 'auto' }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={24} />
          </Box>
        ) : notifications.length === 0 ? (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <NotificationsIcon sx={{ fontSize: 40, color: 'text.disabled', mb: 1 }} />
            <Typography variant="body2" color="text.secondary">
              No notifications yet
            </Typography>
          </Box>
        ) : (
          <List disablePadding>
            {notifications.map((notification, index) => {
              const config = typeConfig[notification.type] || typeConfig.info
              return (
                <React.Fragment key={notification.id}>
                  {index > 0 && (
                    <Divider sx={{ mx: 2 }} />
                  )}
                  <ListItem
                    button
                    onClick={() => handleNotificationClick(notification)}
                    sx={{
                      px: 2,
                      py: 1.5,
                      bgcolor: notification.is_read ? 'transparent' : 'action.hover',
                      '&:hover': {
                        bgcolor: 'action.selected',
                      },
                      cursor: 'pointer',
                    }}
                  >
                    <ListItemIcon sx={{ minWidth: 36, color: config.color }}>
                      {config.icon}
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Typography
                          variant="body2"
                          sx={{
                            fontWeight: notification.is_read ? 400 : 600,
                            color: 'text.primary',
                            lineHeight: 1.3,
                          }}
                        >
                          {notification.title}
                        </Typography>
                      }
                      secondary={
                        <Box>
                          {notification.message && (
                            <Typography
                              variant="caption"
                              sx={{
                                color: 'text.secondary',
                                display: 'block',
                                mt: 0.25,
                                lineHeight: 1.3,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                                maxWidth: 280,
                              }}
                            >
                              {notification.message}
                            </Typography>
                          )}
                          <Typography
                            variant="caption"
                            sx={{ color: 'text.disabled', fontSize: 10, mt: 0.25, display: 'block' }}
                          >
                            {formatTime(notification.created_at)}
                          </Typography>
                        </Box>
                      }
                      sx={{ my: 0 }}
                    />
                    {!notification.is_read && (
                      <Box
                        sx={{
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          bgcolor: '#3b66ff',
                          flexShrink: 0,
                          ml: 1,
                        }}
                      />
                    )}
                  </ListItem>
                </React.Fragment>
              )
            })}
          </List>
        )}
      </Box>
    </Paper>
  )
}

export default NotificationsPanel

