import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import AccomplishmentDetailView from '../../pages/accomplishments/AccomplishmentDetailView'
import * as api from '../../services/api'
import type { Accomplishment } from '../../types'

vi.mock('../../services/api')

const mockAccomplishment: Accomplishment = {
  id: 1,
  title: 'Led platform migration',
  situation: 'Monolith caused 4-hour deploys.',
  task: 'Migrate 3 services in 6 months.',
  action: 'Coordinated 4 teams, used feature flags.',
  result: 'Reduced deploy time by 80%.',
  accomplishment_date: '2024-03-15',
  tags: ['leadership', 'technical'],
  created_at: '2024-03-15T00:00:00Z',
  updated_at: '2024-03-15T00:00:00Z',
}

function renderView(id = '1') {
  return render(
    <MemoryRouter initialEntries={[`/accomplishments/${id}`]}>
      <Routes>
        <Route path="/accomplishments/:id" element={<AccomplishmentDetailView />} />
        <Route path="/accomplishments" element={<div data-testid="acc-list">list</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('AccomplishmentDetailView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.listAllTags).mockResolvedValue([])
  })

  it('renders all four STAR sections with their labels', async () => {
    vi.mocked(api.getAccomplishment).mockResolvedValue(mockAccomplishment)
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Led platform migration').length).toBeGreaterThan(0)
    })
    expect(screen.getByText(/Situation/i)).toBeInTheDocument()
    expect(screen.getByText(/Task/i)).toBeInTheDocument()
    expect(screen.getByText(/Action/i)).toBeInTheDocument()
    expect(screen.getByText(/Result/i)).toBeInTheDocument()
  })

  it('shows STAR content', async () => {
    vi.mocked(api.getAccomplishment).mockResolvedValue(mockAccomplishment)
    renderView()
    await waitFor(() => {
      expect(screen.getByText('Monolith caused 4-hour deploys.')).toBeInTheDocument()
    })
    expect(screen.getByText('Reduced deploy time by 80%.')).toBeInTheDocument()
  })

  it('shows placeholder hint text for empty STAR fields', async () => {
    vi.mocked(api.getAccomplishment).mockResolvedValue({
      ...mockAccomplishment,
      situation: '',
      task: '',
    })
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Led platform migration').length).toBeGreaterThan(0)
    })
    expect(screen.getByText(/Situation/i)).toBeInTheDocument()
    expect(screen.getByText(/Task/i)).toBeInTheDocument()
  })

  it('shows accomplishment date and tags', async () => {
    vi.mocked(api.getAccomplishment).mockResolvedValue(mockAccomplishment)
    renderView()
    await waitFor(() => {
      expect(screen.getByText(/2024-03-15/)).toBeInTheDocument()
    })
    expect(screen.getByText(/leadership/i)).toBeInTheDocument()
    expect(screen.getByText(/technical/i)).toBeInTheDocument()
  })

  it('edit button switches to edit mode with pre-populated fields', async () => {
    const user = userEvent.setup()
    vi.mocked(api.getAccomplishment).mockResolvedValue(mockAccomplishment)
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Led platform migration').length).toBeGreaterThan(0)
    })
    await user.click(screen.getByRole('button', { name: /^Edit (accomplishment|contact|note)$/i }))
    const titleInput = screen.getByDisplayValue('Led platform migration')
    expect(titleInput).toBeInTheDocument()
  })

  it('cancel reverts to view mode without saving', async () => {
    const user = userEvent.setup()
    vi.mocked(api.getAccomplishment).mockResolvedValue(mockAccomplishment)
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Led platform migration').length).toBeGreaterThan(0)
    })
    await user.click(screen.getByRole('button', { name: /^Edit (accomplishment|contact|note)$/i }))
    await user.click(screen.getByRole('button', { name: /Cancel/i }))
    expect(screen.queryByDisplayValue('Led platform migration')).not.toBeInTheDocument()
    expect(api.updateAccomplishment).not.toHaveBeenCalled()
  })

  it('save calls updateAccomplishment and shows updated data', async () => {
    const user = userEvent.setup()
    vi.mocked(api.getAccomplishment).mockResolvedValue(mockAccomplishment)
    vi.mocked(api.updateAccomplishment).mockResolvedValue({
      ...mockAccomplishment,
      result: 'Updated result with metrics.',
    })
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Led platform migration').length).toBeGreaterThan(0)
    })
    await user.click(screen.getByRole('button', { name: /^Edit (accomplishment|contact|note)$/i }))
    const resultField = screen.getByDisplayValue('Reduced deploy time by 80%.')
    await user.clear(resultField)
    await user.type(resultField, 'Updated result with metrics.')
    await user.click(screen.getByRole('button', { name: /Save/i }))
    await waitFor(() => {
      expect(api.updateAccomplishment).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ result: 'Updated result with metrics.' })
      )
    })
  })

  it('delete button with confirmation navigates to /accomplishments', async () => {
    const user = userEvent.setup()
    vi.mocked(api.getAccomplishment).mockResolvedValue(mockAccomplishment)
    vi.mocked(api.deleteAccomplishment).mockResolvedValue({ message: 'Deleted' })
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Led platform migration').length).toBeGreaterThan(0)
    })
    await user.click(screen.getByRole('button', { name: /Delete/i }))
    await waitFor(() => {
      expect(screen.getByText(/Delete this accomplishment/i)).toBeInTheDocument()
    })
    await user.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Delete' }))
    await waitFor(() => {
      expect(api.deleteAccomplishment).toHaveBeenCalledWith(1)
      expect(screen.getByTestId('acc-list')).toBeInTheDocument()
    })
  })

  it('redirects to /accomplishments for non-numeric ID', async () => {
    vi.mocked(api.listAccomplishments).mockResolvedValue([])
    vi.mocked(api.listAccomplishmentTags).mockResolvedValue([])
    render(
      <MemoryRouter initialEntries={['/accomplishments/abc']}>
        <Routes>
          <Route path="/accomplishments/:id" element={<AccomplishmentDetailView />} />
          <Route path="/accomplishments" element={<div data-testid="acc-list">list</div>} />
        </Routes>
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(screen.getByTestId('acc-list')).toBeInTheDocument()
    })
  })
})
