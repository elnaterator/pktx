/**
 * Tests for the new job application API functions.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import * as api from '../../services/api'

// Mock fetch globally
global.fetch = vi.fn()

const mockFetch = (data: unknown, ok = true, status = 200) => {
  ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok,
    status,
    statusText: ok ? 'OK' : 'Error',
    json: async () => data,
  })
}

describe('Resume Version API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('listResumes', () => {
    it('fetches /api/resumes', async () => {
      mockFetch([])
      await api.listResumes()
      expect(global.fetch).toHaveBeenCalledWith('/api/resumes', undefined)
    })
  })

  describe('getResumeVersion', () => {
    it('fetches /api/resumes/:id', async () => {
      mockFetch({ id: 1, label: 'Main' })
      await api.getResumeVersion(1)
      expect(global.fetch).toHaveBeenCalledWith('/api/resumes/1', undefined)
    })
  })

  describe('createResume', () => {
    it('sends POST to /api/resumes with label', async () => {
      mockFetch({ id: 2, label: 'New Version' })
      await api.createResume('New Version')
      expect(global.fetch).toHaveBeenCalledWith('/api/resumes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label: 'New Version' }),
      })
    })

    it('can start from a JSON Resume document', async () => {
      mockFetch({ id: 2 })
      await api.createResume('Imported', { basics: { name: 'Ada' } })
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/resumes',
        expect.objectContaining({
          body: JSON.stringify({ label: 'Imported', data: { basics: { name: 'Ada' } } }),
        }),
      )
    })
  })

  describe('deleteResume', () => {
    it('sends DELETE to /api/resumes/:id', async () => {
      mockFetch({ message: 'Deleted' })
      await api.deleteResume(3)
      expect(global.fetch).toHaveBeenCalledWith('/api/resumes/3', { method: 'DELETE' })
    })
  })

  describe('updateResume', () => {
    it('sends PATCH with only the changes', async () => {
      mockFetch({ id: 1, label: 'Updated Label' })
      await api.updateResume(1, { label: 'Updated Label' })
      expect(global.fetch).toHaveBeenCalledWith('/api/resumes/1', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label: 'Updated Label' }),
      })
    })

    it('sets the default through is_default', async () => {
      mockFetch({ id: 2, is_default: true })
      await api.updateResume(2, { is_default: true })
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/resumes/2',
        expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ is_default: true }) }),
      )
    })
  })

  describe('getResumeSchema', () => {
    it('fetches /api/resumes/schema', async () => {
      mockFetch([])
      await api.getResumeSchema()
      expect(global.fetch).toHaveBeenCalledWith('/api/resumes/schema', undefined)
    })
  })

  describe('replaceResumeData', () => {
    it('sends PUT to /api/resumes/:id/data', async () => {
      mockFetch({ id: 1 })
      await api.replaceResumeData(1, { basics: { name: 'Jane' } })
      expect(global.fetch).toHaveBeenCalledWith('/api/resumes/1/data', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ basics: { name: 'Jane' } }),
      })
    })
  })

  describe('updateBasics', () => {
    it('sends PATCH to /api/resumes/:id/data/basics', async () => {
      mockFetch({ name: 'Jane' })
      await api.updateBasics(1, { name: 'Jane' })
      expect(global.fetch).toHaveBeenCalledWith('/api/resumes/1/data/basics', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Jane' }),
      })
    })
  })

  describe('addEntry', () => {
    it('sends POST to the section endpoint', async () => {
      mockFetch({ id: 'e1' })
      const data = { name: 'Languages', keywords: ['Go'] }
      await api.addEntry(1, 'skills', data)
      expect(global.fetch).toHaveBeenCalledWith('/api/resumes/1/data/skills', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
    })

    it('passes the insert position as a query parameter', async () => {
      mockFetch({ id: 'e1' })
      await api.addEntry(1, 'work', { name: 'Acme' }, 0)
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/resumes/1/data/work?position=0',
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  describe('updateEntry', () => {
    it('sends PATCH to the entry endpoint by id', async () => {
      mockFetch({ id: 'e 1' })
      await api.updateEntry(1, 'skills', 'e 1', { name: 'Updated' })
      expect(global.fetch).toHaveBeenCalledWith('/api/resumes/1/data/skills/e%201', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Updated' }),
      })
    })
  })

  describe('removeEntry', () => {
    it('sends DELETE and accepts 204 No Content', async () => {
      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        status: 204,
        statusText: 'No Content',
        json: async () => {
          throw new Error('no body')
        },
      })
      await expect(api.removeEntry(1, 'work', 'w1')).resolves.toBeUndefined()
      expect(global.fetch).toHaveBeenCalledWith('/api/resumes/1/data/work/w1', {
        method: 'DELETE',
      })
    })

    it('throws the API error detail on failure', async () => {
      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: async () => ({ detail: 'Resume work entry not found' }),
      })
      await expect(api.removeEntry(1, 'work', 'zz')).rejects.toThrow(
        'Resume work entry not found',
      )
    })
  })

  describe('reorderEntries', () => {
    it('sends PUT with the full id order', async () => {
      mockFetch([])
      await api.reorderEntries(1, 'work', ['b', 'a'])
      expect(global.fetch).toHaveBeenCalledWith('/api/resumes/1/data/work/order', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: ['b', 'a'] }),
      })
    })
  })
})

describe('Application API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('listApplications', () => {
    it('fetches /api/applications without params', async () => {
      mockFetch([])
      await api.listApplications()
      expect(global.fetch).toHaveBeenCalledWith('/api/applications', undefined)
    })

    it('fetches with status filter', async () => {
      mockFetch([])
      await api.listApplications(['Applied'])
      expect(global.fetch).toHaveBeenCalledWith('/api/applications?status=Applied', undefined)
    })

    it('fetches with multiple statuses', async () => {
      mockFetch([])
      await api.listApplications(['Applied', 'Interview'])
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/applications?status=Applied&status=Interview',
        undefined
      )
    })

    it('fetches with search query', async () => {
      mockFetch([])
      await api.listApplications(undefined, 'google')
      expect(global.fetch).toHaveBeenCalledWith('/api/applications?q=google', undefined)
    })

    it('fetches with both status and query', async () => {
      mockFetch([])
      await api.listApplications(['Applied'], 'google')
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/applications?status=Applied&q=google',
        undefined
      )
    })
  })

  describe('getApplication', () => {
    it('fetches /api/applications/:id', async () => {
      mockFetch({ id: 5 })
      await api.getApplication(5)
      expect(global.fetch).toHaveBeenCalledWith('/api/applications/5', undefined)
    })
  })

  describe('createApplication', () => {
    it('sends POST with application data', async () => {
      const data = { company: 'Acme', position: 'Engineer', status: 'Applied' }
      mockFetch({ id: 1, ...data })
      await api.createApplication(data)
      expect(global.fetch).toHaveBeenCalledWith('/api/applications', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
    })
  })

  describe('updateApplication', () => {
    it('sends PATCH with updated fields', async () => {
      const data = { status: 'Interview' }
      mockFetch({ id: 1, ...data })
      await api.updateApplication(1, data)
      expect(global.fetch).toHaveBeenCalledWith('/api/applications/1', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
    })
  })

  describe('deleteApplication', () => {
    it('sends DELETE to /api/applications/:id', async () => {
      mockFetch({ message: 'Deleted' })
      await api.deleteApplication(3)
      expect(global.fetch).toHaveBeenCalledWith('/api/applications/3', { method: 'DELETE' })
    })
  })
})

