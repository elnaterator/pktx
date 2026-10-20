import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import HomeView from '../../pages/home/index'
import * as api from '../../services/api'
import { renderWithQuery } from '../test-utils'
import type { Application } from '../../types'

vi.mock('../../services/api')
vi.mock('@clerk/clerk-react', () => ({
  useUser: () => ({ user: null }),
  APIKeys: () => null,
}))

const app = (id: number, status: string) =>
  ({ id, status, company: `C${id}`, position: 'Eng', tags: [], updated_at: '2026-01-01' }) as unknown as Application

describe('HomeView — applications stat card', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.listResumes).mockResolvedValue([])
    vi.mocked(api.listNotes).mockResolvedValue([])
    vi.mocked(api.listAccomplishments).mockResolvedValue([])
    vi.mocked(api.listContacts).mockResolvedValue([])
    vi.mocked(api.listAllTags).mockResolvedValue([])
    vi.mocked(api.globalSearch).mockResolvedValue([])
  })

  it('links the active count to the applications list filtered to active statuses', async () => {
    vi.mocked(api.listApplications).mockResolvedValue([
      app(1, 'Applied'),
      app(2, 'Interview'),
      app(3, 'Rejected'),
      app(4, 'Accepted'),
    ])
    renderWithQuery(
      <MemoryRouter>
        <HomeView />
      </MemoryRouter>,
    )
    const link = await screen.findByRole('link', { name: '2 active' })
    const url = new URL(link.getAttribute('href')!, 'http://x')
    expect(url.pathname).toBe('/applications')
    expect(url.searchParams.getAll('status')).toEqual([
      'Interested',
      'Applied',
      'Phone Screen',
      'Interview',
      'Offer',
    ])
    expect(screen.getByRole('link', { name: /^Applications/ })).toHaveAttribute('href', '/applications')
  })
})
