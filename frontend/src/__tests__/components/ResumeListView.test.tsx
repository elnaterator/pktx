import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import ResumeListView from '../../pages/resumes/ResumeListView'
import * as api from '../../services/api'
import type { ResumeVersionSummary } from '../../types'

vi.mock('../../services/api')

const mockVersions: ResumeVersionSummary[] = [
  {
    id: 1,
    label: 'Default Resume',
    is_default: true,
    app_count: 3,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 2,
    label: 'Senior Engineer Version',
    is_default: false,
    app_count: 1,
    created_at: '2024-02-01T00:00:00Z',
    updated_at: '2024-02-01T00:00:00Z',
  },
]

function renderView() {
  return render(
    <MemoryRouter>
      <ResumeListView />
    </MemoryRouter>
  )
}

describe('ResumeListView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading spinner while fetching', () => {
    vi.mocked(api.listResumes).mockReturnValue(new Promise(() => {}))
    renderView()
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
  })

  it('renders resume versions after loading', async () => {
    vi.mocked(api.listResumes).mockResolvedValue(mockVersions)
    renderView()
    await waitFor(() => {
      expect(screen.getByText('Default Resume')).toBeInTheDocument()
    })
    expect(screen.getByText('Senior Engineer Version')).toBeInTheDocument()
  })

  it('shows default badge on the default version', async () => {
    vi.mocked(api.listResumes).mockResolvedValue(mockVersions)
    renderView()
    await waitFor(() => {
      expect(screen.getByText('Default')).toBeInTheDocument()
    })
  })

  it('shows app count for each version', async () => {
    vi.mocked(api.listResumes).mockResolvedValue(mockVersions)
    renderView()
    await waitFor(() => {
      expect(screen.getByText(/3 applications/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/1 application$/)).toBeInTheDocument()
  })

  it('renders each version as a link to its detail page', async () => {
    vi.mocked(api.listResumes).mockResolvedValue(mockVersions)
    renderView()
    await waitFor(() => {
      expect(screen.getByText('Default Resume')).toBeInTheDocument()
    })
    const links = screen.getAllByRole('link')
    const resumeLinks = links.filter((l) => l.getAttribute('href')?.startsWith('/resumes/'))
    expect(resumeLinks.length).toBe(2)
    expect(resumeLinks[0]).toHaveAttribute('href', '/resumes/1')
    expect(resumeLinks[1]).toHaveAttribute('href', '/resumes/2')
  })

  it('shows Default badge only on default version', async () => {
    vi.mocked(api.listResumes).mockResolvedValue(mockVersions)
    renderView()
    await waitFor(() => {
      expect(screen.getByText('Senior Engineer Version')).toBeInTheDocument()
    })
    const defaultBadges = screen.getAllByText('Default')
    expect(defaultBadges.length).toBe(1)
  })

  it('shows empty state when no versions exist', async () => {
    vi.mocked(api.listResumes).mockResolvedValue([])
    renderView()
    await waitFor(() => {
      expect(screen.getByText(/no resume versions yet/i)).toBeInTheDocument()
    })
  })

  it('shows error message on fetch failure', async () => {
    vi.mocked(api.listResumes).mockRejectedValue(new Error('Server error'))
    renderView()
    await waitFor(() => {
      expect(screen.getByText(/couldn't load resume versions/i)).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })
})
