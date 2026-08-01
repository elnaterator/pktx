/**
 * Data export endpoint.
 */

import { API_BASE, fetchWithErrorHandling, ApiClientError } from './client'

export interface DataExport {
  blob: Blob
  filename: string
}

const FILENAME_PATTERN = /filename="?([^";]+)"?/

/**
 * Download the signed-in user's full data export as a JSON blob.
 *
 * Returns the blob plus the filename the server asked for, so the caller can
 * trigger a download without re-deriving the name.
 */
export async function fetchDataExport(): Promise<DataExport> {
  const response = await fetchWithErrorHandling(`${API_BASE}/export`)
  if (!response.ok) {
    throw new ApiClientError(
      `Export failed (HTTP ${response.status})`,
      response.status,
      response.statusText
    )
  }

  const disposition = response.headers.get('content-disposition') ?? ''
  const match = FILENAME_PATTERN.exec(disposition)
  const today = new Date().toISOString().slice(0, 10)

  return {
    blob: await response.blob(),
    filename: match ? match[1] : `pktx-export-${today}.json`,
  }
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
