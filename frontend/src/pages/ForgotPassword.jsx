import React, { useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Paper,
  Stack,
  TextField,
  Typography,
  InputAdornment,
  Link,
} from '@mui/material'
import EmailOutlinedIcon from '@mui/icons-material/EmailOutlined'
import LockOutlinedIcon from '@mui/icons-material/LockOutlined'
import PinOutlinedIcon from '@mui/icons-material/PinOutlined'
import {
  requestPasswordReset,
  verifyResetCode,
  resetPassword,
} from '../services/Authenticationservice.js'

// Step numbers, for readability
const STEP_REQUEST = 1
const STEP_VERIFY = 2
const STEP_RESET = 3

const ForgotPassword = () => {
  const [step, setStep] = useState(STEP_REQUEST)

  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const validateEmail = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)

  // --- Step 1: request the code ---
  const handleRequestCode = async (event) => {
    event.preventDefault()
    setError('')
    setStatus('')

    if (!email.trim() || !validateEmail(email)) {
      setError('Please enter a valid email address.')
      return
    }

    setIsLoading(true)
    try {
      const result = await requestPasswordReset({ email })
      setStatus(result?.message || 'If this email is registered, a reset code has been sent.')
      setStep(STEP_VERIFY)
    } catch (err) {
      setError(err?.message || 'Unable to send reset code. Try again later.')
    } finally {
      setIsLoading(false)
    }
  }

  // --- Step 2: verify the code ---
  const handleVerifyCode = async (event) => {
    event.preventDefault()
    setError('')
    setStatus('')

    if (!code.trim() || code.trim().length !== 6) {
      setError('Enter the 6-digit code sent to your email.')
      return
    }

    setIsLoading(true)
    try {
      await verifyResetCode({ email, code })
      setStatus('Code verified. Please set your new password.')
      setStep(STEP_RESET)
    } catch (err) {
      setError(err?.message || 'Invalid or expired code.')
    } finally {
      setIsLoading(false)
    }
  }

  // --- Step 3: set the new password ---
  const handleResetPassword = async (event) => {
    event.preventDefault()
    setError('')
    setStatus('')

    if (!newPassword || newPassword.length < 6) {
      setError('Password must be at least 6 characters.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setIsLoading(true)
    try {
      const result = await resetPassword({ email, code, newPassword })
      setStatus(result?.message || 'Password reset successfully. You can now sign in.')
      // Reset local state — user can navigate back to login from here
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setError(err?.message || 'Unable to reset password. The code may have expired.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Box
      component="main"
      sx={{
        minHeight: '100vh',
        background: 'linear-gradient(180deg, #2b0338 0%, #3a0f64 35%, #6b1f8a 70%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        px: 2,
        py: 6,
      }}
    >
      <Paper
        elevation={10}
        sx={{
          width: '100%',
          maxWidth: 520,
          borderRadius: '32px',
          overflow: 'hidden',
          boxShadow: '0 40px 120px rgba(31, 41, 55, 0.12)',
          background: '#f8fbff',
          px: { xs: 5, md: 7 },
          py: { xs: 7, md: 8 },
        }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 4 }}>
          <Box
            sx={{
              width: 64,
              height: 64,
              borderRadius: 3,
              background: '#eef4ff',
              display: 'grid',
              placeItems: 'center',
              color: '#3b66ff',
              fontWeight: 700,
              fontSize: 24,
            }}
          >
            A
          </Box>
        </Box>

        <Typography variant="h5" align="center" sx={{ fontWeight: 700, mb: 1 }}>
          Reset your password
        </Typography>
        <Typography variant="body2" align="center" color="text.secondary" sx={{ mb: 4 }}>
          {step === STEP_REQUEST && 'Enter your email to receive a reset code.'}
          {step === STEP_VERIFY && `Enter the 6-digit code sent to ${email}.`}
          {step === STEP_RESET && 'Choose a new password for your account.'}
        </Typography>

        {error ? <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert> : null}
        {status ? <Alert severity="success" sx={{ mb: 3 }}>{status}</Alert> : null}

        {/* --- STEP 1: request code --- */}
        {step === STEP_REQUEST && (
          <Stack component="form" spacing={3} onSubmit={handleRequestCode} noValidate>
            <TextField
              fullWidth
              required
              label="Email"
              placeholder="Enter your email address"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start" sx={{ color: '#64748b' }}>
                    <EmailOutlinedIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
              sx={{ borderRadius: 3, background: '#ffffff' }}
            />
            <Button
              type="submit"
              fullWidth
              variant="contained"
              disabled={isLoading}
              sx={{
                py: 1.6,
                borderRadius: 6,
                textTransform: 'none',
                background: 'linear-gradient(90deg, #6b1f8a 0%, #a02bbf 50%, #ff4ea1 100%)',
                color: '#ffffff',
              }}
            >
              {isLoading ? 'Sending code...' : 'Send reset code'}
            </Button>
          </Stack>
        )}

        {/* --- STEP 2: verify code --- */}
        {step === STEP_VERIFY && (
          <Stack component="form" spacing={3} onSubmit={handleVerifyCode} noValidate>
            <TextField
              fullWidth
              required
              label="6-digit code"
              placeholder="Enter the code from your email"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              inputProps={{ maxLength: 6, inputMode: 'numeric' }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start" sx={{ color: '#64748b' }}>
                    <PinOutlinedIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
              sx={{ borderRadius: 3, background: '#ffffff' }}
            />
            <Button
              type="submit"
              fullWidth
              variant="contained"
              disabled={isLoading}
              sx={{
                py: 1.6,
                borderRadius: 6,
                textTransform: 'none',
                background: 'linear-gradient(90deg, #6b1f8a 0%, #a02bbf 50%, #ff4ea1 100%)',
                color: '#ffffff',
              }}
            >
              {isLoading ? 'Verifying...' : 'Verify code'}
            </Button>
            <Typography align="center" variant="body2" color="text.secondary">
              Didn't get a code?{' '}
              <Link
                component="button"
                type="button"
                underline="hover"
                onClick={(e) => {
                  e.preventDefault()
                  setStep(STEP_REQUEST)
                  setStatus('')
                  setError('')
                }}
              >
                Try again
              </Link>
            </Typography>
          </Stack>
        )}

        {/* --- STEP 3: set new password --- */}
        {step === STEP_RESET && (
          <Stack component="form" spacing={3} onSubmit={handleResetPassword} noValidate>
            <TextField
              fullWidth
              required
              label="New password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start" sx={{ color: '#64748b' }}>
                    <LockOutlinedIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
              sx={{ borderRadius: 3, background: '#ffffff' }}
            />
            <TextField
              fullWidth
              required
              label="Confirm new password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start" sx={{ color: '#64748b' }}>
                    <LockOutlinedIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
              sx={{ borderRadius: 3, background: '#ffffff' }}
            />
            <Button
              type="submit"
              fullWidth
              variant="contained"
              disabled={isLoading}
              sx={{
                py: 1.6,
                borderRadius: 6,
                textTransform: 'none',
                background: 'linear-gradient(90deg, #6b1f8a 0%, #a02bbf 50%, #ff4ea1 100%)',
                color: '#ffffff',
              }}
            >
              {isLoading ? 'Resetting...' : 'Reset password'}
            </Button>
          </Stack>
        )}

        <Typography align="center" sx={{ color: 'text.secondary', mt: 4 }}>
          Remembered your password?{' '}
          <Link href="/login" underline="hover">
            Back to Sign In
          </Link>
        </Typography>
      </Paper>
    </Box>
  )
}

export default ForgotPassword