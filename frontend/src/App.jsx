import React, { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Box } from '@mui/material'
import { AuthProvider, useAuth } from './context/AuthContext.jsx'
import { ThemeModeProvider } from './context/ThemeContext.jsx'
import { DashboardCustomizerProvider, useDashboardCustomizer } from './context/DashboardCustomizerContext.jsx'

//  Components (these are in src/components/)
import Login from './components/authentication/Login.jsx'
import DashboardCustomizerPanel from './components/DashboardCustomizerPanel.jsx'

//  Layout components (these are in src/DashbaordLayout/)
import Sidebar from './DashbaordLayout/Sidebar.jsx'
import Topbar from './DashbaordLayout/Topbar.jsx'
import Dashboard from './DashbaordLayout/DashboardHome.jsx'

//  Pages (these are in src/pages/)
import Register from './pages/Register.jsx'
import Profile from './pages/Profile.jsx'
import ConfigurationIngest from './pages/ConfigurationIngest.jsx'
import TaskManagement from './pages/TaskManagement.jsx'
import SkillEngine from './pages/SkillEngine.jsx'
import AiAssistant from './pages/AiAssistant.jsx'
import UserManagement from './pages/UserManagement.jsx'
import Landingpage from './pages/Landingpage.jsx'

//  Route guard — redirects to /login if not authenticated
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, isInitializing } = useAuth()

  if (isInitializing) {
    return null // or a loading spinner
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return children
}

// Defined once at module scope, not inside AppContent's render body.
// A component declared inline in another component's function is a
// brand-new function identity on every render of that parent — React
// then treats it as a different component type at the same JSX spot
// and unmounts/remounts everything under it. That was silently
// nuking Topbar's own state on every keystroke (searchTerm lived in
// AppContent, so typing re-rendered AppContent, which redefined
// Layout, which remounted Topbar): the search box could never hold
// more than the last character typed, and nothing ever got filtered.
const Layout = ({ children, sidebarWidth, sidebarCollapsed, searchTerm, setSearchTerm }) => {
  const childrenWithProps = React.Children.map(children, (child) => {
    if (React.isValidElement(child)) {
      return React.cloneElement(child, { searchTerm, setSearchTerm })
    }
    return child
  })

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar collapsed={sidebarCollapsed} />
      <Topbar
        onSearch={setSearchTerm}
        searchPlaceholder="Search tasks, requests, users..."
        sidebarWidth={sidebarWidth}
      />
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          mt: '64px',
          ml: `${sidebarWidth}px`,
          width: `calc(100% - ${sidebarWidth}px)`,
          minHeight: 'calc(100vh - 64px)',
          overflow: 'auto',
          transition: 'margin-left 0.3s ease, width 0.3s ease',
        }}
      >
        {childrenWithProps}
      </Box>
      <DashboardCustomizerPanel />
    </Box>
  )
}

function AppContent() {
  const { settings } = useDashboardCustomizer()
  const [searchTerm, setSearchTerm] = useState('')

  const sidebarWidth = settings.sidebarCollapsed ? 72 : settings.sidebarWidth

  const layoutProps = {
    sidebarWidth,
    sidebarCollapsed: settings.sidebarCollapsed,
    searchTerm,
    setSearchTerm,
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/landing" element={<Landingpage />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/" element={<ProtectedRoute><Layout {...layoutProps}><Dashboard /></Layout></ProtectedRoute>} />
        <Route path="/dashboard" element={<ProtectedRoute><Layout {...layoutProps}><Dashboard /></Layout></ProtectedRoute>} />
        <Route path="/dashboard/request" element={<ProtectedRoute><Layout {...layoutProps}><ConfigurationIngest /></Layout></ProtectedRoute>} />
        <Route path="/dashboard/tasks" element={<ProtectedRoute><Layout {...layoutProps}><TaskManagement /></Layout></ProtectedRoute>} />
        <Route path="/dashboard/rules" element={<ProtectedRoute><Layout {...layoutProps}><SkillEngine /></Layout></ProtectedRoute>} />
        {/* The sidebar has always linked here; the route was missing,
            so it fell through to the catch-all and redirected. */}
        <Route path="/dashboard/ai-assistant" element={<ProtectedRoute><Layout {...layoutProps}><AiAssistant /></Layout></ProtectedRoute>} />
        {/* Same situation: the sidebar has always linked to
            /dashboard/users, but nothing was registered for it. */}
        <Route path="/dashboard/users" element={<ProtectedRoute><Layout {...layoutProps}><UserManagement /></Layout></ProtectedRoute>} />
        <Route path="/profile" element={<ProtectedRoute><Layout {...layoutProps}><Profile /></Layout></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

function App() {
  return (
    <AuthProvider>
      <DashboardCustomizerProvider>
        <ThemeModeProvider>
          <AppContent />
        </ThemeModeProvider>
      </DashboardCustomizerProvider>
    </AuthProvider>
  )
}

export default App
