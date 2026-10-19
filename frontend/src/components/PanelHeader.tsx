import type { ReactNode } from 'react'
import { EditActions } from './EditActions'
import styles from './PanelHeader.module.css'

interface PanelHeaderProps {
  editing: boolean
  /** View-mode title, rendered as the panel's h2. */
  title: ReactNode
  /** Edit-mode replacement for the title (inputs; use `styles.titleInput`). */
  titleEditor: ReactNode
  /** Lower-case noun for the edit/delete labels ("note" → "Edit note"). */
  entity: string
  onEdit?: () => void
  onDelete?: () => void
  onSave?: () => void
  onCancel?: () => void
  saving?: boolean
}

/** Title row of a resource panel: title (or its inputs) plus edit actions. */
export function PanelHeader({
  editing,
  title,
  titleEditor,
  entity,
  onEdit,
  onDelete,
  onSave,
  onCancel,
  saving,
}: PanelHeaderProps) {
  return (
    <div className={styles.header}>
      {editing ? (
        <div className={styles.main}>{titleEditor}</div>
      ) : (
        <h2 className={styles.title}>{title}</h2>
      )}
      <EditActions
        editing={editing}
        onEdit={onEdit}
        onDelete={onDelete}
        onSave={onSave}
        onCancel={onCancel}
        saving={saving}
        editLabel={`Edit ${entity}`}
        deleteLabel={`Delete ${entity}`}
      />
    </div>
  )
}
