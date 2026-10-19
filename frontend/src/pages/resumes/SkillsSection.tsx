import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Check, Pencil, Trash2, X } from 'lucide-react'
import type { Skill } from '../../types'
import { useToast } from '../../components/toast'
import { addEntry, removeEntry, reorderEntries, updateEntry } from '../../services/api'
import { SkillAdder } from './SkillAdder'
import SectionHeader from './SectionHeader'
import SortableList from '../../components/SortableList'
import styles from './SkillsSection.module.css'

interface SkillsSectionProps {
  /** Skills as JSON Resume names them: a name and its keywords, e.g. "Languages": Go, Python. */
  skills: Skill[]
  versionId: number
  onUpdate?: () => void
  /** Dismiss an empty section; offered only while it has no skills. */
  onClose?: () => void
}

const SECTION = 'skills'

export default function SkillsSection({ skills, versionId, onUpdate, onClose }: SkillsSectionProps) {
  /** Id of the skill being edited (keyword chips removable + adder open), or null. */
  const [editingId, setEditingId] = useState<string | null>(null)
  /** Client-only skill name: exists until its first keyword is persisted. */
  const [draft, setDraft] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const draftAdderRef = useRef<HTMLInputElement>(null)
  /**
   * Keywords as last written, per skill. A write replaces the whole list, so a
   * second one issued before the refetch lands must build on the first, not on
   * the stale prop. Cleared whenever fresh data arrives.
   */
  const written = useRef(new Map<string, string[]>())
  /** The newest props, for work that starts after the render that queued it. */
  const latest = useRef(skills)
  latest.current = skills
  /** Writes run one at a time, so fast typing can never overwrite an earlier keyword. */
  const queue = useRef<Promise<void>>(Promise.resolve())
  /** Draft skills already created, by lowercase name, until the refetch shows them. */
  const created = useRef(new Map<string, Skill & { id: string }>())
  const { success, error, warning } = useToast()

  useEffect(() => {
    written.current.clear()
  }, [skills])

  useEffect(() => {
    if (draft === null) created.current.clear()
  }, [draft])

  const keywordsOf = (group: Skill): string[] =>
    (group.id ? written.current.get(group.id) : undefined) ?? group.keywords ?? []

  /** Replaces a skill's keywords and remembers them until the refetch lands. */
  const writeKeywords = async (group: Skill & { id: string }, keywords: string[]) => {
    await updateEntry(versionId, SECTION, group.id, { keywords })
    written.current.set(group.id, keywords)
  }

  // A draft stays mounted — keeping focus in its keyword input — until the parent
  // refetch confirms the skill exists, then editing moves to the real skill.
  // Layout effect, not effect: swap before paint so no duplicate group flashes.
  const groupKey = skills.map((s) => `${s.id}:${s.name}`).join('\u0000')
  useLayoutEffect(() => {
    const label = draft?.trim().toLowerCase()
    const created = label ? skills.find((s) => s.name?.toLowerCase() === label) : undefined
    if (created) {
      setDraft(null)
      setEditingId(created.id ?? null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- keyed by groupKey
  }, [groupKey, draft])

  const refresh = () => onUpdate?.()

  /**
   * Adds keywords to a skill in one write. A draft skill is created by its first
   * keyword: it exists nowhere but this component's state until then.
   */
  const doCommit = async (target: Skill | null, label: string, names: string[]) => {
    const groupName = label.trim()
    if (!groupName) {
      warning('Name the skill first')
      return
    }

    // Resolve against what we know now, not what was rendered when the write was queued.
    const made = created.current.get(groupName.toLowerCase())
    const group =
      (target?.id ? latest.current.find((s) => s.id === target.id) : undefined) ?? target ?? made ?? null
    const current = group ? keywordsOf(group) : []
    const seen = new Set(current.map((k) => k.toLowerCase()))
    const toAdd: string[] = []
    let duplicates = 0
    // Filter case-insensitive duplicates up front, including repeats inside a
    // single pasted list.
    for (const raw of names) {
      const name = raw.trim()
      if (!name) continue
      if (seen.has(name.toLowerCase())) {
        duplicates++
        continue
      }
      seen.add(name.toLowerCase())
      toAdd.push(name)
    }

    if (toAdd.length === 0) {
      if (duplicates > 0) warning(`Skipped ${duplicates} already in ${groupName}`)
      return
    }

    setSaving(true)
    try {
      if (group?.id) {
        await writeKeywords({ ...group, id: group.id }, [...current, ...toAdd])
      } else {
        const entry = await addEntry(versionId, SECTION, { name: groupName, keywords: toAdd })
        const made = { id: entry.id as string, name: groupName, keywords: toAdd }
        written.current.set(made.id, toAdd)
        created.current.set(groupName.toLowerCase(), made)
      }
      success(`Added ${toAdd.length} keyword${toAdd.length === 1 ? '' : 's'} to ${groupName}`)
      if (duplicates > 0) warning(`Skipped ${duplicates} already in ${groupName}`)
    } catch {
      error(`Failed to add: ${toAdd.join(', ')}`)
    } finally {
      setSaving(false)
    }
    refresh()
  }

  const commitKeywords = (group: Skill | null, label: string, names: string[]) => {
    const run = queue.current.then(() => doCommit(group, label, names))
    queue.current = run
    return run
  }

  const renameGroup = async (group: Skill, value: string) => {
    const name = value.trim()
    if (!group.id || name === group.name) return
    if (!name) {
      warning('A skill needs a name')
      return
    }
    try {
      await updateEntry(versionId, SECTION, group.id, { name })
      refresh()
    } catch {
      error('Failed to rename skill')
    }
  }

  /**
   * Enter or Tab in the draft's name field hands focus straight to its keyword
   * input, so a new skill can be filled in without leaving the keyboard.
   */
  const handleDraftNameKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      setDraft(null)
      return
    }
    if (e.key !== 'Enter' && !(e.key === 'Tab' && !e.shiftKey)) return

    e.preventDefault()
    if (!draft?.trim()) {
      warning('Name the skill first')
      return
    }
    draftAdderRef.current?.focus()
  }

  // No confirm dialog for a single keyword — remove it immediately, offer Undo.
  const removeKeyword = async (group: Skill, keyword: string) => {
    if (!group.id) return
    const target = { ...group, id: group.id }
    try {
      await writeKeywords(
        target,
        keywordsOf(group).filter((k) => k !== keyword),
      )
    } catch (err) {
      error(err instanceof Error ? err.message : 'Failed to delete keyword')
      return
    }
    refresh()

    success(`Deleted ${keyword}`, {
      duration: 8000,
      action: {
        label: 'Undo',
        onClick: async () => {
          try {
            const now = keywordsOf(group)
            if (!now.includes(keyword)) await writeKeywords(target, [...now, keyword])
            refresh()
          } catch {
            error(`Failed to restore ${keyword}`)
          }
        },
      },
    })
  }

  const reorderSkills = async (ids: string[]) => {
    try {
      await reorderEntries(versionId, SECTION, ids)
      refresh()
    } catch (e) {
      error('Failed to reorder skills')
      throw e // the grid snaps back to the saved order
    }
  }

  const deleteGroup = async (group: Skill, index: number) => {
    if (!group.id) return
    try {
      await removeEntry(versionId, SECTION, group.id)
    } catch (err) {
      error(err instanceof Error ? err.message : 'Failed to delete skill')
      return
    }
    setEditingId(null)
    refresh()

    success(`Deleted ${group.name ?? 'skill'}`, {
      duration: 8000,
      action: {
        label: 'Undo',
        onClick: async () => {
          try {
            // Re-created with a fresh id, at its old position.
            await addEntry(
              versionId,
              SECTION,
              { name: group.name, level: group.level, keywords: group.keywords },
              index,
            )
            refresh()
          } catch {
            error(`Failed to restore ${group.name ?? 'skill'}`)
          }
        },
      },
    })
  }

  return (
    <section className={styles.container} data-testid="skills-section">
      <SectionHeader title="Skills">
        {draft === null && (
          <>
            {skills.length === 0 && onClose && (
              <button type="button" data-quiet onClick={onClose}>
                Remove section
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                setEditingId(null)
                setDraft('')
              }}
            >
              + Add Skill
            </button>
          </>
        )}
      </SectionHeader>

      {skills.length > 0 || draft !== null ? (
        <div className={styles.list}>
          {draft !== null && (
            <div className={styles.skill} data-testid="draft-skill">
              <div className={styles.draftHeader}>
                <input
                  className={styles.draftName}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={handleDraftNameKeyDown}
                  placeholder="Skill name"
                  aria-label="New skill name"
                  autoComplete="off"
                  autoFocus
                />
                <button
                  className={styles.draftCancel}
                  onClick={() => setDraft(null)}
                  aria-label="Discard new skill"
                >
                  <X size={12} />
                </button>
              </div>
              <div className={styles.keywords}>
                <SkillAdder
                  ref={draftAdderRef}
                  label="Add keyword to new skill"
                  busy={saving}
                  autoFocus={false}
                  onCommit={(names) => void commitKeywords(null, draft, names)}
                  onClose={() => setDraft(null)}
                />
              </div>
              <p className={styles.draftHint}>
                {draft.trim()
                  ? `Add a keyword to save “${draft.trim()}”.`
                  : 'Name your skill, then add its keywords.'}
              </p>
            </div>
          )}

          <SortableList
            className={styles.contents}
            layout="grid"
            items={skills}
            getId={(group) => group.id as string}
            getLabel={(group) => group.name ?? 'skill'}
            onReorder={reorderSkills}
            renderItem={(group, row) => {
            const editing = editingId === group.id
            const name = group.name ?? 'Other'
            return (
              <div ref={row.setNodeRef} style={row.style} className={styles.skill}>
                <div className={styles.groupHeader}>
                  {row.handle}
                  {editing ? (
                    <input
                      className={styles.draftName}
                      defaultValue={name}
                      onBlur={(e) => void renameGroup(group, e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') e.currentTarget.blur()
                      }}
                      aria-label={`${name} skill name`}
                      autoComplete="off"
                    />
                  ) : (
                    <span className={styles.skillLabel}>{name}</span>
                  )}
                  {editing ? (
                    <>
                      <button
                        className={styles.draftCancel}
                        onClick={() => void deleteGroup(group, skills.findIndex((s) => s.id === group.id))}
                        aria-label={`Delete ${name} skill`}
                      >
                        <Trash2 size={12} />
                      </button>
                      <button
                        className={styles.doneButton}
                        onClick={() => setEditingId(null)}
                        aria-label={`Done editing ${name}`}
                      >
                        <Check size={14} aria-hidden="true" />
                      </button>
                    </>
                  ) : (
                    <button
                      className={styles.editSkillButton}
                      onClick={() => {
                        setDraft(null)
                        setEditingId(group.id ?? null)
                      }}
                      aria-label={`Edit ${name} skill`}
                    >
                      <Pencil size={12} />
                    </button>
                  )}
                </div>

                <div className={styles.keywords}>
                  {(group.keywords ?? []).map((keyword) => (
                    <div key={keyword} className={styles.keyword}>
                      <span className={styles.keywordName}>{keyword}</span>
                      {editing && (
                        <button
                          className={styles.chipRemove}
                          onClick={() => void removeKeyword(group, keyword)}
                          aria-label={`Remove ${keyword}`}
                        >
                          <X size={10} />
                        </button>
                      )}
                    </div>
                  ))}

                  {editing && (
                    <SkillAdder
                      label={`Add keyword to ${name}`}
                      busy={saving}
                      onCommit={(names) => void commitKeywords(group, name, names)}
                      onClose={() => setEditingId(null)}
                    />
                  )}
                </div>
              </div>
            )
          }}
          />
        </div>
      ) : (
        <p className={styles.placeholder}>Click "Add Skill" to add your first skill</p>
      )}

    </section>
  )
}
