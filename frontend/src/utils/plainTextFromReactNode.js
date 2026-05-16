import { isValidElement } from 'react'

/** Flatten React nodes to plain text (for markdown code-block body checks). */
export function plainTextFromReactNode(node) {
  if (node == null || node === false || node === true) return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(plainTextFromReactNode).join('')
  if (isValidElement(node)) return plainTextFromReactNode(node.props.children)
  return ''
}
