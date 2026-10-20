import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import { cx } from '../utils/cx'
import styles from './Modal.module.css'

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

interface ModalProps {
  onClose: () => void
  children: ReactNode
  /** Accessible name: the id of a visible heading, or a plain label. */
  labelledBy?: string
  label?: string
  describedBy?: string
  /** `alertdialog` for confirmations that interrupt the user. */
  role?: 'dialog' | 'alertdialog'
  /** Sizing/layout of the dialog box. */
  className?: string
  /** Element to focus on open; defaults to an autoFocus child or the first control. */
  initialFocus?: RefObject<HTMLElement | null>
  /** `bottom` docks the dialog to the bottom edge as a sheet (phone menus). */
  placement?: 'center' | 'bottom'
}

/**
 * Accessible modal: rendered in a portal over a dimmed overlay, closes on
 * Escape or an overlay click, keeps Tab inside, and returns focus to the
 * element that opened it.
 */
export function Modal({
  onClose,
  children,
  labelledBy,
  label,
  describedBy,
  role = 'dialog',
  className,
  initialFocus,
  placement = 'center',
}: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  // Captured during render, before any autoFocus child steals focus.
  const [opener] = useState(() => document.activeElement as HTMLElement | null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (initialFocus?.current) {
      initialFocus.current.focus()
    } else if (!dialog.contains(document.activeElement)) {
      ;(dialog.querySelector<HTMLElement>(FOCUSABLE) ?? dialog).focus()
    }
    return () => opener?.focus?.()
  }, [initialFocus, opener])

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape' && !e.defaultPrevented) {
      e.stopPropagation()
      onClose()
      return
    }
    if (e.key !== 'Tab' || !dialogRef.current) return
    const items = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE))
    if (items.length === 0) {
      e.preventDefault()
      return
    }
    const first = items[0]
    const last = items[items.length - 1]
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }

  return createPortal(
    <div
      className={cx(styles.overlay, placement === 'bottom' && styles.overlayBottom)}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        ref={dialogRef}
        role={role}
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-label={labelledBy ? undefined : label}
        aria-describedby={describedBy}
        tabIndex={-1}
        className={cx(styles.dialog, className)}
        onKeyDown={handleKeyDown}
      >
        {children}
      </div>
    </div>,
    document.body,
  )
}
