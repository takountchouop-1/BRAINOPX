import React, { useState } from 'react'
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
import EmailOutlinedIconImport from '@mui/icons-material/EmailOutlined'
import LockOutlinedIconImport from '@mui/icons-material/LockOutlined'
import PersonOutlineIconImport from '@mui/icons-material/PersonOutline'
import VisibilityIconImport from '@mui/icons-material/Visibility'
import VisibilityOffIconImport from '@mui/icons-material/VisibilityOff'
import AppleIconImport from '@mui/icons-material/Apple'
import { GoogleGlyph, FacebookGlyph } from '../components/authentication/SocialIcons.jsx'
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
} from '../components/authentication/authStyles.js'

const EmailOutlinedIcon = EmailOutlinedIconImport?.default || EmailOutlinedIconImport
const LockOutlinedIcon = LockOutlinedIconImport?.default || LockOutlinedIconImport
const PersonOutlineIcon = PersonOutlineIconImport?.default || PersonOutlineIconImport
const VisibilityIcon = VisibilityIconImport?.default || VisibilityIconImport
const VisibilityOffIcon = VisibilityOffIconImport?.default || VisibilityOffIconImport
const AppleIcon = AppleIconImport?.default || AppleIconImport

const Register = () => {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [agree, setAgree] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [fullNameError, setFullNameError] = useState('')
  const [emailError, setEmailError] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [confirmPasswordError, setConfirmPasswordError] = useState('')
  const [agreeError, setAgreeError] = useState('')

  const validateEmail = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setStatus('')

    const fErr = !fullName.trim() ? 'Full name is required.' : ''
    const eErr = !email.trim() ? 'Email is required.' : !validateEmail(email) ? 'Enter a valid email.' : ''
    const pErr = !password ? 'Password is required.' : password.length < 8 ? 'Password must be at least 8 characters.' : ''
    const cErr = !confirmPassword ? 'Please confirm your password.' : password !== confirmPassword ? 'Passwords do not match.' : ''
    const aErr = !agree ? 'You must agree to the terms and privacy policy.' : ''

    setFullNameError(fErr)
    setEmailError(eErr)
    setPasswordError(pErr)
    setConfirmPasswordError(cErr)
    setAgreeError(aErr)

    if (fErr || eErr || pErr || cErr || aErr) {
      return
    }

    setIsLoading(true)
    try {
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
      const resp = await fetch(`${API_BASE_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: fullName, email, password }),
      })
      if (!resp.ok) {
        const payload = await resp.json().catch(() => null)
        const detailMessage = Array.isArray(payload?.detail)
          ? payload.detail.map((d) => d.msg).join(', ')
          : payload?.detail
        throw new Error(detailMessage || 'Registration failed.')
      }
      setStatus('Account created successfully. You can now sign in.')
      setFullName('')
      setEmail('')
      setPassword('')
      setConfirmPassword('')
      setAgree(false)
    } catch (err) {
      setError(err?.message || 'Unable to register. Try again later.')
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
      }}
    >
      <Paper
        elevation={10}
        sx={{
          width: '100%',
          maxWidth: 900,
          borderRadius: AUTH_CARD_RADIUS,
          overflow: 'hidden',
          boxShadow: AUTH_CARD_SHADOW,
          background: '#ffffff'
        }}
      >
         <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1.05fr' }, minHeight: { xs: 'auto', md: 370 } }}>
          <Box sx={{ position: 'relative', background: AUTH_HERO_BG, color: '#ffffff', px: { xs: 3.5, md: 4 }, py: { xs: 3, md: 4 }, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', overflow: 'hidden' }}>
            <Box sx={{ zIndex: 1 }}>
              <motion.div initial={{ y: -24, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.75, ease: 'easeOut' }}>
                <Typography sx={{ fontWeight: 800, fontSize: { xs: 22, md: 25 }, lineHeight: 1.15, mb: 1.25, ...AUTH_TITLE_GRADIENT }}>
                  CREATE YOUR ACCOUNT
                </Typography>
              </motion.div>
            </Box>

            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, mt: 2.25, zIndex: 1 }}>
              <Box sx={{ width: 44, height: 44, borderRadius: 3, bgcolor: 'rgba(255,255,255,0.12)' }} />
              <Box sx={{ width: 30, height: 30, borderRadius: 2, bgcolor: 'rgba(255,255,255,0.18)' }} />
              <Box sx={{ width: 60, height: 60, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.08)' }} />
            </Box>
          </Box>

          <Box sx={{ background: '#ffffff', px: { xs: 3.5, md: 4 }, py: { xs: 3, md: 4 }, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Box sx={{ width: '100%', maxWidth: 360 }}>
              <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2.25 }}>
                <Box sx={{ width: 48, height: 48, borderRadius: 3, background: '#eef4ff', display: 'grid', placeItems: 'center', color: '#3b66ff', fontWeight: 700, fontSize: 19 }}>A</Box>
              </Box>

              <Typography variant="h5" align="center" sx={{ fontWeight: 700, mb: 0.6, color: '#1e293b' }}>Welcome</Typography>
              <Typography variant="body2" align="center" sx={{ mb: 2.5, color: '#64748b' }}>Create an account to get started.</Typography>

              <Stack component="form" spacing={2} onSubmit={handleSubmit} noValidate>
                {error ? <Alert severity="error">{error}</Alert> : null}
                {status ? <Alert severity="success">{status}</Alert> : null}

                <TextField
                  fullWidth
                  required
                  label="Full Name"
                  placeholder="Enter your full name"
                  name="fullName"
                  value={fullName}
                  onChange={(e) => {
                    setFullName(e.target.value)
                    if (!e.target.value.trim()) setFullNameError('Full name is required.')
                    else setFullNameError('')
                  }}
                  onBlur={() => {
                    if (!fullName.trim()) setFullNameError('Full name is required.')
                  }}
                  autoComplete="name"
                  InputProps={{ startAdornment: (<InputAdornment position="start" sx={{ color: '#64748b' }}><PersonOutlineIcon fontSize="small" /></InputAdornment>) }}
                  error={!!fullNameError}
                  helperText={fullNameError}
                  sx={authInputStyles}
                />

                <TextField
                  fullWidth
                  required
                  label="Email"
                  placeholder="Enter your email address"
                  name="email"
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value)
                    if (!e.target.value.trim()) setEmailError('Email is required.')
                    else if (!validateEmail(e.target.value)) setEmailError('Enter a valid email.')
                    else setEmailError('')
                  }}
                  onBlur={() => {
                    if (!email.trim()) setEmailError('Email is required.')
                  }}
                  autoComplete="email"
                  InputProps={{ startAdornment: (<InputAdornment position="start" sx={{ color: '#64748b' }}><EmailOutlinedIcon fontSize="small" /></InputAdornment>) }}
                  error={!!emailError}
                  helperText={emailError}
                  sx={authInputStyles}
                />

                <TextField
                  fullWidth
                  required
                  label="Password"
                  placeholder="Create a password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    if (!e.target.value) setPasswordError('Password is required.')
                    else if (e.target.value.length < 8) setPasswordError('Password must be at least 8 characters.')
                    else setPasswordError('')
                    if (confirmPassword && e.target.value !== confirmPassword) setConfirmPasswordError('Passwords do not match.')
                    else if (confirmPassword) setConfirmPasswordError('')
                  }}
                  autoComplete="new-password"
                  InputProps={{ startAdornment: (<InputAdornment position="start" sx={{ color: '#64748b' }}><LockOutlinedIcon fontSize="small" /></InputAdornment>), endAdornment: (<InputAdornment position="end"><IconButton edge="end" aria-label={showPassword ? 'Hide password' : 'Show password'} onClick={() => setShowPassword((s) => !s)} onMouseDown={(e) => e.preventDefault()} sx={{ color: '#64748b' }}>{showPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}</IconButton></InputAdornment>) }}
                  error={!!passwordError}
                  helperText={passwordError}
                  sx={authInputStyles}
                />

                <TextField
                  fullWidth
                  required
                  label="Confirm Password"
                  placeholder="Re-enter your password"
                  name="confirmPassword"
                  type={showPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value)
                    if (!e.target.value) setConfirmPasswordError('Please confirm your password.')
                    else if (password !== e.target.value) setConfirmPasswordError('Passwords do not match.')
                    else setConfirmPasswordError('')
                  }}
                  autoComplete="new-password"
                  InputProps={{ startAdornment: (<InputAdornment position="start" sx={{ color: '#64748b' }}><LockOutlinedIcon fontSize="small" /></InputAdornment>) }}
                  error={!!confirmPasswordError}
                  helperText={confirmPasswordError}
                  sx={authInputStyles}
                />

                <FormControlLabel 
                  control={<Checkbox checked={agree} onChange={(e) => { setAgree(e.target.checked); if (e.target.checked) setAgreeError('') }} sx={authCheckboxStyles} />} 
                  label={<Typography variant="body2" sx={{ color: '#475569' }}>I agree to the <Link href="#" underline="hover" sx={authLinkStyles}>Terms</Link> and <Link href="#" underline="hover" sx={authLinkStyles}>Privacy Policy</Link>.</Typography>} 
                  sx={{ ml: -1 }} 
                />
                {agreeError ? <Typography variant="caption" color="error" sx={{ display: 'block', ml: 1 }}>{agreeError}</Typography> : null}

                 <Button type="submit" fullWidth variant="contained" sx={{ ...authButtonStyles, py: 1.15 }} disabled={isLoading}>{isLoading ? 'Creating account...' : 'Create account'}</Button>

                 <Divider sx={{ my: 0.75, '&::before, &::after': { borderColor: '#cbd5e1' }, color: '#64748b' }}>or</Divider>

                 <Stack direction="row" spacing={2} justifyContent="center">
                  <IconButton aria-label="Continue with Google" sx={authSocialCircleStyles}>
                    <GoogleGlyph size={20} />
                  </IconButton>
                  <IconButton aria-label="Continue with Facebook" sx={authSocialCircleStyles}>
                    <FacebookGlyph size={20} />
                  </IconButton>
                  <IconButton aria-label="Continue with Apple" sx={authSocialCircleStyles}>
                    <AppleIcon sx={{ color: '#1e293b' }} />
                  </IconButton>
                </Stack>

                 <Typography align="center" sx={{ color: '#64748b', mt: 0.5 }}>Already have an account? <Link href="/login" underline="hover" sx={authLinkStyles}>Sign in</Link></Typography>
              </Stack>
            </Box>
          </Box>
        </Box>
      </Paper>
    </Box>
  )
}

export default Register