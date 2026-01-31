import React, { useState } from 'react'
import ChatInterface from './components/ChatInterface'
import './App.css'

const FEEDBACK_EMAIL = import.meta.env.VITE_FEEDBACK_EMAIL || ''

function App() {
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const [feedbackText, setFeedbackText] = useState('')

  const handleSupportClick = () => {
    // No route yet – placeholder for future support link
  }

  const openFeedback = () => {
    setFeedbackText('')
    setFeedbackOpen(true)
  }

  const closeFeedback = () => {
    setFeedbackOpen(false)
    setFeedbackText('')
  }

  const sendFeedback = () => {
    const subject = encodeURIComponent('Realtor Clause Assistant – Feature request / Feedback')
    const body = encodeURIComponent(feedbackText.trim() || '(No message provided)')
    const to = FEEDBACK_EMAIL ? `mailto:${FEEDBACK_EMAIL}` : 'mailto:'
    const url = `${to}?subject=${subject}&body=${body}`
    window.open(url, '_blank', 'noopener,noreferrer')
    closeFeedback()
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
          <button
            type="button"
            className="header-button support-button"
            onClick={handleSupportClick}
          >
            Support
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
            <p className="feedback-description">
              Share ideas, report issues, or suggest improvements. Your message will open in your email client.
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
              <button type="button" className="feedback-cancel" onClick={closeFeedback}>
                Cancel
              </button>
              <button type="button" className="feedback-send" onClick={sendFeedback}>
                Send feedback
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
