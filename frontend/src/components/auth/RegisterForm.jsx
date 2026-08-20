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
import StepIndicator from './StepIndicator.jsx'

const steps = [
  { label: 'Sign up your account' },
  { label: 'Verify your account' },
  { label: 'Set up your workspace' },
]

const RegisterForm = () => {
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setIsLoading(true)

    if (!email || !email.includes('@')) {
      setError('Please enter a valid email address.')
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
        Get Start with Us
      </Typography>
      <Typography color="rgba(226, 232, 240, 0.9)" sx={{ mb: 4 }}>
        Welcome to Pathsdata - let's create your account.
      </Typography>

      <StepIndicator steps={steps} activeStep={0} />

      <Box component="form" onSubmit={handleSubmit} sx={{ display: 'grid', gap: 3 }}>
        <Box>
          <Typography variant="subtitle1" sx={{ color: '#ffffff', mb: 1, fontWeight: 600 }}>
            Sign up account
          </Typography>
          <Typography color="rgba(148, 163, 184, 0.9)" sx={{ fontSize: 14, mb: 2 }}>
            Reclaim control of your data with confidence. Secure, seamless, and built to empower you every step of the way.
          </Typography>
        </Box>

        {error ? (
          <Typography color="#ef4444" sx={{ fontSize: 14 }}>
            {error}
          </Typography>
        ) : null}

        <TextField
          fullWidth
          label="Email"
          placeholder="Please enter email"
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
          {isLoading ? <CircularProgress size={20} color="inherit" /> : 'Continue'}
        </Button>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 1 }}>
          <Typography variant="body2" color="rgba(148, 163, 184, 0.9)">
            Don't have an account?
          </Typography>
          <Link href="#" underline="hover" sx={{ color: '#818cf8', fontWeight: 600 }}>
            Sign Up
          </Link>
        </Box>

        <Link href="#" underline="hover" sx={{ color: '#94a3b8', textAlign: 'center', mt: 1 }}>
          Book a Demo
        </Link>
      </Box>
    </Paper>
  )
}

export default RegisterForm
