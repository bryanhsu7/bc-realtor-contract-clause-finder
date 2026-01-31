import React, { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { HEADLINE_SECTIONS } from '../data/headlineSections'
import './ChatInterface.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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
            👍
          </button>
          <button
            type="button"
            className="feedback-btn feedback-down"
            onClick={() => onFeedback(messageIndex, conversationId, turnIndex, false)}
            aria-label="No, not helpful"
          >
            👎
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
  const [expandedSource, setExpandedSource] = useState(null)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const handlePillClick = (section) => {
    setInput(`I need clauses for ${section}`)
    inputRef.current?.focus()
  }

  const handleFeedback = (messageIndex, convId, turnIndex, helpful) => {
    setMessages((prev) =>
      prev.map((m, i) =>
        i === messageIndex ? { ...m, feedback: helpful ? 'up' : 'down' } : m
      )
    )
    fetch(`${API_URL}/api/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: convId,
        turn_index: turnIndex,
        helpful,
      }),
    }).catch((err) => console.error('Feedback request failed:', err))
  }

  const startNewConversation = () => {
    if (isLoading) return
    setConversationId(null)
    setMessages(INITIAL_MESSAGES)
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')

    setMessages((prev) => [...prev, { role: 'user', content: userMessage, sources: [] }])
    setIsLoading(true)

    try {
      const response = await fetch(`${API_URL}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: userMessage,
          ...(conversationId && { conversation_id: conversationId }),
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body.getReader()
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
      console.error('Error:', error)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, I encountered an error. Please try again or contact support.',
          sources: [],
          isStreaming: false,
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="chat-interface">
      <div className="chat-header">
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
      <div className="messages-container">
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            <div className="message-content">
              {message.role === 'assistant' ? (
                message.isStreaming ? (
                  <div className="message-plain" style={{ whiteSpace: 'pre-wrap' }}>
                    {message.content}
                  </div>
                ) : index === 0 ? (
                  <>
                    <ReactMarkdown
                      components={{
                        h2: ({ node, ...props }) => (
                          <h2 style={{ marginTop: '20px', marginBottom: '10px' }} {...props} />
                        ),
                        strong: ({ node, ...props }) => (
                          <strong style={{ fontWeight: 600 }} {...props} />
                        ),
                        p: ({ node, ...props }) => (
                          <p style={{ marginBottom: '12px' }} {...props} />
                        ),
                      }}
                    >
                      {message.content}
                    </ReactMarkdown>
                    <p className="headline-pills-label">Or choose a topic to narrow your search:</p>
                    <div className="headline-pills">
                      {HEADLINE_SECTIONS.map((section) => (
                        <button
                          key={section}
                          type="button"
                          className="headline-pill"
                          onClick={() => handlePillClick(section)}
                          disabled={isLoading}
                        >
                          {section}
                        </button>
                      ))}
                    </div>
                  </>
                ) : (
                  <ReactMarkdown
                    components={{
                      h2: ({ node, ...props }) => (
                        <h2 style={{ marginTop: '20px', marginBottom: '10px' }} {...props} />
                      ),
                      strong: ({ node, ...props }) => (
                        <strong style={{ fontWeight: 600 }} {...props} />
                      ),
                      p: ({ node, ...props }) => (
                        <p style={{ marginBottom: '12px' }} {...props} />
                      ),
                    }}
                  >
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
        ))}
        {isLoading && (
          <div className="message assistant">
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      
      <form onSubmit={handleSubmit} className="input-form">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your question here..."
          disabled={isLoading}
          className="message-input"
        />
        <button 
          type="submit" 
          disabled={isLoading || !input.trim()}
          className="send-button"
        >
          Send
        </button>
      </form>
    </div>
  )
}

export default ChatInterface
