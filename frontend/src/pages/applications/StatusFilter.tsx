import { useCallback, useRef, useState, KeyboardEvent } from 'react'
import { X } from 'lucide-react'
import { ICON_SIZE } from '../../theme'
import styles from './StatusFilter.module.css'

export interface StatusFilterProps {
  value: string[]
  onChange: (v: string[]) => void
  options: string[]
  placeholder?: string
}

export function StatusFilter({ value, onChange, options, placeholder = 'Filter by status...' }: StatusFilterProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const toggleStatus = useCallback(
    (status: string) => {
      onChange(
        value.includes(status)
          ? value.filter((s) => s !== status)
          : [...value, status]
      )
    },
    [value, onChange]
  )

  const removeStatus = useCallback(
    (status: string) => {
      onChange(value.filter((s) => s !== status))
    },
    [value, onChange]
  )

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Backspace' && value.length > 0 && document.activeElement === containerRef.current) {
      onChange(value.slice(0, -1))
    } else if (e.key === 'Escape') {
      setOpen(false)
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      setOpen((o) => !o)
    }
  }

  const handleBlur = () => setOpen(false)

  const handleDropdownMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
  }

  return (
    <div className={styles.container}>
      <div
        ref={containerRef}
        className={styles.inputRow}
        tabIndex={0}
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label="Filter by status"
        onClick={() => setOpen((o) => !o)}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
      >
        {value.map((status) => (
          <span key={status} className={styles.chip}>
            <span className={styles.chipLabel}>{status}</span>
            <button
              type="button"
              className={styles.chipRemove}
              aria-label={`Remove ${status}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={(e) => {
                e.stopPropagation()
                removeStatus(status)
              }}
            >
              <X size={ICON_SIZE.xs} />
            </button>
          </span>
        ))}
        {value.length === 0 && <span className={styles.placeholder}>{placeholder}</span>}
      </div>

      {open && (
        <ul role="listbox" className={styles.dropdown} onMouseDown={handleDropdownMouseDown}>
          {options.map((status) => (
            <li
              key={status}
              role="option"
              aria-selected={value.includes(status)}
              className={
                value.includes(status)
                  ? `${styles.dropdownItem} ${styles.dropdownItemActive}`
                  : styles.dropdownItem
              }
              onClick={() => toggleStatus(status)}
            >
              {status}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
