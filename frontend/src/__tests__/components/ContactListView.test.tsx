import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import ContactListView from '../../pages/contacts/ContactListView'
import * as api from '../../services/api'
import type { ContactSummary } from '../../types'

vi.mock('../../services/api')

const mockSummaries: ContactSummary[] = [
  {
    id: 1,
    name: 'Jane Doe',
    company: 'Acme',
    title: 'Recruiter',
    relationship: 'Recruiter',
    followup_date: null,
    tags: ['hiring'],
    updated_at: '2026-04-01T10:00:00Z',
  },
  {
    id: 2,
    name: 'Bob Smith',
    company: null,
    title: null,
    relationship: 'Peer',
    followup_date: '2026-05-15',
    tags: [],
    updated_at: '2026-03-28T10:00:00Z',
  },
]

function renderView() {
  return render(
    <MemoryRouter>
      <ContactListView />
    </MemoryRouter>
  )
}

describe('ContactListView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.listAllTags).mockResolvedValue([])
  })

  it('renders contacts after loading', async () => {
    vi.mocked(api.listContacts).mockResolvedValue(mockSummaries)
    renderView()
    await waitFor(() => {
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    })
    expect(screen.getByText('Bob Smith')).toBeInTheDocument()
  })

  it('shows empty state when no contacts', async () => {
    vi.mocked(api.listContacts).mockResolvedValue([])
    renderView()
    expect(await screen.findByText(/No contacts yet/i)).toBeInTheDocument()
    expect(screen.queryByText('Jane Doe')).not.toBeInTheDocument()
  })

  it('renders each contact as a link to its detail page', async () => {
    vi.mocked(api.listContacts).mockResolvedValue(mockSummaries)
    renderView()
    await waitFor(() => {
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    })
    const links = screen.getAllByRole('link')
    const contactLinks = links.filter((l) => l.getAttribute('href')?.startsWith('/contacts/'))
    expect(contactLinks.length).toBe(2)
    expect(contactLinks[0]).toHaveAttribute('href', '/contacts/1')
    expect(contactLinks[1]).toHaveAttribute('href', '/contacts/2')
  })

  it('shows relationship badge when present', async () => {
    vi.mocked(api.listContacts).mockResolvedValue(mockSummaries)
    renderView()
    await waitFor(() => {
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    })
    expect(screen.getByText('Recruiter')).toBeInTheDocument()
    expect(screen.getByText('Peer')).toBeInTheDocument()
  })

  it('shows followup_date when present', async () => {
    vi.mocked(api.listContacts).mockResolvedValue(mockSummaries)
    renderView()
    await waitFor(() => {
      expect(screen.getByText('Bob Smith')).toBeInTheDocument()
    })
    expect(screen.getByText(/Follow up:.*2026-05-15/)).toBeInTheDocument()
  })

  it('has New Contact button that reveals create form', async () => {
    const user = userEvent.setup()
    vi.mocked(api.listContacts).mockResolvedValue([])
    renderView()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /New Contact/i })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /New Contact/i }))
    expect(screen.getByLabelText(/Name/i)).toBeInTheDocument()
  })

  it('submitting with no name shows an error', async () => {
    const user = userEvent.setup()
    vi.mocked(api.listContacts).mockResolvedValue([])
    renderView()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /New Contact/i })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /New Contact/i }))
    const saveButton = screen.getByRole('button', { name: /^Save$/i })
    await user.click(saveButton)
    expect(screen.getByText(/Name.*required|required.*Name/i)).toBeInTheDocument()
  })

  it('calls createContact and reloads list on valid submit', async () => {
    const user = userEvent.setup()
    vi.mocked(api.listContacts).mockResolvedValue([])
    vi.mocked(api.createContact).mockResolvedValue({
      id: 99,
      name: 'New Person',
      notes: '',
      tags: [],
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })
    renderView()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /New Contact/i })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /New Contact/i }))
    await user.type(screen.getByLabelText(/^Name/i), 'New Person')
    await user.click(screen.getByRole('button', { name: /^Save$/i }))
    await waitFor(() => {
      expect(api.createContact).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'New Person' })
      )
    })
  })
})
