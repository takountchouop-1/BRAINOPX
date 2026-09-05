import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
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
import EmailOutlinedIconImport from '@mui/icons-material/EmailOutlined'
import LockOutlinedIconImport from '@mui/icons-material/LockOutlined'
import PinOutlinedIconImport from '@mui/icons-material/PinOutlined'
import {
  requestPasswordReset,
  verifyResetCode,
  resetPassword,
} from '../services/Authenticationservice.js'
import {
  AUTH_PAGE_BG,
  authButtonStyles,
} from '../components/authentication/authStyles.js'

const EmailOutlinedIcon = EmailOutlinedIconImport?.default || EmailOutlinedIconImport
const LockOutlinedIcon = LockOutlinedIconImport?.default || LockOutlinedIconImport
const PinOutlinedIcon = PinOutlinedIconImport?.default || PinOutlinedIconImport

// Step numbers, for readability
const STEP_REQUEST = 1
const STEP_VERIFY = 2
const STEP_RESET = 3

// How long a reset code stays valid, mirrors RESET_CODE_VALID_MINUTES on the backend
const CODE_VALID_MINUTES = 5

const formatTimeLeft = (totalSeconds) => {
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

const ForgotPassword = () => {
  const { t } = useTranslation('pages')
  const [step, setStep] = useState(STEP_REQUEST)

  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  // Countdown session for the OTP code: set once a code is (re)sent, ticks
  // down every second, and drives the expired state once it hits zero.
  const [codeExpiresAt, setCodeExpiresAt] = useState(null)
  const [secondsLeft, setSecondsLeft] = useState(0)

  useEffect(() => {
    if (!codeExpiresAt) {
      setSecondsLeft(0)
      return
    }

    const tick = () => {
      const remaining = Math.max(0, Math.round((codeExpiresAt - Date.now()) / 1000))
      setSecondsLeft(remaining)
    }

    tick()
    const intervalId = setInterval(tick, 1000)
    return () => clearInterval(intervalId)
  }, [codeExpiresAt])

  const isCodeExpired = step === STEP_VERIFY && codeExpiresAt !== null && secondsLeft <= 0

  const validateEmail = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)

  // --- Step 1: request the code ---
  const handleRequestCode = async (event) => {
    event.preventDefault()
    setError('')
    setStatus('')

    if (!email.trim() || !validateEmail(email)) {
      setError(t('forgotPassword.errorInvalidEmail'))
      return
    }

    setIsLoading(true)
    try {
      const result = await requestPasswordReset({ email })
      setStatus(result?.message || t('forgotPassword.statusCodeSentDefault'))
      setCode('')
      setCodeExpiresAt(Date.now() + CODE_VALID_MINUTES * 60 * 1000)
      setStep(STEP_VERIFY)
    } catch (err) {
      setError(err?.message || t('forgotPassword.errorSendCodeFailed'))
    } finally {
      setIsLoading(false)
    }
  }

  // --- Step 2: verify the code ---
  const handleVerifyCode = async (event) => {
    event.preventDefault()
    setError('')
    setStatus('')

    if (isCodeExpired) {
      setError(t('forgotPassword.errorCodeExpired'))
      return
    }

    if (!code.trim() || code.trim().length !== 6) {
      setError(t('forgotPassword.errorInvalidCode'))
      return
    }

    setIsLoading(true)
    try {
      await verifyResetCode({ email, code })
      setStatus(t('forgotPassword.statusCodeVerified'))
      setStep(STEP_RESET)
    } catch (err) {
      setError(err?.message || t('forgotPassword.errorInvalidOrExpiredCode'))
    } finally {
      setIsLoading(false)
    }
  }

  // --- Resend: request a fresh code without leaving the verify step ---
  const handleResendCode = async (event) => {
    if (event?.preventDefault) event.preventDefault()
    setError('')
    setStatus('')

    setIsLoading(true)
    try {
      const result = await requestPasswordReset({ email })
      setStatus(result?.message || t('forgotPassword.statusNewCodeSentDefault'))
      setCode('')
      setCodeExpiresAt(Date.now() + CODE_VALID_MINUTES * 60 * 1000)
    } catch (err) {
      setError(err?.message || t('forgotPassword.errorResendFailed'))
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
      setError(t('forgotPassword.errorPasswordTooShort'))
      return
    }
    if (newPassword !== confirmPassword) {
      setError(t('forgotPassword.errorPasswordsMismatch'))
      return
    }

    setIsLoading(true)
    try {
      const result = await resetPassword({ email, code, newPassword })
      setStatus(result?.message || t('forgotPassword.statusPasswordResetSuccess'))
      // Reset local state — user can navigate back to login from here
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setError(err?.message || t('forgotPassword.errorResetFailed'))
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
          {t('forgotPassword.title')}
        </Typography>
        <Typography variant="body2" align="center" color="text.secondary" sx={{ mb: 4 }}>
          {step === STEP_REQUEST && t('forgotPassword.subtitleRequest')}
          {step === STEP_VERIFY && t('forgotPassword.subtitleVerify', { email })}
          {step === STEP_RESET && t('forgotPassword.subtitleReset')}
        </Typography>

        {error ? <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert> : null}
        {status ? <Alert severity="success" sx={{ mb: 3 }}>{status}</Alert> : null}

        {/* --- STEP 1: request code --- */}
        {step === STEP_REQUEST && (
          <Stack component="form" spacing={3} onSubmit={handleRequestCode} noValidate>
            <TextField
              fullWidth
              required
              label={t('forgotPassword.emailLabel')}
              placeholder={t('forgotPassword.emailPlaceholder')}
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
              sx={authButtonStyles}
            >
              {isLoading ? t('forgotPassword.sendingCode') : t('forgotPassword.sendResetCode')}
            </Button>
          </Stack>
        )}

        {/* --- STEP 2: verify code --- */}
        {step === STEP_VERIFY && (
          <Stack component="form" spacing={3} onSubmit={handleVerifyCode} noValidate>
            <TextField
              fullWidth
              required
              label={t('forgotPassword.codeLabel')}
              placeholder={t('forgotPassword.codePlaceholder')}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              disabled={isCodeExpired}
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

            <Typography
              align="center"
              variant="body2"
              color={isCodeExpired ? 'error' : 'text.secondary'}
            >
              {isCodeExpired
                ? t('forgotPassword.codeExpiredShort')
                : t('forgotPassword.codeExpiresIn', { time: formatTimeLeft(secondsLeft) })}
            </Typography>

            <Button
              type="submit"
              fullWidth
              variant="contained"
              disabled={isLoading || isCodeExpired}
              sx={authButtonStyles}
            >
              {isLoading ? t('forgotPassword.verifying') : t('forgotPassword.verifyCode')}
            </Button>

            {isCodeExpired ? (
              <Typography align="center" variant="body2" color="text.secondary">
                <Link
                  component="button"
                  type="button"
                  underline="hover"
                  onClick={handleResendCode}
                >
                  {t('forgotPassword.sendNewCode')}
                </Link>
              </Typography>
            ) : (
              <Typography align="center" variant="body2" color="text.secondary">
                {t('forgotPassword.noCodeQuestion')}{' '}
                <Link
                  component="button"
                  type="button"
                  underline="hover"
                  onClick={(e) => {
                    e.preventDefault()
                    setStep(STEP_REQUEST)
                    setStatus('')
                    setError('')
                    setCodeExpiresAt(null)
                    setCode('')
                  }}
                >
                  {t('forgotPassword.tryAgain')}
                </Link>
              </Typography>
            )}
          </Stack>
        )}

        {/* --- STEP 3: set new password --- */}
        {step === STEP_RESET && (
          <Stack component="form" spacing={3} onSubmit={handleResetPassword} noValidate>
            <TextField
              fullWidth
              required
              label={t('forgotPassword.newPasswordLabel')}
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
              label={t('forgotPassword.confirmNewPasswordLabel')}
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
              sx={authButtonStyles}
            >
              {isLoading ? t('forgotPassword.resetting') : t('forgotPassword.resetPasswordButton')}
            </Button>
          </Stack>
        )}

        <Typography align="center" sx={{ color: 'text.secondary', mt: 4 }}>
          {t('forgotPassword.rememberedPassword')}{' '}
          <Link href="/login" underline="hover">
            {t('forgotPassword.backToSignIn')}
          </Link>
        </Typography>
      </Paper>
    </Box>
  )
}

export default ForgotPassword