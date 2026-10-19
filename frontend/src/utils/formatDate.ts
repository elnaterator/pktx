/** Short, locale-aware date for list rows and metadata: "Oct 1, 2026". */
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}
