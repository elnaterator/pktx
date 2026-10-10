import { useMemo, useState } from 'react'
import { Pencil, Trash2 } from 'lucide-react'
import type { ListEntry, SectionField, SectionMeta } from '../../types'
import { EntryForm, type FieldConfig } from '../../components/EntryForm'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { ExternalLink } from '../../components/ExternalLink'
import { useToast } from '../../components/toast'
import { useResumeMutations } from '../../hooks/queries'
import { buildEntrySchema } from '../../schemas/resumeEntry'
import { sortEntriesByDate } from './sortEntriesByDate'
import styles from './GenericListSection.module.css'

interface GenericListSectionProps {
  /** Registry definition; `custom` is reused for every user-defined section. */
  meta: SectionMeta
  /** Key used in API paths: a built-in section key or `custom:<id>`. */
  sectionKey: string
  /** Display title (layout override or registry label). */
  title: string
  entries: ListEntry[]
  versionId: number
  onUpdate?: () => void
}

type Mode = 'view' | 'add' | { type: 'edit'; ref: string | number } | { type: 'delete'; ref: string | number }
type FormValues = Record<string, string | string[]>

const SHORT = new Set(['text', 'url', 'tags'])

/** Registry fields -> form fields; short fields after the primary share a row. */
function toFieldConfigs(meta: SectionMeta): FieldConfig[] {
  return meta.fields.map((f) => {
    const config: FieldConfig = {
      name: f.name,
      label: f.widget === 'tags' ? `${f.label} (comma separated)` : f.label,
      type: f.widget === 'textarea' ? 'textarea' : f.widget === 'bullets' ? 'highlights' : 'text',
      required: f.required,
      placeholder: f.label,
    }
    if (f.name !== meta.primary_field && SHORT.has(f.widget)) config.group = 'meta'
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

function toPayload(data: FormValues, fields: SectionField[]): Record<string, unknown> {
  const payload: Record<string, unknown> = {}
  for (const f of fields) {
    const v = data[f.name]
    if (f.widget === 'bullets') payload[f.name] = (v as string[] | undefined) ?? []
    else if (f.widget === 'tags') {
      payload[f.name] = String(v ?? '').split(',').map((t) => t.trim()).filter(Boolean)
    } else {
      const text = String(v ?? '').trim()
      payload[f.name] = f.required ? text : text || null
    }
  }
  return payload
}

function str(v: unknown): string {
  return typeof v === 'string' ? v : ''
}

function EntryView({ meta, entry }: { meta: SectionMeta; entry: ListEntry }) {
  const byName = new Map(meta.fields.map((f) => [f.name, f]))
  const primary = str(entry[meta.primary_field ?? ''])
  const hasDates = byName.has('start_date') && byName.has('end_date')

  const metaParts: React.ReactNode[] = []
  for (const f of meta.fields) {
    if (f.name === meta.primary_field || f.widget === 'textarea' || f.widget === 'bullets') continue
    if (f.widget === 'url') continue
    if (hasDates && (f.name === 'start_date' || f.name === 'end_date')) continue
    const v = entry[f.name]
    const text = f.widget === 'tags' ? (Array.isArray(v) ? (v as string[]).join(', ') : '') : str(v)
    if (text) metaParts.push(text)
  }
  if (hasDates && (entry.start_date || entry.end_date)) {
    metaParts.push(
      <span key="dates" className={styles.entryDates}>
        {str(entry.start_date) || 'N/A'} – {str(entry.end_date) || 'Present'}
      </span>,
    )
  }
  const url = byName.has('url') ? str(entry.url) : ''
  const longText = meta.fields.filter((f) => f.widget === 'textarea' && f.name !== meta.primary_field)
  const bullets = Array.isArray(entry.highlights) ? (entry.highlights as string[]) : []

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
      {longText.map((f) =>
        str(entry[f.name]) ? (
          <p key={f.name} className={styles.entryText}>
            {str(entry[f.name])}
          </p>
        ) : null,
      )}
      {bullets.length > 0 && (
        <ul className={styles.highlights}>
          {bullets.map((b, i) => (
            <li key={i} className={styles.highlight}>
              {b}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function GenericListSection({
  meta,
  sectionKey,
  title,
  entries,
  versionId,
  onUpdate,
}: GenericListSectionProps) {
  const [mode, setMode] = useState<Mode>('view')
  const { success, error } = useToast()
  const { addEntry, updateEntry, removeEntry } = useResumeMutations()

  const fieldConfigs = useMemo(() => toFieldConfigs(meta), [meta])
  const schema = useMemo(() => buildEntrySchema(meta.fields), [meta])
  const noun = title.toLowerCase()
  const dated = meta.fields.some((f) => f.name === 'end_date')

  // Stable id when present; legacy entries (no id) fall back to their index.
  const refOf = (entry: ListEntry, index: number): string | number => entry.id ?? index
  const rows = dated
    ? sortEntriesByDate(entries as unknown as { start_date: string | null; end_date: string | null }[]).map(
        ({ index }) => ({ entry: entries[index], index }),
      )
    : entries.map((entry, index) => ({ entry, index }))

  const finish = (msg: string) => {
    success(msg)
    setMode('view')
    onUpdate?.()
  }

  const handleAdd = async (data: FormValues) => {
    try {
      await addEntry.mutateAsync({ id: versionId, section: sectionKey, data: toPayload(data, meta.fields) })
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
        section: sectionKey,
        entryRef: mode.ref,
        data: toPayload(data, meta.fields),
      })
      finish(`${title} updated successfully`)
    } catch {
      error(`Failed to update ${noun}`)
    }
  }

  const handleDelete = async () => {
    if (typeof mode !== 'object' || mode.type !== 'delete') return
    try {
      await removeEntry.mutateAsync({ id: versionId, section: sectionKey, entryRef: mode.ref })
      finish(`${title} deleted successfully`)
    } catch {
      error(`Failed to delete ${noun}`)
      setMode('view')
    }
  }

  return (
    <section className={styles.container} data-testid={`${meta.key}-section`}>
      <h2 className={styles.sectionLabel}>{title}</h2>

      {entries.length > 0 ? (
        <div className={styles.list}>
          {rows.map(({ entry, index }) => {
            const ref = refOf(entry, index)
            if (typeof mode === 'object' && mode.type === 'edit' && mode.ref === ref) {
              return (
                <EntryForm
                  key={ref}
                  fields={fieldConfigs}
                  schema={schema}
                  defaultValues={toFormValues(entry, meta.fields)}
                  onSubmit={handleEdit}
                  onCancel={() => setMode('view')}
                />
              )
            }
            return (
              <div key={ref} className={styles.entry}>
                <div className={styles.entryHeader}>
                  <EntryView meta={meta} entry={entry} />
                  <div className={styles.entryActions}>
                    <button
                      className={styles.editButton}
                      onClick={() => setMode({ type: 'edit', ref })}
                      aria-label={`Edit ${noun}`}
                    >
                      <Pencil size={13} />
                    </button>
                    <button
                      className={styles.deleteButton}
                      onClick={() => setMode({ type: 'delete', ref })}
                      aria-label={`Delete ${noun}`}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        mode !== 'add' && <p className={styles.placeholder}>Nothing here yet — add your first entry.</p>
      )}

      {mode === 'add' && (
        <EntryForm
          fields={fieldConfigs}
          schema={schema}
          onSubmit={handleAdd}
          onCancel={() => setMode('view')}
        />
      )}

      {mode === 'view' && (
        <button className={styles.addButton} onClick={() => setMode('add')}>
          Add {title}
        </button>
      )}

      {typeof mode === 'object' && mode.type === 'delete' && (
        <ConfirmDialog
          message={`Are you sure you want to delete this ${noun} entry?`}
          onConfirm={handleDelete}
          onCancel={() => setMode('view')}
        />
      )}
    </section>
  )
}
