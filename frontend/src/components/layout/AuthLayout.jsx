import React from 'react'
import { Box, Paper } from '@mui/material'

const AuthLayout = ({ children }) => {
  const childArray = React.Children.toArray(children)

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: 'radial-gradient(circle at top left, rgba(79, 70, 229, 0.18), transparent 22%), radial-gradient(circle at bottom right, rgba(59, 130, 246, 0.16), transparent 24%), linear-gradient(180deg, #020814 0%, #071a37 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        px: 3,
        py: 8,
      }}
    >
      <Box
        sx={{
          width: '100%',
          maxWidth: 1200,
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '0.95fr 1.05fr' },
          gap: 4,
        }}
      >
        <Paper
          elevation={10}
          sx={{
            p: { xs: 5, md: 6 },
            borderRadius: 5,
            background: 'rgba(15, 23, 42, 0.95)',
            border: '1px solid rgba(148, 163, 184, 0.12)',
            boxShadow: '0 36px 120px rgba(15, 23, 42, 0.24)',
          }}
        >
          {childArray[0] ?? null}
        </Paper>

        <Paper
          elevation={10}
          sx={{
            p: { xs: 5, md: 6 },
            borderRadius: 5,
            background: 'rgba(10, 18, 39, 0.9)',
            border: '1px solid rgba(148, 163, 184, 0.08)',
            boxShadow: '0 36px 120px rgba(15, 23, 42, 0.14)',
          }}
        >
          {childArray[1] ?? null}
        </Paper>
      </Box>
    </Box>
  )
}

export default AuthLayout

