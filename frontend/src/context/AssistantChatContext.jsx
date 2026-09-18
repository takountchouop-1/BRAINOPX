import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useAuth } from './AuthContext.jsx'

// The AI-assistant conversation is kept here, *above* the router, so it
// survives navigating between sidebar pages. Only an explicit "new chat"
// (or "clear conversations") resets it. It is also mirrored to
// sessionStorage so a full page refresh keeps the thread as well —
// sessionStorage is cleared when the tab is closed, not on reload.
const STORAGE_KEY = 'brainopx.assistant.conversation.v1'

const readStoredConversation = () => {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === 'object' && Array.isArray(parsed.messages)) {
      return {
        conversationId: parsed.conversationId ?? null,
        messages: parsed.messages,
        selectedTask: parsed.selectedTask ?? null,
      }
    }
  } catch {
    // Corrupted or unavailable storage — fall back to a fresh chat.
  }
  return null
}

// The user id persisted in localStorage is available synchronously, unlike
// the React state AuthContext restores in an effect — so it's safe to read
// here while the provider is still mounting.
const readStoredUserId = () => {
  try {
    const raw = window.localStorage.getItem('brainopx_user')
    if (!raw) return null
    return JSON.parse(raw)?.id ?? null
  } catch {
    return null
  }
}

const AssistantChatContext = createContext(null)

export const AssistantChatProvider = ({ children }) => {
  const { user, isInitializing } = useAuth()

  const [conversation, setConversation] = useState(() => {
    const stored = readStoredConversation()
    return {
      conversationId: stored?.conversationId ?? null,
      messages: stored?.messages ?? [],
      selectedTask: stored?.selectedTask ?? null,
    }
  })

  const [input, setInput] = useState('')
  const [pendingAttachments, setPendingAttachments] = useState([])

  const setConversationId = (value) =>
    setConversation((prev) => ({ ...prev, conversationId: value }))

  // Supports both direct values and functional updates so call sites that
  // do `setMessages(prev => [...prev, msg])` keep working unchanged.
  const setMessages = (value) =>
    setConversation((prev) => ({
      ...prev,
      messages: typeof value === 'function' ? value(prev.messages) : value,
    }))

  const setSelectedTask = (value) =>
    setConversation((prev) => ({ ...prev, selectedTask: value }))

  const resetConversation = useCallback(() => {
    setConversation({ conversationId: null, messages: [], selectedTask: null })
    setInput('')
    setPendingAttachments([])
  }, [])

  // Mirror the conversation to sessionStorage so it survives a full page
  // refresh, and drop the entry once the thread is emptied.
  useEffect(() => {
    try {
      const hasConversation =
        Boolean(conversation.conversationId) || conversation.messages.length > 0
      if (!hasConversation) {
        window.sessionStorage.removeItem(STORAGE_KEY)
        return
      }
      const payload = {
        conversationId: conversation.conversationId,
        // Strip the one-off `_animate` flag before persisting so restored
        // messages don't replay their entrance animation.
        messages: conversation.messages.map(({ _animate, ...rest }) => rest),
        selectedTask: conversation.selectedTask,
      }
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
    } catch {
      // Storage may be full or unavailable — persistence is best-effort.
    }
  }, [conversation])

  // Drop the previous account's conversation when the signed-in user
  // changes (e.g. logout then a different member signs in on the same
  // tab). The ref starts at the id that was in localStorage at mount, so
  // the initial auth restore doesn't read as a "change" and wipe the
  // restored thread.
  const lastUserIdRef = useRef(readStoredUserId())
  useEffect(() => {
    if (isInitializing) return
    const userId = user?.id ?? null
    if (userId !== lastUserIdRef.current) {
      lastUserIdRef.current = userId
      resetConversation()
    }
  }, [user?.id, isInitializing, resetConversation])

  const value = useMemo(
    () => ({
      conversationId: conversation.conversationId,
      setConversationId,
      messages: conversation.messages,
      setMessages,
      selectedTask: conversation.selectedTask,
      setSelectedTask,
      input,
      setInput,
      pendingAttachments,
      setPendingAttachments,
      resetConversation,
    }),
    [conversation, input, pendingAttachments, resetConversation]
  )

  return (
    <AssistantChatContext.Provider value={value}>
      {children}
    </AssistantChatContext.Provider>
  )
}

export const useAssistantChat = () => {
  const context = useContext(AssistantChatContext)
  if (!context) {
    throw new Error('useAssistantChat must be used within an AssistantChatProvider')
  }
  return context
}

export default AssistantChatContext
