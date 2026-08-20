import React from 'react'
import { Box } from '@mui/material'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import { useDashboardCustomizer } from '../context/DashboardCustomizerContext.jsx'

const Dashboard = () => {
  const { settings } = useDashboardCustomizer()
  const sidebarWidth = settings.sidebarCollapsed ? 72 : settings.sidebarWidth

  return (
    <Box
      sx={{
        display: 'flex',
        height: '100vh',
        width: '100vw',
        overflow: 'hidden',
        background: (theme) =>
          theme.palette.mode === 'dark'
            ? 'radial-gradient(circle at top left, rgba(79, 70, 229, 0.18), transparent 22%), radial-gradient(circle at bottom right, rgba(59, 130, 246, 0.16), transparent 24%), linear-gradient(180deg, #020814 0%, #071a37 100%)'
            : '#f4f7fb',
      }}
    >
      {/* Sidebar - dynamic width */}
      <Box
        sx={{
          width: sidebarWidth,
          flexShrink: 0,
          height: '100vh',
          overflow: 'hidden',
          transition: 'width 0.3s ease',
        }}
      >
        <Sidebar />
      </Box>

      {/* Main Content */}
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
          width: `calc(100% - ${sidebarWidth}px)`,
          overflow: 'hidden',
          transition: 'width 0.3s ease',
        }}
      >
        {/* Topbar */}
        <Box
          sx={{
            flexShrink: 0,
            height: 64,
            overflow: 'hidden',
          }}
        >
          <Topbar />
        </Box>

        {/* Page Content - only this scrolls if needed */}
        <Box
          component="main"
          sx={{
            flex: 1,
            overflowY: 'auto',
            overflowX: 'hidden',
            p: 2,
            height: 'calc(100vh - 64px)',
            width: '100%',
          }}
        >
          <Box sx={{ maxWidth: '100%' }}>
            <Outlet />
          </Box>
        </Box>
      </Box>
    </Box>
  )
}

export default Dashboard
