import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ManageSections from '../../pages/resumes/ManageSections'
import type { LayoutItem, SectionMeta } from '../../types'
import * as api from '../../services/api'
import { renderWithQuery } from '../test-utils'

vi.mock('../../services/api')

const sections = [
  { key: 'experience', label: 'Experience' },
  { key: 'skills', label: 'Skills' },
] as SectionMeta[]

const layout: LayoutItem[] = [
  { section: 'summary', visible: true, title: null },
  { section: 'experience', visible: true, title: null },
  { section: 'skills', visible: false, title: 'Tech' },
  { section: 'custom:ab12', visible: true, title: null },
]

const customSections = { ab12: { title: 'Talks', entries: [] } }

const renderIt = () =>
  renderWithQuery(
    <ManageSections
      versionId={3}
      layout={layout}
      customSections={customSections}
      sections={sections}
    />,
  )

describe('ManageSections', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.updateVersionLayout).mockResolvedValue({ layout })
  })

  it('lists every section with its visibility', () => {
    renderIt()
    expect(screen.getByLabelText('Show Experience')).toBeChecked()
    expect(screen.getByLabelText('Show Skills')).not.toBeChecked()
    expect(screen.getByLabelText('Show Talks')).toBeChecked()
  })

  it('toggles visibility', async () => {
    const user = userEvent.setup()
    renderIt()
    await user.click(screen.getByLabelText('Show Experience'))
    await waitFor(() => {
      expect(api.updateVersionLayout).toHaveBeenCalledWith(
        3,
        layout.map((i) => (i.section === 'experience' ? { ...i, visible: false } : i)),
      )
    })
  })

  it('moves a section up and disables the edges', async () => {
    const user = userEvent.setup()
    renderIt()
    expect(screen.getByLabelText('Move Summary up')).toBeDisabled()
    expect(screen.getByLabelText('Move Talks down')).toBeDisabled()
    await user.click(screen.getByLabelText('Move Experience up'))
    await waitFor(() => {
      const sent = vi.mocked(api.updateVersionLayout).mock.calls[0][1]
      expect(sent.map((i) => i.section).slice(0, 2)).toEqual(['experience', 'summary'])
    })
  })

  it('saves a title override on blur and clears it when emptied', async () => {
    const user = userEvent.setup()
    renderIt()
    const input = screen.getByLabelText('Title for Experience')
    await user.type(input, 'Work')
    await user.tab()
    await waitFor(() => {
      const sent = vi.mocked(api.updateVersionLayout).mock.calls[0][1]
      expect(sent.find((i) => i.section === 'experience')?.title).toBe('Work')
    })
  })

  it('adds a custom section', async () => {
    const user = userEvent.setup()
    vi.mocked(api.addCustomSection).mockResolvedValue({ section: 'custom:zz' })
    renderIt()
    expect(screen.getByRole('button', { name: /add section/i })).toBeDisabled()
    await user.type(screen.getByLabelText('New custom section title'), '  Open Source ')
    await user.click(screen.getByRole('button', { name: /add section/i }))
    await waitFor(() => expect(api.addCustomSection).toHaveBeenCalledWith(3, 'Open Source'))
  })

  it('removes only custom sections after confirmation', async () => {
    const user = userEvent.setup()
    vi.mocked(api.removeCustomSection).mockResolvedValue({ message: 'ok' })
    renderIt()
    expect(screen.queryByLabelText('Remove Experience')).not.toBeInTheDocument()
    await user.click(screen.getByLabelText('Remove Talks'))
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(api.removeCustomSection).toHaveBeenCalledWith(3, 'ab12'))
  })

  it('shows an error toast when saving the layout fails', async () => {
    const user = userEvent.setup()
    vi.mocked(api.updateVersionLayout).mockRejectedValue(new Error('x'))
    renderIt()
    await user.click(screen.getByLabelText('Show Experience'))
    expect(await screen.findByText(/failed to update layout/i)).toBeInTheDocument()
  })
})
