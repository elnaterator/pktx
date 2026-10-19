import type { ListEntry, SectionField, SectionMeta } from '../../types'

/** Form fields for a list section, in schema order (the entry `id` is omitted). */
export function fieldsOf(meta: SectionMeta): SectionField[] {
  return Object.entries(meta.schema.properties)
    .filter(([name]) => name !== 'id')
    .map(([name, prop]) => ({
      name,
      label: prop.title ?? name,
      widget: prop.widget ?? (prop.type === 'array' ? 'tags' : 'text'),
    }))
}

/** True for sections whose entries span a period (new entries go first). */
export function hasDateRange(fields: SectionField[]): boolean {
  return fields.some((f) => f.name === 'startDate') && fields.some((f) => f.name === 'endDate')
}

/** `2021-01 – Present`; an open end date means the entry is current. */
export function dateRange(entry: ListEntry): string {
  const start = typeof entry.startDate === 'string' ? entry.startDate : ''
  const end = typeof entry.endDate === 'string' ? entry.endDate : ''
  if (!start && !end) return ''
  return `${start || 'N/A'} – ${end || 'Present'}`
}

/**
 * List fields shown on their own line below an entry's other details (and as
 * their own row in the form) instead of inline with them.
 */
export const OWN_LINE_FIELDS: ReadonlySet<string> = new Set(['courses'])
