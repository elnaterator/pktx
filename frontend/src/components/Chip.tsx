import type { MouseEvent } from 'react'
import { X } from 'lucide-react'
import { ICON_SIZE } from '../theme'
import styles from './Chip.module.css'

interface ChipProps {
  label: string
  /** Shows a remove button; clicking it keeps focus in the surrounding input. */
  onRemove?: (e: MouseEvent<HTMLButtonElement>) => void
}

/** Removable token inside a multi-value input (tags, status filter). */
export function Chip({ label, onRemove }: ChipProps) {
  return (
    <span className={styles.chip}>
      <span className={styles.label}>{label}</span>
      {onRemove && (
        <button
          type="button"
          className={styles.remove}
          aria-label={`Remove ${label}`}
          onMouseDown={(e) => e.preventDefault()}
          onClick={onRemove}
        >
          <X size={ICON_SIZE.xs} aria-hidden="true" />
        </button>
      )}
    </span>
  )
}
