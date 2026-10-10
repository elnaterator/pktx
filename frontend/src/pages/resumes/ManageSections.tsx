import { useState } from 'react'
import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react'
import type { CustomSection, LayoutItem, SectionMeta } from '../../types'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { useToast } from '../../components/toast'
import { useResumeMutations } from '../../hooks/queries'
import { CUSTOM_PREFIX, defaultTitle } from './layout'
import styles from './ManageSections.module.css'

interface ManageSectionsProps {
  versionId: number
  layout: LayoutItem[]
  customSections: Record<string, CustomSection>
  sections: SectionMeta[]
}

/** Reorder, show/hide, rename and add/remove sections of one resume version. */
export default function ManageSections({
  versionId,
  layout,
  customSections,
  sections,
}: ManageSectionsProps) {
  const { error } = useToast()
  const { updateLayout, addCustom, removeCustom } = useResumeMutations()
  const [newTitle, setNewTitle] = useState('')
  const [removing, setRemoving] = useState<string | null>(null)

  const save = async (next: LayoutItem[]) => {
    try {
      await updateLayout.mutateAsync({ id: versionId, layout: next })
    } catch {
      error('Failed to update layout')
    }
  }

  const patch = (index: number, change: Partial<LayoutItem>) =>
    save(layout.map((item, i) => (i === index ? { ...item, ...change } : item)))

  const move = (index: number, delta: -1 | 1) => {
    const target = index + delta
    if (target < 0 || target >= layout.length) return
    const next = [...layout]
    ;[next[index], next[target]] = [next[target], next[index]]
    return save(next)
  }

  const handleAdd = async () => {
    const title = newTitle.trim()
    if (!title) return
    try {
      await addCustom.mutateAsync({ id: versionId, title })
      setNewTitle('')
    } catch {
      error('Failed to add section')
    }
  }

  const handleRemove = async () => {
    if (!removing) return
    try {
      await removeCustom.mutateAsync({ id: versionId, customId: removing.slice(CUSTOM_PREFIX.length) })
    } catch {
      error('Failed to remove section')
    }
    setRemoving(null)
  }

  return (
    <details className={styles.container} data-testid="manage-sections">
      <summary className={styles.summary}>Manage sections</summary>
      <ul className={styles.list}>
        {layout.map((item, index) => {
          const base = defaultTitle(item.section, sections, customSections)
          const isCustom = item.section.startsWith(CUSTOM_PREFIX)
          return (
            <li key={item.section} className={styles.row}>
              <input
                type="checkbox"
                checked={item.visible}
                onChange={(e) => patch(index, { visible: e.target.checked })}
                aria-label={`Show ${base}`}
              />
              <input
                className={styles.titleInput}
                defaultValue={item.title ?? ''}
                placeholder={base}
                maxLength={200}
                aria-label={`Title for ${base}`}
                onBlur={(e) => {
                  const value = e.target.value.trim()
                  if (value !== (item.title ?? '')) void patch(index, { title: value || null })
                }}
              />
              <div className={styles.actions}>
                <button
                  className={styles.iconButton}
                  onClick={() => void move(index, -1)}
                  disabled={index === 0}
                  aria-label={`Move ${base} up`}
                >
                  <ArrowUp size={14} />
                </button>
                <button
                  className={styles.iconButton}
                  onClick={() => void move(index, 1)}
                  disabled={index === layout.length - 1}
                  aria-label={`Move ${base} down`}
                >
                  <ArrowDown size={14} />
                </button>
                {isCustom && (
                  <button
                    className={styles.iconButton}
                    onClick={() => setRemoving(item.section)}
                    aria-label={`Remove ${base}`}
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            </li>
          )
        })}
      </ul>
      <form
        className={styles.addRow}
        onSubmit={(e) => {
          e.preventDefault()
          void handleAdd()
        }}
      >
        <input
          className={styles.titleInput}
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          placeholder="New custom section title"
          maxLength={200}
          aria-label="New custom section title"
        />
        <button type="submit" className={styles.addButton} disabled={!newTitle.trim()}>
          <Plus size={14} /> Add section
        </button>
      </form>
      {removing && (
        <ConfirmDialog
          message="Delete this section and all of its entries?"
          onConfirm={handleRemove}
          onCancel={() => setRemoving(null)}
        />
      )}
    </details>
  )
}
