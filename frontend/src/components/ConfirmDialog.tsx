import { useId, useRef } from 'react'
import { Button } from './Button'
import { Modal } from './Modal'
import styles from './ConfirmDialog.module.css'

interface ConfirmDialogProps {
  message: string
  onConfirm: () => void
  onCancel: () => void
  /** Verb for the confirm button, e.g. "Delete" or "Remove". */
  confirmLabel?: string
  /** Disables the buttons while the confirmed action runs. */
  busy?: boolean
}

/** Destructive confirmation. Focus starts on Cancel so Enter never deletes by accident. */
export function ConfirmDialog({
  message,
  onConfirm,
  onCancel,
  confirmLabel = 'Confirm',
  busy = false,
}: ConfirmDialogProps) {
  const messageId = useId()
  const cancelRef = useRef<HTMLButtonElement>(null)
  return (
    <Modal
      role="alertdialog"
      label={confirmLabel}
      describedBy={messageId}
      onClose={onCancel}
      initialFocus={cancelRef}
      className={styles.dialog}
    >
      <p id={messageId} className={styles.message}>{message}</p>
      <div className={styles.buttons}>
        <Button ref={cancelRef} onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
        <Button variant="danger" onClick={onConfirm} disabled={busy}>
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  )
}
