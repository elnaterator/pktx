import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import type { ClipboardEvent, KeyboardEvent } from 'react'
import styles from './SkillAdder.module.css'

/** Separators accepted when typing or pasting several keywords at once. */
const SPLIT = /[,;\n\r\t]+/

interface SkillAdderProps {
  /** Called with one or more trimmed, non-empty keywords. */
  onCommit: (names: string[]) => void
  /** Escape pressed — the caller decides whether to unmount the adder. */
  onClose: () => void
  label: string
  /** A write is in flight. The field stays usable so typing can carry on. */
  busy?: boolean
  placeholder?: string
  autoFocus?: boolean
}

/**
 * Chip-sized inline input for adding keywords to one skill. Commits on Enter,
 * comma, or blur; a pasted separated list commits every value at once. Stays
 * mounted after committing so several keywords can be typed in a row.
 *
 * Forwards a ref to the input so callers can hand it the focus.
 */
export const SkillAdder = forwardRef<HTMLInputElement, SkillAdderProps>(function SkillAdder(
  { onCommit, onClose, label, busy = false, placeholder = 'add keyword…', autoFocus = true },
  ref
) {
  const [text, setText] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useImperativeHandle(ref, () => inputRef.current as HTMLInputElement)

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus()
  }, [autoFocus])

  const commit = (raws: string[]) => {
    const names = raws.map((n) => n.trim()).filter(Boolean)
    setText('')
    if (names.length > 0) onCommit(names)
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      commit([text])
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setText('')
      onClose()
    }
  }

  const handlePaste = (e: ClipboardEvent<HTMLInputElement>) => {
    const pasted = e.clipboardData.getData('text')
    if (!SPLIT.test(pasted)) return
    e.preventDefault()
    commit((text + pasted).split(SPLIT))
  }

  const handleBlur = () => {
    if (text.trim()) commit([text])
  }

  return (
    <input
      ref={inputRef}
      type="text"
      className={styles.input}
      // Grow with the text so the adder reads as another chip in the row
      style={{ width: `${Math.max(text.length + 2, 14)}ch` }}
      value={text}
      onChange={(e) => setText(e.target.value)}
      onKeyDown={handleKeyDown}
      onPaste={handlePaste}
      onBlur={handleBlur}
      aria-busy={busy}
      placeholder={placeholder}
      aria-label={label}
      autoComplete="off"
    />
  )
})
