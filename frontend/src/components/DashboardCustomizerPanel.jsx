import React from 'react'
import {
  Box,
  Drawer,
  Typography,
  IconButton,
  Slider,
  Button,
  Divider,
  Stack,
  Tooltip,
  Chip,
  Switch,
  FormControlLabel,
} from '@mui/material'
import CloseIconImport from '@mui/icons-material/Close'
import RestartAltIconImport from '@mui/icons-material/RestartAlt'
import PaletteIconImport from '@mui/icons-material/Palette'
import TextFieldsIconImport from '@mui/icons-material/TextFields'
import ViewSidebarIconImport from '@mui/icons-material/ViewSidebar'
import { useTranslation } from 'react-i18next'
import { useDashboardCustomizer } from '../context/DashboardCustomizerContext.jsx'
import { useThemeMode } from '../context/ThemeContext.jsx'

const CloseIcon = CloseIconImport?.default || CloseIconImport
const RestartAltIcon = RestartAltIconImport?.default || RestartAltIconImport
const PaletteIcon = PaletteIconImport?.default || PaletteIconImport
const TextFieldsIcon = TextFieldsIconImport?.default || TextFieldsIconImport
const ViewSidebarIcon = ViewSidebarIconImport?.default || ViewSidebarIconImport

const DashboardCustomizerPanel = () => {
  const {
    settings,
    open,
    closePanel,
    updateSetting,
    updateSettings,
    resetSettings,
    PRESET_COLORS,
    PRESET_SIDEBAR_BGS,
    QUICK_THEMES,
  } = useDashboardCustomizer()
  const { mode } = useThemeMode()
  const { t } = useTranslation('components')

  const colors = PRESET_COLORS[mode] || PRESET_COLORS.dark
  const sidebarBgs = PRESET_SIDEBAR_BGS[mode] || PRESET_SIDEBAR_BGS.dark

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={closePanel}
      PaperProps={{
        sx: {
          width: 340,
          maxWidth: '90vw',
          p: 0,
          bgcolor: (theme) => theme.palette.background.default,
          color: (theme) => theme.palette.text.primary,
        },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          p: 2.5,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: (theme) =>
            `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`,
        }}
      >
        <Stack direction="row" spacing={1.5} alignItems="center">
          <PaletteIcon color="primary" />
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
              {t('dashboardCustomizerPanel.title')}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              {t('dashboardCustomizerPanel.subtitle')}
            </Typography>
          </Box>
        </Stack>
        <IconButton onClick={closePanel} size="small" sx={{ color: 'text.secondary' }}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      <Box sx={{ p: 2.5, overflowY: 'auto', flex: 1 }}>
        {/* ── THEME SECTION ───────────────────────────────────────── */}
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
          <PaletteIcon fontSize="small" color="primary" />
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
            {t('dashboardCustomizerPanel.theme')}
          </Typography>
        </Stack>

        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
          {t('dashboardCustomizerPanel.themeDescription')}
        </Typography>

        <Stack direction="row" spacing={1.5} sx={{ mb: 2.5 }}>
          {QUICK_THEMES.map((quickTheme) => {
            const isActive =
              settings.sidebarBg === quickTheme.sidebarBg &&
              settings.primaryColor === quickTheme.primaryColor

            return (
              <Box
                key={quickTheme.name}
                onClick={() =>
                  updateSettings({
                    sidebarBg: quickTheme.sidebarBg,
                    primaryColor: quickTheme.primaryColor,
                  })
                }
                sx={{
                  flex: 1,
                  cursor: 'pointer',
                  borderRadius: 2,
                  overflow: 'hidden',
                  border: (t) =>
                    isActive
                      ? `2px solid ${quickTheme.primaryColor}`
                      : `1px solid ${t.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}`,
                  transition: 'transform 0.15s ease',
                  '&:hover': { transform: 'translateY(-2px)' },
                }}
              >
                {/* Miniature sidebar preview, so the swatch shows what
                    it does rather than just naming it. */}
                <Box sx={{ height: 54, background: quickTheme.sidebarBg, position: 'relative' }}>
                  <Box
                    sx={{
                      position: 'absolute',
                      left: 8,
                      right: 8,
                      top: 10,
                      height: 8,
                      borderRadius: 1,
                      bgcolor: quickTheme.primaryColor,
                    }}
                  />
                  <Box
                    sx={{
                      position: 'absolute',
                      left: 8,
                      right: 8,
                      top: 24,
                      height: 6,
                      borderRadius: 1,
                      bgcolor: 'rgba(255,255,255,0.15)',
                    }}
                  />
                  <Box
                    sx={{
                      position: 'absolute',
                      left: 8,
                      right: 8,
                      top: 34,
                      height: 6,
                      borderRadius: 1,
                      bgcolor: 'rgba(255,255,255,0.15)',
                    }}
                  />
                </Box>
                <Box
                  sx={{
                    py: 0.75,
                    textAlign: 'center',
                    bgcolor: (t) => (t.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : '#fff'),
                  }}
                >
                  <Typography variant="caption" sx={{ fontWeight: 700 }}>
                    {quickTheme.name}
                  </Typography>
                </Box>
              </Box>
            )
          })}
        </Stack>

        <Divider sx={{ mb: 2.5 }} />

        {/* ── COLORS SECTION ──────────────────────────────────────── */}
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
          <PaletteIcon fontSize="small" color="primary" />
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
            {t('dashboardCustomizerPanel.colors')}
          </Typography>
        </Stack>

        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
          {t('dashboardCustomizerPanel.primaryAccentColor')}
        </Typography>
        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 0.5, mb: 1.5 }}>
          <Tooltip title={t('dashboardCustomizerPanel.themeDefault')}>
            <Box
              onClick={() => updateSetting('primaryColor', null)}
              sx={{
                width: 32,
                height: 32,
                borderRadius: '50%',
                border: (theme) =>
                  settings.primaryColor === null
                    ? '2px solid ' + theme.palette.primary.main
                    : '2px solid transparent',
                background: 'conic-gradient(#a02bbf, #3b66ff, #0d9488, #e11d48, #a02bbf)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                '&:hover': { transform: 'scale(1.1)' },
                transition: 'transform 0.15s ease',
              }}
            >
              <Box
                sx={{
                  width: 12,
                  height: 12,
                  borderRadius: '50%',
                  bgcolor: (theme) => theme.palette.background.default,
                }}
              />
            </Box>
          </Tooltip>
          {colors.map((c) => (
            <Tooltip title={c.name} key={c.value}>
              <Box
                onClick={() => updateSetting('primaryColor', c.value)}
                sx={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  bgcolor: c.value,
                  cursor: 'pointer',
                  border: (theme) =>
                    settings.primaryColor === c.value
                      ? '2px solid ' + theme.palette.primary.main
                      : '2px solid transparent',
                  '&:hover': { transform: 'scale(1.1)' },
                  transition: 'transform 0.15s ease',
                }}
              />
            </Tooltip>
          ))}
        </Stack>

        {/* Custom hex input */}
        <Box
          component="form"
          onSubmit={(e) => {
            e.preventDefault()
            const val = e.target.elements.hex.value.trim()
            if (/^#[0-9a-fA-F]{6}$/.test(val)) {
              updateSetting('primaryColor', val)
            }
          }}
          sx={{ display: 'flex', gap: 1, mb: 2 }}
        >
          <Box
            sx={{
              width: 32,
              height: 32,
              borderRadius: 1,
              bgcolor: settings.primaryColor || '#a02bbf',
              flexShrink: 0,
              border: '1px solid rgba(255,255,255,0.1)',
            }}
          />
          <input
            name="hex"
            defaultValue={settings.primaryColor || ''}
            placeholder={t('dashboardCustomizerPanel.hexColorPlaceholder')}
            style={{
              flex: 1,
              background: 'transparent',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 6,
              padding: '4px 8px',
              color: 'inherit',
              fontSize: 12,
              fontFamily: 'monospace',
              outline: 'none',
            }}
          />
          <Button
            type="submit"
            size="small"
            variant="outlined"
            sx={{ textTransform: 'none', fontSize: 11, minWidth: 40 }}
          >
            {t('dashboardCustomizerPanel.set')}
          </Button>
        </Box>

        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
          {t('dashboardCustomizerPanel.sidebarBackground')}
        </Typography>
        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 0.5, mb: 2 }}>
          <Tooltip title={t('dashboardCustomizerPanel.themeDefault')}>
            <Box
              onClick={() => updateSetting('sidebarBg', null)}
              sx={{
                width: 36,
                height: 36,
                borderRadius: 1.5,
                border: (theme) =>
                  settings.sidebarBg === null
                    ? '2px solid ' + theme.palette.primary.main
                    : '2px solid transparent',
                background: 'conic-gradient(#2b0338, #1e3a8a, #0f766e, #581c87, #2b0338)',
                cursor: 'pointer',
                '&:hover': { transform: 'scale(1.08)' },
                transition: 'transform 0.15s ease',
              }}
            />
          </Tooltip>
          {sidebarBgs.map((bg) => (
            <Tooltip title={bg.name} key={bg.name}>
              <Box
                onClick={() => updateSetting('sidebarBg', bg.value)}
                sx={{
                  width: 36,
                  height: 36,
                  borderRadius: 1.5,
                  background: bg.value,
                  cursor: 'pointer',
                  border: (theme) =>
                    settings.sidebarBg === bg.value
                      ? '2px solid ' + theme.palette.primary.main
                      : '2px solid transparent',
                  '&:hover': { transform: 'scale(1.08)' },
                  transition: 'transform 0.15s ease',
                }}
              />
            </Tooltip>
          ))}
        </Stack>

        <Divider sx={{ my: 2.5 }} />

        {/* ── LAYOUT SECTION ──────────────────────────────────────── */}
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
          <ViewSidebarIcon fontSize="small" color="primary" />
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
            {t('dashboardCustomizerPanel.layout')}
          </Typography>
        </Stack>

        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
          {t('dashboardCustomizerPanel.sidebarWidthLabel')} <strong>{settings.sidebarWidth}px</strong>
        </Typography>
        <Slider
          value={settings.sidebarWidth}
          onChange={(e, val) => updateSetting('sidebarWidth', val)}
          min={180}
          max={400}
          step={10}
          valueLabelDisplay="auto"
          sx={{ mb: 1.5 }}
        />

        <FormControlLabel
          control={
            <Switch
              checked={settings.sidebarCollapsed}
              onChange={(e) => updateSetting('sidebarCollapsed', e.target.checked)}
              size="small"
            />
          }
          label={
            <Typography variant="body2" sx={{ fontSize: 13 }}>
              {t('dashboardCustomizerPanel.collapseSidebar')}
            </Typography>
          }
          sx={{ mb: 1.5 }}
        />

        <Divider sx={{ my: 2.5 }} />

        {/* ── FONT SECTION ────────────────────────────────────────── */}
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
          <TextFieldsIcon fontSize="small" color="primary" />
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
            {t('dashboardCustomizerPanel.fontSize')}
          </Typography>
        </Stack>

        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
          {t('dashboardCustomizerPanel.scaleLabel')} <strong>{settings.fontScale.toFixed(1)}x</strong>
        </Typography>
        <Slider
          value={settings.fontScale}
          onChange={(e, val) => updateSetting('fontScale', val)}
          min={0.8}
          max={1.5}
          step={0.1}
          valueLabelDisplay="auto"
          marks={[
            { value: 0.8, label: '0.8x' },
            { value: 1.0, label: '1x' },
            { value: 1.2, label: '1.2x' },
            { value: 1.5, label: '1.5x' },
          ]}
          sx={{ mb: 1 }}
        />

        <Box
          sx={{
            p: 1.5,
            borderRadius: 2,
            bgcolor: (theme) =>
              theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)',
            border: (theme) =>
              `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}`,
            fontSize: 12 * settings.fontScale,
            lineHeight: 1.5,
          }}
        >
          <Typography
            variant="caption"
            sx={{
              fontWeight: 700,
              color: 'primary.main',
              display: 'block',
              mb: 0.5,
              fontSize: 'inherit',
            }}
          >
            {t('dashboardCustomizerPanel.preview')}
          </Typography>
          <Typography
            variant="body2"
            sx={{ fontSize: 'inherit', color: 'text.secondary' }}
          >
            {t('dashboardCustomizerPanel.previewDescription', { scale: settings.fontScale.toFixed(1) })}
          </Typography>
        </Box>
      </Box>

      {/* Footer */}
      <Box
        sx={{
          p: 2,
          borderTop: (theme) =>
            `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`,
        }}
      >
        <Button
          fullWidth
          variant="outlined"
          startIcon={<RestartAltIcon />}
          onClick={resetSettings}
          sx={{ textTransform: 'none', borderRadius: 2 }}
        >
          {t('dashboardCustomizerPanel.resetToDefaults')}
        </Button>
      </Box>
    </Drawer>
  )
}

export default DashboardCustomizerPanel
