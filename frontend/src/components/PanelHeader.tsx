import type { ReactNode } from 'react'
import { EditActions } from './EditActions'
import styles from './PanelHeader.module.css'

interface PanelHeaderProps {
  /** The panel's title, rendered as its h2. */
  title: ReactNode
  /** Lower-case noun for the edit/delete labels ("note" → "Edit note"). */
  entity: string
  onEdit?: () => void
  onDelete?: () => void
}

/**
 * Title row of a resource panel in view mode: title plus edit/delete.
 * Edit mode replaces the whole panel with an `EditForm`.
 */
export function PanelHeader({ title, entity, onEdit, onDelete }: PanelHeaderProps) {
  return (
    <div className={styles.header}>
      <h2 className={styles.title}>{title}</h2>
      <EditActions
        editing={false}
        onEdit={onEdit}
        onDelete={onDelete}
        className={styles.actions}
        editLabel={`Edit ${entity}`}
        deleteLabel={`Delete ${entity}`}
      />
    </div>
  )
}
