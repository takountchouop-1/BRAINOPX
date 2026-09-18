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
import ArrowBackIconImport from '@mui/icons-material/ArrowBack'
import { useAuth } from '../context/AuthContext.jsx'

const EmailIcon = EmailOutlinedIconImport?.default || EmailOutlinedIconImport
const LockIcon = LockOutlinedIconImport?.default || LockOutlinedIconImport
const VisibilityIcon = VisibilityIconImport?.default || VisibilityIconImport
const VisibilityOffIcon = VisibilityOffIconImport?.default || VisibilityOffIconImport
const ArrowBackIcon = ArrowBackIconImport?.default || ArrowBackIconImport

const SpecialistLogin = () => {
  const navigate = useNavigate()
  const { login, logout } = useAuth()
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
      const result = await login({ email, password })
      const role = result?.user?.role

      if (role !== 'specialist' && role !== 'admin') {
        logout()
        setError('This sign-in is for specialists only.')
        setIsLoading(false)
        return
      }

      navigate('/specialist')
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
        background:
          'radial-gradient(1200px 600px at 15% -10%, rgba(59,102,255,0.18), transparent 60%),' +
          'radial-gradient(900px 500px at 100% 110%, rgba(16,185,129,0.12), transparent 55%),' +
          '#0b1020',
      }}
    >
      <Button
        onClick={() => navigate('/landing')}
        startIcon={<ArrowBackIcon />}
        sx={{
          position: 'absolute',
          top: 20,
          left: 20,
          color: '#cbd5e1',
          textTransform: 'none',
          fontWeight: 600,
          '&:hover': { color: '#fff', backgroundColor: 'rgba(255,255,255,0.08)' },
        }}
      >
        Back
      </Button>

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
            background: 'rgba(255,255,255,0.98)',
            boxShadow: '0 30px 80px rgba(0,0,0,0.45)',
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
                background: 'linear-gradient(135deg, #3b66ff 0%, #2563eb 100%)',
                color: '#fff',
                fontWeight: 800,
                fontSize: 20,
              }}
            >
              S
            </Box>
            <Typography variant="h5" sx={{ fontWeight: 800, color: '#1e293b' }}>
              Specialist Portal
            </Typography>
            <Typography variant="body2" sx={{ color: '#64748b', mt: 0.5 }}>
              Sign in to view and respond to user requests.
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
              sx={{
                py: 1.3,
                fontWeight: 700,
                textTransform: 'none',
                background: 'linear-gradient(120deg, #3b66ff 0%, #2563eb 100%)',
                '&:hover': { filter: 'brightness(1.05)' },
              }}
            >
              {isLoading ? 'Signing in…' : 'Sign in'}
            </Button>
          </Stack>

          <Typography variant="caption" sx={{ display: 'block', textAlign: 'center', mt: 3, color: '#94a3b8' }}>
            Looking for the regular dashboard?{' '}
            <Link component={RouterLink} to="/login" sx={{ fontWeight: 600, color: '#3b66ff' }}>
              User sign in
            </Link>
          </Typography>
        </Paper>
      </motion.div>
    </Box>
  )
}

export default SpecialistLogin
