import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'

const DashboardCustomizerContext = createContext(null)

const STORAGE_KEY = 'brainopx_dashboard_customizer'

const DEFAULTS = {
  primaryColor: null, // null = use theme default
  sidebarBg: null, // null = use theme default
  fontScale: 1.0,
  sidebarWidth: 260,
  sidebarCollapsed: false,
}

const PRESET_COLORS = {
  dark: [
    { name: 'Purple', value: '#a02bbf' },
    { name: 'Blue', value: '#3b66ff' },
    { name: 'Teal', value: '#0d9488' },
    { name: 'Rose', value: '#e11d48' },
    { name: 'Amber', value: '#d97706' },
    { name: 'Green', value: '#16a34a' },
  ],
  light: [
    { name: 'Indigo', value: '#4f46e5' },
    { name: 'Blue', value: '#1976d2' },
    { name: 'Teal', value: '#0d9488' },
    { name: 'Rose', value: '#e11d48' },
    { name: 'Amber', value: '#d97706' },
    { name: 'Green', value: '#16a34a' },
  ],
}

const PRESET_SIDEBAR_BGS = {
  dark: [
    { name: 'Midnight', value: 'linear-gradient(180deg, #0a0a12 0%, #0d0d18 100%)' },
    { name: 'Blue Deep', value: 'linear-gradient(180deg, #0a1740 0%, #0e2151 55%, #123069 100%)' },
    { name: 'Deep Purple', value: 'linear-gradient(180deg, #2b0338 0%, #3a0f64 35%, #6b1f8a 70%)' },
    { name: 'Dark Blue', value: 'linear-gradient(180deg, #0c1445 0%, #1a237e 50%, #283593 100%)' },
    { name: 'Slate', value: 'linear-gradient(180deg, #0f172a 0%, #1e293b 50%, #334155 100%)' },
    { name: 'Charcoal', value: 'linear-gradient(180deg, #111827 0%, #1f2937 50%, #374151 100%)' },
  ],
  light: [
    { name: 'Indigo', value: 'linear-gradient(180deg, #1e3a8a 0%, #2563eb 45%, #3b82f6 100%)' },
    { name: 'Blue Gray', value: 'linear-gradient(180deg, #1e293b 0%, #334155 50%, #475569 100%)' },
    { name: 'Teal', value: 'linear-gradient(180deg, #0f766e 0%, #14b8a6 50%, #2dd4bf 100%)' },
    { name: 'Purple', value: 'linear-gradient(180deg, #581c87 0%, #7c3aed 50%, #a855f7 100%)' },
    { name: 'White', value: '#ffffff' },
  ],
}

// Two one-click sidebar looks: a near-black "Dark" mode and a solid
// "Blue Deep" mode. Each bundles a sidebar background with the accent
// colour the navigation highlight and logout pill pick up, so picking
// one visibly changes both together rather than requiring two
// separate choices.
const QUICK_THEMES = [
  {
    name: 'Dark',
    sidebarBg: PRESET_SIDEBAR_BGS.dark[0].value,
    primaryColor: '#3b66ff',
  },
  {
    name: 'Blue Deep',
    sidebarBg: PRESET_SIDEBAR_BGS.dark[1].value,
    primaryColor: '#2f6fed',
  },
]

export const DashboardCustomizerProvider = ({ children }) => {
  const [settings, setSettings] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        return { ...DEFAULTS, ...parsed }
      }
    } catch (e) {
      // ignore
    }
    return { ...DEFAULTS }
  })

  const [open, setOpen] = useState(false)

  // Persist to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
    } catch (e) {
      // ignore
    }
  }, [settings])

  const updateSetting = useCallback((key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }))
  }, [])

  // Sets several settings in one render, so a quick theme's sidebar
  // background and accent colour land together rather than as two
  // separate updates.
  const updateSettings = useCallback((partial) => {
    setSettings((prev) => ({ ...prev, ...partial }))
  }, [])

  const resetSettings = useCallback(() => {
    setSettings({ ...DEFAULTS })
  }, [])

  const togglePanel = useCallback(() => {
    setOpen((prev) => !prev)
  }, [])

  const closePanel = useCallback(() => {
    setOpen(false)
  }, [])

  const value = {
    settings,
    open,
    updateSetting,
    updateSettings,
    resetSettings,
    togglePanel,
    closePanel,
    PRESET_COLORS,
    PRESET_SIDEBAR_BGS,
    QUICK_THEMES,
  }

  return (
    <DashboardCustomizerContext.Provider value={value}>
      {children}
    </DashboardCustomizerContext.Provider>
  )
}

export const useDashboardCustomizer = () => {
  const context = useContext(DashboardCustomizerContext)
  if (!context) {
    throw new Error('useDashboardCustomizer must be used within a DashboardCustomizerProvider')
  }
  return context
}

export { DEFAULTS, PRESET_COLORS, PRESET_SIDEBAR_BGS, QUICK_THEMES }
