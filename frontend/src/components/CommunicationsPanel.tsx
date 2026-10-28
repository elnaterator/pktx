import { useEffect, useId, useMemo, useState, type ReactNode } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  ArrowDownLeft,
  ArrowUpRight,
  ChevronDown,
  Mail,
  MessageSquare,
  NotebookPen,
  Pencil,
  Phone,
  Plus,
  Trash2,
  type LucideIcon,
} from 'lucide-react'
import { ICON_SIZE } from '../theme'
import type { Communication } from '../types'
import { ApiClientError } from '../services/api'
import {
  useAllTags,
  useCommunicationMutations,
  useContactCommunications,
} from '../hooks/queries'
import {
  communicationCreateSchema,
  commDirectionLabel,
  commLabel,
  COMM_DIRECTION_LABELS,
  COMM_DIRECTIONS,
  COMM_STATUS_LABELS,
  COMM_STATUSES,
  COMM_TYPE_LABELS,
  COMM_TYPES,
  type CommunicationCreateInput,
} from '../schemas/communication'
import { cx } from '../utils/cx'
import { formatDate } from '../utils/formatDate'
import { AutoResizeTextarea } from './AutoResizeTextarea'
import { Button } from './Button'
import { CommStatusBadge } from './CommStatusBadge'
import { ConfirmDialog } from './ConfirmDialog'
import { DateInput } from './DateInput'
import { EditForm, FormField } from './EditForm'
import form from './EditForm.module.css'
import { EmptyState } from './EmptyState'
import { IconButton } from './IconButton'
import { LoadingSpinner } from './LoadingSpinner'
import { MarkdownContent } from './MarkdownContent'
import { SectionCard } from './SectionCard'
import { TagInput } from './TagInput'
import { TagList } from './TagList'
import { useToast } from './toast'
import styles from './CommunicationsPanel.module.css'

const TYPE_ICON: Record<string, LucideIcon> = {
  email: Mail,
  phone: Phone,
  interview_note: NotebookPen,
  other: MessageSquare,
}

const DIRECTION_ICON: Record<string, LucideIcon> = {
  sent: ArrowUpRight,
  received: ArrowDownLeft,
}

export interface CommunicationsPanelProps {
  contactId: number
  /** Used for "To Jane" / "From Jane" direction labels. */
  contactName?: string
  initialExpandId?: number
}

const today = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const emptyDefaults = (): CommunicationCreateInput => ({
  type: 'email',
  direction: 'sent',
  subject: undefined,
  body: undefined,
  date: today(),
  status: 'draft',
  tags: [],
})

const fromCommunication = (comm: Communication): CommunicationCreateInput => ({
  type: comm.type as CommunicationCreateInput['type'],
  direction: comm.direction as CommunicationCreateInput['direction'],
  subject: comm.subject || undefined,
  body: comm.body || undefined,
  date: comm.date.slice(0, 10),
  status: comm.status as CommunicationCreateInput['status'],
  tags: comm.tags ?? [],
})

const toPayload = (data: CommunicationCreateInput) => ({
  ...data,
  subject: data.subject ?? '',
  body: data.body ?? '',
})

const errorMessage = (err: unknown, fallback: string) =>
  err instanceof ApiClientError ? err.detail ?? err.message : fallback

export default function CommunicationsPanel({
  contactId,
  contactName,
  initialExpandId,
}: CommunicationsPanelProps) {
  const [adding, setAdding] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null)
  const [expandedIds, setExpandedIds] = useState<Set<number>>(
    initialExpandId !== undefined ? new Set([initialExpandId]) : new Set(),
  )
  const { success, error: toastError } = useToast()

  const commsQuery = useContactCommunications(contactId)
  const tagsQuery = useAllTags()
  const { add, update, remove } = useCommunicationMutations()

  const allTags = tagsQuery.data ?? []

  const communications = useMemo<Communication[]>(() => {
    const data = commsQuery.data ?? []
    return [...data].sort((a, b) => b.date.localeCompare(a.date))
  }, [commsQuery.data])

  useEffect(() => {
    if (commsQuery.isSuccess && initialExpandId !== undefined) {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          document
            .getElementById(`comm-${initialExpandId}`)
            ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
        })
      })
    }
  }, [commsQuery.isSuccess, initialExpandId])

  const toggleExpand = (id: number) =>
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const startAdding = () => {
    setEditingId(null)
    setAdding(true)
  }

  const startEditing = (id: number) => {
    setAdding(false)
    setEditingId(id)
  }

  const handleAdd = async (data: CommunicationCreateInput) => {
    try {
      await add.mutateAsync({ contactId, data: toPayload(data) })
      setAdding(false)
      success('Communication added')
    } catch (err) {
      toastError(errorMessage(err, 'Failed to add communication'))
    }
  }

  const handleUpdate = async (commId: number, data: CommunicationCreateInput) => {
    try {
      await update.mutateAsync({ contactId, commId, data: toPayload(data) })
      setEditingId(null)
      success('Communication updated')
    } catch (err) {
      toastError(errorMessage(err, 'Failed to update communication'))
    }
  }

  const handleDelete = async () => {
    if (deleteTarget === null) return
    try {
      await remove.mutateAsync({ contactId, commId: deleteTarget })
      success('Communication removed')
    } catch (err) {
      toastError(errorMessage(err, 'Failed to remove communication'))
    } finally {
      setDeleteTarget(null)
    }
  }

  let body: ReactNode
  if (commsQuery.isPending) {
    body = <LoadingSpinner />
  } else if (commsQuery.isError) {
    body = (
      <EmptyState
        action={
          <Button variant="link" size="sm" onClick={() => void commsQuery.refetch()}>
            Retry
          </Button>
        }
      >
        {errorMessage(commsQuery.error, "Couldn't load communications.")}
      </EmptyState>
    )
  } else if (communications.length === 0 && !adding) {
    body = <EmptyState>No communications yet.</EmptyState>
  } else {
    body = (
      <ul className={styles.list}>
        {adding && (
          <li className={cx(styles.item, styles.itemEditing)}>
            <CommunicationForm
              mode="add"
              initial={emptyDefaults()}
              allTags={allTags}
              onSubmit={handleAdd}
              onCancel={() => setAdding(false)}
            />
          </li>
        )}
        {communications.map((comm) => (
          <li
            key={comm.id}
            id={`comm-${comm.id}`}
            className={cx(styles.item, editingId === comm.id && styles.itemEditing)}
          >
            {editingId === comm.id ? (
              <CommunicationForm
                mode="edit"
                initial={fromCommunication(comm)}
                allTags={allTags}
                onSubmit={(data) => handleUpdate(comm.id, data)}
                onCancel={() => setEditingId(null)}
              />
            ) : (
              <CommunicationRow
                comm={comm}
                contactName={contactName}
                expanded={expandedIds.has(comm.id)}
                onToggle={() => toggleExpand(comm.id)}
                onEdit={() => startEditing(comm.id)}
                onDelete={() => setDeleteTarget(comm.id)}
              />
            )}
          </li>
        ))}
      </ul>
    )
  }

  return (
    <div className={styles.panel} id="communications">
      <SectionCard
        label="Communications"
        action={
          !adding && (
            <Button variant="link" size="sm" onClick={startAdding}>
              <Plus size={ICON_SIZE.sm} aria-hidden="true" />
              Add communication
            </Button>
          )
        }
      >
        {body}
      </SectionCard>

      {deleteTarget !== null && (
        <ConfirmDialog
          confirmLabel="Remove"
          message="Remove this communication?"
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
          busy={remove.isPending}
        />
      )}
    </div>
  )
}

// ─── Row ──────────────────────────────────────────────────────────────────────

interface CommunicationRowProps {
  comm: Communication
  contactName?: string
  expanded: boolean
  onToggle: () => void
  onEdit: () => void
  onDelete: () => void
}

function CommunicationRow({
  comm,
  contactName,
  expanded,
  onToggle,
  onEdit,
  onDelete,
}: CommunicationRowProps) {
  const bodyId = useId()
  const expandable = Boolean(comm.body)
  const TypeIcon = TYPE_ICON[comm.type] ?? MessageSquare
  const DirectionIcon = DIRECTION_ICON[comm.direction] ?? ArrowUpRight
  const incoming = comm.direction === 'received'
  const directionClass = incoming ? styles.incoming : styles.outgoing

  return (
    <>
      {/* Clicking anywhere on the row toggles it for mouse users; the chevron
          button is the keyboard / screen-reader control. */}
      <div
        className={cx(styles.row, expandable && styles.rowExpandable)}
        onClick={expandable ? onToggle : undefined}
      >
        {/* Direction at a glance: a coloured arrow tile leads every row. */}
        <span className={cx(styles.directionTile, directionClass)} aria-hidden="true">
          <DirectionIcon size={ICON_SIZE.md} />
        </span>
        <div className={styles.rowMain}>
          <div className={styles.meta}>
            <span className={styles.date}>{formatDate(comm.date)}</span>
            <span className={cx(styles.directionLabel, directionClass)}>
              {commDirectionLabel(comm.direction, contactName)}
            </span>
            <span className={styles.metaItem}>
              <TypeIcon size={ICON_SIZE.sm} aria-hidden="true" />
              {commLabel(COMM_TYPE_LABELS, comm.type)}
            </span>
            <CommStatusBadge status={comm.status} />
          </div>
          {!expanded && (comm.subject || comm.body) && (
            <p className={styles.summary}>
              {comm.subject && <strong className={styles.subject}>{comm.subject}</strong>}
              {comm.subject && comm.body && <span className={styles.sep}> · </span>}
              {comm.body && <span className={styles.preview}>{comm.body}</span>}
            </p>
          )}
        </div>
        <TagList tags={comm.tags ?? []} />
        <div className={styles.actions} onClick={(e) => e.stopPropagation()}>
          <IconButton icon={Pencil} label="Edit communication" onClick={onEdit} />
          <IconButton icon={Trash2} label="Delete communication" tone="danger" onClick={onDelete} />
          {expandable ? (
            <IconButton
              icon={ChevronDown}
              label={expanded ? 'Collapse message' : 'Expand message'}
              tone="neutral"
              aria-expanded={expanded}
              aria-controls={bodyId}
              className={cx(styles.chevron, expanded && styles.chevronOpen)}
              onClick={onToggle}
            />
          ) : (
            // Keeps edit/delete in the same place on every row.
            <span className={styles.chevronSlot} aria-hidden="true" />
          )}
        </div>
      </div>
      {expanded && expandable && (
        <div id={bodyId} className={styles.body}>
          {comm.subject && <p className={styles.bodySubject}>{comm.subject}</p>}
          <MarkdownContent>{comm.body}</MarkdownContent>
        </div>
      )}
    </>
  )
}

// ─── Form ─────────────────────────────────────────────────────────────────────

interface CommunicationFormProps {
  initial: CommunicationCreateInput
  allTags: string[]
  /** Add (new) or edit (existing) — sets the form's heading. */
  mode: 'add' | 'edit'
  onSubmit: (data: CommunicationCreateInput) => Promise<void>
  onCancel: () => void
}

/** Add / edit form, in the shared `EditForm` look used by every edit mode. */
function CommunicationForm({ initial, allTags, mode, onSubmit, onCancel }: CommunicationFormProps) {
  const id = useId()
  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<CommunicationCreateInput>({
    resolver: zodResolver(communicationCreateSchema),
    mode: 'onSubmit',
    defaultValues: initial,
  })

  return (
    <EditForm
      heading={mode === 'add' ? 'New communication' : 'Editing communication'}
      onSubmit={handleSubmit(onSubmit)}
      onCancel={onCancel}
      saving={isSubmitting}
    >
      <div className={form.fields}>
        <FormField label="Subject" htmlFor={`${id}-subject`}>
          <input
            id={`${id}-subject`}
            className={form.inputTitle}
            placeholder="Subject line"
            autoFocus
            {...register('subject')}
          />
        </FormField>
        <FormField label="Type" htmlFor={`${id}-type`} half>
          <select id={`${id}-type`} className={form.select} {...register('type')}>
            {COMM_TYPES.map((t) => (
              <option key={t} value={t}>{COMM_TYPE_LABELS[t]}</option>
            ))}
          </select>
        </FormField>
        <FormField label="Direction" htmlFor={`${id}-direction`} half>
          <select id={`${id}-direction`} className={form.select} {...register('direction')}>
            {COMM_DIRECTIONS.map((d) => (
              <option key={d} value={d}>{COMM_DIRECTION_LABELS[d]}</option>
            ))}
          </select>
        </FormField>
        <FormField label="Date" htmlFor={`${id}-date`} half error={errors.date}>
          <Controller
            control={control}
            name="date"
            render={({ field }) => (
              <DateInput
                id={`${id}-date`}
                className={form.input}
                value={field.value ?? ''}
                onChange={field.onChange}
                placeholder="YYYY-MM-DD"
                invalid={!!errors.date}
                days
              />
            )}
          />
        </FormField>
        <FormField label="Status" htmlFor={`${id}-status`} half>
          <select id={`${id}-status`} className={form.select} {...register('status')}>
            {COMM_STATUSES.map((s) => (
              <option key={s} value={s}>{COMM_STATUS_LABELS[s]}</option>
            ))}
          </select>
        </FormField>
        <FormField label="Body" htmlFor={`${id}-body`}>
          <Controller
            control={control}
            name="body"
            render={({ field }) => (
              <AutoResizeTextarea
                id={`${id}-body`}
                className={form.textarea}
                value={field.value ?? ''}
                onChange={field.onChange}
                placeholder="Message body..."
              />
            )}
          />
        </FormField>
        <FormField label="Tags">
          <Controller
            control={control}
            name="tags"
            render={({ field }) => (
              <TagInput value={field.value ?? []} onChange={field.onChange} availableTags={allTags} allowCreate />
            )}
          />
        </FormField>
      </div>
    </EditForm>
  )
}
