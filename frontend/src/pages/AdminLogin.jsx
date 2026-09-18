import React, { useState } from 'react'
import {
  Alert,
  Box,
  Button,
  InputAdornment,
  Paper,
  Stack,
  TextField,
  Typography,
  IconButton,
  Link,
} from '@mui/material'
import { motion } from 'framer-motion'
import { useNavigate, Link as RouterLink } from 'react-router-dom'
import EmailOutlinedIconImport from '@mui/icons-material/EmailOutlined'
import LockOutlinedIconImport from '@mui/icons-material/LockOutlined'
import VisibilityIconImport from '@mui/icons-material/Visibility'
import VisibilityOffIconImport from '@mui/icons-material/VisibilityOff'
import AdminPanelSettingsOutlinedIconImport from '@mui/icons-material/AdminPanelSettingsOutlined'
import ArrowForwardIconImport from '@mui/icons-material/ArrowForward'
import { authButtonStyles } from '../components/authentication/authStyles.js'
import { useAuth } from '../context/AuthContext.jsx'

const EmailIcon = EmailOutlinedIconImport?.default || EmailOutlinedIconImport
const LockIcon = LockOutlinedIconImport?.default || LockOutlinedIconImport
const VisibilityIcon = VisibilityIconImport?.default || VisibilityIconImport
const VisibilityOffIcon = VisibilityOffIconImport?.default || VisibilityOffIconImport
const AdminIcon = AdminPanelSettingsOutlinedIconImport?.default || AdminPanelSettingsOutlinedIconImport
const ArrowForwardIcon = ArrowForwardIconImport?.default || ArrowForwardIconImport

const AdminLogin = () => {
  const navigate = useNavigate()
  const { loginAdmin } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')

    if (!email.trim() || !password.trim()) {
      setError('Enter your email and password.')
      return
    }

    setIsLoading(true)
    try {
      // The backend /admin-login endpoint already rejects any account
      // that is not an admin or specialist, so no session is ever
      // created for a regular user here.
      const result = await loginAdmin({ email, password })
      const role = result?.user?.role
      navigate(role === 'specialist' ? '/specialist' : '/dashboard')
    } catch (authError) {
      setError(authError?.message || 'Sign-in failed.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        px: 2,
        py: 4,
        background: '#ffffff',
      }}
    >
      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        style={{ width: '100%', maxWidth: 420 }}
      >
        <Paper
          elevation={0}
          sx={{
            borderRadius: 4,
            px: { xs: 3, sm: 5 },
            py: 5,
            background: '#ffffff',
            boxShadow: '0 24px 60px rgba(59,102,255,0.16), 0 4px 16px rgba(15,23,42,0.06)',
          }}
        >
          <Box sx={{ textAlign: 'center', mb: 1 }}>
            <Box
              sx={{
                width: 54,
                height: 54,
                mx: 'auto',
                mb: 2,
                borderRadius: 3,
                display: 'grid',
                placeItems: 'center',
                background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                color: '#fff',
              }}
            >
              <AdminIcon />
            </Box>
            <Typography variant="h5" sx={{ fontWeight: 800, color: '#1e293b' }}>
              Admin Portal
            </Typography>
            <Typography variant="body2" sx={{ color: '#64748b', mt: 0.5 }}>
              Sign in to manage users, tasks and rules.
            </Typography>
          </Box>

          <Stack component="form" spacing={2.25} onSubmit={handleSubmit} noValidate sx={{ mt: 3 }}>
            {error ? <Alert severity="error">{error}</Alert> : null}

            <TextField
              fullWidth
              required
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start" sx={{ color: '#64748b' }}>
                    <EmailIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
            />

            <TextField
              fullWidth
              required
              label="Password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start" sx={{ color: '#64748b' }}>
                    <LockIcon fontSize="small" />
                  </InputAdornment>
                ),
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton onClick={() => setShowPassword((v) => !v)} edge="end">
                      {showPassword ? <VisibilityOffIcon fontSize="small" /> : <VisibilityIcon fontSize="small" />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />

            <Button
              type="submit"
              fullWidth
              disabled={isLoading}
              variant="contained"
              endIcon={<ArrowForwardIcon />}
              sx={{
                ...authButtonStyles,
                py: 1.3,
                '& .MuiButton-endIcon': { transition: 'transform 0.3s ease' },
                '&:hover .MuiButton-endIcon': { transform: 'translateX(5px)' },
              }}
            >
              {isLoading ? 'Signing in…' : 'Sign in'}
            </Button>
          </Stack>

          <Typography variant="caption" sx={{ display: 'block', textAlign: 'center', mt: 3, color: '#94a3b8' }}>
            Not an administrator?{' '}
            <Link component={RouterLink} to="/login" sx={{ fontWeight: 600, color: '#4f46e5' }}>
              User sign in
            </Link>
          </Typography>
        </Paper>
      </motion.div>
    </Box>
  )
}

export default AdminLogin
