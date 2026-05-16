import html2canvas from 'html2canvas'

/**
 * Renders `.app` to a PNG blob, excluding the feedback overlay from both
 * masking and capture. Temporarily hides the overlay so the dim layer is not composited.
 * @param {HTMLElement | null} overlayEl - The `.feedback-overlay` node (optional)
 * @returns {Promise<Blob>}
 */
export async function captureAppScreenshot(overlayEl) {
  const root = document.querySelector('.app')
  if (!root) {
    throw new Error('App root not found')
  }

  const prevVisibility = overlayEl?.style?.visibility
  if (overlayEl) {
    overlayEl.style.visibility = 'hidden'
  }
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))

  try {
    const canvas = await html2canvas(root, {
      ignoreElements: (el) => !!el.closest?.('.feedback-overlay'),
      useCORS: true,
      scale: Math.min(2, window.devicePixelRatio || 1),
    })
    const blob = await new Promise((resolve, reject) => {
      canvas.toBlob(
        (b) => (b ? resolve(b) : reject(new Error('Could not encode screenshot'))),
        'image/png',
        0.92
      )
    })
    return blob
  } finally {
    if (overlayEl) {
      overlayEl.style.visibility = prevVisibility || ''
    }
  }
}
