import React from 'react'
import { Box, Pagination, Select, MenuItem, Typography, Stack } from '@mui/material'
import { useTranslation } from 'react-i18next'

const PAGE_SIZE_OPTIONS = [10, 25, 50]

const navButtonSx = {
  appearance: 'none',
  cursor: 'pointer',
  border: 'none',
  background: 'transparent',
  borderRadius: 1.5,
  px: 1.25,
  py: 0.5,
  fontSize: 13,
  fontWeight: 600,
  color: 'text.secondary',
  fontFamily: 'inherit',
  '&:disabled': { color: 'text.disabled', cursor: 'not-allowed' },
  '&:hover:not(:disabled)': {
    bgcolor: (theme) => (theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)'),
    color: 'text.primary',
  },
}

const pageButtonSx = {
  appearance: 'none',
  cursor: 'pointer',
  border: 'none',
  minWidth: 32,
  height: 32,
  borderRadius: 1.5,
  fontSize: 13,
  fontFamily: 'inherit',
  fontWeight: 600,
  transition: 'background 0.12s ease, color 0.12s ease',
}

/**
 * A page strip: « Prev, numbered pages with an ellipsis for large
 * ranges, Next », a record count, and a rows-per-page picker.
 *
 * Purely a controlled display piece — page numbering and the
 * ellipsis placement come from MUI's Pagination (usePagination under
 * the hood), so edge cases like "few pages near the start" are
 * handled the same way MUI already tests them; only how each item
 * renders is customised here. The caller owns page/pageSize state
 * and slices its own data — this component does not fetch or filter
 * anything.
 */
const PaginationBar = ({
  page,
  pageSize,
  totalRecords,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = PAGE_SIZE_OPTIONS,
  recordLabel,
}) => {
  const { t } = useTranslation('components')
  const effectiveRecordLabel = recordLabel || t('paginationBar.records')
  const pageCount = Math.max(1, Math.ceil(totalRecords / pageSize))

  if (totalRecords === 0) {
    return null
  }

  return (
    <Stack
      direction={{ xs: 'column', sm: 'row' }}
      alignItems="center"
      justifyContent="space-between"
      spacing={1.5}
      sx={{
        px: 2,
        py: 1.5,
        borderTop: (theme) =>
          `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : '#e5e7eb'}`,
      }}
    >
      <Pagination
        page={page}
        count={pageCount}
        onChange={(_, value) => onPageChange(value)}
        siblingCount={1}
        boundaryCount={1}
        renderItem={(item) => {
          if (item.type === 'previous') {
            return (
              <Box component="button" type="button" disabled={item.disabled} onClick={item.onClick} sx={navButtonSx}>
                {t('paginationBar.prev')}
              </Box>
            )
          }

          if (item.type === 'next') {
            return (
              <Box component="button" type="button" disabled={item.disabled} onClick={item.onClick} sx={navButtonSx}>
                {t('paginationBar.next')}
              </Box>
            )
          }

          if (item.type === 'start-ellipsis' || item.type === 'end-ellipsis') {
            return (
              <Box
                sx={{
                  width: 28,
                  height: 32,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'text.disabled',
                  fontSize: 14,
                }}
              >
                …
              </Box>
            )
          }

          // 'page'
          return (
            <Box
              component="button"
              type="button"
              onClick={item.onClick}
              aria-current={item.selected ? 'page' : undefined}
              sx={{
                ...pageButtonSx,
                bgcolor: item.selected ? '#4f46e5' : 'transparent',
                color: item.selected ? '#fff' : 'text.secondary',
                '&:hover': {
                  bgcolor: item.selected
                    ? '#4338ca'
                    : (theme) => (theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)'),
                },
              }}
            >
              {item.page}
            </Box>
          )
        }}
        sx={{ '& .MuiPagination-ul': { gap: 4 } }}
      />

      <Stack direction="row" alignItems="center" spacing={2}>
        <Typography variant="body2" sx={{ color: 'text.secondary', whiteSpace: 'nowrap' }}>
          {totalRecords} {effectiveRecordLabel}
        </Typography>

        <Select
          size="small"
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          sx={{ fontSize: 13, minWidth: 116, borderRadius: 2 }}
        >
          {pageSizeOptions.map((size) => (
            <MenuItem key={size} value={size} sx={{ fontSize: 13 }}>
              {t('paginationBar.perPage', { size })}
            </MenuItem>
          ))}
        </Select>
      </Stack>
    </Stack>
  )
}

export default PaginationBar
