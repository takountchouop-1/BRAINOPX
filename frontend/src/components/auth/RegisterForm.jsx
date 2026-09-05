import React, { useState } from 'react'
import {
  Box,
  Button,
  CircularProgress,
  FormControlLabel,
  Checkbox,
  Paper,
  TextField,
  Typography,
  Link,
} from '@mui/material'
import { useTranslation } from 'react-i18next'
import StepIndicator from './StepIndicator.jsx'

const RegisterForm = () => {
  const { t } = useTranslation('components')
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const steps = [
    { label: t('registerForm.steps.signUp') },
    { label: t('registerForm.steps.verify') },
    { label: t('registerForm.steps.setupWorkspace') },
  ]

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setIsLoading(true)

    if (!email || !email.includes('@')) {
      setError(t('registerForm.invalidEmail'))
      setIsLoading(false)
      return
    }

    await new Promise((resolve) => setTimeout(resolve, 900))
    setIsLoading(false)
  }

  return (
    <Paper
      elevation={10}
      sx={{
        p: { xs: 5, md: 6 },
        borderRadius: 5,
        background: 'rgba(12, 18, 44, 0.96)',
        border: '1px solid rgba(148, 163, 184, 0.12)',
        boxShadow: '0 36px 120px rgba(15, 23, 42, 0.24)',
      }}
    >
      <Typography variant="h5" sx={{ color: '#ffffff', fontWeight: 700, mb: 1 }}>
        {t('registerForm.title')}
      </Typography>
      <Typography color="rgba(226, 232, 240, 0.9)" sx={{ mb: 4 }}>
        {t('registerForm.welcomeSubtitle')}
      </Typography>

      <StepIndicator steps={steps} activeStep={0} />

      <Box component="form" onSubmit={handleSubmit} sx={{ display: 'grid', gap: 3 }}>
        <Box>
          <Typography variant="subtitle1" sx={{ color: '#ffffff', mb: 1, fontWeight: 600 }}>
            {t('registerForm.signUpAccount')}
          </Typography>
          <Typography color="rgba(148, 163, 184, 0.9)" sx={{ fontSize: 14, mb: 2 }}>
            {t('registerForm.description')}
          </Typography>
        </Box>

        {error ? (
          <Typography color="#ef4444" sx={{ fontSize: 14 }}>
            {error}
          </Typography>
        ) : null}

        <TextField
          fullWidth
          label={t('registerForm.emailLabel')}
          placeholder={t('registerForm.emailPlaceholder')}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          InputLabelProps={{ style: { color: 'rgba(226, 232, 240, 0.8)' } }}
          InputProps={{
            style: {
              background: '#0b122d',
              borderColor: '#1e2a57',
              color: '#ffffff',
              borderRadius: 16,
            },
          }}
          inputProps={{
            style: { color: '#ffffff' },
          }}
          sx={{
            '& .MuiOutlinedInput-notchedOutline': {
              borderColor: 'rgba(148, 163, 184, 0.18)',
            },
            '&:hover .MuiOutlinedInput-notchedOutline': {
              borderColor: 'rgba(79, 70, 229, 0.5)',
            },
            '& .Mui-focused .MuiOutlinedInput-notchedOutline': {
              borderColor: '#4f46e5',
            },
          }}
        />

        <Button
          type="submit"
          fullWidth
          variant="contained"
          sx={{
            py: 1.8,
            borderRadius: 14,
            background: 'linear-gradient(135deg, #4f46e5, #4338ca)',
            boxShadow: '0 18px 50px rgba(79, 70, 229, 0.24)',
            textTransform: 'none',
          }}
          disabled={isLoading}
        >
          {isLoading ? <CircularProgress size={20} color="inherit" /> : t('registerForm.continue')}
        </Button>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 1 }}>
          <Typography variant="body2" color="rgba(148, 163, 184, 0.9)">
            {t('registerForm.noAccount')}
          </Typography>
          <Link href="#" underline="hover" sx={{ color: '#818cf8', fontWeight: 600 }}>
            {t('registerForm.signUp')}
          </Link>
        </Box>

        <Link href="#" underline="hover" sx={{ color: '#94a3b8', textAlign: 'center', mt: 1 }}>
          {t('registerForm.bookDemo')}
        </Link>
      </Box>
    </Paper>
  )
}

export default RegisterForm
