import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
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
import ArrowBackIconImport from '@mui/icons-material/ArrowBack'
import InstagramIconImport from '@mui/icons-material/Instagram'
import YouTubeIconImport from '@mui/icons-material/YouTube'
import LinkedInIconImport from '@mui/icons-material/LinkedIn'
import { GoogleGlyph, FacebookGlyph } from '../components/authentication/SocialIcons.jsx'
import LanguageSwitcher from '../components/LanguageSwitcher.jsx'
import {
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
import { FloatingCard, BarChartMock, PieChartMock, IconChip, AuthPageBackdrop } from '../components/authentication/AuthDecorations.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const EmailOutlinedIcon = EmailOutlinedIconImport?.default || EmailOutlinedIconImport
const LockOutlinedIcon = LockOutlinedIconImport?.default || LockOutlinedIconImport
const PersonOutlineIcon = PersonOutlineIconImport?.default || PersonOutlineIconImport
const VisibilityIcon = VisibilityIconImport?.default || VisibilityIconImport
const VisibilityOffIcon = VisibilityOffIconImport?.default || VisibilityOffIconImport
const AppleIcon = AppleIconImport?.default || AppleIconImport
const ArrowBackIcon = ArrowBackIconImport?.default || ArrowBackIconImport
const InstagramIcon = InstagramIconImport?.default || InstagramIconImport
const YouTubeIcon = YouTubeIconImport?.default || YouTubeIconImport
const LinkedInIcon = LinkedInIconImport?.default || LinkedInIconImport

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const Register = () => {
  const { t } = useTranslation('pages')
  const navigate = useNavigate()
  const { login } = useAuth()
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

  const handleGoogleSignIn = () => {
    window.location.href = `${API_BASE_URL}/api/auth/google/login`
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setStatus('')

    const fErr = !fullName.trim() ? t('register.errorFullNameRequired') : ''
    const eErr = !email.trim() ? t('register.errorEmailRequired') : !validateEmail(email) ? t('register.errorEmailInvalid') : ''
    const pErr = !password ? t('register.errorPasswordRequired') : password.length < 8 ? t('register.errorPasswordTooShort') : ''
    const cErr = !confirmPassword ? t('register.errorConfirmPasswordRequired') : password !== confirmPassword ? t('register.errorPasswordsMismatch') : ''
    const aErr = !agree ? t('register.errorAgreeRequired') : ''

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
        throw new Error(detailMessage || t('register.errorRegistrationFailedDefault'))
      }
      setStatus(t('register.statusAccountCreated'))

      // Sign the freshly-created account in right away so the success
      // page's "Next" button can drop the user straight into the
      // dashboard instead of bouncing them to /login.
      try {
        await login({ email, password })
      } catch {
        // If auto sign-in fails for any reason, the success page's
        // "Next" button will simply send them to /login instead.
      }

      navigate('/register/success', { state: { fullName } })
    } catch (err) {
      setError(err?.message || t('register.errorRegisterFailedDefault'))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Box
      component="main"
      sx={{
        minHeight: '100vh',
        background: '#ffffff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        px: 2,
        py: 3,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <AuthPageBackdrop />
      <Button
        onClick={() => navigate('/landing')}
        startIcon={<ArrowBackIcon />}
        sx={{
          position: 'absolute',
          zIndex: 1,
          top: { xs: 12, md: 24 },
          left: { xs: 12, md: 24 },
          textTransform: 'none',
          fontWeight: 600,
          color: '#1e293b',
          '&:hover': { backgroundColor: 'rgba(15,23,42,0.06)' },
        }}
      >
        {t('register.backToHome')}
      </Button>
      <Box
        sx={{
          position: 'absolute',
          zIndex: 1,
          top: { xs: 12, md: 24 },
          right: { xs: 12, md: 24 },
        }}
      >
        <LanguageSwitcher variant="label" />
      </Box>
      <Paper
        elevation={10}
        sx={{
          position: 'relative',
          zIndex: 1,
          width: '100%',
          maxWidth: 960,
          borderRadius: AUTH_CARD_RADIUS,
          overflow: 'hidden',
          boxShadow: AUTH_CARD_SHADOW,
          background: '#ffffff'
        }}
      >
         <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1.05fr' }, minHeight: { xs: 'auto', md: 400 } }}>
          <Box sx={{ position: 'relative', background: AUTH_HERO_BG, color: '#ffffff', px: { xs: 4, md: 4.5 }, py: { xs: 3.5, md: 4.5 }, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', overflow: 'hidden' }}>
            <Box sx={{ position: 'absolute', bottom: -20, left: -20, width: 160, height: 160, borderRadius: '50%', background: 'radial-gradient(circle, rgba(59,102,255,0.28), transparent 70%)', filter: 'blur(4px)' }} />

            <FloatingCard top="3%" right="8%" duration={5.5} delay={0.5} rotateFrom={10} rotateTo={-6}>
              <IconChip icon={<InstagramIcon fontSize="small" />} color="#e1306c" />
            </FloatingCard>
            <FloatingCard top="36%" right="3%" duration={7} delay={1.1} rotateFrom={-10} rotateTo={8}>
              <IconChip icon={<YouTubeIcon fontSize="small" />} color="#ff4d4d" />
            </FloatingCard>
            <FloatingCard bottom="30%" right="8%" duration={6} delay={0.3} rotateFrom={6} rotateTo={-8}>
              <IconChip icon={<LinkedInIcon fontSize="small" />} color="#5b9bff" />
            </FloatingCard>
            <FloatingCard bottom="8%" left="6%" duration={6.5} rotateFrom={-6} rotateTo={5}>
              <BarChartMock />
            </FloatingCard>
            <FloatingCard bottom="6%" right="16%" duration={7.5} delay={0.8} rotateFrom={-5} rotateTo={7}>
              <PieChartMock />
            </FloatingCard>

            <Box sx={{ zIndex: 1 }}>
              <motion.div initial={{ y: -24, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.75, ease: 'easeOut' }}>
                <Typography sx={{ fontWeight: 800, fontSize: { xs: 22, md: 25 }, lineHeight: 1.15, mb: 1.25, ...AUTH_TITLE_GRADIENT }}>
                  {t('register.heroTitle')}
                </Typography>
              </motion.div>
            </Box>
          </Box>

          <Box sx={{ background: '#ffffff', px: { xs: 4, md: 6 }, py: { xs: 3.5, md: 4.5 }, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Box sx={{ width: '100%', maxWidth: 360 }}>
              <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2.25 }}>
                <Box sx={{ width: 48, height: 48, borderRadius: 3, background: '#eef4ff', display: 'grid', placeItems: 'center', color: '#3b66ff', fontWeight: 700, fontSize: 19 }}>A</Box>
              </Box>

              <Typography variant="h5" align="center" sx={{ fontWeight: 700, mb: 0.6, color: '#1e293b' }}>{t('register.welcome')}</Typography>
              <Typography variant="body2" align="center" sx={{ mb: 2.5, color: '#64748b' }}>{t('register.subtitle')}</Typography>

              <Stack component="form" spacing={2} onSubmit={handleSubmit} noValidate>
                {error ? <Alert severity="error">{error}</Alert> : null}
                {status ? <Alert severity="success">{status}</Alert> : null}

                <TextField
                  fullWidth
                  required
                  label={t('register.fullNameLabel')}
                  placeholder={t('register.fullNamePlaceholder')}
                  name="fullName"
                  value={fullName}
                  onChange={(e) => {
                    setFullName(e.target.value)
                    if (!e.target.value.trim()) setFullNameError(t('register.errorFullNameRequired'))
                    else setFullNameError('')
                  }}
                  onBlur={() => {
                    if (!fullName.trim()) setFullNameError(t('register.errorFullNameRequired'))
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
                  label={t('register.emailLabel')}
                  placeholder={t('register.emailPlaceholder')}
                  name="email"
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value)
                    if (!e.target.value.trim()) setEmailError(t('register.errorEmailRequired'))
                    else if (!validateEmail(e.target.value)) setEmailError(t('register.errorEmailInvalid'))
                    else setEmailError('')
                  }}
                  onBlur={() => {
                    if (!email.trim()) setEmailError(t('register.errorEmailRequired'))
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
                  label={t('register.passwordLabel')}
                  placeholder={t('register.passwordPlaceholder')}
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    if (!e.target.value) setPasswordError(t('register.errorPasswordRequired'))
                    else if (e.target.value.length < 8) setPasswordError(t('register.errorPasswordTooShort'))
                    else setPasswordError('')
                    if (confirmPassword && e.target.value !== confirmPassword) setConfirmPasswordError(t('register.errorPasswordsMismatch'))
                    else if (confirmPassword) setConfirmPasswordError('')
                  }}
                  autoComplete="new-password"
                  InputProps={{ startAdornment: (<InputAdornment position="start" sx={{ color: '#64748b' }}><LockOutlinedIcon fontSize="small" /></InputAdornment>), endAdornment: (<InputAdornment position="end"><IconButton edge="end" aria-label={showPassword ? t('register.hidePassword') : t('register.showPassword')} onClick={() => setShowPassword((s) => !s)} onMouseDown={(e) => e.preventDefault()} sx={{ color: '#64748b' }}>{showPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}</IconButton></InputAdornment>) }}
                  error={!!passwordError}
                  helperText={passwordError}
                  sx={authInputStyles}
                />

                <TextField
                  fullWidth
                  required
                  label={t('register.confirmPasswordLabel')}
                  placeholder={t('register.confirmPasswordPlaceholder')}
                  name="confirmPassword"
                  type={showPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value)
                    if (!e.target.value) setConfirmPasswordError(t('register.errorConfirmPasswordRequired'))
                    else if (password !== e.target.value) setConfirmPasswordError(t('register.errorPasswordsMismatch'))
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
                  label={<Typography variant="body2" sx={{ color: '#475569' }}>{t('register.agreePrefix')} <Link href="#" underline="hover" sx={authLinkStyles}>{t('register.termsLink')}</Link> {t('register.agreeAnd')} <Link href="#" underline="hover" sx={authLinkStyles}>{t('register.privacyLink')}</Link>.</Typography>}
                  sx={{ ml: -1 }} 
                />
                {agreeError ? <Typography variant="caption" color="error" sx={{ display: 'block', ml: 1 }}>{agreeError}</Typography> : null}

                 <Button type="submit" fullWidth variant="contained" sx={{ ...authButtonStyles, py: 1.15 }} disabled={isLoading}>{isLoading ? t('register.creatingAccount') : t('register.createAccount')}</Button>

                 <Divider sx={{ my: 0.75, '&::before, &::after': { borderColor: '#cbd5e1' }, color: '#64748b' }}>{t('register.or')}</Divider>

                 <Stack direction="row" spacing={2} justifyContent="center">
                  <IconButton aria-label={t('register.continueWithGoogle')} onClick={handleGoogleSignIn} sx={authSocialCircleStyles}>
                    <GoogleGlyph size={20} />
                  </IconButton>
                  <IconButton aria-label={t('register.continueWithFacebook')} sx={authSocialCircleStyles}>
                    <FacebookGlyph size={20} />
                  </IconButton>
                  <IconButton aria-label={t('register.continueWithApple')} sx={authSocialCircleStyles}>
                    <AppleIcon sx={{ color: '#1e293b' }} />
                  </IconButton>
                </Stack>

                 <Typography align="center" sx={{ color: '#64748b', mt: 0.5 }}>{t('register.alreadyHaveAccount')} <Link href="/login" underline="hover" sx={authLinkStyles}>{t('register.signIn')}</Link></Typography>
              </Stack>
            </Box>
          </Box>
        </Box>
      </Paper>
    </Box>
  )
}

export default Register