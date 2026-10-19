import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import NoteDetailView from '../../pages/notes/NoteDetailView'
import * as api from '../../services/api'
import type { Note } from '../../types'

vi.mock('../../services/api')

const mockNote: Note = {
  id: 1,
  title: 'Python async patterns',
  content: 'Key learnings from building async services with asyncio and FastAPI.',
  tags: ['python', 'async'],
  created_at: '2026-03-26T10:00:00Z',
  updated_at: '2026-03-26T14:30:00Z',
}

function renderView(id = '1') {
  return render(
    <MemoryRouter initialEntries={[`/notes/${id}`]}>
      <Routes>
        <Route path="/notes/:id" element={<NoteDetailView />} />
        <Route path="/notes" element={<div data-testid="note-list">list</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('NoteDetailView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.listAllTags).mockResolvedValue([])
  })

  it('renders note title and content', async () => {
    vi.mocked(api.getNote).mockResolvedValue(mockNote)
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Python async patterns').length).toBeGreaterThan(0)
    })
    expect(screen.getByText(/Key learnings/)).toBeInTheDocument()
  })

  it('shows tags', async () => {
    vi.mocked(api.getNote).mockResolvedValue(mockNote)
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Python async patterns').length).toBeGreaterThan(0)
    })
    const tagBadges = document.querySelectorAll('[class*="tagBadge"]')
    const tagTexts = Array.from(tagBadges).map((el) => el.textContent)
    expect(tagTexts).toContain('python')
    expect(tagTexts).toContain('async')
  })

  it('edit button switches to edit mode with pre-populated fields', async () => {
    const user = userEvent.setup()
    vi.mocked(api.getNote).mockResolvedValue(mockNote)
    vi.mocked(api.listNoteTags).mockResolvedValue(['python', 'async'])
    vi.mocked(api.listAccomplishmentTags).mockResolvedValue([])
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Python async patterns').length).toBeGreaterThan(0)
    })
    await user.click(screen.getByRole('button', { name: /^Edit (accomplishment|contact|note)$/i }))
    const titleInput = screen.getByDisplayValue('Python async patterns')
    expect(titleInput).toBeInTheDocument()
  })

  it('cancel reverts to view mode without saving', async () => {
    const user = userEvent.setup()
    vi.mocked(api.getNote).mockResolvedValue(mockNote)
    vi.mocked(api.listNoteTags).mockResolvedValue(['python', 'async'])
    vi.mocked(api.listAccomplishmentTags).mockResolvedValue([])
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Python async patterns').length).toBeGreaterThan(0)
    })
    await user.click(screen.getByRole('button', { name: /^Edit (accomplishment|contact|note)$/i }))
    await user.click(screen.getByRole('button', { name: /Cancel/i }))
    expect(screen.queryByDisplayValue('Python async patterns')).not.toBeInTheDocument()
    expect(api.updateNote).not.toHaveBeenCalled()
  })

  it('save calls updateNote and shows updated data', async () => {
    const user = userEvent.setup()
    vi.mocked(api.getNote).mockResolvedValue(mockNote)
    vi.mocked(api.listNoteTags).mockResolvedValue(['python', 'async'])
    vi.mocked(api.listAccomplishmentTags).mockResolvedValue([])
    vi.mocked(api.updateNote).mockResolvedValue({
      ...mockNote,
      content: 'Updated content.',
    })
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Python async patterns').length).toBeGreaterThan(0)
    })
    await user.click(screen.getByRole('button', { name: /^Edit (accomplishment|contact|note)$/i }))
    const contentField = screen.getByDisplayValue(/Key learnings/)
    await user.clear(contentField)
    await user.type(contentField, 'Updated content.')
    await user.click(screen.getByRole('button', { name: /Save/i }))
    await waitFor(() => {
      expect(api.updateNote).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ content: 'Updated content.' })
      )
    })
  })

  it('delete button with confirmation navigates to /notes', async () => {
    const user = userEvent.setup()
    vi.mocked(api.getNote).mockResolvedValue(mockNote)
    vi.mocked(api.deleteNote).mockResolvedValue({ message: 'Deleted' })
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Python async patterns').length).toBeGreaterThan(0)
    })
    await user.click(screen.getByRole('button', { name: /Delete/i }))
    await waitFor(() => {
      expect(screen.getByText(/Delete this note/i)).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /Confirm|Yes/i }))
    await waitFor(() => {
      expect(api.deleteNote).toHaveBeenCalledWith(1)
      expect(screen.getByTestId('note-list')).toBeInTheDocument()
    })
  })

  it('redirects to /notes for non-numeric ID', async () => {
    vi.mocked(api.listNotes).mockResolvedValue([])
    vi.mocked(api.listNoteTags).mockResolvedValue([])
    vi.mocked(api.listAccomplishmentTags).mockResolvedValue([])
    render(
      <MemoryRouter initialEntries={['/notes/abc']}>
        <Routes>
          <Route path="/notes/:id" element={<NoteDetailView />} />
          <Route path="/notes" element={<div data-testid="note-list">list</div>} />
        </Routes>
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(screen.getByTestId('note-list')).toBeInTheDocument()
    })
  })
})
