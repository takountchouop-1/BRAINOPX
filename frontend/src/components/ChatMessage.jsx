import React, { useEffect, useMemo, useRef, useState } from 'react'
import Avatar from '@mui/material/Avatar'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import CheckCircleIconImport from '@mui/icons-material/CheckCircle'
import SmartToyIconImport from '@mui/icons-material/SmartToy'
import InsertDriveFileIconImport from '@mui/icons-material/InsertDriveFileOutlined'
import SearchIconImport from '@mui/icons-material/SearchOutlined'
import SettingsIconImport from '@mui/icons-material/SettingsOutlined'
import TrendingUpIconImport from '@mui/icons-material/TrendingUpOutlined'
import RocketLaunchIconImport from '@mui/icons-material/RocketLaunchOutlined'
import TrackChangesIconImport from '@mui/icons-material/TrackChangesOutlined'
import { useTranslation } from 'react-i18next'
import assistantAvatar from '../assets/agent.jpg'

const CheckCircleIcon = CheckCircleIconImport?.default || CheckCircleIconImport
const SmartToyIcon = SmartToyIconImport?.default || SmartToyIconImport
const InsertDriveFileIcon = InsertDriveFileIconImport?.default || InsertDriveFileIconImport
const SearchIcon = SearchIconImport?.default || SearchIconImport
const SettingsIcon = SettingsIconImport?.default || SettingsIconImport
const TrendingUpIcon = TrendingUpIconImport?.default || TrendingUpIconImport
const RocketLaunchIcon = RocketLaunchIconImport?.default || RocketLaunchIconImport
const TrackChangesIcon = TrackChangesIconImport?.default || TrackChangesIconImport

// Cycled by step index so a long guide still reads with some visual
// variety instead of the same glyph repeated down the list.
const STEP_ICONS = [SearchIcon, SettingsIcon, TrendingUpIcon, RocketLaunchIcon, TrackChangesIcon]

// A single continuous hue sweep (cyan → indigo → magenta) sampled per
// step, so each card's gradient flows smoothly into the next one's
// down the whole list rather than repeating a fixed pair of tones.
const STEP_HUE_START = 190
const STEP_HUE_SPAN = 150

const stepHue = (position) => STEP_HUE_START + STEP_HUE_SPAN * position

const stepHsl = (hue) => `hsl(${hue}, 82%, 56%)`

const stepGradient = (index, total) => {
  const t0 = total <= 1 ? 0 : index / total
  const t1 = total <= 1 ? 1 : (index + 1) / total
  return `linear-gradient(135deg, ${stepHsl(stepHue(t0))}, ${stepHsl(stepHue(t1))})`
}

const stepAccent = (index, total) => {
  const mid = total <= 1 ? 0.5 : (index + 0.5) / total
  return stepHsl(stepHue(mid))
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// ─── PALETTE ─────────────────────────────────────────────────────────────────
// The established colours: indigo for the person, white for the assistant.
// Only the shape and spacing are new.

export const USER_BG = '#4f46e5'
export const USER_TEXT = '#ffffff'

export const ASSISTANT_BG = (theme) =>
  theme.palette.mode === 'dark' ? '#2b2b2e' : '#ffffff'

export const ASSISTANT_TEXT = (theme) =>
  theme.palette.mode === 'dark' ? '#ececee' : '#1f2937'

export const ASSISTANT_BORDER_COLOR = (theme) =>
  theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.14)' : 'rgba(0,0,0,0.10)'

export const VALIDATED_COLOR = '#16a34a'

// The surface the conversation sits on: a soft blue easing into
// white, drawn from the same indigo family as the bubbles. Light
// enough that a white assistant card still reads as raised.
export const conversationBackground = (theme) =>
  theme.palette.mode === 'dark'
    ? 'linear-gradient(180deg, #1b1c22 0%, #17181d 55%, #141519 100%)'
    : 'linear-gradient(180deg, #eaeeff 0%, #f4f7ff 40%, #fdfdff 100%)'

// The composer sits at the foot of that gradient, so it fades from
// the surface rather than sitting on a hard band.
export const composerBackground = (theme) =>
  theme.palette.mode === 'dark'
    ? 'linear-gradient(180deg, rgba(20,21,25,0) 0%, #141519 22%)'
    : 'linear-gradient(180deg, rgba(253,253,255,0) 0%, #fdfdff 22%)'

// ─── ASSISTANT CONTENT STYLES ────────────────────────────────────────────────
// The assistant's messages arrive as markup with class names on each line.
// Kept here so both chat pages style them identically.

export const assistantContentStyles = (theme) => {
  const dark = theme.palette.mode === 'dark'

  return {
    fontSize: 15.5,
    lineHeight: 1.65,

    '& .task-title': {
      display: 'block',
      fontWeight: 400,
      marginBottom: '14px',
    },
    '& .task-title strong': { fontWeight: 800 },

    '& .workflow-step': {
      display: 'inline-block',
      background: '#16a34a',
      color: '#ffffff',
      padding: '5px 12px',
      borderRadius: '999px',
      fontWeight: 700,
      fontSize: '12px',
      letterSpacing: '0.3px',
      marginBottom: '10px',
    },

    '& .rule-name': {
      display: 'block',
      fontWeight: 700,
      marginBottom: '12px',
    },

    '& .rule-description': {
      display: 'block',
      marginBottom: '8px',
    },

    '& .example-box': {
      display: 'block',
      whiteSpace: 'pre-wrap',
      background: dark ? 'rgba(255,255,255,0.06)' : '#f1f5f9',
      border: dark ? '1px solid rgba(255,255,255,0.12)' : '1px solid rgba(0,0,0,0.08)',
      borderRadius: '10px',
      padding: '8px 12px',
      fontFamily: 'Consolas, monospace',
      fontSize: '13.5px',
      color: dark ? '#ece9e7' : '#334155',
      margin: '6px 0',
    },

    '& .success-message': {
      display: 'block',
      color: dark ? '#4ade80' : '#16a34a',
      fontWeight: 700,
      marginBottom: '8px',
    },

    '& .failure-message': {
      display: 'block',
      color: dark ? '#f87171' : '#dc2626',
      fontWeight: 600,
      marginBottom: '4px',
    },

    // Table steps. Scrolls inside itself so a wide table never
    // stretches the chat panel.
    '& .data-table': {
      display: 'block',
      overflowX: 'auto',
      width: '100%',
      borderCollapse: 'collapse',
      margin: '8px 0',
      fontSize: '13px',
      fontFamily: 'Consolas, monospace',
    },
    '& .data-table caption': {
      textAlign: 'left',
      fontSize: '12px',
      fontWeight: 700,
      opacity: 0.75,
      marginBottom: '4px',
      fontFamily: 'inherit',
    },
    '& .data-table th, & .data-table td': {
      border: dark ? '1px solid rgba(255,255,255,0.14)' : '1px solid rgba(0,0,0,0.12)',
      padding: '5px 9px',
      textAlign: 'left',
      whiteSpace: 'nowrap',
    },
    '& .data-table th': {
      background: dark ? 'rgba(255,255,255,0.08)' : '#eef2ff',
      fontWeight: 700,
    },
    '& .data-table .row-number': {
      width: '1%',
      opacity: 0.55,
      textAlign: 'right',
    },
    '& .data-table .bad-cell': {
      background: dark ? 'rgba(248,113,113,0.22)' : '#fee2e2',
      color: dark ? '#fecaca' : '#b91c1c',
      fontWeight: 700,
    },
    '& .data-table .bad-row td': {
      background: dark ? 'rgba(248,113,113,0.12)' : '#fef2f2',
    },
  }
}

// ─── HELPERS ─────────────────────────────────────────────────────────────────

const initialsOf = (fullName) =>
  fullName
    ? fullName
        .split(' ')
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0].toUpperCase())
        .join('')
    : '?'

const profileUrlOf = (user) =>
  user?.profile_picture
    ? `${API_BASE_URL}/uploads/profiles/${user.profile_picture}`
    : null

const clockOf = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const formatFileSize = (bytes, t) => {
  if (!bytes && bytes !== 0) return ''
  if (bytes < 1024) return t('chatMessage.fileSizeBytes', { size: bytes })
  if (bytes < 1024 * 1024) return t('chatMessage.fileSizeKB', { size: (bytes / 1024).toFixed(1) })
  return t('chatMessage.fileSizeMB', { size: (bytes / (1024 * 1024)).toFixed(1) })
}

/**
 * Small file chips shown inside a message bubble for any documents
 * (PDF/Word/etc.) attached to that turn.
 */
const AttachmentChips = ({ attachments, isUser }) => {
  const { t } = useTranslation('components')
  return (
  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 1 }}>
    {attachments.map((attachment) => (
      <Box
        key={attachment.id}
        component={attachment.url ? 'a' : 'div'}
        href={attachment.url ? `${API_BASE_URL}${attachment.url}` : undefined}
        target={attachment.url ? '_blank' : undefined}
        rel={attachment.url ? 'noopener noreferrer' : undefined}
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 0.6,
          px: 1.1,
          py: 0.5,
          borderRadius: '10px',
          textDecoration: 'none',
          fontSize: 12.5,
          fontWeight: 600,
          bgcolor: isUser ? 'rgba(255,255,255,0.16)' : 'rgba(79,70,229,0.08)',
          color: isUser ? '#ffffff' : 'inherit',
          maxWidth: '100%',
        }}
      >
        <InsertDriveFileIcon sx={{ fontSize: 15, flexShrink: 0 }} />
        <Box
          component="span"
          sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
        >
          {attachment.filename}
        </Box>
        {attachment.size_bytes != null && (
          <Box component="span" sx={{ opacity: 0.75, flexShrink: 0 }}>
            {formatFileSize(attachment.size_bytes, t)}
          </Box>
        )}
      </Box>
    ))}
  </Box>
  )
}

// ─── TYPEWRITER REVEAL ───────────────────────────────────────────────────────
// Assistant replies arrive whole from the API, but a message the caller
// flags as freshly-arrived (`animate`) is revealed a few characters at a
// time so it reads like a live response instead of popping in all at
// once — history loaded from the server is never flagged, so it renders
// instantly as before.

const plainLengthOf = (content, isHtml) => {
  const str = String(content || '')
  return isHtml ? str.replace(/<[^>]*>/g, '').length : str.length
}

const VOID_TAGS = new Set([
  'br', 'hr', 'img', 'input', 'col', 'area', 'base', 'embed', 'link', 'meta', 'source', 'track', 'wbr',
])

// Walks an HTML string, copying tags through untouched and only counting
// text-node characters against `charBudget`, closing any tag still open
// at the cutoff so the truncated markup stays valid mid-reveal.
const revealHtml = (html, charBudget) => {
  const str = String(html || '')
  let out = ''
  let budget = charBudget
  let i = 0
  const stack = []

  while (i < str.length) {
    if (budget <= 0) break

    if (str[i] === '<') {
      const end = str.indexOf('>', i)
      if (end === -1) break
      const tag = str.slice(i, end + 1)
      out += tag

      const closeMatch = tag.match(/^<\/([a-zA-Z0-9]+)/)
      const openMatch = tag.match(/^<([a-zA-Z0-9]+)/)
      if (closeMatch) {
        const name = closeMatch[1].toLowerCase()
        const idx = stack.lastIndexOf(name)
        if (idx !== -1) stack.splice(idx, 1)
      } else if (openMatch && !tag.endsWith('/>') && !VOID_TAGS.has(openMatch[1].toLowerCase())) {
        stack.push(openMatch[1].toLowerCase())
      }

      i = end + 1
      continue
    }

    out += str[i]
    budget -= 1
    i += 1
  }

  for (let k = stack.length - 1; k >= 0; k -= 1) {
    out += `</${stack[k]}>`
  }

  return out
}

const useTypewriterReveal = (content, enabled, isHtml) => {
  const totalLength = useMemo(() => plainLengthOf(content, isHtml), [content, isHtml])
  const [revealedLength, setRevealedLength] = useState(enabled ? 0 : totalLength)
  const timerRef = useRef(null)

  useEffect(() => {
    clearTimeout(timerRef.current)

    if (!enabled || totalLength === 0) {
      setRevealedLength(totalLength)
      return undefined
    }

    const reducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reducedMotion) {
      setRevealedLength(totalLength)
      return undefined
    }

    let count = 0
    setRevealedLength(0)
    // A handful of characters per tick, scaled to length, so a short
    // reply still feels instant and a long one doesn't take forever.
    const charsPerTick = Math.max(2, Math.round(totalLength / 150))
    const TICK_MS = 22

    const tick = () => {
      count = Math.min(totalLength, count + charsPerTick)
      setRevealedLength(count)
      if (count < totalLength) {
        timerRef.current = setTimeout(tick, TICK_MS)
      }
    }
    timerRef.current = setTimeout(tick, TICK_MS)

    return () => clearTimeout(timerRef.current)
  }, [content, enabled, totalLength])

  return { revealedLength, totalLength }
}

// ─── LIGHTWEIGHT MARKDOWN ────────────────────────────────────────────────────
// The assistant's replies come back as plain text with **bold**, numbered
// (1. 2. 3.) and bulleted (- or •) lines rather than real markup. Rendered
// as-is, the asterisks and dashes just show up literally. This turns that
// text into React elements (never raw HTML, so nothing here can inject
// markup the model happened to produce) — bold spans, and proper <ol>/<ul>
// lists so numbered and bulleted points actually read as points.

// Only these schemes are ever turned into a clickable link — anything
// else (javascript:, data:, etc.) renders as plain text instead, so a
// model reply can never smuggle an executable href into the page.
const isSafeHref = (href) => /^(https?:|mailto:)/i.test(href)

const AssistantLink = ({ href, children, keyPrefix }) => {
  if (!isSafeHref(href)) return <React.Fragment key={keyPrefix}>{children}</React.Fragment>
  return (
    <a
      key={keyPrefix}
      href={href}
      target={href.startsWith('mailto:') ? undefined : '_blank'}
      rel="noopener noreferrer"
      style={{ color: '#4f46e5', fontWeight: 600, textDecoration: 'underline', wordBreak: 'break-word' }}
    >
      {children}
    </a>
  )
}

const renderInline = (line, keyPrefix) => {
  const segments = line
    .split(/(\*\*[^*]+\*\*|\[[^\]]+\]\([^\s)]+\)|https?:\/\/[^\s)]+)/g)
    .filter(Boolean)

  return segments.map((segment, i) => {
    const key = `${keyPrefix}-${i}`

    const boldMatch = segment.match(/^\*\*([^*]+)\*\*$/)
    if (boldMatch) return <strong key={key}>{boldMatch[1]}</strong>

    const linkMatch = segment.match(/^\[([^\]]+)\]\(([^\s)]+)\)$/)
    if (linkMatch) {
      return (
        <AssistantLink key={key} keyPrefix={key} href={linkMatch[2]}>
          {linkMatch[1]}
        </AssistantLink>
      )
    }

    if (/^https?:\/\/[^\s)]+$/.test(segment)) {
      return (
        <AssistantLink key={key} keyPrefix={key} href={segment}>
          {segment}
        </AssistantLink>
      )
    }

    return <React.Fragment key={key}>{segment}</React.Fragment>
  })
}

// A markdown pipe-table row: "| a | b |" (leading/trailing pipe required).
const isTableRow = (line) => /^\|(.+)\|$/.test(line)

// The header/body divider row, e.g. "| --- | :---: |".
const isTableSeparatorRow = (line) => {
  if (!isTableRow(line)) return false
  const cells = line.slice(1, -1).split('|').map((c) => c.trim())
  return cells.length > 0 && cells.every((c) => /^:?-{1,}:?$/.test(c))
}

const splitTableRow = (line) => line.slice(1, -1).split('|').map((c) => c.trim())

// A guide-step line: "**Short Title** — one-sentence description."
// (also accepts an en/em dash, hyphen, or colon as the separator, since
// the model doesn't always reach for an em dash). Matched against the
// system prompt's requested "**Title** — sentence" step format.
const STEP_LINE_RE = /^\*\*([^*]+)\*\*\s*(?:—|–|-|:)\s*(.+)$/

// An ordered list only renders as illustrated step cards when every
// item follows that shape — a single non-matching item (a plain
// numbered instruction, no bold lead) falls the whole list back to a
// normal <ol> rather than rendering a mismatched mix of the two.
const asStepItems = (items) => {
  const parsed = items.map((item) => item.match(STEP_LINE_RE))
  if (!parsed.every(Boolean)) return null
  return parsed.map((match) => ({ title: match[1].trim(), description: match[2].trim() }))
}

const parseAssistantBlocks = (text) => {
  const lines = String(text || '').split('\n').map((l) => l.trim())
  const blocks = []
  let currentList = null

  const flushList = () => {
    if (currentList) {
      blocks.push(currentList)
      currentList = null
    }
  }

  let i = 0
  while (i < lines.length) {
    const line = lines[i]

    if (!line) {
      flushList()
      i += 1
      continue
    }

    // A table: a row, then a "---" separator row, then zero or more rows.
    if (isTableRow(line) && isTableSeparatorRow(lines[i + 1] || '')) {
      flushList()
      const headers = splitTableRow(line)
      const rows = []
      i += 2
      while (i < lines.length && isTableRow(lines[i])) {
        rows.push(splitTableRow(lines[i]))
        i += 1
      }
      blocks.push({ type: 'table', headers, rows })
      continue
    }

    const heading = line.match(/^(#{1,3})\s+(.*)$/)
    if (heading) {
      flushList()
      blocks.push({ type: `h${heading[1].length}`, text: heading[2].trim() })
      i += 1
      continue
    }

    const numbered = line.match(/^\d+[.)]\s+(.*)$/)
    const bulleted = line.match(/^[-•]\s+(.*)$/)

    if (numbered) {
      if (!currentList || currentList.type !== 'ol') {
        flushList()
        currentList = { type: 'ol', items: [] }
      }
      currentList.items.push(numbered[1])
      i += 1
      continue
    }

    if (bulleted) {
      if (!currentList || currentList.type !== 'ul') {
        flushList()
        currentList = { type: 'ul', items: [] }
      }
      currentList.items.push(bulleted[1])
      i += 1
      continue
    }

    flushList()
    blocks.push({ type: 'p', text: line })
    i += 1
  }

  flushList()
  return blocks
}

/**
 * A markdown table parsed out of the assistant's plain text, rendered as
 * a real <table> — scrolling inside itself so a wide table never
 * stretches the chat bubble.
 */
const AssistantTable = ({ headers, rows }) => (
  <Box sx={{ overflowX: 'auto', mb: 1, '&:last-child': { mb: 0 } }}>
    <Box
      component="table"
      sx={{
        borderCollapse: 'collapse',
        width: 'max-content',
        minWidth: '100%',
        fontSize: 13.5,
        '& th, & td': {
          border: (theme) =>
            theme.palette.mode === 'dark'
              ? '1px solid rgba(255,255,255,0.14)'
              : '1px solid rgba(0,0,0,0.12)',
          padding: '5px 10px',
          textAlign: 'left',
          whiteSpace: 'nowrap',
        },
        '& th': {
          background: (theme) =>
            theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : '#eef2ff',
          fontWeight: 700,
        },
      }}
    >
      <Box component="thead">
        <Box component="tr">
          {headers.map((cell, i) => (
            <Box component="th" key={i}>
              {renderInline(cell, `th-${i}`)}
            </Box>
          ))}
        </Box>
      </Box>
      <Box component="tbody">
        {rows.map((row, r) => (
          <Box component="tr" key={r}>
            {row.map((cell, c) => (
              <Box component="td" key={c}>
                {renderInline(cell, `td-${r}-${c}`)}
              </Box>
            ))}
          </Box>
        ))}
      </Box>
    </Box>
  </Box>
)

/**
 * One step of an illustrated guide, styled after a fused "pill + tab"
 * infographic: a rounded number tab on one side, a rounded card with an
 * icon badge and title/description on the other — the two pieces share
 * a straight seam so they read as a single connected shape. The number
 * tab alternates sides down the list (a light zigzag), and the icon
 * always sits at the card's outer edge, text always sits against the
 * seam next to the number.
 */
const StepGuideCard = ({ number, title, description, Icon, gradient, accent, numberOnRight }) => {
  const RADIUS = 22

  const tab = (
    <Box
      sx={{
        width: 52,
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: gradient,
        color: '#fff',
        fontSize: 19,
        fontWeight: 800,
        borderRadius: numberOnRight ? `0 ${RADIUS}px ${RADIUS}px 0` : `${RADIUS}px 0 0 ${RADIUS}px`,
      }}
    >
      {String(number).padStart(2, '0')}
    </Box>
  )

  const iconBadge = (
    <Box
      sx={{
        width: 34,
        height: 34,
        borderRadius: '50%',
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        border: `1.5px solid ${accent}55`,
        color: accent,
      }}
    >
      <Icon sx={{ fontSize: 17 }} />
    </Box>
  )

  const textBlock = (
    <Box sx={{ minWidth: 0 }}>
      <Box sx={{ width: 22, height: 2.5, borderRadius: 2, background: gradient, mb: 0.6 }} />
      <Typography
        sx={{
          fontSize: 11.5,
          fontWeight: 800,
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
          color: accent,
          mb: 0.35,
        }}
      >
        {title}
      </Typography>
      <Typography sx={{ fontSize: 13, lineHeight: 1.45, opacity: 0.78 }}>{description}</Typography>
    </Box>
  )

  const card = (
    <Box
      sx={{
        flex: 1,
        minWidth: 0,
        display: 'flex',
        alignItems: 'center',
        gap: 1.25,
        px: 2,
        py: 1.5,
        bgcolor: (theme) => (theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : '#ffffff'),
        boxShadow: (theme) =>
          theme.palette.mode === 'dark'
            ? '0 4px 14px rgba(0,0,0,0.3)'
            : '0 4px 14px rgba(16,24,40,0.10)',
        borderRadius: numberOnRight ? `${RADIUS}px 0 0 ${RADIUS}px` : `0 ${RADIUS}px ${RADIUS}px 0`,
      }}
    >
      {numberOnRight ? (
        <>
          {iconBadge}
          {textBlock}
        </>
      ) : (
        <>
          {textBlock}
          {iconBadge}
        </>
      )}
    </Box>
  )

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'stretch',
        ml: numberOnRight ? 0 : { xs: 1, sm: 2 },
        mr: numberOnRight ? { xs: 1, sm: 2 } : 0,
        mb: 1.5,
        '&:last-child': { mb: 0 },
      }}
    >
      {numberOnRight ? (
        <>
          {card}
          {tab}
        </>
      ) : (
        <>
          {tab}
          {card}
        </>
      )}
    </Box>
  )
}

const StepGuideList = ({ steps }) => (
  <Box sx={{ mb: 1, '&:last-child': { mb: 0 } }}>
    {steps.map((step, i) => (
      <StepGuideCard
        key={i}
        number={i + 1}
        title={step.title}
        description={step.description}
        Icon={STEP_ICONS[i % STEP_ICONS.length]}
        gradient={stepGradient(i, steps.length)}
        accent={stepAccent(i, steps.length)}
        numberOnRight={i % 2 === 0}
      />
    ))}
  </Box>
)

// Structured reports the assistant produces use '#'/'##'/'###' headings —
// rendered with real heading typography instead of literal '#' characters.
const HEADING_STYLES = {
  h1: { fontSize: 18, fontWeight: 800, mt: 0.5, mb: 1 },
  h2: { fontSize: 16.5, fontWeight: 800, mt: 0.5, mb: 0.75 },
  h3: { fontSize: 15.5, fontWeight: 700, mt: 0.5, mb: 0.5 },
}

/**
 * Renders assistant plain text with bold spans, headings, and real
 * numbered/bulleted lists instead of literal #, **, and - characters.
 */
const AssistantRichText = ({ text }) => {
  const blocks = parseAssistantBlocks(text)

  return (
    <Box sx={{ fontSize: 15.5, lineHeight: 1.65, '& > :last-child': { mb: 0 } }}>
      {blocks.map((block, i) => {
        if (block.type === 'h1' || block.type === 'h2' || block.type === 'h3') {
          return (
            <Typography
              key={i}
              component="div"
              sx={{ ...HEADING_STYLES[block.type], '&:first-of-type': { mt: 0 } }}
            >
              {renderInline(block.text, `${block.type}-${i}`)}
            </Typography>
          )
        }

        if (block.type === 'table') {
          return <AssistantTable key={i} headers={block.headers} rows={block.rows} />
        }

        if (block.type === 'p') {
          return (
            <Typography
              key={i}
              variant="body2"
              sx={{ fontSize: 15.5, lineHeight: 1.65, mb: 1, '&:last-child': { mb: 0 } }}
            >
              {renderInline(block.text, `p-${i}`)}
            </Typography>
          )
        }

        if (block.type === 'ol') {
          const steps = asStepItems(block.items)
          if (steps) return <StepGuideList key={i} steps={steps} />
        }

        const ListTag = block.type === 'ol' ? 'ol' : 'ul'
        return (
          <Box
            key={i}
            component={ListTag}
            sx={{ pl: 2.75, m: 0, mb: 1, '&:last-child': { mb: 0 }, '& li': { mb: 0.4 } }}
          >
            {block.items.map((item, j) => (
              <Typography
                key={j}
                component="li"
                variant="body2"
                sx={{ fontSize: 15.5, lineHeight: 1.6 }}
              >
                {renderInline(item, `li-${i}-${j}`)}
              </Typography>
            ))}
          </Box>
        )
      })}
    </Box>
  )
}

/**
 * One turn of a guided conversation.
 *
 * The person is shown by their profile picture; the assistant is
 * labelled "Assistant". Bubbles carry a tail towards their speaker,
 * so a glance is enough to tell who said what.
 */
const ChatMessage = ({
  sender,
  text,
  timestamp,
  validated,
  html = false,
  user = null,
  attachments = [],
  animate = false,
}) => {
  const { t } = useTranslation('components')
  const isUser = sender === 'user'
  const clock = clockOf(timestamp)

  // Only ever animates a message the caller has flagged as freshly
  // arrived; the person's own bubble is never typed out.
  const canAnimate = animate && !isUser
  const { revealedLength } = useTypewriterReveal(text, canAnimate, html)
  const displayedText = !canAnimate
    ? text
    : html
      ? revealHtml(text, revealedLength)
      : String(text || '').slice(0, revealedLength)

  const bubbleBase = {
    position: 'relative',
    maxWidth: '100%',
    wordBreak: 'break-word',
  }

  // The person's bubble carries the indigo fill; the assistant's is the
  // plain white/dark card. Person on the right, assistant on the left.
  const bubble = isUser
    ? {
        ...bubbleBase,
        px: 2.5,
        py: 2,
        bgcolor: USER_BG,
        color: USER_TEXT,
        borderRadius: '20px 20px 6px 20px',
        // Soft indigo lift, tinted to the bubble rather than grey,
        // so the shadow reads as part of the colour.
        boxShadow: '0 8px 20px rgba(79,70,229,0.24)',
        // Tail pointing down-right, towards the person's avatar.
        '&::after': {
          content: '""',
          position: 'absolute',
          right: -6,
          bottom: 0,
          width: 0,
          height: 0,
          borderStyle: 'solid',
          borderWidth: '0 0 10px 10px',
          borderColor: `transparent transparent transparent ${USER_BG}`,
        },
      }
    : {
        ...bubbleBase,
        // The assistant carries the step, the example and often a
        // table, so it is given more room than a typed reply.
        px: 2,
        py: 1.4,
        bgcolor: ASSISTANT_BG,
        color: ASSISTANT_TEXT,
        borderRadius: '20px 20px 20px 6px',
        border: (theme) =>
          theme.palette.mode === 'dark'
            ? '1.5px solid rgba(255,255,255,0.10)'
            : '1.5px solid rgba(79,70,229,0.22)',
        boxShadow: (theme) =>
          theme.palette.mode === 'dark'
            ? '0 8px 24px rgba(0,0,0,0.36), 0 1px 2px rgba(0,0,0,0.24)'
            : '0 8px 24px rgba(79,70,229,0.10), 0 2px 6px rgba(16,24,40,0.05)',
      }

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-end',
        gap: 1,
        flexDirection: isUser ? 'row-reverse' : 'row',
        alignSelf: isUser ? 'flex-end' : 'flex-start',
        // The bubble hugs its own content — a short reply stays short —
        // but is capped so a long paragraph or a table still wraps
        // instead of running edge to edge.
        maxWidth: isUser ? '78%' : '88%',
        width: 'fit-content',
      }}
    >
      {/* Who is speaking */}
      {isUser ? (
        <Avatar
          src={profileUrlOf(user) || undefined}
          alt={user?.full_name || t('chatMessage.you')}
          sx={{
            width: 30,
            height: 30,
            fontSize: 12,
            fontWeight: 700,
            bgcolor: USER_BG,
            color: '#fff',
            flexShrink: 0,
          }}
        >
          {initialsOf(user?.full_name)}
        </Avatar>
      ) : (
        <Avatar
          src={assistantAvatar}
          alt={t('chatMessage.assistant')}
          sx={{
            width: 36,
            height: 36,
            bgcolor: (theme) =>
              theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : '#eef2ff',
            color: USER_BG,
            flexShrink: 0,
            // A soft ring, matching the bubble's border.
            border: (theme) =>
              theme.palette.mode === 'dark'
                ? '1.5px solid rgba(255,255,255,0.10)'
                : '1.5px solid rgba(79,70,229,0.22)',
            boxShadow: (theme) =>
              theme.palette.mode === 'dark'
                ? 'none'
                : '0 3px 10px rgba(79,70,229,0.12)',
          }}
        >
          <SmartToyIcon sx={{ fontSize: 19 }} />
        </Avatar>
      )}

      <Box
        sx={{
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          flex: '0 1 auto',
        }}
      >
        {/* The assistant is named; the person is shown by their picture. */}
        {!isUser && (
          <Typography
            variant="caption"
            sx={{
              color: 'text.secondary',
              fontWeight: 700,
              fontSize: 12.5,
              letterSpacing: 0.2,
              mb: 0.5,
              ml: 0.5,
            }}
          >
            {t('chatMessage.assistant')}
          </Typography>
        )}

        <Box sx={bubble}>
          {html ? (
            <Typography
              component="div"
              variant="body2"
              sx={assistantContentStyles}
              dangerouslySetInnerHTML={{ __html: displayedText }}
            />
          ) : isUser ? (
            <Typography
              variant="body2"
              sx={{ whiteSpace: 'pre-wrap', fontSize: 15.5, lineHeight: 1.6 }}
            >
              {text}
            </Typography>
          ) : (
            <AssistantRichText text={displayedText} />
          )}

          {attachments.length > 0 && (
            <AttachmentChips attachments={attachments} isUser={isUser} />
          )}
        </Box>

        {/* Time, and whether the value was accepted. */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            mt: 0.4,
            px: 0.5,
            justifyContent: isUser ? 'flex-end' : 'flex-start',
          }}
        >
          {isUser && validated === true && (
            <>
              <CheckCircleIcon sx={{ fontSize: 13, color: VALIDATED_COLOR }} />
              <Typography
                variant="caption"
                sx={{ fontSize: 11, fontWeight: 700, color: VALIDATED_COLOR }}
              >
                {t('chatMessage.validated')}
              </Typography>
            </>
          )}
          {clock && (
            <Typography
              variant="caption"
              sx={{ fontSize: 11, color: 'text.secondary', opacity: 0.8 }}
            >
              {clock}
            </Typography>
          )}
        </Box>
      </Box>
    </Box>
  )
}

/**
 * The bare three-dot animation, with no avatar or bubble around it —
 * for chat surfaces that show their own loading caption inline rather
 * than as a full message bubble (e.g. next to "AI is responding...").
 */
export const TypingDots = ({ size = 6, color, dark }) => (
  <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
    {[0, 1, 2].map((i) => (
      <Box
        key={i}
        sx={{
          width: size,
          height: size,
          borderRadius: '50%',
          bgcolor: color || (dark ? '#8b8b95' : '#9295a6'),
          animation: 'bx-typing-dot 1.2s infinite ease-in-out',
          animationDelay: `${i * 0.16}s`,
          '@keyframes bx-typing-dot': {
            '0%, 60%, 100%': { transform: 'translateY(0)', opacity: 0.5 },
            '30%': { transform: 'translateY(-4px)', opacity: 1 },
          },
        }}
      />
    ))}
  </Box>
)

/**
 * "Assistant is thinking" — an animated three-dot bubble shown in place
 * of a message while a response is in flight. Styled like an assistant
 * ChatMessage bubble so it reads as part of the same conversation
 * instead of a generic spinner floating outside the message list.
 */
export const TypingIndicator = ({ label }) => {
  const { t } = useTranslation('components')
  const resolvedLabel = label || t('chatMessage.assistantThinking')
  return (
  <Box
    sx={{
      display: 'flex',
      alignItems: 'flex-end',
      gap: 1,
      alignSelf: 'flex-start',
      maxWidth: '88%',
    }}
  >
    <Avatar
      src={assistantAvatar}
      alt={t('chatMessage.assistant')}
      sx={{
        width: 36,
        height: 36,
        bgcolor: (theme) =>
          theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : '#eef2ff',
        color: USER_BG,
        flexShrink: 0,
        border: (theme) =>
          theme.palette.mode === 'dark'
            ? '1.5px solid rgba(255,255,255,0.10)'
            : '1.5px solid rgba(79,70,229,0.22)',
      }}
    >
      <SmartToyIcon sx={{ fontSize: 19 }} />
    </Avatar>

    <Box
      sx={{
        position: 'relative',
        borderRadius: '20px 20px 20px 6px',
        p: '2px', // reveals the gradient ring as a border
        // Linear gradient: blue -> green -> pink.
        background: 'linear-gradient(135deg, #3b82f6, #22c55e, #ec4899)',
        // Soft coloured glow so the ring reads clearly against the page.
        boxShadow: '0 0 14px rgba(99,102,241,0.35), 0 0 4px rgba(236,72,153,0.25)',
        // Cycles the gradient's hue and brightness so the ring's colours
        // rotate and shine, without spinning the box's shape.
        animation: 'bx-thinking-ring-shine 3s linear infinite',
        '@keyframes bx-thinking-ring-shine': {
          '0%': { filter: 'hue-rotate(0deg) brightness(1)' },
          '50%': { filter: 'hue-rotate(180deg) brightness(1.25)' },
          '100%': { filter: 'hue-rotate(360deg) brightness(1)' },
        },
      }}
    >
      <Box
        role="status"
        aria-label={resolvedLabel}
        sx={{
          px: 2.2,
          py: 1.6,
          bgcolor: ASSISTANT_BG,
          borderRadius: '18px 18px 18px 5px',
          display: 'flex',
          alignItems: 'center',
          gap: '5px',
        }}
      >
        {[0, 1, 2].map((i) => (
          <Box
            key={i}
            sx={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              bgcolor: (theme) => (theme.palette.mode === 'dark' ? '#8b8b95' : '#9295a6'),
              animation: 'bx-typing-dot 1.2s infinite ease-in-out',
              animationDelay: `${i * 0.16}s`,
              '@keyframes bx-typing-dot': {
                '0%, 60%, 100%': { transform: 'translateY(0)', opacity: 0.5 },
                '30%': { transform: 'translateY(-4px)', opacity: 1 },
              },
            }}
          />
        ))}
      </Box>
    </Box>
  </Box>
  )
}

export default ChatMessage
