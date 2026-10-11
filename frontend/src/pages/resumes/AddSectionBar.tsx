import { Plus } from 'lucide-react'
import type { SectionMeta } from '../../types'
import styles from './AddSectionBar.module.css'

interface AddSectionBarProps {
  /** Optional sections not yet on this resume. */
  available: SectionMeta[]
  onAdd: (key: string) => void
}

/** Buttons to add the optional sections a resume does not have yet. */
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
            <Plus size={13} aria-hidden="true" />
            {meta.label}
          </button>
        ))}
      </div>
    </div>
  )
}
