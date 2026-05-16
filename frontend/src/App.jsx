import React, { useState } from 'react'
import ChatInterface from './components/ChatInterface'
import FeedbackModal from './components/FeedbackModal'
import './App.css'

function App() {
  const [feedbackOpen, setFeedbackOpen] = useState(false)

  const openFeedback = () => {
    setFeedbackOpen(true)
  }

  const closeFeedback = () => {
    setFeedbackOpen(false)
  }

  return (
    <div className="app">
      <div className="app-header">
        <div className="app-header-text">
          <p className="app-header-eyebrow">BCFSA clause helper</p>
          <h1>Realtor Clause Assistant</h1>
          <p className="app-header-subtitle">
            Describe your scenario and get the right BCFSA clause with copy-paste wording
          </p>
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

      <FeedbackModal isOpen={feedbackOpen} onClose={closeFeedback} />
    </div>
  )
}

export default App
