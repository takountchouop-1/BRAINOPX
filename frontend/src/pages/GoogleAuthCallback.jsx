import React, { useEffect, useState } from 'react'
import { Box, CircularProgress, Typography } from '@mui/material'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext.jsx'
import { AUTH_PAGE_BG } from '../components/authentication/authStyles.js'

// Landing spot for the redirect Google (via our backend) sends the
// browser back to once the user picks an account and grants access.
const GoogleAuthCallback = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { loginWithToken } = useAuth()
  const [error, setError] = useState('')
  const { t } = useTranslation('pages')

  useEffect(() => {
    const token = searchParams.get('token')

    if (!token) {
      navigate('/login?error=google_auth_failed', { replace: true })
      return
    }

    loginWithToken(token)
      .then(() => navigate('/dashboard', { replace: true }))
      .catch((err) => {
        setError(err?.message || t('googleAuthCallback.error'))
        setTimeout(() => navigate('/login?error=google_auth_failed', { replace: true }), 1500)
      })
    // Only ever run once, on mount, against whatever token was in the URL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: AUTH_PAGE_BG,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
      }}
    >
      <CircularProgress />
      <Typography sx={{ color: '#475569' }}>
        {error || t('googleAuthCallback.finishing')}
      </Typography>
    </Box>
  )
}

export default GoogleAuthCallback
