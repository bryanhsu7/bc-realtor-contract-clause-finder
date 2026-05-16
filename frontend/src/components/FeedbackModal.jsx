import React, { useCallback, useEffect, useRef, useState } from 'react'
import { apiUrl } from '../config/api'
import { captureAppScreenshot } from '../utils/captureAppScreenshot'

function blobToFile(blob, name) {
  return new File([blob], name, { type: blob.type || 'image/png' })
}

export default function FeedbackModal({ isOpen, onClose }) {
  const [feedbackText, setFeedbackText] = useState('')
  const [feedbackSending, setFeedbackSending] = useState(false)
  const [feedbackSent, setFeedbackSent] = useState(false)
  const [capturing, setCapturing] = useState(false)
  const [screenshotFile, setScreenshotFile] = useState(null)
  const [screenshotPreviewUrl, setScreenshotPreviewUrl] = useState(null)
  const overlayRef = useRef(null)

  const clearScreenshot = useCallback(() => {
    setScreenshotFile(null)
    setScreenshotPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
  }, [])

  useEffect(() => {
    if (!isOpen) {
      setFeedbackText('')
      setFeedbackSent(false)
      setFeedbackSending(false)
      setCapturing(false)
      clearScreenshot()
    }
  }, [isOpen, clearScreenshot])

  const attachFile = useCallback(
    (file) => {
      if (!file || !file.type.startsWith('image/')) return
      clearScreenshot()
      const url = URL.createObjectURL(file)
      setScreenshotPreviewUrl(url)
      setScreenshotFile(file)
    },
    [clearScreenshot]
  )

  const handleCaptureScreenshot = async () => {
    if (capturing || feedbackSending) return
    setCapturing(true)
    try {
      const blob = await captureAppScreenshot(overlayRef.current)
      const file = blobToFile(blob, 'screenshot.png')
      attachFile(file)
    } catch (_) {
      // best-effort capture
    } finally {
      setCapturing(false)
    }
  }

  const handlePaste = (e) => {
    const items = e.clipboardData?.items
    if (!items?.length) return
    for (let i = 0; i < items.length; i += 1) {
      const item = items[i]
      if (item.kind === 'file' && item.type.startsWith('image/')) {
        e.preventDefault()
        const f = item.getAsFile()
        if (f) attachFile(f)
        break
      }
    }
  }

  const sendFeedback = async () => {
    const message = feedbackText.trim()
    const hasImage = Boolean(screenshotFile)
    if ((!message && !hasImage) || feedbackSending) return
    setFeedbackSending(true)
    try {
      const body = new FormData()
      body.append('message', message)
      if (screenshotFile) {
        body.append('screenshot', screenshotFile, screenshotFile.name || 'screenshot.png')
      }
      await fetch(apiUrl('/api/feedback/general'), {
        method: 'POST',
        body,
      })
    } catch (_) {
      // best-effort — don't block the tester on a network hiccup
    } finally {
      setFeedbackSending(false)
      setFeedbackSent(true)
      setTimeout(onClose, 1500)
    }
  }

  if (!isOpen) return null

  const canSend =
    (feedbackText.trim().length > 0 || screenshotFile) && !feedbackSending && !capturing

  return (
    <div
      ref={overlayRef}
      className="feedback-overlay"
      onClick={onClose}
      role="presentation"
    >
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
              onPaste={handlePaste}
              placeholder="Type your feedback or feature request..."
              rows={4}
              aria-label="Feedback message"
            />
            <div className="feedback-screenshot-row">
              <button
                type="button"
                className="feedback-attach-screenshot"
                onClick={handleCaptureScreenshot}
                disabled={capturing || feedbackSending}
              >
                {capturing ? 'Capturing…' : 'Attach screenshot'}
              </button>
              {screenshotPreviewUrl ? (
                <div className="feedback-screenshot-preview-wrap">
                  <img
                    src={screenshotPreviewUrl}
                    alt="Screenshot preview"
                    className="feedback-screenshot-thumb"
                  />
                  <button
                    type="button"
                    className="feedback-screenshot-remove"
                    onClick={clearScreenshot}
                    aria-label="Remove screenshot"
                  >
                    Remove
                  </button>
                </div>
              ) : null}
            </div>
            <div className="feedback-modal-actions">
              <button type="button" className="feedback-cancel" onClick={onClose}>
                Cancel
              </button>
              <button
                type="button"
                className="feedback-send"
                onClick={sendFeedback}
                disabled={!canSend}
              >
                {feedbackSending ? 'Sending…' : 'Send'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
