/**
 * File downloads: the full data export and resume PDFs.
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

/** Download one resume version rendered as a PDF. */
export function fetchResumePdf(id: number): Promise<DataExport> {
  return fetchDownload(`/resumes/${id}/pdf`, 'PDF export', `resume-${id}.pdf`)
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
