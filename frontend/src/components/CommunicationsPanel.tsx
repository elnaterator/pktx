import { useEffect, useMemo, useState } from 'react'
import { Pencil, Trash2, Check, X, ChevronDown } from 'lucide-react'
import { ICON_SIZE } from '../theme'
import { useForm, Controller, type UseFormRegister, type Control } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import type { Communication } from '../types'
import { ApiClientError } from '../services/api'
import {
  useAllTags,
  useCommunicationMutations,
  useContactCommunications,
} from '../hooks/queries'
import { TagInput } from './TagInput'
import { ConfirmDialog } from './ConfirmDialog'
import { useToast } from './toast'
import { AutoResizeTextarea } from './AutoResizeTextarea'
import { MarkdownContent } from './MarkdownContent'
import {
  communicationCreateSchema,
  COMM_TYPES,
  COMM_DIRECTIONS,
  COMM_STATUSES,
  type CommunicationCreateInput,
} from '../schemas/communication'
import styles from './CommunicationsPanel.module.css'

const STATUS_CLASS: Record<string, string> = {
  draft: styles.statusDraft,
  ready: styles.statusReady,
  sent: styles.statusSent,
  archived: styles.statusArchived,
}

export interface CommunicationsPanelProps {
  contactId: number
  initialExpandId?: number
}

const today = () => new Date().toISOString().slice(0, 10)

const emptyDefaults = (): CommunicationCreateInput => ({
  type: 'email',
  direction: 'sent',
  subject: undefined,
  body: undefined,
  date: today(),
  status: 'draft',
  tags: [],
})

export default function CommunicationsPanel({ contactId, initialExpandId }: CommunicationsPanelProps) {
  const [showAddForm, setShowAddForm] = useState(false)
  const [editTarget, setEditTarget] = useState<Communication | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null)
  const [expandedIds, setExpandedIds] = useState<Set<number>>(
    initialExpandId !== undefined ? new Set([initialExpandId]) : new Set()
  )
  const { success, error: toastError } = useToast()

  const commsQuery = useContactCommunications(contactId)
  const tagsQuery = useAllTags()
  const { add, update, remove } = useCommunicationMutations()

  const allTags = tagsQuery.data ?? []
  const submitting = add.isPending || update.isPending

  const { register, handleSubmit, reset, control, formState: { isSubmitting } } = useForm<CommunicationCreateInput>({
    resolver: zodResolver(communicationCreateSchema),
    mode: 'onSubmit',
    defaultValues: emptyDefaults(),
  })

  const communications = useMemo<Communication[]>(() => {
    const data = commsQuery.data ?? []
    return [...data].sort(
      (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
    )
  }, [commsQuery.data])

  useEffect(() => {
    if (commsQuery.isSuccess && initialExpandId !== undefined) {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          document.getElementById(`comm-${initialExpandId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
        })
      })
    }
  }, [commsQuery.isSuccess, initialExpandId])

  useEffect(() => {
    if (commsQuery.isError) {
      const err = commsQuery.error
      const msg = err instanceof ApiClientError ? err.detail ?? err.message : 'Failed to load communications'
      toastError(msg)
    }
  }, [commsQuery.isError, commsQuery.error, toastError])

  const toggleExpand = (id: number) =>
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) { next.delete(id) } else { next.add(id) }
      return next
    })

  const onAddSubmit = handleSubmit(async (data) => {
    try {
      await add.mutateAsync({ contactId, data: { ...data, subject: data.subject ?? '', body: data.body ?? '' } })
      reset(emptyDefaults())
      setShowAddForm(false)
      success('Communication added')
    } catch (err) {
      const msg = err instanceof ApiClientError ? (err as ApiClientError).detail ?? err.message : 'Failed to add communication'
      toastError(msg)
    }
  })

  const onEditSubmit = handleSubmit(async (data) => {
    if (!editTarget) return
    try {
      await update.mutateAsync({ contactId, commId: editTarget.id, data: { ...data, subject: data.subject ?? '', body: data.body ?? '' } })
      setEditTarget(null)
      reset(emptyDefaults())
      success('Communication updated')
    } catch (err) {
      const msg = err instanceof ApiClientError ? (err as ApiClientError).detail ?? err.message : 'Failed to update communication'
      toastError(msg)
    }
  })

  const startEdit = (comm: Communication) => {
    reset({
      type: comm.type as CommunicationCreateInput['type'],
      direction: comm.direction as CommunicationCreateInput['direction'],
      subject: comm.subject || undefined,
      body: comm.body || undefined,
      date: comm.date.slice(0, 10),
      status: comm.status as CommunicationCreateInput['status'],
      tags: comm.tags ?? [],
    })
    setEditTarget(comm)
    setShowAddForm(false)
  }

  const handleDelete = async () => {
    if (deleteTarget === null) return
    try {
      await remove.mutateAsync({ contactId, commId: deleteTarget })
      setDeleteTarget(null)
      success('Communication removed')
    } catch (err) {
      const msg = err instanceof ApiClientError ? (err as ApiClientError).detail ?? err.message : 'Failed to remove communication'
      toastError(msg)
      setDeleteTarget(null)
    }
  }

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })

  return (
    <div className={styles.container} id="communications" style={{ scrollMarginTop: 'var(--header-h, 64px)' }}>
      <div className={styles.panelHeader}>
        <h3 className={styles.panelTitle}>Communications</h3>
        {!showAddForm && (
          <button
            className={styles.addBtn}
            onClick={() => { reset(emptyDefaults()); setShowAddForm(true); setEditTarget(null) }}
          >
            Add Communication
          </button>
        )}
      </div>

      {showAddForm && (
        <form className={styles.form} onSubmit={onAddSubmit} noValidate>
          <div className={styles.formHeader}>
            <button type="submit" className={styles.saveIconBtn} disabled={isSubmitting || submitting} aria-label="Save">
              <Check size={ICON_SIZE.md} />
            </button>
            <button
              type="button"
              className={styles.cancelIconBtn}
              onClick={() => { setShowAddForm(false); reset(emptyDefaults()) }}
              aria-label="Cancel"
            >
              <X size={ICON_SIZE.md} />
            </button>
          </div>
          <CommFormFields register={register} control={control} allTags={allTags} />
        </form>
      )}

      {communications.length === 0 && !showAddForm ? (
        <p className={styles.empty}>No communications yet.</p>
      ) : (
        <ul className={styles.timeline}>
          {communications.map((comm) => (
            <li key={comm.id} id={`comm-${comm.id}`} className={styles.timelineItem}>
              {editTarget?.id === comm.id ? (
                <form className={styles.form} onSubmit={onEditSubmit} noValidate>
                  <div className={styles.formHeader}>
                    <button type="submit" className={styles.saveIconBtn} disabled={isSubmitting || submitting} aria-label="Save">
                      <Check size={ICON_SIZE.md} />
                    </button>
                    <button
                      type="button"
                      className={styles.cancelIconBtn}
                      onClick={() => { setEditTarget(null); reset(emptyDefaults()) }}
                      aria-label="Cancel"
                    >
                      <X size={ICON_SIZE.md} />
                    </button>
                  </div>
                  <CommFormFields register={register} control={control} allTags={allTags} />
                </form>
              ) : (
                <div
                  className={styles.commCard}
                  onClick={() => comm.body && toggleExpand(comm.id)}
                  style={{ cursor: comm.body ? 'pointer' : 'default' }}
                >
                  <div className={styles.commTopRow}>
                    <div className={styles.commMeta}>
                      <span className={styles.commDate}>{formatDate(comm.date)}</span>
                      <span className={styles.commType}>{comm.type}</span>
                      <span className={styles.commDirection}>{comm.direction}</span>
                      <span className={`${styles.statusBadge} ${STATUS_CLASS[comm.status] || ''}`}>
                        {comm.status}
                      </span>
                    </div>
                    <div className={styles.commRight}>
                      {comm.tags && comm.tags.length > 0 && (
                        <div className={styles.tagRow}>
                          {comm.tags.map((tag) => (
                            <span key={tag} className={styles.tagChip}>{tag}</span>
                          ))}
                        </div>
                      )}
                      <div className={styles.commActions}>
                        <button
                          className={styles.editBtn}
                          onClick={(e) => { e.stopPropagation(); startEdit(comm) }}
                          aria-label="Edit communication"
                        ><Pencil size={ICON_SIZE.md} /></button>
                        <button
                          className={styles.deleteBtn}
                          onClick={(e) => { e.stopPropagation(); setDeleteTarget(comm.id) }}
                          aria-label="Delete communication"
                        ><Trash2 size={ICON_SIZE.md} /></button>
                      </div>
                      {comm.body && (
                        <ChevronDown
                          size={ICON_SIZE.md}
                          className={expandedIds.has(comm.id) ? styles.chevronOpen : styles.chevron}
                        />
                      )}
                    </div>
                  </div>
                  {(comm.subject || comm.body) && !expandedIds.has(comm.id) && (
                    <p className={styles.commSummaryRow}>
                      {comm.subject && <strong className={styles.commSubject}>{comm.subject}</strong>}
                      {comm.subject && comm.body && <span className={styles.commSep}> · </span>}
                      {comm.body && <span className={styles.commBodyPreview}>{comm.body}</span>}
                    </p>
                  )}
                  {expandedIds.has(comm.id) && (
                    <>
                      {comm.subject && <p className={styles.commSubjectExpanded}>{comm.subject}</p>}
                      {comm.body && (
                        <div className={styles.commBodyFull}>
                          <MarkdownContent>{comm.body}</MarkdownContent>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {deleteTarget !== null && (
        <ConfirmDialog
          message="Remove this communication?"
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  )
}

interface CommFormFieldsProps {
  register: UseFormRegister<CommunicationCreateInput>
  control: Control<CommunicationCreateInput>
  allTags: string[]
}

function CommFormFields({ register, control, allTags }: CommFormFieldsProps) {
  return (
    <div className={styles.formGrid}>
      <div className={styles.formField}>
        <label className={styles.label} htmlFor="comm-type">Type</label>
        <select id="comm-type" className={styles.select} {...register('type')}>
          {COMM_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      <div className={styles.formField}>
        <label className={styles.label} htmlFor="comm-direction">Direction</label>
        <select id="comm-direction" className={styles.select} {...register('direction')}>
          {COMM_DIRECTIONS.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
      </div>
      <div className={styles.formField}>
        <label className={styles.label} htmlFor="comm-date">Date</label>
        <input id="comm-date" type="date" className={styles.input} {...register('date')} />
      </div>
      <div className={styles.formField}>
        <label className={styles.label} htmlFor="comm-status">Status</label>
        <select id="comm-status" className={styles.select} {...register('status')}>
          {COMM_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <div className={`${styles.formField} ${styles.fullWidth}`}>
        <label className={styles.label} htmlFor="comm-subject">Subject</label>
        <input id="comm-subject" className={styles.input} placeholder="Subject line" {...register('subject')} />
      </div>
      <div className={`${styles.formField} ${styles.fullWidth}`}>
        <label className={styles.label} htmlFor="comm-body">Body</label>
        <Controller
          control={control}
          name="body"
          render={({ field }) => (
            <AutoResizeTextarea
              id="comm-body"
              className={styles.textarea}
              value={field.value ?? ''}
              onChange={field.onChange}
              placeholder="Message body..."
            />
          )}
        />
      </div>
      <div className={`${styles.formField} ${styles.fullWidth}`}>
        <label className={styles.label}>Tags</label>
        <Controller
          control={control}
          name="tags"
          render={({ field }) => (
            <TagInput
              value={field.value ?? []}
              onChange={field.onChange}
              availableTags={allTags}
            />
          )}
        />
      </div>
    </div>
  )
}
