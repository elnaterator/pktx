import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import ApplicationListView from '../../pages/applications/ApplicationListView'
import * as api from '../../services/api'
import type { Application } from '../../types'

vi.mock('../../services/api')

const mockApplications: Application[] = [
  {
    id: 1,
    company: 'Acme Corp',
    position: 'Software Engineer',
    description: 'Great job',
    status: 'Applied',
    url: 'https://acme.com/job',
    notes: 'Looks promising',
    tags: ['python', 'backend'],
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-15T00:00:00Z',
    links: {},
  },
  {
    id: 2,
    company: 'Globex',
    position: 'Senior Engineer',
    description: '',
    status: 'Interview',
    url: null,
    notes: '',
    tags: [],
    created_at: '2024-02-01T00:00:00Z',
    updated_at: '2024-02-10T00:00:00Z',
    links: {},
  },
]

function renderView() {
  return render(
    <MemoryRouter>
      <ApplicationListView />
    </MemoryRouter>
  )
}

describe('ApplicationListView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.listAllTags).mockResolvedValue([])
    vi.mocked(api.listResumes).mockResolvedValue([])
  })

  it('shows loading spinner while fetching', () => {
    vi.mocked(api.listApplications).mockReturnValue(new Promise(() => {}))
    renderView()
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
  })

  it('renders applications after loading', async () => {
    vi.mocked(api.listApplications).mockResolvedValue(mockApplications)
    renderView()
    await waitFor(() => {
      expect(screen.getByText('Software Engineer')).toBeInTheDocument()
    })
    expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    expect(screen.getByText('Senior Engineer')).toBeInTheDocument()
    expect(screen.getByText('Globex')).toBeInTheDocument()
  })

  it('shows status badges for each application', async () => {
    vi.mocked(api.listApplications).mockResolvedValue(mockApplications)
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Applied').length).toBeGreaterThan(0)
    })
    expect(screen.getAllByText('Interview').length).toBeGreaterThan(0)
  })

  it('renders each application as a link to its detail page', async () => {
    vi.mocked(api.listApplications).mockResolvedValue(mockApplications)
    renderView()
    await waitFor(() => {
      expect(screen.getByText('Software Engineer')).toBeInTheDocument()
    })
    const links = screen.getAllByRole('link')
    const appLinks = links.filter((l) => l.getAttribute('href')?.startsWith('/applications/'))
    expect(appLinks.length).toBe(2)
    expect(appLinks[0]).toHaveAttribute('href', '/applications/1')
    expect(appLinks[1]).toHaveAttribute('href', '/applications/2')
  })

  it('shows empty state when no applications exist', async () => {
    vi.mocked(api.listApplications).mockResolvedValue([])
    renderView()
    await waitFor(() => {
      expect(screen.getByText(/no applications yet/i)).toBeInTheDocument()
    })
  })

  it('shows error message on fetch failure', async () => {
    vi.mocked(api.listApplications).mockRejectedValue(new Error('Server error'))
    renderView()
    await waitFor(() => {
      expect(screen.getByText(/couldn't load applications/i)).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('shows New Application button', async () => {
    vi.mocked(api.listApplications).mockResolvedValue([])
    renderView()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /new application/i })).toBeInTheDocument()
    })
  })

  it('toggles new application form when button is clicked', async () => {
    const user = userEvent.setup()
    vi.mocked(api.listApplications).mockResolvedValue([])
    renderView()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /new application/i })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /new application/i }))
    expect(screen.getByLabelText(/company \*/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/position \*/i)).toBeInTheDocument()
  })

  it('renders status filter dropdown', async () => {
    vi.mocked(api.listApplications).mockResolvedValue([])
    renderView()
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /filter by status/i })).toBeInTheDocument()
    })
  })

  it('renders search input', async () => {
    vi.mocked(api.listApplications).mockResolvedValue([])
    renderView()
    await waitFor(() => {
      expect(screen.getByRole('textbox')).toBeInTheDocument()
    })
  })

  it('renders tag badges on applications', async () => {
    vi.mocked(api.listApplications).mockResolvedValue(mockApplications)
    renderView()
    await waitFor(() => {
      expect(screen.getByText('python')).toBeInTheDocument()
    })
    expect(screen.getByText('backend')).toBeInTheDocument()
  })

  it('populates tag autocomplete from listAllTags', async () => {
    vi.mocked(api.listApplications).mockResolvedValue([])
    vi.mocked(api.listAllTags).mockResolvedValue(['python', 'backend', 'react'])
    renderView()
    await waitFor(() => {
      expect(api.listAllTags).toHaveBeenCalled()
    })
  })

  it('selects multiple statuses as chips and filters by all of them', async () => {
    const user = userEvent.setup()
    vi.mocked(api.listApplications).mockResolvedValue([])
    renderView()

    const combobox = await screen.findByRole('combobox', { name: /filter by status/i })
    await user.click(combobox)
    await user.click(await screen.findByRole('option', { name: 'Applied' }))
    await user.click(await screen.findByRole('option', { name: 'Interview' }))

    expect(screen.getByRole('button', { name: /remove applied/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /remove interview/i })).toBeInTheDocument()
    await waitFor(() => {
      expect(api.listApplications).toHaveBeenLastCalledWith(
        ['Applied', 'Interview'],
        undefined,
        undefined
      )
    })
  })

  it('removes a status chip via its remove button', async () => {
    const user = userEvent.setup()
    vi.mocked(api.listApplications).mockResolvedValue([])
    renderView()

    const combobox = await screen.findByRole('combobox', { name: /filter by status/i })
    await user.click(combobox)
    await user.click(await screen.findByRole('option', { name: 'Applied' }))
    expect(screen.getByRole('button', { name: /remove applied/i })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /remove applied/i }))

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /remove applied/i })).not.toBeInTheDocument()
    })
    await waitFor(() => {
      expect(api.listApplications).toHaveBeenLastCalledWith(undefined, undefined, undefined)
    })
  })

  it('pre-filters by the statuses in the URL and ignores unknown ones', async () => {
    vi.mocked(api.listApplications).mockResolvedValue(mockApplications)
    render(
      <MemoryRouter initialEntries={['/applications?status=Applied&status=Interview&status=Bogus']}>
        <ApplicationListView />
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(api.listApplications).toHaveBeenCalledWith(['Applied', 'Interview'], undefined, undefined)
    })
    // The filter shows the URL's statuses as removable chips.
    expect(screen.getByRole('button', { name: 'Remove Applied' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove Interview' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remove Bogus' })).not.toBeInTheDocument()
  })
})
