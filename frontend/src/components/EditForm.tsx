import { forwardRef, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import type { FieldError as HookFieldError } from 'react-hook-form'
import { cx } from '../utils/cx'
import { Button } from './Button'
import { FieldError } from './FieldError'
import styles from './EditForm.module.css'

interface EditFormProps {
  children: ReactNode
  /** Shown above the fields, e.g. "Editing Senior Engineer". */
  heading?: string
  onSubmit: () => void
  onCancel: () => void
  /** Disables save while a save is in flight. */
  saving?: boolean
  /** Accessible names for the footer buttons when "Save"/"Cancel" alone is ambiguous. */
  saveLabel?: string
  cancelLabel?: string
  className?: string
}

/**
 * Edit-mode frame: a recessed panel with an accent edge, an optional heading,
 * and Save/Cancel in a footer that stays in reach while scrolling.
 * ⌘/Ctrl+Enter saves; Escape cancels unless something inside handled it first
 * (a calendar popover calls `preventDefault`). Put fields in a
 * `<div className={styles.fields}>` grid as `FormField`s, and style controls
 * with the module's `input` / `inputTitle` / `select` / `textarea` classes.
 */
export const EditForm = forwardRef<HTMLFormElement, EditFormProps>(function EditForm(
  { children, heading, onSubmit, onCancel, saving = false, saveLabel, cancelLabel, className },
  ref,
) {
  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!saving) onSubmit()
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLFormElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      if (!saving) onSubmit()
    } else if (e.key === 'Escape' && !e.defaultPrevented) {
      e.preventDefault()
      onCancel()
    }
  }

  return (
    <form
      ref={ref}
      className={cx(styles.form, className)}
      onSubmit={handleSubmit}
      onKeyDown={handleKeyDown}
      noValidate
    >
      {heading && <p className={styles.heading}>{heading}</p>}
      {children}
      <div className={styles.footer}>
        <span className={styles.shortcut}>⌘/Ctrl+Enter to save · Esc to cancel</span>
        <Button size="sm" onClick={onCancel} aria-label={cancelLabel}>
          Cancel
        </Button>
        <Button size="sm" variant="primary" type="submit" disabled={saving} aria-label={saveLabel}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
      </div>
    </form>
  )
})

interface FormFieldProps {
  label: ReactNode
  /** Id of the control the label names; omit for composite controls (tags, lists). */
  htmlFor?: string
  required?: boolean
  error?: HookFieldError
  /** Share a row with the next half field (one column on phones). */
  half?: boolean
  /** Small control at the label's right, e.g. a "Present" checkbox. */
  aside?: ReactNode
  className?: string
  children: ReactNode
}

/** One labelled cell of the `fields` grid: label (+ aside), control, error. */
export function FormField({
  label,
  htmlFor,
  required = false,
  error,
  half = false,
  aside,
  className,
  children,
}: FormFieldProps) {
  const labelEl = htmlFor ? (
    <label htmlFor={htmlFor} className={styles.label}>
      {label}
      {required && <span className={styles.required}> *</span>}
    </label>
  ) : (
    <span className={styles.label}>
      {label}
      {required && <span className={styles.required}> *</span>}
    </span>
  )
  return (
    <div className={cx(styles.field, half && styles.half, className)}>
      {aside ? (
        <div className={styles.labelRow}>
          {labelEl}
          {aside}
        </div>
      ) : (
        labelEl
      )}
      {children}
      <FieldError error={error} />
    </div>
  )
}
