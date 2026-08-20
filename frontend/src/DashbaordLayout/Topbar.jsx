import React, { useState, useEffect } from 'react'
import { Box, InputBase, IconButton, Paper, Tooltip, Avatar, Badge } from '@mui/material'
import SearchIconImport from '@mui/icons-material/Search'
import DarkModeIconImport from '@mui/icons-material/DarkMode'
import LightModeIconImport from '@mui/icons-material/LightMode'
import NotificationsIconImport from '@mui/icons-material/Notifications'
import PaletteIconImport from '@mui/icons-material/Palette'
import { useThemeMode } from '../context/ThemeContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useNavigate } from 'react-router-dom'
import { fetchUnreadCount } from '../services/NotificationService'
import NotificationsPanel from '../components/NotificationsPanel'
import { useDashboardCustomizer } from '../context/DashboardCustomizerContext.jsx'

const SearchIcon = SearchIconImport?.default || SearchIconImport
const DarkModeIcon = DarkModeIconImport?.default || DarkModeIconImport
const LightModeIcon = LightModeIconImport?.default || LightModeIconImport
const NotificationsIcon = NotificationsIconImport?.default || NotificationsIconImport
const PaletteIcon = PaletteIconImport?.default || PaletteIconImport

const Topbar = ({ onSearch, searchPlaceholder = 'Search...', sidebarWidth = 260 }) => {
  const { mode, toggleMode } = useThemeMode()
  const { user } = useAuth()
  const { togglePanel } = useDashboardCustomizer()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [searchFocused, setSearchFocused] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const searchActive = searchFocused || query.length > 0

  useEffect(() => {
    loadUnreadCount()
    const interval = setInterval(loadUnreadCount, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadUnreadCount = async () => {
    try {
      const data = await fetchUnreadCount()
      setUnreadCount(data.count)
    } catch (err) {
      // Silently fail
    }
  }

  const handleChange = (event) => {
    const value = event.target.value
    setQuery(value)
    if (onSearch) onSearch(value)
  }

  const handleNotificationsToggle = () => {
    setNotificationsOpen((prev) => !prev)
  }

  const handleNotificationsClose = () => {
    setNotificationsOpen(false)
  }

  const handleUnreadCountChange = (count) => {
    setUnreadCount(count)
  }

  const initials = user?.full_name
    ? user.full_name
        .split(' ')
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0].toUpperCase())
        .join('')
    : '?'

  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const profilePictureUrl = user?.profile_picture
    ? `${API_BASE_URL}/uploads/profiles/${user.profile_picture}`
    : null

  return (
    <Box
      sx={{
        position: 'fixed',
        top: 0,
        left: sidebarWidth,
        right: 0,
        zIndex: 1100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 2,
        px: 3,
        py: 2,
        transition: 'left 0.3s ease',
        borderBottom: (theme) =>
          `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`,
        background: (theme) => theme.palette.background.default,
      }}
    >
      <Box
        sx={{
          flex: 1,
          maxWidth: 480,
          borderRadius: 3.5,
          p: '1.5px',
          background: searchActive
            ? 'linear-gradient(120deg, #3b66ff 0%, #7ea2ff 50%, #bfdbfe 100%)'
            : 'linear-gradient(120deg, #dbe4ff 0%, #eef2ff 55%, #ffffff 100%)',
          boxShadow: searchActive
            ? '0 0 0 4px rgba(59,102,255,0.14), 0 10px 24px rgba(59,102,255,0.18)'
            : '0 2px 6px rgba(15,23,42,0.04)',
          transition: 'background 0.4s ease, box-shadow 0.4s ease',
        }}
      >
        <Paper
          component="form"
          onSubmit={(e) => e.preventDefault()}
          sx={{
            display: 'flex',
            alignItems: 'center',
            px: 2,
            py: 0.5,
            borderRadius: 3,
            // Opaque, not translucent — this sits on top of the
            // gradient border below, and a see-through fill let that
            // light gradient bleed through in dark mode, washing out
            // white input text to the point of being unreadable.
            background: (theme) =>
              theme.palette.mode === 'dark' ? '#11162a' : '#ffffff',
            boxShadow: 'none',
          }}
        >
          <SearchIcon
            fontSize="small"
            sx={{
              color: searchActive ? '#3b66ff' : 'text.secondary',
              mr: 1,
              transition: 'color 0.3s ease, transform 0.3s ease',
              transform: searchActive ? 'scale(1.08)' : 'scale(1)',
            }}
          />
          <InputBase
            placeholder={searchPlaceholder}
            value={query}
            onChange={handleChange}
            onFocus={() => setSearchFocused(true)}
            onBlur={() => setSearchFocused(false)}
            fullWidth
            sx={{ color: 'text.primary', fontSize: 14 }}
          />
        </Paper>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        {/* Customizer Button */}
        <Tooltip title="Customize Dashboard">
          <IconButton
            onClick={togglePanel}
            sx={{
              color: 'text.primary',
              background: (theme) =>
                theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : '#ffffff',
              border: (theme) =>
                `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
              '&:hover': {
                background: (theme) =>
                  theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.12)' : '#f3f4f6',
              },
            }}
          >
            <PaletteIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        {/* Theme Toggle */}
        <Tooltip title={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
          <IconButton
            onClick={toggleMode}
            sx={{
              color: 'text.primary',
              background: (theme) =>
                theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : '#ffffff',
              border: (theme) =>
                `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
              '&:hover': {
                background: (theme) =>
                  theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.12)' : '#f3f4f6',
              },
            }}
          >
            {mode === 'dark' ? <LightModeIcon fontSize="small" /> : <DarkModeIcon fontSize="small" />}
          </IconButton>
        </Tooltip>

        <Box sx={{ position: 'relative' }}>
          <Tooltip title="Notifications">
            <IconButton
              onClick={handleNotificationsToggle}
              sx={{
                color: 'text.primary',
                background: (theme) =>
                  theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : '#ffffff',
                border: (theme) =>
                  `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}`,
                '&:hover': {
                  background: (theme) =>
                    theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.12)' : '#f3f4f6',
                },
              }}
            >
              <Badge badgeContent={unreadCount} color="error">
                <NotificationsIcon fontSize="small" />
              </Badge>
            </IconButton>
          </Tooltip>
          {notificationsOpen && (
            <NotificationsPanel
              open={notificationsOpen}
              onClose={handleNotificationsClose}
              onUnreadCountChange={handleUnreadCountChange}
            />
          )}
        </Box>

        <Tooltip title={user?.full_name || 'Profile'}>
          <Avatar
            onClick={() => navigate('/profile')}
            sx={{
              width: 38,
              height: 38,
              bgcolor: profilePictureUrl ? 'transparent' : '#3b66ff',
              fontSize: 14,
              fontWeight: 700,
              cursor: 'pointer',
              '&:hover': {
                opacity: 0.85,
              },
            }}
            src={profilePictureUrl}
          >
            {!profilePictureUrl && initials}
          </Avatar>
        </Tooltip>
      </Box>
    </Box>
  )
}

export default Topbar
