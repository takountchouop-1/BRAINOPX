import React from 'react'
import Avatar from '@mui/material/Avatar'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import CheckCircleIconImport from '@mui/icons-material/CheckCircle'
import SmartToyIconImport from '@mui/icons-material/SmartToy'
import InsertDriveFileIconImport from '@mui/icons-material/InsertDriveFileOutlined'
import assistantAvatar from '../assets/agent.jpg'

const CheckCircleIcon = CheckCircleIconImport?.default || CheckCircleIconImport
const SmartToyIcon = SmartToyIconImport?.default || SmartToyIconImport
const InsertDriveFileIcon = InsertDriveFileIconImport?.default || InsertDriveFileIconImport

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

const formatFileSize = (bytes) => {
  if (!bytes && bytes !== 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * Small file chips shown inside a message bubble for any documents
 * (PDF/Word/etc.) attached to that turn.
 */
const AttachmentChips = ({ attachments, isUser }) => (
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
            {formatFileSize(attachment.size_bytes)}
          </Box>
        )}
      </Box>
    ))}
  </Box>
)

// ─── LIGHTWEIGHT MARKDOWN ────────────────────────────────────────────────────
// The assistant's replies come back as plain text with **bold**, numbered
// (1. 2. 3.) and bulleted (- or •) lines rather than real markup. Rendered
// as-is, the asterisks and dashes just show up literally. This turns that
// text into React elements (never raw HTML, so nothing here can inject
// markup the model happened to produce) — bold spans, and proper <ol>/<ul>
// lists so numbered and bulleted points actually read as points.

const renderInline = (line, keyPrefix) => {
  const segments = line.split(/(\*\*[^*]+\*\*)/g).filter(Boolean)

  return segments.map((segment, i) => {
    const boldMatch = segment.match(/^\*\*([^*]+)\*\*$/)
    return boldMatch ? (
      <strong key={`${keyPrefix}-${i}`}>{boldMatch[1]}</strong>
    ) : (
      <React.Fragment key={`${keyPrefix}-${i}`}>{segment}</React.Fragment>
    )
  })
}

const parseAssistantBlocks = (text) => {
  const lines = String(text || '').split('\n')
  const blocks = []
  let currentList = null

  const flushList = () => {
    if (currentList) {
      blocks.push(currentList)
      currentList = null
    }
  }

  lines.forEach((rawLine) => {
    const line = rawLine.trim()

    if (!line) {
      flushList()
      return
    }

    const heading = line.match(/^(#{1,3})\s+(.*)$/)
    if (heading) {
      flushList()
      blocks.push({ type: `h${heading[1].length}`, text: heading[2].trim() })
      return
    }

    const numbered = line.match(/^\d+[.)]\s+(.*)$/)
    const bulleted = line.match(/^[-•]\s+(.*)$/)

    if (numbered) {
      if (!currentList || currentList.type !== 'ol') {
        flushList()
        currentList = { type: 'ol', items: [] }
      }
      currentList.items.push(numbered[1])
      return
    }

    if (bulleted) {
      if (!currentList || currentList.type !== 'ul') {
        flushList()
        currentList = { type: 'ul', items: [] }
      }
      currentList.items.push(bulleted[1])
      return
    }

    flushList()
    blocks.push({ type: 'p', text: line })
  })

  flushList()
  return blocks
}

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
}) => {
  const isUser = sender === 'user'
  const clock = clockOf(timestamp)

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
          alt={user?.full_name || 'You'}
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
          alt="Assistant"
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
            Assistant
          </Typography>
        )}

        <Box sx={bubble}>
          {html ? (
            <Typography
              component="div"
              variant="body2"
              sx={assistantContentStyles}
              dangerouslySetInnerHTML={{ __html: text }}
            />
          ) : isUser ? (
            <Typography
              variant="body2"
              sx={{ whiteSpace: 'pre-wrap', fontSize: 15.5, lineHeight: 1.6 }}
            >
              {text}
            </Typography>
          ) : (
            <AssistantRichText text={text} />
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
                Validated
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
export const TypingIndicator = ({ label = 'Assistant is thinking' }) => (
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
      alt="Assistant"
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
        aria-label={label}
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

export default ChatMessage
