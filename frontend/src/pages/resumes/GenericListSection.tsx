import { useMemo, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { ICON_SIZE } from '../../theme'
import type { ListEntry, SectionField, SectionMeta } from '../../types'
import { EntryForm, type FieldConfig } from '../../components/EntryForm'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import SortableList from '../../components/SortableList'
import { ExternalLink } from '../../components/ExternalLink'
import { useToast } from '../../components/toast'
import { useResumeMutations } from '../../hooks/queries'
import { buildEntrySchema } from '../../schemas/resumeEntry'
import SectionHeader from './SectionHeader'
import { OWN_LINE_FIELDS, dateRange, fieldsOf, hasDateRange } from './sectionFields'
import { IconButton } from '../../components/IconButton'
import styles from './GenericListSection.module.css'

interface GenericListSectionProps {
  /** Section definition from `GET /api/resumes/schema`. */
  meta: SectionMeta
  entries: ListEntry[]
  versionId: number
  onUpdate?: () => void
  /** Open the add form straight away (the section was just added). */
  startAdding?: boolean
  /** Dismiss an empty section; offered only while it has no entries. */
  onClose?: () => void
}

type Mode = 'view' | 'add' | { type: 'edit'; id: string } | { type: 'delete'; id: string }
type FormValues = Record<string, string | string[]>

const SHORT = new Set(['text', 'url', 'tags', 'date', 'email'])
const PLACEHOLDERS: Record<string, string> = {
  date: 'YYYY-MM',
  url: 'https://…',
  email: 'name@example.com',
}

/** Schema fields -> form fields; short fields after the primary share a row. */
function toFieldConfigs(fields: SectionField[], primaryField: string): FieldConfig[] {
  return fields.map((f) => {
    const config: FieldConfig = {
      name: f.name,
      label: f.widget === 'tags' ? `${f.label} (comma separated)` : f.label,
      type:
        f.widget === 'textarea'
          ? 'textarea'
          : f.widget === 'bullets'
            ? 'highlights'
            : f.widget === 'date'
              ? 'date'
              : 'text',
      required: f.name === primaryField,
      placeholder: PLACEHOLDERS[f.widget] ?? f.label,
    }
    // Periods (start/end) are month-precise; single dates (awarded, issued) can name a day.
    if (f.widget === 'date') config.days = f.name !== 'startDate' && f.name !== 'endDate'
    if (f.name !== primaryField && SHORT.has(f.widget) && !OWN_LINE_FIELDS.has(f.name)) {
      config.group = 'meta'
    }
    return config
  })
}

function toFormValues(entry: ListEntry, fields: SectionField[]): FormValues {
  const values: FormValues = {}
  for (const f of fields) {
    const v = entry[f.name]
    if (f.widget === 'bullets') values[f.name] = Array.isArray(v) ? (v as string[]) : []
    else if (f.widget === 'tags') values[f.name] = Array.isArray(v) ? (v as string[]).join(', ') : ''
    else values[f.name] = typeof v === 'string' ? v : ''
  }
  return values
}

/** Form values -> API body; blank fields become null, which clears them on update. */
function toPayload(data: FormValues, fields: SectionField[]): Record<string, unknown> {
  const payload: Record<string, unknown> = {}
  for (const f of fields) {
    const v = data[f.name]
    if (f.widget === 'bullets') {
      payload[f.name] = ((v as string[] | undefined) ?? []).filter((b) => b.trim())
    } else if (f.widget === 'tags') {
      payload[f.name] = String(v ?? '').split(',').map((t) => t.trim()).filter(Boolean)
    } else {
      payload[f.name] = String(v ?? '').trim() || null
    }
  }
  return payload
}

function str(v: unknown): string {
  return typeof v === 'string' ? v : ''
}

function EntryView({
  meta,
  fields,
  entry,
}: {
  meta: SectionMeta
  fields: SectionField[]
  entry: ListEntry
}) {
  const ranged = hasDateRange(fields)
  const primary = str(entry[meta.primaryField])

  const metaParts: React.ReactNode[] = []
  for (const f of fields) {
    if (f.name === meta.primaryField) continue
    if (f.widget === 'textarea' || f.widget === 'bullets' || f.widget === 'url') continue
    if (ranged && (f.name === 'startDate' || f.name === 'endDate')) continue
    if (OWN_LINE_FIELDS.has(f.name)) continue
    const v = entry[f.name]
    const text = Array.isArray(v) ? (v as string[]).join(', ') : str(v)
    if (text) metaParts.push(text)
  }
  const range = ranged ? dateRange(entry) : ''
  if (range) {
    metaParts.push(
      <span key="dates" className={styles.entryDates}>
        {range}
      </span>,
    )
  }
  const url = fields.some((f) => f.name === 'url') ? str(entry.url) : ''
  const longText = fields.filter((f) => f.widget === 'textarea' && f.name !== meta.primaryField)
  const bullets = fields.filter((f) => f.widget === 'bullets')
  const ownLine = fields.filter((f) => OWN_LINE_FIELDS.has(f.name))

  return (
    <div className={styles.entryInfo}>
      <span className={styles.entryTitle}>{primary || meta.label}</span>
      {(metaParts.length > 0 || url) && (
        <span className={styles.entryMeta}>
          {metaParts.map((part, i) => (
            <span key={i}>
              {i > 0 && ' · '}
              {part}
            </span>
          ))}
          {url && (
            <>
              {metaParts.length > 0 && ' · '}
              <ExternalLink href={url} className={styles.entryLink}>
                {url.replace(/^https?:\/\//, '')}
              </ExternalLink>
            </>
          )}
        </span>
      )}
      {ownLine.map((f) => {
        const items = Array.isArray(entry[f.name]) ? (entry[f.name] as string[]) : []
        return items.length > 0 ? (
          <span key={f.name} className={styles.entryMeta}>
            {f.label}: {items.join(', ')}
          </span>
        ) : null
      })}
      {longText.map((f) =>
        str(entry[f.name]) ? (
          <p key={f.name} className={styles.entryText}>
            {str(entry[f.name])}
          </p>
        ) : null,
      )}
      {bullets.map((f) => {
        const items = Array.isArray(entry[f.name]) ? (entry[f.name] as string[]) : []
        return items.length > 0 ? (
          <ul key={f.name} className={styles.highlights}>
            {items.map((b, i) => (
              <li key={i} className={styles.highlight}>
                {b}
              </li>
            ))}
          </ul>
        ) : null
      })}
    </div>
  )
}

export default function GenericListSection({
  meta,
  entries,
  versionId,
  onUpdate,
  startAdding = false,
  onClose,
}: GenericListSectionProps) {
  const [mode, setMode] = useState<Mode>(startAdding ? 'add' : 'view')
  const { success, error } = useToast()
  const { addEntry, updateEntry, removeEntry, reorder } = useResumeMutations()

  const fields = useMemo(() => fieldsOf(meta), [meta])
  const fieldConfigs = useMemo(() => toFieldConfigs(fields, meta.primaryField), [fields, meta])
  const schema = useMemo(() => buildEntrySchema(fields, meta.primaryField), [fields, meta])
  const title = meta.label
  const noun = title.toLowerCase()
  // Period-based sections list the newest entry first.
  const newestFirst = hasDateRange(fields)

  const finish = (msg: string) => {
    success(msg)
    setMode('view')
    onUpdate?.()
  }

  const handleAdd = async (data: FormValues) => {
    try {
      await addEntry.mutateAsync({
        id: versionId,
        section: meta.key,
        data: toPayload(data, fields),
        position: newestFirst ? 0 : undefined,
      })
      finish(`${title} added successfully`)
    } catch {
      error(`Failed to add ${noun}`)
    }
  }

  const handleEdit = async (data: FormValues) => {
    if (typeof mode !== 'object' || mode.type !== 'edit') return
    try {
      await updateEntry.mutateAsync({
        id: versionId,
        section: meta.key,
        entryId: mode.id,
        data: toPayload(data, fields),
      })
      finish(`${title} updated successfully`)
    } catch {
      error(`Failed to update ${noun}`)
    }
  }

  const handleDelete = async () => {
    if (typeof mode !== 'object' || mode.type !== 'delete') return
    try {
      await removeEntry.mutateAsync({ id: versionId, section: meta.key, entryId: mode.id })
      finish(`${title} deleted successfully`)
    } catch {
      error(`Failed to delete ${noun}`)
      setMode('view')
    }
  }

  const handleReorder = async (ids: string[]) => {
    try {
      await reorder.mutateAsync({ id: versionId, section: meta.key, ids })
      onUpdate?.()
    } catch (e) {
      error(`Failed to reorder ${noun}`)
      throw e // the list snaps back to the saved order
    }
  }

  return (
    <section className={styles.container} data-testid={`${meta.key}-section`}>
      <SectionHeader title={title}>
        {mode === 'view' && (
          <>
            {entries.length === 0 && onClose && (
              <button type="button" data-quiet onClick={onClose}>
                Remove section
              </button>
            )}
            <button type="button" onClick={() => setMode('add')}>
              <Plus size={ICON_SIZE.sm} aria-hidden="true" /> Add {title}
            </button>
          </>
        )}
      </SectionHeader>

      {mode === 'add' && (
        <div className={styles.addForm}>
          <EntryForm
            fields={fieldConfigs}
            schema={schema}
            onSubmit={handleAdd}
            onCancel={() => {
              setMode('view')
              if (entries.length === 0) onClose?.()
            }}
          />
        </div>
      )}

      {entries.length > 0 ? (
        <SortableList
          className={styles.list}
          items={entries}
          getId={(entry) => entry.id as string}
          getLabel={(entry) => str(entry[meta.primaryField]) || noun}
          onReorder={handleReorder}
          renderItem={(entry, row) => {
            const entryId = entry.id as string
            if (typeof mode === 'object' && mode.type === 'edit' && mode.id === entryId) {
              return (
                <div ref={row.setNodeRef} style={row.style}>
                  <EntryForm
                    fields={fieldConfigs}
                    schema={schema}
                    defaultValues={toFormValues(entry, fields)}
                    onSubmit={handleEdit}
                    onCancel={() => setMode('view')}
                  />
                </div>
              )
            }
            return (
              <div ref={row.setNodeRef} style={row.style} className={styles.entry}>
                <div className={styles.entryHeader}>
                  <EntryView meta={meta} fields={fields} entry={entry} />
                  <div className={styles.entryActions}>
                    {row.handle}
                    <IconButton
                      icon={Pencil}
                      label={`Edit ${noun}`}
                      onClick={() => setMode({ type: 'edit', id: entryId })}
                    />
                    <IconButton
                      icon={Trash2}
                      label={`Delete ${noun}`}
                      tone="danger"
                      onClick={() => setMode({ type: 'delete', id: entryId })}
                    />
                  </div>
                </div>
              </div>
            )
          }}
        />
      ) : (
        mode !== 'add' && (
          <p className={styles.placeholder}>Nothing here yet — add your first entry.</p>
        )
      )}

      {typeof mode === 'object' && mode.type === 'delete' && (
        <ConfirmDialog
          confirmLabel="Delete"
          message={`Are you sure you want to delete this ${noun} entry?`}
          onConfirm={handleDelete}
          onCancel={() => setMode('view')}
        />
      )}
    </section>
  )
}
