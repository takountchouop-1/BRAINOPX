import { useState } from 'react'
import { Box, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Tooltip, Typography } from '@mui/material'
import { alpha } from '@mui/material/styles'
import { motion } from 'framer-motion'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import DashboardIconImport from '@mui/icons-material/Dashboard'
import AssignmentIconImport from '@mui/icons-material/Assignment'
import CheckCircleIconImport from '@mui/icons-material/CheckCircle'
import PeopleIconImport from '@mui/icons-material/People'
import SettingsIconImport from '@mui/icons-material/Settings'
import PersonIconImport from '@mui/icons-material/Person'
import LogoutIconImport from '@mui/icons-material/Logout'
import agentIcon from '../assets/agent.jpg'
import { useAuth } from '../context/AuthContext.jsx'
import { useDashboardCustomizer } from '../context/DashboardCustomizerContext.jsx'

const DashboardIcon = DashboardIconImport?.default || DashboardIconImport
const AssignmentIcon = AssignmentIconImport?.default || AssignmentIconImport
const CheckCircleIcon = CheckCircleIconImport?.default || CheckCircleIconImport
const PeopleIcon = PeopleIconImport?.default || PeopleIconImport
const SettingsIcon = SettingsIconImport?.default || SettingsIconImport
const PersonIcon = PersonIconImport?.default || PersonIconImport
const LogoutIcon = LogoutIconImport?.default || LogoutIconImport

// Falls back to the same blue as the "Dark" quick theme, so the
// sidebar reads as blue-accented even before anyone opens the
// customizer.
const DEFAULT_ACCENT = '#3b66ff'

const menuItems = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard' },
  { text: 'Request', icon: <AssignmentIcon />, path: '/dashboard/request' },
  { text: 'Task Management', icon: <CheckCircleIcon />, path: '/dashboard/tasks' },
  {
    text: 'General assistant',
    icon: (
      <Box
        component="img"
        src={agentIcon}
        alt=""
        sx={{ width: 24, height: 24, borderRadius: '50%', objectFit: 'cover' }}
      />
    ),
    path: '/dashboard/ai-assistant',
  },
  { text: 'User Management', icon: <PeopleIcon />, path: '/dashboard/users' },
  { text: 'Rule Engine', icon: <SettingsIcon />, path: '/dashboard/rules' },
  { text: 'Profile', icon: <PersonIcon />, path: '/profile' },
]

const Sidebar = ({ collapsed = false }) => {
  const navigate = useNavigate()
  const location = useLocation()
  const { logout } = useAuth()
  const { settings } = useDashboardCustomizer()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const sidebarBg = settings.sidebarBg || null

  // The navigation highlight, hover tint and logout pill all pick up
  // this one colour, so choosing a quick theme (or a custom accent)
  // in the customizer visibly changes the whole sidebar, not just its
  // background.
  const accent = settings.primaryColor || DEFAULT_ACCENT

  return (
    <Box
      sx={{
        width: collapsed ? 72 : settings.sidebarWidth,
        minHeight: '100vh',
        height: '100vh',
        position: 'fixed',
        top: 0,
        left: 0,
        overflowY: 'auto',
        overflowX: 'hidden',
        background: sidebarBg
          ? sidebarBg
          : (theme) =>
              theme.palette.mode === 'dark'
                ? 'linear-gradient(180deg, #0a0a12 0%, #0d0d18 100%)'
                : 'linear-gradient(180deg, #1e3a8a 0%, #2563eb 45%, #3b82f6 100%)',
        color: '#fff',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1), background 0.3s ease',
        boxShadow: '4px 0 24px rgba(0,0,0,0.15)',
        zIndex: 1200,
      }}
    >
      <Box
        sx={{
          px: collapsed ? 2 : 3,
          py: 3,
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'space-between',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        <Typography
          variant="h6"
          sx={{
            fontWeight: 800,
            whiteSpace: 'nowrap',
            color: '#ffffff',
          }}
        >
          {collapsed ? 'IA' : 'Brain OPX'}
        </Typography>
      </Box>

      <List sx={{ flex: 1, px: collapsed ? 1 : 2, py: 2 }}>
        {menuItems.map((item) => {
          // Nested routes (e.g. a future /dashboard/tasks/123) still
          // light up their parent item; "/dashboard" itself is only
          // active on an exact match, or the whole menu would light
          // up together.
          const active =
            item.path === '/dashboard'
              ? location.pathname === '/dashboard' || location.pathname === '/'
              : location.pathname.startsWith(item.path)

          return (
            <Tooltip title={collapsed ? item.text : ''} placement="right" key={item.text}>
              <ListItem disablePadding sx={{ mb: 0.5 }}>
                <ListItemButton
                  component={NavLink}
                  to={item.path}
                  disableRipple
                  sx={{
                    position: 'relative',
                    borderRadius: 2.5,
                    color: active ? '#fff' : 'rgba(255,255,255,0.75)',
                    justifyContent: collapsed ? 'center' : 'flex-start',
                    px: collapsed ? 1.5 : 2,
                    py: 1.2,
                    overflow: 'hidden',
                    transition: 'color 0.15s ease, transform 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                    // An inactive row gets its own hover fill; the
                    // active row's fill is the sliding pill below, so
                    // it only needs the slide.
                    '&:hover': {
                      color: '#fff',
                      background: active ? 'transparent' : alpha(accent, 0.14),
                      transform: collapsed ? 'none' : 'translateX(3px)',
                    },
                  }}
                >
                  {/* One shared element: framer-motion glides this
                      between menu items on navigation instead of it
                      just appearing on the new one. */}
                  {active && (
                    <Box
                      component={motion.div}
                      layoutId="sidebar-active-pill"
                      transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                      sx={{
                        position: 'absolute',
                        inset: 0,
                        borderRadius: 2.5,
                        background: accent,
                        boxShadow: `0 6px 16px ${alpha(accent, 0.38)}`,
                        zIndex: 0,
                      }}
                    />
                  )}

                  <ListItemIcon
                    sx={{
                      position: 'relative',
                      zIndex: 1,
                      color: 'inherit',
                      minWidth: collapsed ? 0 : 40,
                      justifyContent: 'center',
                    }}
                  >
                    {item.icon}
                  </ListItemIcon>
                  {!collapsed && (
                    <ListItemText primary={item.text} sx={{ position: 'relative', zIndex: 1 }} />
                  )}
                </ListItemButton>
              </ListItem>
            </Tooltip>
          )
        })}
      </List>

      {/* Logout — a filled pill, matching the accent rather than the
          left-aligned list rows above it. */}
      <Box sx={{ px: collapsed ? 1 : 2, pb: 2.5, pt: 1 }}>
        <Tooltip title={collapsed ? 'Logout' : ''} placement="right">
          <Box
            component="button"
            type="button"
            onClick={handleLogout}
            sx={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 1,
              appearance: 'none',
              cursor: 'pointer',
              borderRadius: '999px',
              border: `1.5px solid ${alpha(accent, 0.55)}`,
              background: alpha(accent, 0.14),
              color: accent,
              fontFamily: 'inherit',
              fontWeight: 700,
              fontSize: 14,
              letterSpacing: 0.3,
              py: 1.1,
              px: collapsed ? 0 : 2,
              transition: 'background 0.15s ease, transform 0.15s ease',
              '&:hover': {
                background: alpha(accent, 0.24),
                transform: 'translateY(-1px)',
              },
              '&:active': {
                transform: 'translateY(0)',
              },
            }}
          >
            <LogoutIcon sx={{ fontSize: 19 }} />
            {!collapsed && 'LOGOUT'}
          </Box>
        </Tooltip>
      </Box>
    </Box>
  )
}

export default Sidebar
