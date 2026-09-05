import { useState } from 'react'
import { Box, Menu, MenuItem, Tooltip } from '@mui/material'
import TranslateIconImport from '@mui/icons-material/Translate'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext.jsx'
import { LANGUAGE_STORAGE_KEY, SUPPORTED_LANGUAGES } from '../i18n/index.js'

const TranslateIcon = TranslateIconImport?.default || TranslateIconImport

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Compact language toggle: shown collapsed (icon only) in the sidebar
// rail, or fully labelled in flows that have room for it (Login,
// Register, Landingpage). Switching persists to localStorage always,
// and to the signed-in user's profile when there is a session — the
// same `language` field the backend reads to decide what language the
// AI assistant replies in, so this one control drives both.
const LanguageSwitcher = ({ collapsed = false, variant = 'icon', sx = {} }) => {
  const { t, i18n } = useTranslation('layout')
  const { user, token, updateUser } = useAuth()
  const [anchorEl, setAnchorEl] = useState(null)
  const [saving, setSaving] = useState(false)

  const currentLanguage = SUPPORTED_LANGUAGES.includes(i18n.language) ? i18n.language : 'en'

  const openMenu = (event) => setAnchorEl(event.currentTarget)
  const closeMenu = () => setAnchorEl(null)

  const selectLanguage = async (language) => {
    closeMenu()
    if (language === currentLanguage) return

    i18n.changeLanguage(language)
    localStorage.setItem(LANGUAGE_STORAGE_KEY, language)

    if (token) {
      setSaving(true)
      try {
        const response = await fetch(`${API_BASE_URL}/api/users/profile`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ language }),
        })
        if (response.ok) {
          const updated = await response.json()
          updateUser({ language: updated.language })
        }
      } catch {
        // UI language already switched locally; a failed sync just
        // means the preference won't follow the user to another
        // device until they try again — not worth blocking on.
      } finally {
        setSaving(false)
      }
    }
  }

  const languageLabel = (language) => (language === 'fr' ? t('language.french') : t('language.english'))

  const trigger =
    variant === 'icon' ? (
      <Tooltip title={t('language.switchTo', { language: languageLabel(currentLanguage === 'en' ? 'fr' : 'en') })} placement="right">
        <Box
          component="button"
          type="button"
          onClick={openMenu}
          disabled={saving}
          aria-label={t('language.label')}
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            gap: 1,
            width: '100%',
            appearance: 'none',
            cursor: 'pointer',
            border: '1px solid rgba(255,255,255,0.2)',
            borderRadius: '999px',
            background: 'rgba(255,255,255,0.06)',
            color: 'rgba(255,255,255,0.85)',
            fontFamily: 'inherit',
            fontWeight: 600,
            fontSize: 13,
            py: 0.9,
            px: collapsed ? 0 : 1.75,
            transition: 'background 0.15s ease',
            '&:hover': { background: 'rgba(255,255,255,0.12)' },
            ...sx,
          }}
        >
          <TranslateIcon sx={{ fontSize: 17 }} />
          {!collapsed && currentLanguage.toUpperCase()}
        </Box>
      </Tooltip>
    ) : (
      <Box
        component="button"
        type="button"
        onClick={openMenu}
        disabled={saving}
        aria-label={t('language.label')}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
          appearance: 'none',
          cursor: 'pointer',
          border: '1px solid rgba(0,0,0,0.12)',
          borderRadius: '999px',
          background: 'transparent',
          color: 'inherit',
          fontFamily: 'inherit',
          fontWeight: 600,
          fontSize: 13,
          py: 0.7,
          px: 1.5,
          ...sx,
        }}
      >
        <TranslateIcon sx={{ fontSize: 17 }} />
        {languageLabel(currentLanguage)}
      </Box>
    )

  return (
    <>
      {trigger}
      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={closeMenu}>
        {SUPPORTED_LANGUAGES.map((language) => (
          <MenuItem key={language} selected={language === currentLanguage} onClick={() => selectLanguage(language)}>
            {languageLabel(language)}
          </MenuItem>
        ))}
      </Menu>
    </>
  )
}

export default LanguageSwitcher
