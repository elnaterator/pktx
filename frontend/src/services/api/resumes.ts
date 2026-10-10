/**
 * Resume and resume version API endpoints.
 */

import type {
  Resume,
  ContactInfo,
  WorkExperience,
  Education,
  Skill,
  ResumeVersion,
  ResumeVersionSummary,
  LayoutItem,
  SectionMeta,
  ApiSuccessResponse,
} from '../../types'
import { API_BASE, fetchWithErrorHandling, handleResponse } from './client'

/**
 * Get the full resume
 */
export async function getResume(): Promise<Resume> {
  const response = await fetchWithErrorHandling(`${API_BASE}/resume`)
  return handleResponse<Resume>(response)
}

/**
 * Get a specific section of the resume
 */
export async function getSection(
  section: 'contact' | 'summary' | 'experience' | 'education' | 'skills'
): Promise<ContactInfo | string | WorkExperience[] | Education[] | Skill[]> {
  const response = await fetchWithErrorHandling(`${API_BASE}/resume/${section}`)
  return handleResponse(response)
}

/**
 * Update resume contact information
 */
export async function updateResumeContact(
  data: Partial<ContactInfo>
): Promise<ApiSuccessResponse> {
  const response = await fetchWithErrorHandling(`${API_BASE}/resume/contact`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  return handleResponse<ApiSuccessResponse>(response)
}

/**
 * Update summary text
 */
export async function updateSummary(text: string): Promise<ApiSuccessResponse> {
  const response = await fetchWithErrorHandling(`${API_BASE}/resume/summary`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ text }),
  })
  return handleResponse<ApiSuccessResponse>(response)
}

/**
 * Add a new entry to a list-based section
 */
export async function addEntry(
  section: 'experience' | 'education' | 'skills',
  data: WorkExperience | Education | Skill
): Promise<ApiSuccessResponse> {
  const response = await fetchWithErrorHandling(`${API_BASE}/resume/${section}/entries`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  return handleResponse<ApiSuccessResponse>(response)
}

/**
 * Update an existing entry in a list-based section
 */
export async function updateEntry(
  section: 'experience' | 'education' | 'skills',
  index: number,
  data: Partial<WorkExperience | Education | Skill>
): Promise<ApiSuccessResponse> {
  const response = await fetchWithErrorHandling(
    `${API_BASE}/resume/${section}/entries/${index}`,
    {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }
  )
  return handleResponse<ApiSuccessResponse>(response)
}

/**
 * Remove an entry from a list-based section
 */
export async function removeEntry(
  section: 'experience' | 'education' | 'skills',
  index: number
): Promise<ApiSuccessResponse> {
  const response = await fetchWithErrorHandling(
    `${API_BASE}/resume/${section}/entries/${index}`,
    {
      method: 'DELETE',
    }
  )
  return handleResponse<ApiSuccessResponse>(response)
}

// ─── Resume version API ───────────────────────────────────────────────────────

/**
 * List all resume versions (summaries without full resume data)
 */
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

/**
 * Get a single resume version by ID (includes full resume_data)
 */
export async function getResumeVersion(id: number): Promise<ResumeVersion> {
  const response = await fetchWithErrorHandling(`${API_BASE}/resumes/${id}`)
  return handleResponse<ResumeVersion>(response)
}

/**
 * Get the default resume version
 */
export async function getDefaultResume(): Promise<ResumeVersion> {
  const response = await fetchWithErrorHandling(`${API_BASE}/resumes/default`)
  return handleResponse<ResumeVersion>(response)
}

/**
 * Create a new resume version by cloning the current default
 */
export async function createResume(label: string): Promise<ResumeVersion> {
  const response = await fetchWithErrorHandling(`${API_BASE}/resumes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label }),
  })
  return handleResponse<ResumeVersion>(response)
}

/**
 * Delete a resume version
 */
export async function deleteResume(id: number): Promise<ApiSuccessResponse> {
  const response = await fetchWithErrorHandling(`${API_BASE}/resumes/${id}`, {
    method: 'DELETE',
  })
  return handleResponse<ApiSuccessResponse>(response)
}

/**
 * Set a resume version as the default
 */
export async function setDefaultResume(id: number): Promise<ApiSuccessResponse> {
  const response = await fetchWithErrorHandling(`${API_BASE}/resumes/${id}/default`, {
    method: 'POST',
  })
  return handleResponse<ApiSuccessResponse>(response)
}

/**
 * Update the label and/or tags of a resume version
 */
export async function updateResumeLabel(
  id: number,
  label: string,
  tags?: string[]
): Promise<ResumeVersion> {
  const body: Record<string, unknown> = { label }
  if (tags !== undefined) body.tags = tags
  const response = await fetchWithErrorHandling(`${API_BASE}/resumes/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return handleResponse<ResumeVersion>(response)
}

/**
 * Update contact info for a specific resume version
 */
export async function updateVersionContact(
  versionId: number,
  data: Partial<ContactInfo>
): Promise<ApiSuccessResponse> {
  const response = await fetchWithErrorHandling(
    `${API_BASE}/resumes/${versionId}/contact`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }
  )
  return handleResponse<ApiSuccessResponse>(response)
}

/**
 * Update summary for a specific resume version
 */
export async function updateVersionSummary(
  versionId: number,
  text: string
): Promise<ApiSuccessResponse> {
  const response = await fetchWithErrorHandling(
    `${API_BASE}/resumes/${versionId}/summary`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }
  )
  return handleResponse<ApiSuccessResponse>(response)
}

/**
 * Add an entry to a version-scoped section
 */
export async function addVersionEntry(
  versionId: number,
  section: string,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any
): Promise<ApiSuccessResponse> {
  const response = await fetchWithErrorHandling(
    `${API_BASE}/resumes/${versionId}/${section}/entries`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }
  )
  return handleResponse<ApiSuccessResponse>(response)
}

/**
 * Update an entry in a version-scoped section
 */
export async function updateVersionEntry(
  versionId: number,
  section: string,
  /** Stable entry id (a legacy 0-based index is also accepted by the API). */
  entryRef: string | number,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any
): Promise<ApiSuccessResponse> {
  const response = await fetchWithErrorHandling(
    `${API_BASE}/resumes/${versionId}/${section}/entries/${encodeURIComponent(entryRef)}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }
  )
  return handleResponse<ApiSuccessResponse>(response)
}

/**
 * Remove an entry from a version-scoped section
 */
export async function removeVersionEntry(
  versionId: number,
  section: string,
  entryRef: string | number
): Promise<ApiSuccessResponse> {
  const response = await fetchWithErrorHandling(
    `${API_BASE}/resumes/${versionId}/${section}/entries/${encodeURIComponent(entryRef)}`,
    { method: 'DELETE' }
  )
  return handleResponse<ApiSuccessResponse>(response)
}

/**
 * Section registry (field definitions for every list section)
 */
export async function listResumeSections(): Promise<SectionMeta[]> {
  const response = await fetchWithErrorHandling(`${API_BASE}/resume-sections`)
  return handleResponse<SectionMeta[]>(response)
}

/**
 * Replace the section order / visibility / titles of a version
 */
export async function updateVersionLayout(
  versionId: number,
  layout: LayoutItem[]
): Promise<{ layout: LayoutItem[] }> {
  const response = await fetchWithErrorHandling(
    `${API_BASE}/resumes/${versionId}/layout`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ layout }),
    }
  )
  return handleResponse<{ layout: LayoutItem[] }>(response)
}

/**
 * Add a user-defined section; resolves to its `custom:<id>` key
 */
export async function addCustomSection(
  versionId: number,
  title: string
): Promise<{ section: string }> {
  const response = await fetchWithErrorHandling(
    `${API_BASE}/resumes/${versionId}/custom-sections`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    }
  )
  return handleResponse<{ section: string }>(response)
}

/**
 * Delete a user-defined section (`customId` is the part after `custom:`)
 */
export async function removeCustomSection(
  versionId: number,
  customId: string
): Promise<ApiSuccessResponse> {
  const response = await fetchWithErrorHandling(
    `${API_BASE}/resumes/${versionId}/custom-sections/${encodeURIComponent(customId)}`,
    { method: 'DELETE' }
  )
  return handleResponse<ApiSuccessResponse>(response)
}
