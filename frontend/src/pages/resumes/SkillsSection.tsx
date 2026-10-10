import { useLayoutEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Pencil, X } from 'lucide-react'
import type { Skill } from '../../types'
import { useToast } from '../../components/toast'
import { addEntry, removeEntry, addVersionEntry, removeVersionEntry } from '../../services/api'
import { SkillAdder } from './SkillAdder'
import styles from './SkillsSection.module.css'

interface SkillsSectionProps {
  /** Heading override from the resume layout. */
  title?: string

  skills: Skill[]
  onUpdate?: () => void
  versionId?: number
}

/** Display label for skills stored with a null category. */
const UNCATEGORIZED = 'Other'

export default function SkillsSection({ skills, onUpdate, versionId, title = 'Skills' }: SkillsSectionProps) {
  /** Category label being edited (chips removable + adder open), or null. */
  const [editingCategory, setEditingCategory] = useState<string | null>(null)
  /** Client-only category: exists until its first skill is persisted. */
  const [draftCategory, setDraftCategory] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const draftAdderRef = useRef<HTMLInputElement>(null)
  const { success, error, warning } = useToast()

  const groupedSkills = skills.reduce((acc, skill, index) => {
    const category = skill.category || UNCATEGORIZED
    if (!acc[category]) {
      acc[category] = []
    }
    acc[category].push({ ...skill, originalIndex: index })
    return acc
  }, {} as Record<string, Array<Skill & { originalIndex: number }>>)

  // Alphabetical, with the catch-all "Other" group pinned last
  const categories = Object.keys(groupedSkills).sort((a, b) => {
    if (a === UNCATEGORIZED) return 1
    if (b === UNCATEGORIZED) return -1
    return a.localeCompare(b)
  })

  // A draft stays mounted — keeping focus in its skill input — until the parent
  // refetch confirms the category exists, then editing moves to the real group.
  // Layout effect, not effect: swap before paint so no duplicate group flashes.
  // categoryKey is joined so the effect keys off content, not array identity;
  // the NUL separator keeps multi-word category names intact.
  const categoryKey = categories.join('\u0000')
  useLayoutEffect(() => {
    const label = draftCategory?.trim()
    if (label && categoryKey.split('\u0000').includes(label)) {
      setDraftCategory(null)
      setEditingCategory(label)
    }
  }, [categoryKey, draftCategory])

  const addSkill = (entry: Skill) =>
    versionId !== undefined
      ? addVersionEntry(versionId, 'skills', entry)
      : addEntry('skills', entry)

  /**
   * Persists one or more skills under `categoryLabel`. Saving the first skill
   * of a draft category is what makes that category real — it exists nowhere
   * but this component's state until then.
   */
  const commitSkills = async (categoryLabel: string, names: string[]) => {
    const label = categoryLabel.trim()
    if (!label) {
      warning('Name the category first')
      return
    }

    const existing = new Set(skills.map((s) => s.name.toLowerCase()))
    const seen = new Set<string>()
    const toAdd: string[] = []
    let duplicates = 0

    // The backend rejects case-insensitive duplicates — filter them up front,
    // including repeats inside a single pasted list.
    for (const raw of names) {
      const name = raw.trim()
      if (!name) continue
      const key = name.toLowerCase()
      if (existing.has(key) || seen.has(key)) {
        duplicates++
        continue
      }
      seen.add(key)
      toAdd.push(name)
    }

    if (toAdd.length === 0) {
      if (duplicates > 0) {
        warning(`Skipped ${duplicates} already on this resume`)
      }
      return
    }

    const category = label === UNCATEGORIZED ? null : label
    const failed: string[] = []

    // Sequential, not parallel: each POST rewrites the whole skills array
    // server-side, so concurrent writes would drop entries.
    setSaving(true)
    for (const name of toAdd) {
      try {
        await addSkill({ name, category })
      } catch {
        failed.push(name)
      }
    }
    setSaving(false)

    const added = toAdd.length - failed.length
    if (added > 0) success(`Added ${added} skill${added === 1 ? '' : 's'} to ${label}`)
    if (duplicates > 0) warning(`Skipped ${duplicates} already on this resume`)
    if (failed.length > 0) error(`Failed to add: ${failed.join(', ')}`)

    if (onUpdate) onUpdate()
  }

  /**
   * Enter or Tab in the draft category's name field hands focus straight to its
   * skill input, so a new category can be filled in without leaving the keyboard.
   */
  const handleDraftNameKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      setDraftCategory(null)
      return
    }
    if (e.key !== 'Enter' && !(e.key === 'Tab' && !e.shiftKey)) return

    e.preventDefault()
    if (!draftCategory?.trim()) {
      warning('Name the category first')
      return
    }
    draftAdderRef.current?.focus()
  }

  // No confirm dialog for a single skill — delete immediately, offer Undo.
  // Undo re-adds the skill, which appends it to the end of its category.
  const handleDelete = async (ref: string | number, skill: Skill) => {
    try {
      if (versionId !== undefined) {
        await removeVersionEntry(versionId, 'skills', ref)
      } else {
        await removeEntry('skills', Number(ref))
      }
    } catch (err) {
      error(err instanceof Error ? err.message : 'Failed to delete skill')
      return
    }

    if (onUpdate) onUpdate()

    success(`Deleted ${skill.name}`, {
      duration: 8000,
      action: {
        label: 'Undo',
        onClick: async () => {
          try {
            await addSkill({ name: skill.name, category: skill.category ?? null })
            if (onUpdate) onUpdate()
          } catch {
            error(`Failed to restore ${skill.name}`)
          }
        },
      },
    })
  }

  return (
    <section className={styles.container} data-testid="skills-section">
      <h2 className={styles.sectionLabel}>{title}</h2>

      {categories.length > 0 || draftCategory !== null ? (
        <div className={styles.list}>
          {categories.map((category) => {
            const editing = editingCategory === category
            return (
              <div key={category} className={styles.skillGroup}>
                <div className={styles.groupHeader}>
                  <span className={styles.categoryLabel}>{category}</span>
                  {editing ? (
                    <button
                      className={styles.doneButton}
                      onClick={() => setEditingCategory(null)}
                    >
                      done
                    </button>
                  ) : (
                    <button
                      className={styles.editCategoryButton}
                      onClick={() => {
                        setDraftCategory(null)
                        setEditingCategory(category)
                      }}
                      aria-label={`Edit ${category} skills`}
                    >
                      <Pencil size={12} />
                    </button>
                  )}
                </div>

                <div className={styles.skillItems}>
                  {groupedSkills[category].map((skill) => (
                    <div key={skill.originalIndex} className={styles.skillItem}>
                      <span className={styles.skillName}>{skill.name}</span>
                      {editing && (
                        <button
                          className={styles.chipRemove}
                          onClick={() => handleDelete(skill.id ?? skill.originalIndex, skill)}
                          aria-label={`Remove ${skill.name}`}
                        >
                          <X size={10} />
                        </button>
                      )}
                    </div>
                  ))}

                  {editing && (
                    <SkillAdder
                      label={`Add skill to ${category}`}
                      busy={saving}
                      onCommit={(names) => void commitSkills(category, names)}
                      onClose={() => setEditingCategory(null)}
                    />
                  )}
                </div>
              </div>
            )
          })}

          {draftCategory !== null && (
            <div className={styles.skillGroup} data-testid="draft-category">
              <div className={styles.draftHeader}>
                <input
                  className={styles.draftName}
                  value={draftCategory}
                  onChange={(e) => setDraftCategory(e.target.value)}
                  onKeyDown={handleDraftNameKeyDown}
                  placeholder="Category name"
                  aria-label="New category name"
                  autoComplete="off"
                  autoFocus
                />
                <button
                  className={styles.draftCancel}
                  onClick={() => setDraftCategory(null)}
                  aria-label="Discard new category"
                >
                  <X size={12} />
                </button>
              </div>
              <div className={styles.skillItems}>
                <SkillAdder
                  ref={draftAdderRef}
                  label="Add skill to new category"
                  busy={saving}
                  autoFocus={false}
                  onCommit={(names) => void commitSkills(draftCategory, names)}
                  onClose={() => setDraftCategory(null)}
                />
              </div>
              <p className={styles.draftHint}>Unsaved — adding a skill creates this category</p>
            </div>
          )}
        </div>
      ) : (
        <p className={styles.placeholder}>Click "Add Category" to add skills</p>
      )}

      {draftCategory === null && (
        <button
          className={styles.addButton}
          onClick={() => {
            setEditingCategory(null)
            setDraftCategory('')
          }}
        >
          + Add Category
        </button>
      )}
    </section>
  )
}
