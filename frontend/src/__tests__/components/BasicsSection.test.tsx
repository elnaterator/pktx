import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BasicsSection from '../../pages/resumes/BasicsSection'
import type { Basics } from '../../types'
import * as api from '../../services/api'
import { renderWithQuery } from '../test-utils'

vi.mock('../../services/api')

const full: Basics = {
  name: 'Jane Smith',
  label: 'Staff Engineer',
  email: 'jane@example.com',
  phone: '555-9876',
  url: 'https://janesmith.com',
  summary: 'Builds **reliable** systems.',
  location: { address: '1 Main St', city: 'New York', region: 'NY', countryCode: 'US' },
  profiles: [
    { id: 'p1', network: 'LinkedIn', url: 'https://linkedin.com/in/janesmith' },
    { id: 'p2', network: 'Matrix', username: '@jane:hs.org' },
  ],
}

const VERSION = 3

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.updateBasics).mockResolvedValue({})
})

const renderEditable = (basics: Basics, onUpdate = vi.fn()) =>
  renderWithQuery(<BasicsSection basics={basics} versionId={VERSION} onUpdate={onUpdate} />)

const startEditing = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole('button', { name: /edit basics/i }))
}

const save = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole('button', { name: /save basics/i }))
}

describe('BasicsSection profiles header', () => {
  it('labels the profile links with a Profiles heading', () => {
    renderWithQuery(<BasicsSection basics={full} versionId={VERSION} />)
    const heading = screen.getByRole('heading', { level: 3, name: 'Profiles' })
    expect(heading.parentElement).toContainElement(screen.getByRole('link', { name: 'LinkedIn' }))
    // Email, website and the rest are not profiles.
    expect(heading.parentElement).not.toContainElement(screen.getByRole('link', { name: 'Website' }))
  })

  it('shows no Profiles heading without profiles', () => {
    renderWithQuery(<BasicsSection basics={{ name: 'Jane' }} versionId={VERSION} />)
    expect(screen.queryByRole('heading', { name: 'Profiles' })).not.toBeInTheDocument()
  })

  it('puts Add profile at the top right of the Profiles header when editing', async () => {
    const user = userEvent.setup()
    renderEditable({ name: 'Jane' })
    await user.click(screen.getByRole('button', { name: /edit basics/i }))
    const heading = screen.getByRole('heading', { level: 3, name: 'Profiles' })
    expect(heading.parentElement).toContainElement(screen.getByRole('button', { name: /add profile/i }))
  })
})

describe('BasicsSection (read-only)', () => {
  it('renders name, headline, contact details and summary', () => {
    renderWithQuery(<BasicsSection basics={full} versionId={VERSION} />)

    expect(screen.getByRole('heading', { level: 1, name: 'Jane Smith' })).toBeInTheDocument()
    expect(screen.getByText('Staff Engineer')).toBeInTheDocument()
    expect(screen.getByText('555-9876')).toBeInTheDocument()
    expect(screen.getByText('New York, NY, US')).toBeInTheDocument()
    expect(screen.getByText('reliable')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('links the email, website and profiles; unsafe or missing urls render as text', () => {
    renderWithQuery(<BasicsSection basics={full} versionId={VERSION} />)

    expect(screen.getByRole('link', { name: 'jane@example.com' })).toHaveAttribute(
      'href',
      'mailto:jane@example.com',
    )
    expect(screen.getByRole('link', { name: 'Website' })).toHaveAttribute(
      'href',
      'https://janesmith.com',
    )
    expect(screen.getByRole('link', { name: 'LinkedIn' })).toHaveAttribute(
      'href',
      'https://linkedin.com/in/janesmith',
    )
    expect(screen.getByText('Matrix: @jane:hs.org')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /matrix/i })).not.toBeInTheDocument()
  })

  it('does not link a javascript: profile url', () => {
    renderWithQuery(
      <BasicsSection
        basics={{ profiles: [{ id: 'x', network: 'Evil', url: 'javascript:alert(1)' }] }}
        versionId={VERSION}
      />,
    )
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('renders nothing for empty basics', () => {
    renderWithQuery(<BasicsSection basics={{}} versionId={VERSION} />)
    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
  })
})

describe('BasicsSection (editing)', () => {
  it('drops unsaved edits on cancel', async () => {
    const user = userEvent.setup()
    renderEditable({ name: 'Jane' })
    await startEditing(user)

    await user.clear(screen.getByLabelText('Name'))
    await user.type(screen.getByLabelText('Name'), 'Draft')
    await user.click(screen.getByRole('button', { name: /cancel editing basics/i }))
    await startEditing(user)

    expect(screen.getByLabelText('Name')).toHaveValue('Jane')
  })

  it('prompts to fill in an empty resume', () => {
    renderEditable({})
    expect(screen.getByText(/click the pencil icon/i)).toBeInTheDocument()
  })

  it('pre-fills the form from the basics', async () => {
    const user = userEvent.setup()
    renderEditable(full)
    await startEditing(user)

    expect(screen.getByLabelText('Name')).toHaveValue('Jane Smith')
    expect(screen.getByLabelText('Headline')).toHaveValue('Staff Engineer')
    expect(screen.getByLabelText('City')).toHaveValue('New York')
    expect(screen.getByLabelText('Region')).toHaveValue('NY')
    expect(screen.getByLabelText('Country')).toHaveValue('US')
    expect(screen.getByLabelText('Profile 1 network')).toHaveValue('LinkedIn')
    expect(screen.getByLabelText('Profile 2 username')).toHaveValue('@jane:hs.org')
    expect(screen.getByLabelText('Summary')).toHaveValue('Builds **reliable** systems.')
  })

  it('saves the changed fields; location keeps fields the form does not edit', async () => {
    const user = userEvent.setup()
    const onUpdate = vi.fn()
    renderEditable(full, onUpdate)
    await startEditing(user)

    const name = screen.getByLabelText('Name')
    await user.clear(name)
    await user.type(name, 'Jane Q. Smith')
    await user.clear(screen.getByLabelText('City'))
    await user.type(screen.getByLabelText('City'), 'Boston')
    await save(user)

    await waitFor(() => expect(api.updateBasics).toHaveBeenCalledTimes(1))
    const [id, patch] = vi.mocked(api.updateBasics).mock.calls[0]
    expect(id).toBe(VERSION)
    expect(patch).toMatchObject({
      name: 'Jane Q. Smith',
      label: 'Staff Engineer',
      email: 'jane@example.com',
      url: 'https://janesmith.com',
      location: { address: '1 Main St', city: 'Boston', region: 'NY', countryCode: 'US' },
    })
    expect(patch.profiles).toEqual([
      { id: 'p1', network: 'LinkedIn', username: '', url: 'https://linkedin.com/in/janesmith' },
      { id: 'p2', network: 'Matrix', username: '@jane:hs.org', url: '' },
    ])
    await waitFor(() => expect(onUpdate).toHaveBeenCalled())
  })

  it('sends blank strings to clear a field and null to clear an emptied location', async () => {
    const user = userEvent.setup()
    renderEditable({ name: 'Jane', phone: '555', location: { city: 'Oslo' } })
    await startEditing(user)

    await user.clear(screen.getByLabelText('Phone'))
    await user.clear(screen.getByLabelText('City'))
    await save(user)

    await waitFor(() => expect(api.updateBasics).toHaveBeenCalled())
    const patch = vi.mocked(api.updateBasics).mock.calls[0][1]
    expect(patch.phone).toBe('')
    expect(patch.location).toBeNull()
  })

  it('adds a profile with a bare host normalised to https', async () => {
    const user = userEvent.setup()
    renderEditable({ name: 'Jane' })
    await startEditing(user)

    await user.click(screen.getByRole('button', { name: /add profile/i }))
    await user.type(screen.getByLabelText('Profile 1 network'), 'GitHub')
    await user.type(screen.getByLabelText('Profile 1 URL'), 'github.com/jane')
    await save(user)

    await waitFor(() => expect(api.updateBasics).toHaveBeenCalled())
    expect(vi.mocked(api.updateBasics).mock.calls[0][1].profiles).toEqual([
      { id: undefined, network: 'GitHub', username: '', url: 'https://github.com/jane' },
    ])
  })

  it('puts a newly added profile first, next to the button that added it', async () => {
    const user = userEvent.setup()
    renderEditable(full)
    await startEditing(user)

    await user.click(screen.getByRole('button', { name: /add profile/i }))
    expect(screen.getByLabelText('Profile 1 network')).toHaveValue('')
    expect(screen.getByLabelText('Profile 2 network')).toHaveValue('LinkedIn')
  })

  it('has a drag grip on each profile, labelled by its network', async () => {
    const user = userEvent.setup()
    renderEditable(full)
    await startEditing(user)
    expect(screen.getByRole('button', { name: 'Reorder LinkedIn' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reorder Matrix' })).toBeInTheDocument()
  })

  it('has no grip for a single profile', async () => {
    const user = userEvent.setup()
    renderEditable({ profiles: [full.profiles![0]] })
    await startEditing(user)
    expect(screen.queryByRole('button', { name: /reorder/i })).not.toBeInTheDocument()
  })

  it('removes a profile', async () => {
    const user = userEvent.setup()
    renderEditable(full)
    await startEditing(user)

    await user.click(screen.getByRole('button', { name: 'Remove profile 1' }))
    await save(user)

    await waitFor(() => expect(api.updateBasics).toHaveBeenCalled())
    const profiles = vi.mocked(api.updateBasics).mock.calls[0][1].profiles
    expect(profiles?.map((p) => p.id)).toEqual(['p2'])
  })

  it('suggests common networks', async () => {
    const user = userEvent.setup()
    renderEditable({})
    await user.click(screen.getByRole('button', { name: /edit basics/i }))
    const list = document.getElementById('networks') as HTMLElement
    expect(within(list).getAllByRole('option', { hidden: true }).map((o) => o.getAttribute('value'))).toContain('GitHub')
  })

  it.each([
    ['email', 'Email', 'not-an-email', /invalid email/i],
    ['website', 'Website', 'javascript:alert(1)', /valid http\(s\) url/i],
  ])('blocks saving an invalid %s', async (_n, label, value, message) => {
    const user = userEvent.setup()
    renderEditable({ name: 'Jane' })
    await startEditing(user)

    await user.type(screen.getByLabelText(label), value)
    await save(user)

    expect(await screen.findAllByText(message)).not.toHaveLength(0)
    expect(api.updateBasics).not.toHaveBeenCalled()
  })

  it('requires a network for each profile', async () => {
    const user = userEvent.setup()
    renderEditable({ name: 'Jane' })
    await startEditing(user)

    await user.click(screen.getByRole('button', { name: /add profile/i }))
    await user.type(screen.getByLabelText('Profile 1 URL'), 'github.com/jane')
    await save(user)

    expect(await screen.findByText(/network is required/i)).toBeInTheDocument()
    expect(api.updateBasics).not.toHaveBeenCalled()
  })

  it('shows an error toast and stays in edit mode when the save fails', async () => {
    const user = userEvent.setup()
    vi.mocked(api.updateBasics).mockRejectedValue(new Error('server said no'))
    renderEditable(full)
    await startEditing(user)

    await save(user)

    expect(await screen.findByText('server said no')).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toBeInTheDocument()
  })

  it('discards edits on cancel', async () => {
    const user = userEvent.setup()
    renderEditable(full)
    await startEditing(user)

    await user.clear(screen.getByLabelText('Name'))
    await user.click(screen.getByRole('button', { name: /cancel editing basics/i }))

    expect(screen.getByRole('heading', { level: 1, name: 'Jane Smith' })).toBeInTheDocument()
    expect(api.updateBasics).not.toHaveBeenCalled()
  })
})
