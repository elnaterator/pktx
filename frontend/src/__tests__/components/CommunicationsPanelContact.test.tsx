import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CommunicationsPanel from '../../components/CommunicationsPanel'
import * as api from '../../services/api'
import type { Communication } from '../../types'

vi.mock('../../services/api')

const mockComm: Communication = {
  id: 1,
  contact_ref_id: 42,
  type: 'email',
  direction: 'sent',
  subject: 'Hello',
  body: 'Test body',
  date: '2025-04-01',
  status: 'sent',
  tags: ['outreach'],
  created_at: '2025-04-01T00:00:00Z',
}

function renderPanel(contactId = 42) {
  return render(<CommunicationsPanel contactId={contactId} />)
}

describe('CommunicationsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.listAllTags).mockResolvedValue(['outreach', 'followup'])
    vi.mocked(api.listContactCommunications).mockResolvedValue([mockComm])
  })

  it('lists communications for a contact', async () => {
    renderPanel()
    await waitFor(() => {
      expect(screen.getByText('Hello')).toBeInTheDocument()
    })
    expect(screen.getByText('Test body')).toBeInTheDocument()
    expect(api.listContactCommunications).toHaveBeenCalledWith(42)
  })

  it('renders tag chips on comm row', async () => {
    renderPanel()
    await waitFor(() => {
      expect(screen.getByText('outreach')).toBeInTheDocument()
    })
  })

  it('add form calls addContactCommunication', async () => {
    const user = userEvent.setup()
    vi.mocked(api.addContactCommunication).mockResolvedValue({
      ...mockComm,
      id: 2,
      subject: 'New',
    })
    vi.mocked(api.listContactCommunications)
      .mockResolvedValueOnce([mockComm])
      .mockResolvedValue([mockComm, { ...mockComm, id: 2, subject: 'New' }])

    renderPanel()
    await waitFor(() => expect(screen.getByText('Hello')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /Add Communication/i }))
    const subjectInput = screen.getByPlaceholderText('Subject line')
    await user.clear(subjectInput)
    await user.type(subjectInput, 'New')
    const bodyTextarea = screen.getByPlaceholderText('Message body...')
    await user.type(bodyTextarea, 'body text')
    await user.click(screen.getByRole('button', { name: /Save/i }))

    await waitFor(() => {
      expect(api.addContactCommunication).toHaveBeenCalledWith(
        42,
        expect.objectContaining({ subject: 'New' })
      )
    })
  })

  it('delete calls removeContactCommunication', async () => {
    const user = userEvent.setup()
    vi.mocked(api.removeContactCommunication).mockResolvedValue({ message: 'ok' })
    vi.mocked(api.listContactCommunications)
      .mockResolvedValueOnce([mockComm])
      .mockResolvedValue([])

    renderPanel()
    await waitFor(() => expect(screen.getByText('Hello')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /Delete communication/i }))
    await user.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Remove' }))

    await waitFor(() => {
      expect(api.removeContactCommunication).toHaveBeenCalledWith(42, 1)
    })
  })

  it('shows a spinner, not the empty message, while loading', () => {
    vi.mocked(api.listContactCommunications).mockReturnValue(new Promise(() => {}))
    renderPanel()
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
    expect(screen.queryByText('No communications yet.')).not.toBeInTheDocument()
  })

  it('shows readable labels instead of raw enum values', async () => {
    vi.mocked(api.listContactCommunications).mockResolvedValue([
      { ...mockComm, type: 'interview_note', direction: 'received', status: 'ready' },
    ])
    renderPanel()
    expect(await screen.findByText('Interview note')).toBeInTheDocument()
    expect(screen.getByText('Incoming')).toBeInTheDocument()
    expect(screen.getByText('Ready')).toBeInTheDocument()
    expect(screen.queryByText('interview_note')).not.toBeInTheDocument()
  })

  it('expands and collapses the message from a keyboard-operable button', async () => {
    const user = userEvent.setup()
    renderPanel()
    const toggle = await screen.findByRole('button', { name: 'Expand message' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    toggle.focus()
    await user.keyboard('{Enter}')
    const collapse = screen.getByRole('button', { name: 'Collapse message' })
    expect(collapse).toHaveAttribute('aria-expanded', 'true')
    expect(document.getElementById(collapse.getAttribute('aria-controls')!)).toHaveTextContent('Test body')
  })

  it('opens edit mode prefilled and cancels it with Escape', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(await screen.findByRole('button', { name: 'Edit communication' }))
    const subject = screen.getByRole('textbox', { name: 'Subject' })
    expect(subject).toHaveValue('Hello')
    expect(screen.getByLabelText('Date')).toHaveValue('2025-04-01')
    expect(screen.getByLabelText('Type')).toHaveDisplayValue('Email')
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('textbox', { name: 'Subject' })).not.toBeInTheDocument()
    expect(screen.getByText('Hello')).toBeInTheDocument()
  })

  it('labels direction with the contact name so sent and received read at a glance', async () => {
    vi.mocked(api.listContactCommunications).mockResolvedValue([
      { ...mockComm, id: 1, direction: 'sent' },
      { ...mockComm, id: 2, direction: 'received', subject: 'Re: Hello' },
    ])
    render(<CommunicationsPanel contactId={42} contactName="Jane Doe" />)
    expect(await screen.findByText('To Jane')).toBeInTheDocument()
    expect(screen.getByText('From Jane')).toBeInTheDocument()
  })
})
