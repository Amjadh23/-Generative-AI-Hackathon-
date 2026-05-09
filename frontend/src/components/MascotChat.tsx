import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { useSpeechRecognition } from '../hooks/useSpeechRecognition'
import { speak } from '../hooks/useTurnByTurn'
import { askAssistant, type AssistantResponse } from '../lib/api'
import { Mascot } from './Mascot'

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  intent?: string
  suggestions?: string[]
}

type MascotChatProps = {
  salespersonId: string
  currentCustomerId: string | null
  voiceEnabled: boolean
}

const INITIAL_SUGGESTIONS = [
  "What's my next stop?",
  'How far to the next customer?',
  'Why this customer?',
  'What should I focus on?',
]

let messageCounter = 0
function createMessageId() {
  messageCounter += 1
  return `msg-${Date.now()}-${messageCounter}`
}

export function MascotChat({ currentCustomerId, salespersonId, voiceEnabled }: MascotChatProps) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      content: "Hi, I'm RIQ. Ask me about your stops, distances, or what to focus on.",
      id: createMessageId(),
      role: 'assistant',
      suggestions: INITIAL_SUGGESTIONS,
    },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [readbackEnabled, setReadbackEnabled] = useState(voiceEnabled)
  const [error, setError] = useState<string | null>(null)
  const listEndRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    setReadbackEnabled(voiceEnabled)
  }, [voiceEnabled])

  useEffect(() => {
    if (open) {
      listEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [open, messages])

  const handleResult = useCallback((transcript: string) => {
    setInput(transcript)
  }, [])

  const {
    error: speechError,
    listening,
    start: startListening,
    stop: stopListening,
    supported: speechSupported,
  } = useSpeechRecognition({ onResult: handleResult })

  const latestSuggestions = useMemo(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const message = messages[index]
      if (message.role === 'assistant' && message.suggestions && message.suggestions.length > 0) {
        return message.suggestions
      }
    }
    return INITIAL_SUGGESTIONS
  }, [messages])

  const sendMessage = useCallback(
    async (rawQuestion: string) => {
      const question = rawQuestion.trim()
      if (!question || sending) return

      stopListening()
      setError(null)
      setInput('')
      const userMessage: ChatMessage = {
        content: question,
        id: createMessageId(),
        role: 'user',
      }
      setMessages((current) => [...current, userMessage])
      setSending(true)

      try {
        const response: AssistantResponse = await askAssistant({
          currentCustomerId,
          question,
          salespersonId,
        })
        const assistantMessage: ChatMessage = {
          content: response.answer,
          id: createMessageId(),
          intent: response.intent,
          role: 'assistant',
          suggestions: response.suggestions,
        }
        setMessages((current) => [...current, assistantMessage])
        if (readbackEnabled) {
          speak(response.answer)
        }
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : 'Could not reach the assistant.'
        setError(message)
        setMessages((current) => [
          ...current,
          {
            content: "I couldn't reach the server. Try again in a moment.",
            id: createMessageId(),
            role: 'assistant',
          },
        ])
      } finally {
        setSending(false)
      }
    },
    [currentCustomerId, readbackEnabled, salespersonId, sending, stopListening],
  )

  const onSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    void sendMessage(input)
  }

  const onMicClick = () => {
    if (!speechSupported) return
    if (listening) {
      stopListening()
      if (input.trim()) void sendMessage(input)
    } else {
      startListening()
    }
  }

  const onSuggestionClick = (suggestion: string) => {
    void sendMessage(suggestion)
  }

  const onOpen = () => {
    setOpen(true)
    setTimeout(() => inputRef.current?.focus(), 80)
  }

  const onClose = () => {
    stopListening()
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel()
    }
    setOpen(false)
  }

  return (
    <>
      {!open ? (
        <button
          aria-label="Ask RIQ"
          className="mascot-fab"
          onClick={onOpen}
          type="button"
        >
          <Mascot mood="happy" size={48} />
          <span className="mascot-fab-label">Ask RIQ</span>
        </button>
      ) : null}

      {open ? (
        <>
          <div className="mascot-chat-backdrop" onClick={onClose} role="presentation" />
          <aside aria-label="Chat with RIQ" className="mascot-chat-sheet" role="dialog">
            <header className="mascot-chat-header">
              <div className="mascot-chat-title">
                <Mascot mood="happy" size={36} />
                <div>
                  <strong>RIQ</strong>
                  <small>your route copilot</small>
                </div>
              </div>
              <div className="mascot-chat-actions">
                <button
                  aria-pressed={readbackEnabled}
                  className={readbackEnabled ? 'icon-toggle active' : 'icon-toggle'}
                  onClick={() => setReadbackEnabled((current) => !current)}
                  title={readbackEnabled ? 'Voice replies on' : 'Voice replies off'}
                  type="button"
                >
                  {readbackEnabled ? '🔊' : '🔇'}
                </button>
                <button aria-label="Close chat" className="icon-close" onClick={onClose} type="button">
                  ×
                </button>
              </div>
            </header>

            <div className="mascot-chat-messages">
              {messages.map((message) => (
                <div className={`chat-bubble ${message.role}`} key={message.id}>
                  <p>{message.content}</p>
                </div>
              ))}
              {sending ? (
                <div className="chat-bubble assistant pending">
                  <span className="typing-dots">
                    <span />
                    <span />
                    <span />
                  </span>
                </div>
              ) : null}
              <div ref={listEndRef} />
            </div>

            {latestSuggestions.length > 0 ? (
              <div className="chat-suggestions">
                {latestSuggestions.map((suggestion) => (
                  <button
                    className="suggestion-chip"
                    disabled={sending}
                    key={suggestion}
                    onClick={() => onSuggestionClick(suggestion)}
                    type="button"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            ) : null}

            {error || speechError ? (
              <p className="chat-error">{error ?? speechError}</p>
            ) : null}

            <form className="chat-input-row" onSubmit={onSubmit}>
              <input
                aria-label="Ask RIQ a question"
                disabled={sending}
                onChange={(event) => setInput(event.target.value)}
                placeholder={listening ? 'Listening...' : 'Ask anything about your route'}
                ref={inputRef}
                type="text"
                value={input}
              />
              <button
                aria-label={listening ? 'Stop voice input' : 'Use voice'}
                className={listening ? 'mic-button listening' : 'mic-button'}
                disabled={!speechSupported || sending}
                onClick={onMicClick}
                title={
                  speechSupported
                    ? listening
                      ? 'Tap to stop and send'
                      : 'Tap to speak'
                    : 'Voice input not supported in this browser'
                }
                type="button"
              >
                {listening ? '■' : '🎤'}
              </button>
              <button
                aria-label="Send"
                className="send-button"
                disabled={sending || input.trim().length === 0}
                type="submit"
              >
                ➤
              </button>
            </form>
          </aside>
        </>
      ) : null}
    </>
  )
}
