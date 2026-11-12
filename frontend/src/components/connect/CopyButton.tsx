import { Check, Copy } from 'lucide-react'
import { ICON_SIZE } from '../../theme'
import { useCopyToClipboard } from '../../hooks/useCopyToClipboard'
import styles from './Connect.module.css'

interface CopyButtonProps {
  text: string
  /** Accessible name, e.g. "Copy MCP URL". */
  label: string
  /** `icon` renders a square icon-only button; `text` adds a visible "Copy" label. */
  variant?: 'icon' | 'text'
  className?: string
}

export function CopyButton({ text, label, variant = 'text', className }: CopyButtonProps) {
  const { copied, copy } = useCopyToClipboard()

  const Icon = copied ? Check : Copy
  return (
    <button
      type="button"
      className={`${styles.copyBtn} ${variant === 'icon' ? styles.copyBtnIcon : ''} ${copied ? styles.copyBtnDone : ''} ${className ?? ''}`}
      aria-label={label}
      title={label}
      onClick={() => copy(text)}
    >
      <Icon size={variant === 'icon' ? ICON_SIZE.lg : ICON_SIZE.md} aria-hidden="true" />
      {variant === 'text' && <span>{copied ? 'Copied' : 'Copy'}</span>}
      <span className={styles.srOnly} aria-live="polite">
        {copied ? 'Copied to clipboard' : ''}
      </span>
    </button>
  )
}
