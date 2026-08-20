import React from 'react'
import { Box, Typography } from '@mui/material'

const StepIndicator = ({ steps = [], activeStep = 0 }) => {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, mb: 4 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 3, justifyContent: 'space-between' }}>
        {steps.map((step, index) => {
          const isActive = index === activeStep
          const isCompleted = index < activeStep

          return (
            <Box key={step.label} sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
              <Box
                sx={{
                  width: 36,
                  height: 36,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: isActive || isCompleted ? '#ffffff' : '#94a3b8',
                  background: isActive ? 'linear-gradient(135deg, #4f46e5, #4338ca)' : isCompleted ? '#4338ca' : 'rgba(148, 163, 184, 0.18)',
                  border: isActive ? 'none' : '1px solid rgba(148, 163, 184, 0.3)',
                }}
              >
                <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                  {index + 1}
                </Typography>
              </Box>
              <Typography variant="caption" sx={{ mt: 1, color: isActive || isCompleted ? '#ffffff' : '#94a3b8', textAlign: 'center', maxWidth: 90 }}>
                {step.label}
              </Typography>
            </Box>
          )
        })}
      </Box>
      <Box sx={{ position: 'relative', width: '100%', height: 2, background: 'rgba(148, 163, 184, 0.18)' }}>
        <Box
          sx={{
            position: 'absolute',
            left: 0,
            top: 0,
            height: '100%',
            width: `${((activeStep + 1) / steps.length) * 100}%`,
            background: 'linear-gradient(135deg, #4f46e5, #4338ca)',
            borderRadius: 1,
            transition: 'width 0.3s ease',
          }}
        />
      </Box>
    </Box>
  )
}

export default StepIndicator
