import React, { useState, useRef, useLayoutEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { HEADLINE_SECTIONS } from '../data/headlineSections'
import { EXAMPLE_CONVERSATIONAL_PROMPTS } from '../data/examplePrompts'
import { apiUrl, describeChatRequestFailure } from '../config/api'
import { CopyableMarkdownPre } from './CopyableMarkdownPre'
import { ThumbDownIcon, ThumbUpIcon } from './icons/ThumbsFeedbackIcons'
import './ChatInterface.css'

const MARKDOWN_COMPONENTS = {
  h2: ({ node, ...props }) => (
    <h2 style={{ marginTop: '20px', marginBottom: '10px' }} {...props} />
  ),
  strong: ({ node, ...props }) => (
    <strong style={{ fontWeight: 600 }} {...props} />
  ),
  p: ({ node, ...props }) => <p style={{ marginBottom: '12px' }} {...props} />,
  pre: CopyableMarkdownPre,
  table: ({ children, ...props }) => (
    <div className="markdown-table-wrap">
      <table {...props}>{children}</table>
    </div>
  ),
}

const INITIAL_MESSAGES = [
  {
    role: 'assistant',
    content: "Hello! I'm your Realtor Clause Assistant. Describe your scenario in your own words and I'll recommend the right BCFSA clause and give you the exact wording to copy into the contract.",
    sources: [],
    isStreaming: false,
  }
]

function SourceList({ sources, messageIndex, expandedSource, onToggleSnippet }) {
  return (
    <div className="message-sources">
      <strong>Sources:</strong>
      <ul>
        {sources.map((source, idx) => {
          const key = `${messageIndex}-${idx}`
          const expanded = expandedSource === key
          const hasSnippet = source.snippet && source.snippet.trim().length > 0
          return (
            <li key={idx} className="source-item">
              <div className="source-header">
                <span>
                  {source.source}
                  {source.relevance_score != null && (
                    <span className="relevance-score">
                      {' '}({Math.round(source.relevance_score * 100)}% relevant)
                    </span>
                  )}
                </span>
                {hasSnippet && (
                  <button
                    type="button"
                    className="source-view-snippet"
                    onClick={() => onToggleSnippet(expanded ? null : key)}
                    aria-expanded={expanded}
                  >
                    {expanded ? 'Hide snippet' : 'View snippet'}
                  </button>
                )}
              </div>
              {expanded && hasSnippet && (
                <div className="source-snippet">{source.snippet}</div>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function FeedbackRow({ message, messageIndex, conversationId, onFeedback }) {
  const sent = message.feedback === 'up' || message.feedback === 'down'
  const turnIndex = Math.floor((messageIndex - 1) / 2)
  if (!conversationId || turnIndex < 0) return null
  return (
    <div className="message-feedback">
      {sent ? (
        <span className="feedback-thanks">Thanks for your feedback!</span>
      ) : (
        <>
          <span className="feedback-prompt">Was this helpful?</span>
          <button
            type="button"
            className="feedback-btn feedback-up"
            onClick={() => onFeedback(messageIndex, conversationId, turnIndex, true)}
            aria-label="Yes, helpful"
          >
            <ThumbUpIcon className="feedback-btn-icon" />
          </button>
          <button
            type="button"
            className="feedback-btn feedback-down"
            onClick={() => onFeedback(messageIndex, conversationId, turnIndex, false)}
            aria-label="No, not helpful"
          >
            <ThumbDownIcon className="feedback-btn-icon" />
          </button>
        </>
      )}
    </div>
  )
}

function ChatInterface() {
  const [messages, setMessages] = useState(INITIAL_MESSAGES)
  const [conversationId, setConversationId] = useState(null)
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isWarmingUp, setIsWarmingUp] = useState(false)
  const [expandedSource, setExpandedSource] = useState(null)
  const messagesContainerRef = useRef(null)
  const stickToBottomRef = useRef(true)
  const inputRef = useRef(null)
  const warmingUpTimerRef = useRef(null)

  const PIN_THRESHOLD_PX = 80

  const updateStickToBottomFromScroll = () => {
    const el = messagesContainerRef.current
    if (!el) return
    const slack = PIN_THRESHOLD_PX
    stickToBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight <= slack
  }

  const handlePillClick = (section) => {
    setInput(`I need clauses for ${section}`)
    inputRef.current?.focus()
  }

  const handleExamplePromptClick = (text) => {
    setInput(text)
    inputRef.current?.focus()
  }

  const handleFeedback = (messageIndex, convId, turnIndex, helpful) => {
    setMessages((prev) =>
      prev.map((m, i) =>
        i === messageIndex ? { ...m, feedback: helpful ? 'up' : 'down' } : m
      )
    )
    fetch(apiUrl('/api/feedback'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: convId,
        turn_index: turnIndex,
        helpful,
      }),
    }).catch(() => {})
  }

  const startNewConversation = () => {
    if (isLoading) return
    setConversationId(null)
    setMessages(INITIAL_MESSAGES)
  }

  const scrollMessagesPaneToBottom = () => {
    const pane = messagesContainerRef.current
    if (!pane) return
    pane.scrollTop = pane.scrollHeight
  }

  useLayoutEffect(() => {
    if (!stickToBottomRef.current) return
    scrollMessagesPaneToBottom()
  }, [messages])

  /** Grow composer with content; cap height so messages stay reachable on small screens */
  useLayoutEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    const maxPx = 200
    el.style.height = `${Math.min(el.scrollHeight, maxPx)}px`
  }, [input])

  const sendChatMessage = async () => {
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')

    stickToBottomRef.current = true
    setMessages((prev) => [...prev, { role: 'user', content: userMessage, sources: [] }])
    setIsLoading(true)
    warmingUpTimerRef.current = setTimeout(() => setIsWarmingUp(true), 8000)

    try {
      const response = await fetch(apiUrl('/api/chat/stream'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: userMessage,
          ...(conversationId && { conversation_id: conversationId }),
        }),
      })

      if (!response.ok) {
        const detail = await response.text().catch(() => '')
        const err = new Error(detail.trim() || `HTTP ${response.status}`)
        err.httpStatus = response.status
        throw err
      }

      const reader = response.body.getReader()
      clearTimeout(warmingUpTimerRef.current)
      setIsWarmingUp(false)
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || ''
        for (const chunk of lines) {
          const dataMatch = /^data:\s*(.+)$/m.exec(chunk)
          if (!dataMatch) continue
          try {
            const data = JSON.parse(dataMatch[1])
            if (data.event === 'start') {
              if (data.conversation_id) setConversationId(data.conversation_id)
              setMessages((prev) => {
                const last = prev[prev.length - 1]
                const newMsg = {
                  role: 'assistant',
                  content: data.message ?? '',
                  sources: data.sources ?? [],
                  isStreaming: true,
                }
                if (last?.role === 'assistant') {
                  return prev.map((m, i) =>
                    i === prev.length - 1 ? { ...m, ...newMsg } : m
                  )
                }
                return [...prev, newMsg]
              })
            } else if (data.event === 'token' && data.delta) {
              setMessages((prev) => {
                const next = [...prev]
                const last = next[next.length - 1]
                if (last.role === 'assistant') {
                  next[next.length - 1] = { ...last, content: last.content + data.delta }
                }
                return next
              })
            } else if (data.event === 'done') {
              setMessages((prev) => {
                const last = prev[prev.length - 1]
                if (last?.role === 'assistant')
                  return prev.map((m, i) =>
                    i === prev.length - 1 ? { ...m, isStreaming: false } : m
                  )
                return prev
              })
            } else if (data.event === 'error') {
              const errText = `Error: ${data.message || 'Unknown error'}`
              setMessages((prev) => {
                const last = prev[prev.length - 1]
                if (last?.role === 'assistant') {
                  return prev.map((m, i) =>
                    i === prev.length - 1
                      ? { ...m, content: m.content || errText, isStreaming: false }
                      : m
                  )
                }
                return [
                  ...prev,
                  { role: 'assistant', content: errText, sources: [], isStreaming: false },
                ]
              })
            }
          } catch (_) {
            // ignore parse errors for partial chunks
          }
        }
      }
    } catch (error) {
      const content = describeChatRequestFailure(error, error?.httpStatus)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content,
          sources: [],
          isStreaming: false,
        },
      ])
    } finally {
      clearTimeout(warmingUpTimerRef.current)
      setIsWarmingUp(false)
      setIsLoading(false)
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    void sendChatMessage()
  }

  const handleComposerKeyDown = (e) => {
    if (e.key !== 'Enter') return
    if (e.shiftKey) return
    e.preventDefault()
    void sendChatMessage()
  }

  const isLanding = messages.length === 1 && messages[0]?.role === 'assistant'
  const threadMessages = isLanding ? [] : messages.slice(1)

  const startersRow = (
    <div className="chat-starters-row" role="group" aria-label="Example questions">
      {EXAMPLE_CONVERSATIONAL_PROMPTS.map((prompt) => (
        <button
          key={prompt}
          type="button"
          className="starter-chip"
          onClick={() => handleExamplePromptClick(prompt)}
          disabled={isLoading}
        >
          {prompt}
        </button>
      ))}
    </div>
  )

  const composerForm = (
    <form onSubmit={handleSubmit} className="input-form" aria-label="Send a message">
      <div className="composer-shell">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleComposerKeyDown}
          placeholder="Describe your scenario or ask about a clause…"
          disabled={isLoading}
          className="message-input"
          aria-label="Message"
          rows={1}
          spellCheck
          autoComplete="off"
          enterKeyHint="send"
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="send-button composer-send"
          aria-label="Send message"
          title="Send"
        >
          <span aria-hidden="true">↑</span>
        </button>
      </div>
    </form>
  )

  return (
    <div className="chat-interface">
      <aside className="topic-sidebar" aria-label="Clause topics">
        <p className="topic-sidebar-label">Narrow by topic</p>
        <nav className="topic-sidebar-nav">
          {HEADLINE_SECTIONS.map((section) => (
            <button
              key={section}
              type="button"
              className="topic-sidebar-pill"
              onClick={() => handlePillClick(section)}
              disabled={isLoading}
            >
              {section}
            </button>
          ))}
        </nav>
        <div className="topic-sidebar-footer">
          <button
            type="button"
            className="new-conversation-button"
            onClick={startNewConversation}
            disabled={isLoading}
            title="Start a new conversation"
          >
            New conversation
          </button>
        </div>
      </aside>

      <div className="chat-main">
        {isLanding ? (
          <div className="landing-stage">
            <div className="landing-inner">
              {messages[0] && (
                <div className="chat-landing-intro">
                  <ReactMarkdown components={MARKDOWN_COMPONENTS}>
                    {messages[0].content}
                  </ReactMarkdown>
                </div>
              )}
              {composerForm}
              {startersRow}
            </div>
          </div>
        ) : (
          <>
            <div
              className="messages-container"
              ref={messagesContainerRef}
              onScroll={updateStickToBottomFromScroll}
            >
              <div className="messages-thread">
              {threadMessages.map((message, idx) => {
                const index = idx + 1
                return (
                <div key={index} className={`message ${message.role}`}>
                  <div className="message-content">
                    {message.role === 'assistant' ? (
                      message.isStreaming ? (
                        <div className="message-plain" style={{ whiteSpace: 'pre-wrap' }}>
                          {message.content}
                        </div>
                      ) : (
                        <ReactMarkdown components={MARKDOWN_COMPONENTS}>
                          {message.content}
                        </ReactMarkdown>
                      )
                    ) : (
                      message.content
                    )}
                  </div>
                  {message.sources && message.sources.length > 0 && (
                    <SourceList
                      sources={message.sources}
                      messageIndex={index}
                      expandedSource={expandedSource}
                      onToggleSnippet={setExpandedSource}
                    />
                  )}
                  {message.role === 'assistant' && index > 0 && (
                    <FeedbackRow
                      message={message}
                      messageIndex={index}
                      conversationId={conversationId}
                      onFeedback={handleFeedback}
                    />
                  )}
                </div>
              )
              })}
              {isLoading && (
                <div className="message assistant">
                  <div className="message-content">
                    {isWarmingUp ? (
                      <p className="warming-up-message">
                        The server is warming up — this can take up to a minute on first load. Hang tight...
                      </p>
                    ) : (
                      <div className="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                    )}
                  </div>
                </div>
              )}
              </div>
            </div>
            {composerForm}
          </>
        )}
      </div>
    </div>
  )
}

export default ChatInterface
