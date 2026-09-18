import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { useAuth } from './AuthContext.jsx'
import {
  fetchNotifications,
  fetchUnreadCount,
  markAsRead,
  markAllAsRead,
  deleteNotification as deleteNotificationRequest,
} from '../services/NotificationService.js'

const NotificationContext = createContext(null)

const POLL_INTERVAL_MS = 30000

// Single source of truth for in-app notifications so the sidebar badge,
// the topbar bell and the notifications page never drift apart.
export const NotificationProvider = ({ children }) => {
  const { user, isInitializing } = useAuth()

  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(false)

  const isSignedIn = Boolean(user?.id)
  const lastUserIdRef = useRef(null)

  const refreshNotifications = useCallback(async () => {
    if (!isSignedIn) return
    setLoading(true)
    try {
      const data = await fetchNotifications()
      setNotifications(data)
      setUnreadCount(data.filter((n) => !n.is_read).length)
    } catch (err) {
      // Best-effort: the poll below will retry shortly.
      console.error('Failed to load notifications:', err)
    } finally {
      setLoading(false)
    }
  }, [isSignedIn])

  const refreshUnreadCount = useCallback(async () => {
    if (!isSignedIn) return
    try {
      const data = await fetchUnreadCount()
      setUnreadCount(data.count)
    } catch (err) {
      // Best-effort: the poll below will retry shortly.
      console.error('Failed to load unread count:', err)
    }
  }, [isSignedIn])

  const markNotificationRead = useCallback(
    async (id) => {
      try {
        await markAsRead(id)
        const wasUnread = notifications.some((n) => n.id === id && !n.is_read)
        setNotifications((prev) =>
          prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
        )
        if (wasUnread) {
          setUnreadCount((prev) => Math.max(0, prev - 1))
        }
      } catch (err) {
        console.error('Failed to mark notification as read:', err)
      }
    },
    [notifications]
  )

  const markAllRead = useCallback(async () => {
    try {
      await markAllAsRead()
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
      setUnreadCount(0)
    } catch (err) {
      console.error('Failed to mark all notifications as read:', err)
    }
  }, [])

  const deleteNotification = useCallback(
    async (id) => {
      try {
        await deleteNotificationRequest(id)
        const wasUnread = notifications.some((n) => n.id === id && !n.is_read)
        setNotifications((prev) => prev.filter((n) => n.id !== id))
        if (wasUnread) {
          setUnreadCount((prev) => Math.max(0, prev - 1))
        }
      } catch (err) {
        console.error('Failed to delete notification:', err)
      }
    },
    [notifications]
  )

  // Reset state and reload whenever the signed-in user changes (login,
  // logout, or a different account on the same tab).
  useEffect(() => {
    if (isInitializing) return
    const userId = user?.id ?? null
    if (userId !== lastUserIdRef.current) {
      lastUserIdRef.current = userId
      setNotifications([])
      setUnreadCount(0)
      if (userId) {
        refreshNotifications()
        refreshUnreadCount()
      }
    }
  }, [user?.id, isInitializing, refreshNotifications, refreshUnreadCount])

  // Keep the unread badge fresh without reloading the whole list.
  useEffect(() => {
    if (!isSignedIn) return
    const interval = setInterval(refreshUnreadCount, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [isSignedIn, refreshUnreadCount])

  const value = {
    notifications,
    unreadCount,
    loading,
    refreshNotifications,
    refreshUnreadCount,
    markNotificationRead,
    markAllRead,
    deleteNotification,
  }

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  )
}

export const useNotifications = () => {
  const context = useContext(NotificationContext)
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider')
  }
  return context
}

export default NotificationContext
