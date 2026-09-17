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
import { useTranslation } from 'react-i18next'
import EmailOutlinedIconImport from '@mui/icons-material/EmailOutlined'
import LockOutlinedIconImport from '@mui/icons-material/LockOutlined'
import AppleIconImport from '@mui/icons-material/Apple'
import VisibilityIconImport from '@mui/icons-material/Visibility'
import VisibilityOffIconImport from '@mui/icons-material/VisibilityOff'
import ArrowForwardIconImport from '@mui/icons-material/ArrowForward'
import ArrowBackIconImport from '@mui/icons-material/ArrowBack'
import InstagramIconImport from '@mui/icons-material/Instagram'
import YouTubeIconImport from '@mui/icons-material/YouTube'
import LinkedInIconImport from '@mui/icons-material/LinkedIn'
import { useAuth } from '../../context/AuthContext.jsx'
import LanguageSwitcher from '../LanguageSwitcher.jsx'
import { GoogleGlyph, FacebookGlyph } from './SocialIcons.jsx'
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
} from './authStyles.js'
import { FloatingCard, BarChartMock, PieChartMock, IconChip, AuthPageBackdrop } from './AuthDecorations.jsx'

const EmailOutlinedIcon = EmailOutlinedIconImport?.default || EmailOutlinedIconImport
const LockOutlinedIcon = LockOutlinedIconImport?.default || LockOutlinedIconImport
const AppleIcon = AppleIconImport?.default || AppleIconImport
const VisibilityIcon = VisibilityIconImport?.default || VisibilityIconImport
const VisibilityOffIcon = VisibilityOffIconImport?.default || VisibilityOffIconImport
const ArrowForwardIcon = ArrowForwardIconImport?.default || ArrowForwardIconImport
const ArrowBackIcon = ArrowBackIconImport?.default || ArrowBackIconImport
const InstagramIcon = InstagramIconImport?.default || InstagramIconImport
const YouTubeIcon = YouTubeIconImport?.default || YouTubeIconImport
const LinkedInIcon = LinkedInIconImport?.default || LinkedInIconImport

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const Login = () => {
  const { t } = useTranslation('components')
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

    const params = new URLSearchParams(window.location.search)
    if (params.get('error') === 'google_auth_failed') {
      setError(t('login.googleAuthFailed'))
    } else if (params.get('error') === 'account_deactivated') {
      setError(t('login.accountDeactivated'))
    }
  }, [t])

  const handleGoogleSignIn = () => {
    window.location.href = `${API_BASE_URL}/api/auth/google/login`
  }

  const validateEmail = (value) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setStatus('')

    if (!email.trim() || !validateEmail(email)) {
      setError(t('login.invalidEmail'))
      return
    }

    if (!password.trim() || password.length < 8) {
      setError(t('login.passwordTooShort'))
      return
    }

    setIsLoading(true)
    try {
      // useAuth().login() handles storing the token/user under the single
      // shared key ('brainopx_token') that the rest of the app reads from.
      await login({ email, password })
      setStatus(t('login.signedInSuccess'))

      if (rememberMe) {
        localStorage.setItem('rememberedEmail', email)
      } else {
        localStorage.removeItem('rememberedEmail')
      }
      navigate('/dashboard')
    } catch (authError) {
      setError(authError?.message || t('login.signInFailed'))
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
        {t('login.backToHome')}
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
                  {t('login.heroTitle')}
                </Typography>
              </motion.div>
            </Box>
          </Box>

          <Box sx={{ background: '#ffffff', px: { xs: 4, md: 6 }, py: { xs: 3.5, md: 4.5 }, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Box sx={{ width: '100%', maxWidth: 460 }}>
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
                {t('login.welcomeBack')}
              </Typography>
              <Typography variant="body2" align="center" sx={{ mb: 3, color: '#64748b' }}>
               {t('login.enterCredentials')}
              </Typography>

              <Stack component="form" spacing={2.25} onSubmit={handleSubmit} noValidate>
                {error ? <Alert severity="error">{error}</Alert> : null}
                {status ? <Alert severity="success">{status}</Alert> : null}

                <TextField
                  fullWidth
                  required
                  label={t('login.emailLabel')}
                  placeholder={t('login.emailPlaceholder')}
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
                  label={t('login.passwordLabel')}
                  placeholder={t('login.passwordPlaceholder')}
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
                          aria-label={showPassword ? t('login.hidePassword') : t('login.showPassword')}
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
                    label={<Typography variant="body2" sx={{ color: '#475569' }}>{t('login.rememberMe')}</Typography>}
                    sx={{ ml: -1 }}
                  />
                 <Link href="/forgot-password" underline="hover" sx={{ fontSize: 14, ...authLinkStyles }}>
                 {t('login.resetPassword')}</Link>
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
                  {isLoading ? t('login.signingIn') : t('login.loginButton')}
                </Button>

                <Divider sx={{ my: 1, '&::before, &::after': { borderColor: '#cbd5e1' }, color: '#64748b' }}>{t('login.or')}</Divider>

                <Stack direction="row" spacing={2} justifyContent="center">
                  <IconButton aria-label={t('login.continueWithGoogle')} onClick={handleGoogleSignIn} sx={authSocialCircleStyles}>
                    <GoogleGlyph size={22} />
                  </IconButton>
                  <IconButton aria-label={t('login.continueWithFacebook')} sx={authSocialCircleStyles}>
                    <FacebookGlyph size={22} />
                  </IconButton>
                  <IconButton aria-label={t('login.continueWithApple')} sx={authSocialCircleStyles}>
                    <AppleIcon sx={{ color: '#1e293b' }} />
                  </IconButton>
                </Stack>

                <Typography align="center" sx={{ color: '#64748b', mt: 0.75 }}>
                  {t('login.noAccount')}{' '}
                  <Link href="/register" underline="hover" sx={authLinkStyles}>
                    {t('login.createAccount')}
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