import { Box } from '@mui/material'
import { motion } from 'framer-motion'

// A little decorative card that drifts up/down and gently rocks side to
// side forever — used to build the floating chart/icon mockups in the
// auth hero panels. Hidden below md since there isn't room to float
// things around the form without crowding it.
export const FloatingCard = ({ top, left, right, bottom, duration = 6, delay = 0, rotateFrom = -6, rotateTo = 6, children }) => (
  <Box
    component={motion.div}
    initial={{ y: 0, rotate: rotateFrom }}
    animate={{ y: [0, -16, 0], rotate: [rotateFrom, rotateTo, rotateFrom] }}
    transition={{ duration, delay, repeat: Infinity, ease: 'easeInOut' }}
    sx={{
      display: { xs: 'none', md: 'block' },
      position: 'absolute',
      top,
      left,
      right,
      bottom,
      zIndex: 1,
      pointerEvents: 'none',
    }}
  >
    {children}
  </Box>
)

export const BarChartMock = () => (
  <Box
    sx={{
      width: 118,
      height: 78,
      borderRadius: 3,
      background: 'rgba(255,255,255,0.08)',
      border: '1px solid rgba(255,255,255,0.16)',
      backdropFilter: 'blur(6px)',
      boxShadow: '0 20px 40px rgba(2,6,20,0.45)',
      p: 1.25,
      display: 'flex',
      alignItems: 'flex-end',
    }}
  >
    <svg width="100%" height="100%" viewBox="0 0 90 50" fill="none">
      <defs>
        <linearGradient id="authSparkline" x1="0" y1="0" x2="90" y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#9db8ff" />
        </linearGradient>
      </defs>
      <polyline
        points="0,34 14,22 28,30 42,10 56,20 70,6 90,14"
        fill="none"
        stroke="url(#authSparkline)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="90" cy="14" r="3.5" fill="#ffffff" />
    </svg>
  </Box>
)

export const PieChartMock = () => (
  <Box
    sx={{
      width: 84,
      height: 84,
      borderRadius: 3,
      background: 'rgba(255,255,255,0.08)',
      border: '1px solid rgba(255,255,255,0.16)',
      backdropFilter: 'blur(6px)',
      boxShadow: '0 20px 40px rgba(2,6,20,0.45)',
      display: 'grid',
      placeItems: 'center',
    }}
  >
    <Box
      sx={{
        width: 48,
        height: 48,
        borderRadius: '50%',
        background: 'conic-gradient(#ffffff 0deg 140deg, #9db8ff 140deg 240deg, rgba(255,255,255,0.25) 240deg 360deg)',
        boxShadow: 'inset 0 0 0 14px rgba(10,10,18,0.55)',
      }}
    />
  </Box>
)

export const IconChip = ({ icon, color }) => (
  <Box
    sx={{
      width: 44,
      height: 44,
      borderRadius: '14px',
      background: 'rgba(10,10,20,0.55)',
      border: '1px solid rgba(255,255,255,0.18)',
      backdropFilter: 'blur(6px)',
      boxShadow: '0 14px 30px rgba(2,6,20,0.5)',
      display: 'grid',
      placeItems: 'center',
      color,
    }}
  >
    {icon}
  </Box>
)

// Page-wide backdrop used by both the Login and Register pages: a dark
// gradient with two soft drifting blue blooms and a top glow, plus the
// keyframes they animate with. Rendered once behind everything else.
export const AuthPageBackdrop = () => (
  <>
    <style>{`
      @keyframes authSwirlDrift {
        0% { transform: translate(0, 0) scale(1); }
        50% { transform: translate(-30px, -20px) scale(1.06); }
        100% { transform: translate(0, 0) scale(1); }
      }
    `}</style>
    <Box sx={{ position: 'absolute', inset: 0, zIndex: 0, pointerEvents: 'none', overflow: 'hidden' }}>
      <Box
        sx={{
          position: 'absolute',
          width: 900,
          height: 900,
          right: -320,
          bottom: -420,
          borderRadius: '50%',
          filter: 'blur(60px)',
          background: 'radial-gradient(circle at 40% 40%, rgba(90,120,255,0.55) 0%, rgba(60,70,220,0.35) 35%, rgba(20,20,60,0.05) 70%, transparent 100%)',
          animation: 'authSwirlDrift 16s ease-in-out infinite',
        }}
      />
      <Box
        sx={{
          position: 'absolute',
          width: 700,
          height: 700,
          right: -180,
          bottom: -300,
          borderRadius: '50%',
          filter: 'blur(60px)',
          background: 'radial-gradient(circle at 60% 30%, rgba(140,160,255,0.35) 0%, rgba(80,90,240,0.2) 40%, transparent 75%)',
          animation: 'authSwirlDrift 16s ease-in-out infinite reverse',
        }}
      />
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: '50%',
          transform: 'translateX(-50%)',
          width: '90%',
          height: 260,
          filter: 'blur(72px)',
          background: 'radial-gradient(circle at top center, rgba(130,150,255,0.28) 0%, rgba(90,100,255,0.16) 22%, rgba(255,255,255,0.02) 55%, transparent 100%)',
        }}
      />
    </Box>
  </>
)
