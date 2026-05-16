import React, { useState } from 'react'
import ChatInterface from './components/ChatInterface'
import { apiUrl } from './config/api'
import './App.css'

function App() {
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const [feedbackText, setFeedbackText] = useState('')
  const [feedbackSending, setFeedbackSending] = useState(false)
  const [feedbackSent, setFeedbackSent] = useState(false)

  const openFeedback = () => {
    setFeedbackText('')
    setFeedbackSent(false)
    setFeedbackOpen(true)
  }

  const closeFeedback = () => {
    setFeedbackOpen(false)
    setFeedbackText('')
    setFeedbackSent(false)
  }

  const sendFeedback = async () => {
    const message = feedbackText.trim()
    if (!message || feedbackSending) return
    setFeedbackSending(true)
    try {
      await fetch(apiUrl('/api/feedback/general'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      })
    } catch (_) {
      // best-effort — don't block the tester on a network hiccup
    } finally {
      setFeedbackSending(false)
      setFeedbackSent(true)
      setTimeout(closeFeedback, 1500)
    }
  }

  return (
    <div className="app">
      <div className="app-header">
        <div className="app-header-text">
          <h1>Realtor Clause Assistant</h1>
          <p>Describe your scenario and get the right BCFSA clause with copy-paste wording</p>
        </div>
        <div className="app-header-actions">
          <button
            type="button"
            className="header-button feedback-button"
            onClick={openFeedback}
          >
            Feedback
          </button>
        </div>
      </div>
      <ChatInterface />

      {feedbackOpen && (
        <div className="feedback-overlay" onClick={closeFeedback} role="presentation">
          <div
            className="feedback-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-labelledby="feedback-title"
            aria-modal="true"
          >
            <h2 id="feedback-title">Feature request or feedback</h2>
            {feedbackSent ? (
              <p className="feedback-sent-message">Thanks — your feedback has been sent!</p>
            ) : (
              <>
                <p className="feedback-description">
                  Share ideas, report issues, or suggest improvements.
                </p>
                <textarea
                  className="feedback-textarea"
                  value={feedbackText}
                  onChange={(e) => setFeedbackText(e.target.value)}
                  placeholder="Type your feedback or feature request..."
                  rows={4}
                  aria-label="Feedback message"
                />
                <div className="feedback-modal-actions">
                  <button
                    type="button"
                    className="feedback-cancel"
                    onClick={closeFeedback}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="feedback-send"
                    onClick={sendFeedback}
                    disabled={!feedbackText.trim() || feedbackSending}
                  >
                    {feedbackSending ? 'Sending…' : 'Send'}
                  </button>
                </div>
              </>
            )}

          </div>
        </div>
      )}
    </div>
  )
}

export default App
