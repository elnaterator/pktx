import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import AppRoutes from '../router'
import * as api from '../services/api'

vi.mock('../services/api')
vi.mock('@clerk/clerk-react', () => ({
  useAuth: () => ({ getToken: vi.fn().mockResolvedValue('token') }),
  useUser: () => ({ user: { firstName: 'Test' } }),
  SignedIn: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  SignedOut: () => null,
}))

// Minimal mock data
const mockResumes = [{ id: 1, label: 'Test Resume', is_default: true, app_count: 0, created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z' }]
const mockResume = {
  id: 1,
  label: 'Test Resume',
  is_default: true,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  tags: [],
  links: {},
  data: {},
}

describe('Route: /', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.listResumes).mockResolvedValue(mockResumes)
    vi.mocked(api.listApplications).mockResolvedValue([])
    vi.mocked(api.listNotes).mockResolvedValue([])
    vi.mocked(api.listAccomplishments).mockResolvedValue([])
    vi.mocked(api.listContacts).mockResolvedValue([])
    vi.mocked(api.listAllTags).mockResolvedValue([])
  })

  it('renders HomeView at /', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <AppRoutes />
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(screen.getByText(/welcome back, test/i)).toBeInTheDocument()
    })
  })

  it('redirects unknown routes to /', async () => {
    render(
      <MemoryRouter initialEntries={['/unknown-route']}>
        <AppRoutes />
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(screen.getByText(/welcome back, test/i)).toBeInTheDocument()
    })
  })
})

describe('Route: /resumes', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.listResumes).mockResolvedValue(mockResumes)
  })

  it('renders ResumeListView at /resumes', async () => {
    render(
      <MemoryRouter initialEntries={['/resumes']}>
        <AppRoutes />
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(screen.getByTestId('resume-list-view')).toBeInTheDocument()
    })
  })
})

describe('Route: /resumes/:id', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getResumeVersion).mockResolvedValue(mockResume)
    vi.mocked(api.listAllTags).mockResolvedValue([])
  })

  it('renders ResumeDetailView at /resumes/1', async () => {
    render(
      <MemoryRouter initialEntries={['/resumes/1']}>
        <AppRoutes />
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(screen.getByTestId('resume-detail-view')).toBeInTheDocument()
    })
  })

  it('redirects /resumes/abc (invalid ID) to /resumes', async () => {
    vi.mocked(api.listResumes).mockResolvedValue(mockResumes)
    render(
      <MemoryRouter initialEntries={['/resumes/abc']}>
        <AppRoutes />
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(screen.getByTestId('resume-list-view')).toBeInTheDocument()
    })
  })

  it('shows NotFound for non-existent resume ID', async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const error = Object.assign(new Error('Not found'), { status: 404 }) as any
    vi.mocked(api.getResumeVersion).mockRejectedValue(error)
    render(
      <MemoryRouter initialEntries={['/resumes/999']}>
        <AppRoutes />
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(screen.getByTestId('not-found')).toBeInTheDocument()
    })
  })
})
