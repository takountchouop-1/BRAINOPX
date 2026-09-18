import React, { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Box } from '@mui/material'
import { AuthProvider, useAuth } from './context/AuthContext.jsx'
import { ThemeModeProvider } from './context/ThemeContext.jsx'
import { DashboardCustomizerProvider, useDashboardCustomizer } from './context/DashboardCustomizerContext.jsx'
import { AssistantChatProvider } from './context/AssistantChatContext.jsx'
import { NotificationProvider } from './context/NotificationContext.jsx'

//  Components (these are in src/components/)
import Login from './components/authentication/Login.jsx'
import DashboardCustomizerPanel from './components/DashboardCustomizerPanel.jsx'

//  Layout components (these are in src/DashbaordLayout/)
import Sidebar from './DashbaordLayout/Sidebar.jsx'
import Topbar from './DashbaordLayout/Topbar.jsx'
import Dashboard from './DashbaordLayout/DashboardHome.jsx'

//  Pages (these are in src/pages/)
import Register from './pages/Register.jsx'
import RegisterSuccess from './pages/RegisterSuccess.jsx'
import Profile from './pages/Profile.jsx'
import ConfigurationIngest from './pages/ConfigurationIngest.jsx'
import TaskManagement from './pages/TaskManagement.jsx'
import SkillEngine from './pages/SkillEngine.jsx'
import AiAssistant from './pages/AiAssistant.jsx'
import UserManagement from './pages/UserManagement.jsx'
import Landingpage from './pages/Landingpage.jsx'
import ForgotPassword from './pages/ForgotPassword.jsx'
import GoogleAuthCallback from './pages/GoogleAuthCallback.jsx'
import Support from './pages/Support.jsx'
import Notifications from './pages/Notifications.jsx'
import SpecialistLogin from './pages/SpecialistLogin.jsx'
import SpecialistDashboard from './pages/SpecialistDashboard.jsx'
import AdminLogin from './pages/AdminLogin.jsx'

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

//  Route guard — on top of ProtectedRoute's auth check, also requires
//  the "admin" role; a member hitting the URL directly is bounced to
//  the dashboard instead of seeing the page.
const AdminRoute = ({ children }) => {
  const { user, isAuthenticated, isInitializing } = useAuth()

  if (isInitializing) {
    return null
  }

  if (!isAuthenticated) {
    return <Navigate to="/admin/login" replace />
  }

  if (user?.role !== 'admin') {
    return <Navigate to="/dashboard" replace />
  }

  return children
}

//  Route guard for the dedicated specialist interface. Admins may also
//  work the specialist inbox, but a plain member is bounced to the
//  regular sign-in for that interface.
const SpecialistRoute = ({ children }) => {
  const { user, isAuthenticated, isInitializing } = useAuth()

  if (isInitializing) {
    return null
  }

  if (!isAuthenticated) {
    return <Navigate to="/specialist/login" replace />
  }

  if (user?.role !== 'specialist' && user?.role !== 'admin') {
    return <Navigate to="/specialist/login" replace />
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
      <AssistantChatProvider>
        <NotificationProvider>
          <Routes>
          <Route path="/landing" element={<Landingpage />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/register/success" element={<RegisterSuccess />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/auth/google/callback" element={<GoogleAuthCallback />} />
        <Route path="/specialist/login" element={<SpecialistLogin />} />
        <Route path="/specialist" element={<SpecialistRoute><SpecialistDashboard /></SpecialistRoute>} />
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route path="/" element={<ProtectedRoute><Layout {...layoutProps}><Dashboard /></Layout></ProtectedRoute>} />
        <Route path="/dashboard" element={<ProtectedRoute><Layout {...layoutProps}><Dashboard /></Layout></ProtectedRoute>} />
        <Route path="/dashboard/request" element={<ProtectedRoute><Layout {...layoutProps}><ConfigurationIngest /></Layout></ProtectedRoute>} />
        <Route path="/dashboard/tasks" element={<ProtectedRoute><Layout {...layoutProps}><TaskManagement /></Layout></ProtectedRoute>} />
        <Route path="/dashboard/rules" element={<ProtectedRoute><Layout {...layoutProps}><SkillEngine /></Layout></ProtectedRoute>} />
        {/* The sidebar has always linked here; the route was missing,
            so it fell through to the catch-all and redirected. */}
        <Route path="/dashboard/ai-assistant" element={<ProtectedRoute><Layout {...layoutProps}><AiAssistant /></Layout></ProtectedRoute>} />
        {/* User-facing support threads: view and reply to specialist responses. */}
        <Route path="/dashboard/support" element={<ProtectedRoute><Layout {...layoutProps}><Support /></Layout></ProtectedRoute>} />
        {/* In-app notification inbox — the sidebar bell links here. */}
        <Route path="/dashboard/notifications" element={<ProtectedRoute><Layout {...layoutProps}><Notifications /></Layout></ProtectedRoute>} />
        {/* Same situation: the sidebar has always linked to
            /dashboard/users, but nothing was registered for it. */}
        <Route path="/dashboard/users" element={<AdminRoute><Layout {...layoutProps}><UserManagement /></Layout></AdminRoute>} />
        <Route path="/profile" element={<ProtectedRoute><Layout {...layoutProps}><Profile /></Layout></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </NotificationProvider>
      </AssistantChatProvider>
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
