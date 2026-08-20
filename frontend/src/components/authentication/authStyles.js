// Shared look for the Login and Register pages: black, blue, white —
// matching the sidebar's near-black with its blue accent. Kept in one
// place so the two pages, which were previously two copies of the
// same styling, cannot drift back apart.

export const AUTH_ACCENT = '#3b66ff'
export const AUTH_ACCENT_DARK = '#2d4fd6'

// Page backdrop, behind the card — a soft white easing into a pale
// blue, so the dark card reads as the sole focal point.
export const AUTH_PAGE_BG = 'linear-gradient(160deg, #eef2ff 0%, #f5f8ff 45%, #ffffff 100%)'

// The dark hero panel inside the card — black easing into blue, so
// the two accent colours meet in one place rather than sitting apart.
export const AUTH_HERO_BG = 'linear-gradient(135deg, #05050a 0%, #0d1128 55%, #1a2f6b 100%)'

// The card itself: a slighter, less rounded corner and a soft
// blue-tinted shadow rather than the heavy black one the dark page
// backdrop used to need.
export const AUTH_CARD_RADIUS = 3
export const AUTH_CARD_SHADOW = '0 24px 60px rgba(59,102,255,0.16), 0 4px 16px rgba(15,23,42,0.06)'

// Heading text: white fading into the accent blue.
export const AUTH_TITLE_GRADIENT = {
  background: 'linear-gradient(90deg, #ffffff 0%, #9db8ff 100%)',
  WebkitBackgroundClip: 'text',
  backgroundClip: 'text',
  color: 'transparent',
}

// The primary action carries all three colours at once: black into
// blue, landing on white text.
export const AUTH_BUTTON_GRADIENT = 'linear-gradient(90deg, #0a0a12 0%, #1a2f6b 55%, #3b66ff 100%)'

// Text field styling: dark text and visible borders on the white
// panel, with the accent blue on focus.
export const authInputStyles = {
  borderRadius: 4,
  background: '#ffffff',
  '& .MuiInputBase-input': {
    color: '#0f172a',
    '&::placeholder': {
      color: '#64748b',
      opacity: 0.75,
    },
  },
  '& .MuiInputLabel-root': {
    color: '#475569',
    '&.Mui-focused': {
      color: AUTH_ACCENT,
    },
  },
  '& .MuiOutlinedInput-root': {
    '& fieldset': {
      borderColor: '#cbd5e1',
      borderWidth: '1.5px',
    },
    '&:hover fieldset': {
      borderColor: '#94a3b8',
    },
    '&.Mui-focused fieldset': {
      borderColor: AUTH_ACCENT,
    },
  },
}

export const authCheckboxStyles = {
  color: '#94a3b8',
  '&.Mui-checked': { color: AUTH_ACCENT },
}

export const authLinkStyles = {
  color: AUTH_ACCENT,
  fontWeight: 600,
}

// The primary button carries a diagonal "shine" bar sitting just
// outside its left edge; on hover it sweeps across to the right, and
// a click presses the button down with a tighter, brighter shadow.
export const authButtonStyles = {
  position: 'relative',
  overflow: 'hidden',
  py: 1.6,
  borderRadius: 8,
  textTransform: 'none',
  background: AUTH_BUTTON_GRADIENT,
  color: '#ffffff',
  transition: 'opacity 0.35s ease, transform 0.15s ease, box-shadow 0.3s ease',
  boxShadow: '0 8px 24px rgba(59,102,255,0.28)',
  '&::before': {
    content: '""',
    position: 'absolute',
    top: 0,
    left: '-60%',
    width: '35%',
    height: '100%',
    background: 'linear-gradient(115deg, transparent 0%, rgba(255,255,255,0.55) 50%, transparent 100%)',
    transform: 'skewX(-22deg)',
    transition: 'left 0.65s ease',
    pointerEvents: 'none',
  },
  '&:hover': {
    opacity: 0.95,
    transform: 'translateY(-2px)',
    boxShadow: '0 18px 34px rgba(59,102,255,0.30)',
  },
  '&:hover::before': {
    left: '130%',
  },
  '&:active': {
    transform: 'translateY(0) scale(0.98)',
    boxShadow: '0 4px 14px rgba(59,102,255,0.4)',
  },
}

export const authOutlineButtonStyles = {
  borderColor: '#cbd5e1',
  '&:hover': { bgcolor: 'rgba(0,0,0,0.02)', borderColor: '#94a3b8' },
}

// Circular social-login buttons: a plain white disc with a soft
// shadow that lifts and glows on hover, holding just the brand glyph
// (no label), matching a plain icon-button reference design.
export const authSocialCircleStyles = {
  width: 48,
  height: 48,
  minWidth: 48,
  padding: 0,
  borderRadius: '50%',
  background: '#ffffff',
  border: '1px solid #eef2ff',
  boxShadow: '0 4px 14px rgba(15,23,42,0.10)',
  transition: 'transform 0.25s ease, box-shadow 0.25s ease',
  '&:hover': {
    transform: 'translateY(-3px)',
    boxShadow: '0 12px 24px rgba(59,102,255,0.24)',
  },
  '&:active': {
    transform: 'translateY(-1px) scale(0.96)',
  },
}
