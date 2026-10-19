import { useState } from 'react'
import { TagInput } from './TagInput'
import { useToast } from './toast'
import { EditActions } from './EditActions'
import { TagList } from './TagList'
import styles from './TagsPanel.module.css'

interface TagsPanelProps {
  tags: string[]
  allTags: string[]
  onSave: (tags: string[]) => Promise<unknown>
}

export function TagsPanel({ tags, allTags, onSave }: TagsPanelProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const { error } = useToast()

  const startEdit = () => {
    setDraft(tags)
    setEditing(true)
  }

  const save = async () => {
    setSaving(true)
    try {
      await onSave(draft)
      setEditing(false)
    } catch {
      error('Failed to update tags')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={styles.panel} data-testid="tags-panel">
      <div className={styles.header}>
        <h3 className={styles.title}>Tags</h3>
        <EditActions
          editing={editing}
          onEdit={startEdit}
          onSave={save}
          onCancel={() => setEditing(false)}
          saving={saving}
          editLabel="Edit tags"
          saveLabel="Save tags"
          cancelLabel="Cancel editing tags"
        />
      </div>
      {editing ? (
        <TagInput value={draft} onChange={setDraft} availableTags={allTags} allowCreate placeholder="Add tag..." />
      ) : tags.length > 0 ? (
        <TagList tags={tags} />
      ) : (
        <p className={styles.empty}>No tags</p>
      )}
    </div>
  )
}
