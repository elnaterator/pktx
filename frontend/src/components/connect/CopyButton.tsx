import { useEffect, useRef, useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { useToast } from '../toast'
import styles from './Connect.module.css'

interface CopyButtonProps {
  text: string
  /** Accessible name, e.g. "Copy MCP URL". */
  label: string
  /** `icon` renders a square icon-only button; `text` adds a visible "Copy" label. */
  variant?: 'icon' | 'text'
  className?: string
}

const DONE_MS = 2000

export function CopyButton({ text, label, variant = 'text', className }: CopyButtonProps) {
  const toast = useToast()
  const [copied, setCopied] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => () => clearTimeout(timer.current), [])

  const handleClick = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      clearTimeout(timer.current)
      timer.current = setTimeout(() => setCopied(false), DONE_MS)
    } catch {
      toast.error('Copy failed — select the text and copy it manually.')
    }
  }

  const Icon = copied ? Check : Copy
  return (
    <button
      type="button"
      className={`${styles.copyBtn} ${variant === 'icon' ? styles.copyBtnIcon : ''} ${copied ? styles.copyBtnDone : ''} ${className ?? ''}`}
      aria-label={label}
      title={label}
      onClick={handleClick}
    >
      <Icon size={variant === 'icon' ? 16 : 14} aria-hidden="true" />
      {variant === 'text' && <span>{copied ? 'Copied' : 'Copy'}</span>}
      <span className={styles.srOnly} aria-live="polite">
        {copied ? 'Copied to clipboard' : ''}
      </span>
    </button>
  )
}
