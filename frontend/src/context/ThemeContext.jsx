import React, { createContext, useContext, useState, useMemo, useEffect } from 'react'
import { ThemeProvider, createTheme } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import { useDashboardCustomizer } from './DashboardCustomizerContext.jsx'

const ThemeModeContext = createContext(null)

const MODE_STORAGE_KEY = 'brainopx_theme_mode'

export const ThemeModeProvider = ({ children }) => {
  const [mode, setMode] = useState(() => {
    return localStorage.getItem(MODE_STORAGE_KEY) || 'dark'
  })

  const { settings } = useDashboardCustomizer()

  const toggleMode = () => {
    setMode((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark'
      localStorage.setItem(MODE_STORAGE_KEY, next)
      return next
    })
  }

  const theme = useMemo(() => {
    const primaryColor = settings.primaryColor || (mode === 'dark' ? '#a02bbf' : '#3b66ff')
    const fontScale = settings.fontScale || 1.0

    return createTheme({
      palette: {
        mode,
        ...(mode === 'dark'
          ? {
              background: {
                default: '#020814',
                paper: 'rgba(255,255,255,0.05)',
              },
              text: {
                primary: '#ffffff',
                secondary: 'rgba(255,255,255,0.7)',
              },
            }
          : {
              background: {
                default: '#f4f7fb',
                paper: '#ffffff',
              },
              text: {
                primary: '#1a1a2e',
                secondary: '#6b7280',
              },
            }),
        primary: {
          main: primaryColor,
        },
      },
      typography: {
        fontFamily: ['Inter', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'].join(','),
        htmlFontSize: Math.round(16 * fontScale),
        fontSize: Math.round(14 * fontScale),
        h1: { fontSize: `${Math.round(2.125 * fontScale)}rem` },
        h2: { fontSize: `${Math.round(1.75 * fontScale)}rem` },
        h3: { fontSize: `${Math.round(1.5 * fontScale)}rem` },
        h4: { fontSize: `${Math.round(1.35 * fontScale)}rem` },
        h5: { fontSize: `${Math.round(1.15 * fontScale)}rem` },
        h6: { fontSize: `${Math.round(1.0 * fontScale)}rem` },
        body1: { fontSize: `${Math.round(1.0 * fontScale)}rem` },
        body2: { fontSize: `${Math.round(0.875 * fontScale)}rem` },
        caption: { fontSize: `${Math.round(0.75 * fontScale)}rem` },
        button: { fontSize: `${Math.round(0.875 * fontScale)}rem` },
      },
      components: {
        MuiCssBaseline: {
          styleOverrides: {
            body: {
              fontSize: `${Math.round(14 * fontScale)}px`,
            },
          },
        },
      },
    })
  }, [mode, settings.primaryColor, settings.fontScale])

  const value = { mode, toggleMode }

  return (
    <ThemeModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ThemeModeContext.Provider>
  )
}

export const useThemeMode = () => {
  const context = useContext(ThemeModeContext)
  if (!context) {
    throw new Error('useThemeMode must be used within a ThemeModeProvider')
  }
  return context
}
