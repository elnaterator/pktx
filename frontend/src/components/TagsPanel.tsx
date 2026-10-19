import { useState } from 'react'
import { Pencil, Check, X } from 'lucide-react'
import { TagInput } from './TagInput'
import { useToast } from './toast'
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
        {editing ? (
          <div className={styles.actions}>
            <button type="button" className={`${styles.iconBtn} ${styles.save}`} onClick={save} disabled={saving} aria-label="Save tags">
              <Check size={14} />
            </button>
            <button type="button" className={`${styles.iconBtn} ${styles.cancel}`} onClick={() => setEditing(false)} aria-label="Cancel editing tags">
              <X size={14} />
            </button>
          </div>
        ) : (
          <button type="button" className={styles.iconBtn} onClick={startEdit} aria-label="Edit tags">
            <Pencil size={14} />
          </button>
        )}
      </div>
      {editing ? (
        <TagInput value={draft} onChange={setDraft} availableTags={allTags} allowCreate placeholder="Add tag..." />
      ) : tags.length > 0 ? (
        <div className={styles.tagList}>
          {tags.map((tag) => (
            <span key={tag} className={styles.tagBadge}>{tag}</span>
          ))}
        </div>
      ) : (
        <p className={styles.empty}>No tags</p>
      )}
    </div>
  )
}
