import { Check, Pencil, Trash2, X } from 'lucide-react'
import { IconButton } from './IconButton'
import styles from './EditActions.module.css'

interface EditActionsProps {
  /** Edit mode shows save + cancel; view mode shows edit (+ delete). */
  editing: boolean
  onEdit?: () => void
  onDelete?: () => void
  onSave?: () => void
  onCancel?: () => void
  /** Disables save while a save is in flight. */
  saving?: boolean
  /** `submit` when the actions sit inside the form they save. */
  saveType?: 'button' | 'submit'
  editLabel?: string
  deleteLabel?: string
  saveLabel?: string
  cancelLabel?: string
}

/** The edit/delete ↔ save/cancel icon pair used by every editable panel. */
export function EditActions({
  editing,
  onEdit,
  onDelete,
  onSave,
  onCancel,
  saving = false,
  saveType = 'button',
  editLabel = 'Edit',
  deleteLabel = 'Delete',
  saveLabel = 'Save',
  cancelLabel = 'Cancel',
}: EditActionsProps) {
  return (
    <div className={styles.actions}>
      {editing ? (
        <>
          <IconButton icon={Check} label={saveLabel} type={saveType} onClick={onSave} disabled={saving} />
          <IconButton icon={X} label={cancelLabel} tone="danger" onClick={onCancel} />
        </>
      ) : (
        <>
          {onEdit && <IconButton icon={Pencil} label={editLabel} onClick={onEdit} />}
          {onDelete && <IconButton icon={Trash2} label={deleteLabel} tone="danger" onClick={onDelete} />}
        </>
      )}
    </div>
  )
}
