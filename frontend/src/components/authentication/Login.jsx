import React, { useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  Link,
  Paper,
  Stack,
  TextField,
  Typography,
  InputAdornment,
  IconButton,
  Divider,
} from '@mui/material'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import mascot from '../../assets/mascot.png'
import EmailOutlinedIconImport from '@mui/icons-material/EmailOutlined'
import LockOutlinedIconImport from '@mui/icons-material/LockOutlined'
import AppleIconImport from '@mui/icons-material/Apple'
import VisibilityIconImport from '@mui/icons-material/Visibility'
import VisibilityOffIconImport from '@mui/icons-material/VisibilityOff'
import ArrowForwardIconImport from '@mui/icons-material/ArrowForward'
import ArrowBackIconImport from '@mui/icons-material/ArrowBack'
import { useAuth } from '../../context/AuthContext.jsx'
import { GoogleGlyph, FacebookGlyph } from './SocialIcons.jsx'
import {
  AUTH_PAGE_BG,
  AUTH_HERO_BG,
  AUTH_TITLE_GRADIENT,
  AUTH_CARD_RADIUS,
  AUTH_CARD_SHADOW,
  authInputStyles,
  authCheckboxStyles,
  authLinkStyles,
  authButtonStyles,
  authSocialCircleStyles,
} from './authStyles.js'

const EmailOutlinedIcon = EmailOutlinedIconImport?.default || EmailOutlinedIconImport
const LockOutlinedIcon = LockOutlinedIconImport?.default || LockOutlinedIconImport
const AppleIcon = AppleIconImport?.default || AppleIconImport
const VisibilityIcon = VisibilityIconImport?.default || VisibilityIconImport
const VisibilityOffIcon = VisibilityOffIconImport?.default || VisibilityOffIconImport
const ArrowForwardIcon = ArrowForwardIconImport?.default || ArrowForwardIconImport
const ArrowBackIcon = ArrowBackIconImport?.default || ArrowBackIconImport

const Login = () => {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [rememberMe, setRememberMe] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    const rememberedEmail = localStorage.getItem('rememberedEmail')
    if (rememberedEmail) {
      setEmail(rememberedEmail)
      setRememberMe(true)
    }
  }, [])

  const validateEmail = (value) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setStatus('')

    if (!email.trim() || !validateEmail(email)) {
      setError('Please enter a valid email address.')
      return
    }

    if (!password.trim() || password.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }

    setIsLoading(true)
    try {
      // useAuth().login() handles storing the token/user under the single
      // shared key ('brainopx_token') that the rest of the app reads from.
      await login({ email, password })
      setStatus('Signed in successfully.')

      if (rememberMe) {
        localStorage.setItem('rememberedEmail', email)
      } else {
        localStorage.removeItem('rememberedEmail')
      }
      navigate('/dashboard')
    } catch (authError) {
      setError(authError?.message || 'Unable to sign in. Please check your credentials.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Box
      component="main"
      sx={{
        minHeight: '100vh',
        background: AUTH_PAGE_BG,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        px: 2,
        py: 3,
        position: 'relative',
      }}
    >
      <Button
        onClick={() => navigate('/landing')}
        startIcon={<ArrowBackIcon />}
        sx={{
          position: 'absolute',
          top: { xs: 12, md: 24 },
          left: { xs: 12, md: 24 },
          textTransform: 'none',
          fontWeight: 600,
          color: '#475569',
          '&:hover': { backgroundColor: 'rgba(59,102,255,0.08)' },
        }}
      >
        Back to Home
      </Button>
      <Paper
        elevation={10}
        sx={{
          width: '100%',
          maxWidth: 760,
          borderRadius: AUTH_CARD_RADIUS,
          overflow: 'hidden',
          boxShadow: AUTH_CARD_SHADOW,
          background: '#ffffff'
        }}
      >
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: '1fr 1.05fr' },
            minHeight: { xs: 'auto', md: 400 },
          }}
        >
          <Box
            sx={{
              position: 'relative',
              background: AUTH_HERO_BG,
              color: '#ffffff',
              px: { xs: 4, md: 4.5 },
              py: { xs: 3.5, md: 4.5 },
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              overflow: 'hidden',
            }}
          >
            <Box sx={{ position: 'absolute', top: 18, left: 18, width: 56, height: 56, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.12)' }} />
            <Box sx={{ position: 'absolute', top: 38, left: 86, width: 10, height: 56, borderRadius: 8, bgcolor: 'rgba(255,255,255,0.18)' }} />
            <Box sx={{ position: 'absolute', bottom: 24, right: 32, width: 96, height: 96, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.08)' }} />
            <Box sx={{ position: 'absolute', bottom: 64, left: 32, width: 72, height: 72, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.08)' }} />

            <Box sx={{ zIndex: 1 }}>
              <motion.div
                initial={{ y: -24, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ duration: 0.75, ease: 'easeOut' }}
              >
                <Typography
                  sx={{
                    fontWeight: 800,
                    fontSize: { xs: 24, md: 27 },
                    lineHeight: 1.15,
                    mb: 1.5,
                    ...AUTH_TITLE_GRADIENT,
                  }}
                >
                  OUR INTELLIGENT ASSISTANT BRAINOPX
                </Typography>
              </motion.div>
                 <Box component="img" src={mascot} alt="mascot" sx={{ width: 150, mt: 2, display: 'block' }} />
            </Box>

            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mt: 2.5, zIndex: 1 }}>
              <Box sx={{ width: 48, height: 48, borderRadius: 3, bgcolor: 'rgba(255,255,255,0.12)' }} />
              <Box sx={{ width: 34, height: 34, borderRadius: 2, bgcolor: 'rgba(255,255,255,0.18)' }} />
              <Box sx={{ width: 66, height: 66, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.08)' }} />
            </Box>
          </Box>

          <Box sx={{ background: '#ffffff', px: { xs: 4, md: 4.5 }, py: { xs: 3.5, md: 4.5 }, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Box sx={{ width: '100%', maxWidth: 380 }}>
              <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2.5 }}>
                 <Box
                   sx={{
                     width: 52,
                     height: 52,
                     borderRadius: 3,
                     background: '#eef4ff',
                    display: 'grid',
                    placeItems: 'center',
                    color: '#3b66ff',
                    fontWeight: 700,
                    fontSize: 20,
                  }}
                >
                  A
                </Box>
              </Box>
              <Typography variant="h5" align="center" sx={{ fontWeight: 700, mb: 0.75, color: '#1e293b' }}>
                Hello ! Welcome back
              </Typography>
              <Typography variant="body2" align="center" sx={{ mb: 3, color: '#64748b' }}>
               Enter Your Credentials to access your account .
              </Typography>

              <Stack component="form" spacing={2.25} onSubmit={handleSubmit} noValidate>
                {error ? <Alert severity="error">{error}</Alert> : null}
                {status ? <Alert severity="success">{status}</Alert> : null}

                <TextField
                  fullWidth
                  required
                  label="Email"
                  placeholder="Enter your email address"
                  name="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start" sx={{ color: '#64748b' }}>
                        <EmailOutlinedIcon fontSize="small" />
                      </InputAdornment>
                    ),
                  }}
                  sx={authInputStyles}
                />

                <TextField
                  fullWidth
                  required
                  label="Password"
                  placeholder="Enter your password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start" sx={{ color: '#64748b' }}>
                        <LockOutlinedIcon fontSize="small" />
                      </InputAdornment>
                    ),
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          edge="end"
                          aria-label={showPassword ? 'Hide password' : 'Show password'}
                          onClick={() => setShowPassword((s) => !s)}
                          onMouseDown={(e) => e.preventDefault()}
                          sx={{ color: '#64748b' }}
                        >
                          {showPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                  sx={authInputStyles}
                />

                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <FormControlLabel
                    control={<Checkbox checked={rememberMe} onChange={(event) => setRememberMe(event.target.checked)} sx={authCheckboxStyles} />}
                    label={<Typography variant="body2" sx={{ color: '#475569' }}>Remember me</Typography>}
                    sx={{ ml: -1 }}
                  />
                 <Link href="/forgot-password" underline="hover" sx={{ fontSize: 14, ...authLinkStyles }}>
                 Reset Password?</Link>
                </Box>

                <Button
                  type="submit"
                  fullWidth
                  variant="contained"
                  endIcon={<ArrowForwardIcon />}
                  sx={{
                    ...authButtonStyles,
                    py: 1.3,
                    '& .MuiButton-endIcon': { transition: 'transform 0.3s ease' },
                    '&:hover .MuiButton-endIcon': { transform: 'translateX(5px)' },
                  }}
                  disabled={isLoading}
                >
                  {isLoading ? 'Signing in...' : 'Login'}
                </Button>

                <Divider sx={{ my: 1, '&::before, &::after': { borderColor: '#cbd5e1' }, color: '#64748b' }}>or</Divider>

                <Stack direction="row" spacing={2} justifyContent="center">
                  <IconButton aria-label="Continue with Google" sx={authSocialCircleStyles}>
                    <GoogleGlyph size={22} />
                  </IconButton>
                  <IconButton aria-label="Continue with Facebook" sx={authSocialCircleStyles}>
                    <FacebookGlyph size={22} />
                  </IconButton>
                  <IconButton aria-label="Continue with Apple" sx={authSocialCircleStyles}>
                    <AppleIcon sx={{ color: '#1e293b' }} />
                  </IconButton>
                </Stack>

                <Typography align="center" sx={{ color: '#64748b', mt: 0.75 }}>
                  Don’t have an account?{' '}
                  <Link href="/register" underline="hover" sx={authLinkStyles}>
                    Create Account
                  </Link>
                </Typography>
              </Stack>
            </Box>
          </Box>
        </Box>
      </Paper>
    </Box>
  )
}

export default Login