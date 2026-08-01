/**
 * Tests for the data export API module.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { fetchDataExport, saveBlob } from '../../services/api/export'

global.fetch = vi.fn()

const mockExportResponse = (
  { ok = true, status = 200, disposition = '' } = {} as {
    ok?: boolean
    status?: number
    disposition?: string
  }
) => {
  ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok,
    status,
    statusText: ok ? 'OK' : 'Server Error',
    headers: new Headers(disposition ? { 'content-disposition': disposition } : {}),
    blob: async () => new Blob(['{"resumes":[]}'], { type: 'application/json' }),
  })
}

describe('fetchDataExport', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches /api/export', async () => {
    mockExportResponse()

    await fetchDataExport()

    expect(global.fetch).toHaveBeenCalledWith('/api/export', undefined)
  })

  it('uses the filename the server asked for', async () => {
    mockExportResponse({
      disposition: 'attachment; filename="pktx-export-2026-07-31.json"',
    })

    const result = await fetchDataExport()

    expect(result.filename).toBe('pktx-export-2026-07-31.json')
  })

  it('falls back to a dated filename when the header is absent', async () => {
    mockExportResponse()

    const result = await fetchDataExport()

    expect(result.filename).toMatch(/^pktx-export-\d{4}-\d{2}-\d{2}\.json$/)
  })

  it('throws with the status when the server rejects the request', async () => {
    mockExportResponse({ ok: false, status: 500 })

    await expect(fetchDataExport()).rejects.toThrow('Export failed (HTTP 500)')
  })
})

describe('saveBlob', () => {
  it('clicks a download link and releases the object URL', () => {
    const createObjectURL = vi.fn(() => 'blob:fake')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL })
    const click = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(click)

    saveBlob(new Blob(['{}']), 'pktx-export-2026-07-31.json')

    expect(createObjectURL).toHaveBeenCalled()
    expect(click).toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:fake')
    expect(document.querySelector('a')).toBeNull()

    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })
})
