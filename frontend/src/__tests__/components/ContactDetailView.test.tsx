import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import ContactDetailView from '../../pages/contacts/ContactDetailView'
import * as api from '../../services/api'
import type { Contact } from '../../types'

vi.mock('../../services/api')

const mockContact: Contact = {
  id: 1,
  name: 'Jane Doe',
  email: 'jane@example.com',
  phone: '+1 555 000 0000',
  company: 'Acme Corp',
  title: 'Senior Recruiter',
  relationship: 'Recruiter',
  linkedin_url: 'https://linkedin.com/in/janedoe',
  location: 'San Francisco, CA',
  last_contacted_date: '2026-04-01',
  followup_date: '2026-05-15',
  notes: 'Very helpful in the process.',
  tags: ['hiring', 'ml'],
  created_at: '2026-03-01T00:00:00Z',
  updated_at: '2026-04-01T10:00:00Z',
}

function renderView(id = '1') {
  return render(
    <MemoryRouter initialEntries={[`/contacts/${id}`]}>
      <Routes>
        <Route path="/contacts/:id" element={<ContactDetailView />} />
        <Route path="/contacts" element={<div data-testid="contact-list">list</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ContactDetailView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.listAllTags).mockResolvedValue([])
    vi.mocked(api.listContactCommunications).mockResolvedValue([])
  })

  it('renders contact name', async () => {
    vi.mocked(api.getContact).mockResolvedValue(mockContact)
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Jane Doe').length).toBeGreaterThan(0)
    })
  })

  it('renders structured fields', async () => {
    vi.mocked(api.getContact).mockResolvedValue(mockContact)
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Jane Doe').length).toBeGreaterThan(0)
    })
    expect(screen.getByText('jane@example.com')).toBeInTheDocument()
    expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    expect(screen.getByText('Senior Recruiter')).toBeInTheDocument()
  })

  it('renders notes content', async () => {
    vi.mocked(api.getContact).mockResolvedValue(mockContact)
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Jane Doe').length).toBeGreaterThan(0)
    })
    expect(screen.getByText(/Very helpful/)).toBeInTheDocument()
  })

  it('shows tags', async () => {
    vi.mocked(api.getContact).mockResolvedValue(mockContact)
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Jane Doe').length).toBeGreaterThan(0)
    })
    const tagBadges = document.querySelectorAll('[class*="tagBadge"]')
    const tagTexts = Array.from(tagBadges).map((el) => el.textContent)
    expect(tagTexts).toContain('hiring')
    expect(tagTexts).toContain('ml')
  })

  it('edit button switches to edit mode with pre-populated name', async () => {
    const user = userEvent.setup()
    vi.mocked(api.getContact).mockResolvedValue(mockContact)
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Jane Doe').length).toBeGreaterThan(0)
    })
    await user.click(screen.getByRole('button', { name: /^Edit (accomplishment|contact|note)$/i }))
    const nameInput = screen.getByDisplayValue('Jane Doe')
    expect(nameInput).toBeInTheDocument()
  })

  it('save calls updateContact with edited fields', async () => {
    const user = userEvent.setup()
    vi.mocked(api.getContact).mockResolvedValue(mockContact)
    vi.mocked(api.updateContact).mockResolvedValue({ ...mockContact, name: 'Jane Updated' })
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Jane Doe').length).toBeGreaterThan(0)
    })
    await user.click(screen.getByRole('button', { name: /^Edit (accomplishment|contact|note)$/i }))
    const nameInput = screen.getByDisplayValue('Jane Doe')
    await user.clear(nameInput)
    await user.type(nameInput, 'Jane Updated')
    await user.click(screen.getByRole('button', { name: /Save/i }))
    await waitFor(() => {
      expect(api.updateContact).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ name: 'Jane Updated' })
      )
    })
  })

  it('shows confirm dialog on delete click', async () => {
    const user = userEvent.setup()
    vi.mocked(api.getContact).mockResolvedValue(mockContact)
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Jane Doe').length).toBeGreaterThan(0)
    })
    await user.click(screen.getByRole('button', { name: /Delete/i }))
    expect(screen.getByText(/Delete this contact/i)).toBeInTheDocument()
  })

  it('calls deleteContact and navigates on confirm', async () => {
    const user = userEvent.setup()
    vi.mocked(api.getContact).mockResolvedValue(mockContact)
    vi.mocked(api.deleteContact).mockResolvedValue({ message: 'Deleted' })
    renderView()
    await waitFor(() => {
      expect(screen.getAllByText('Jane Doe').length).toBeGreaterThan(0)
    })
    await user.click(screen.getByRole('button', { name: /Delete/i }))
    const confirmBtn = screen.getByRole('button', { name: /^Confirm$/i })
    await user.click(confirmBtn)
    await waitFor(() => {
      expect(api.deleteContact).toHaveBeenCalledWith(1)
    })
    await waitFor(() => {
      expect(screen.getByTestId('contact-list')).toBeInTheDocument()
    })
  })

  it('shows not found for missing contact', async () => {
    vi.mocked(api.getContact).mockRejectedValue({ status: 404 })
    renderView()
    await waitFor(() => {
      expect(screen.getByText(/Contact not found/i)).toBeInTheDocument()
    })
  })
})
