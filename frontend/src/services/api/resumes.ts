/**
 * Resume API: version CRUD plus edits to the JSON Resume document (`data`).
 */

import type {
  ApiSuccessResponse,
  Basics,
  ListEntry,
  Resume,
  ResumeVersion,
  ResumeVersionSummary,
  SectionMeta,
} from '../../types'
import { API_BASE, fetchWithErrorHandling, handleResponse } from './client'

const JSON_HEADERS = { 'Content-Type': 'application/json' }

function send(method: string, url: string, body?: unknown): Promise<Response> {
  return fetchWithErrorHandling(`${API_BASE}${url}`, {
    method,
    headers: JSON_HEADERS,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

// ─── Resume versions ──────────────────────────────────────────────────────────

/** List resume versions (summaries without the document). */
export async function listResumes(
  tags?: string[],
  q?: string
): Promise<ResumeVersionSummary[]> {
  const params = new URLSearchParams()
  if (tags && tags.length > 0) tags.forEach((t) => params.append('tag', t))
  if (q) params.set('q', q)
  const query = params.toString() ? `?${params.toString()}` : ''
  const response = await fetchWithErrorHandling(`${API_BASE}/resumes${query}`)
  return handleResponse<ResumeVersionSummary[]>(response)
}

/** Get one resume version with its full document. */
export async function getResumeVersion(id: number): Promise<ResumeVersion> {
  const response = await fetchWithErrorHandling(`${API_BASE}/resumes/${id}`)
  return handleResponse<ResumeVersion>(response)
}

/** Create a resume version: a copy of the default, or from a JSON Resume `data`. */
export async function createResume(label: string, data?: Resume): Promise<ResumeVersion> {
  return handleResponse<ResumeVersion>(await send('POST', '/resumes', { label, data }))
}

/** Update label, tags and/or the default flag. */
export async function updateResume(
  id: number,
  changes: { label?: string; tags?: string[]; is_default?: boolean }
): Promise<ResumeVersion> {
  return handleResponse<ResumeVersion>(await send('PATCH', `/resumes/${id}`, changes))
}

/** Delete a resume version. */
export async function deleteResume(id: number): Promise<ApiSuccessResponse> {
  const response = await fetchWithErrorHandling(`${API_BASE}/resumes/${id}`, {
    method: 'DELETE',
  })
  return handleResponse<ApiSuccessResponse>(response)
}

/** Per-section label, primary field and JSON Schema (with UI widget hints). */
export async function getResumeSchema(): Promise<SectionMeta[]> {
  const response = await fetchWithErrorHandling(`${API_BASE}/resumes/schema`)
  return handleResponse<SectionMeta[]>(response)
}

// ─── The JSON Resume document ─────────────────────────────────────────────────

/** Replace the whole document with a JSON Resume (import). */
export async function replaceResumeData(id: number, data: Resume): Promise<ResumeVersion> {
  return handleResponse<ResumeVersion>(await send('PUT', `/resumes/${id}/data`, data))
}

/** Partially update `basics` (`location` and `profiles` replace as a whole). */
export async function updateBasics(id: number, patch: Basics): Promise<Basics> {
  return handleResponse<Basics>(await send('PATCH', `/resumes/${id}/data/basics`, patch))
}

/** Add an entry; `position` is a 0-based index (default: the end). */
export async function addEntry(
  id: number,
  section: string,
  entry: Record<string, unknown>,
  position?: number
): Promise<ListEntry> {
  const query = position === undefined ? '' : `?position=${position}`
  return handleResponse<ListEntry>(await send('POST', `/resumes/${id}/data/${section}${query}`, entry))
}

/** Partially update an entry (a blank value clears a field). */
export async function updateEntry(
  id: number,
  section: string,
  entryId: string,
  patch: Record<string, unknown>
): Promise<ListEntry> {
  const url = `/resumes/${id}/data/${section}/${encodeURIComponent(entryId)}`
  return handleResponse<ListEntry>(await send('PATCH', url, patch))
}

/** Remove an entry. */
export async function removeEntry(
  id: number,
  section: string,
  entryId: string
): Promise<void> {
  const url = `${API_BASE}/resumes/${id}/data/${section}/${encodeURIComponent(entryId)}`
  const response = await fetchWithErrorHandling(url, { method: 'DELETE' })
  await handleResponse<void>(response)
}

/** Reorder a section: `ids` is every entry id of the section, in the new order. */
export async function reorderEntries(
  id: number,
  section: string,
  ids: string[]
): Promise<ListEntry[]> {
  return handleResponse<ListEntry[]>(await send('PUT', `/resumes/${id}/data/${section}/order`, { ids }))
}
