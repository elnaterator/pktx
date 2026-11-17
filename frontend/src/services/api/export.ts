/**
 * File downloads: the full data export, resume PDFs and note (letter) PDFs.
 */

import { API_BASE, fetchWithErrorHandling, ApiClientError } from './client'

export interface DataExport {
  blob: Blob
  filename: string
}

const FILENAME_PATTERN = /filename="?([^";]+)"?/

/**
 * GET a file from the API. Returns the blob plus the filename the server asked
 * for (else `fallback`), so the caller can save it without re-deriving the name.
 */
async function fetchDownload(path: string, what: string, fallback: string): Promise<DataExport> {
  const response = await fetchWithErrorHandling(`${API_BASE}${path}`)
  if (!response.ok) {
    throw new ApiClientError(
      `${what} failed (HTTP ${response.status})`,
      response.status,
      response.statusText
    )
  }
  const match = FILENAME_PATTERN.exec(response.headers.get('content-disposition') ?? '')
  return { blob: await response.blob(), filename: match ? match[1] : fallback }
}

/** Download the signed-in user's full data export as a JSON blob. */
export function fetchDataExport(): Promise<DataExport> {
  const today = new Date().toISOString().slice(0, 10)
  return fetchDownload('/export', 'Export', `pktx-export-${today}.json`)
}

/** Download one resume version rendered as a PDF (server default style unless given). */
export function fetchResumePdf(id: number, theme?: string): Promise<DataExport> {
  const query = theme ? `?${new URLSearchParams({ theme })}` : ''
  return fetchDownload(`/resumes/${id}/pdf${query}`, 'PDF export', `resume-${id}.pdf`)
}

/** Today in the browser's time zone as `YYYY-MM-DD`. */
function localDate(now = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

/**
 * Download one note rendered as a letter PDF, headed by the default resume's
 * name and contact details and dated today (the reader's local date).
 */
export function fetchNotePdf(id: number, theme?: string): Promise<DataExport> {
  const query = new URLSearchParams({ ...(theme ? { theme } : {}), date: localDate() })
  return fetchDownload(`/notes/${id}/pdf?${query}`, 'PDF export', `note-${id}.pdf`)
}

/**
 * Save a blob to the user's disk under the given filename.
 */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
