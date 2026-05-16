import React, { useCallback, useRef, useState } from 'react'
import { plainTextFromReactNode } from '../utils/plainTextFromReactNode'

export function CopyableMarkdownPre({ children, ...props }) {
  const preRef = useRef(null)
  const [showToast, setShowToast] = useState(false)

  const bodyText = plainTextFromReactNode(children).replace(/\u00a0/g, ' ')
  const hasCopyableText = bodyText.trim().length > 0

  const handleCopy = useCallback(async () => {
    const root = preRef.current
    if (!root) return
    const codeEl = root.querySelector('code')
    const text = (codeEl ?? root).innerText ?? ''
    const trimmed = text.replace(/\u00a0/g, ' ').trimEnd()
    if (!trimmed) return
    try {
      await navigator.clipboard.writeText(trimmed)
      setShowToast(true)
      window.setTimeout(() => setShowToast(false), 2200)
    } catch {
      // clipboard API unavailable — copy silently skipped
    }
  }, [])

  return (
    <div
      className={`clause-block-wrap${hasCopyableText ? '' : ' clause-block-wrap--empty'}`}
    >
      <button
        type="button"
        className="clause-copy-btn"
        onClick={handleCopy}
        disabled={!hasCopyableText}
        aria-label="Copy clause to clipboard"
        title={
          hasCopyableText ? 'Copy clause text' : 'No clause text in this block'
        }
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
      </button>
      {showToast && (
        <span className="copy-toast" role="status" aria-live="polite">
          Copied
        </span>
      )}
      <pre ref={preRef} {...props}>
        {hasCopyableText ? (
          children
        ) : (
          <span className="clause-block-placeholder">
            No clause text was included in this block (the model left an empty
            code fence). Check other bullets in this reply, expand Sources, or ask
            again for the full wording.
          </span>
        )}
      </pre>
    </div>
  )
}
