const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/

/**
 * Short, locale-aware date for list rows and metadata: "Oct 1, 2026".
 * A date-only value (`YYYY-MM-DD`) is a calendar day, not an instant: it is
 * read in local time so it never shifts a day for users west of UTC.
 */
export function formatDate(value: string): string {
  const m = DATE_ONLY.exec(value)
  const date = m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : new Date(value)
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}
