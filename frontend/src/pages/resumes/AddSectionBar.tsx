import { Plus } from 'lucide-react'
import { ICON_SIZE } from '../../theme'
import type { SectionMeta } from '../../types'
import styles from './AddSectionBar.module.css'

interface AddSectionBarProps {
  /** Sections the resume has no entries in yet. */
  available: SectionMeta[]
  onAdd: (key: string) => void
}

/** Buttons to open the sections a resume has no entries in yet. */
export default function AddSectionBar({ available, onAdd }: AddSectionBarProps) {
  if (available.length === 0) return null
  return (
    <div className={styles.container} data-testid="add-section-bar">
      <span className={styles.label}>Add section</span>
      <div className={styles.options}>
        {available.map((meta) => (
          <button
            key={meta.key}
            type="button"
            className={styles.option}
            onClick={() => onAdd(meta.key)}
          >
            <Plus size={ICON_SIZE.md} aria-hidden="true" />
            {meta.label}
          </button>
        ))}
      </div>
    </div>
  )
}
