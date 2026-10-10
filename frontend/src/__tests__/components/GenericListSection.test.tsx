import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import GenericListSection from '../../pages/resumes/GenericListSection'
import type { ListEntry, SectionMeta } from '../../types'
import * as api from '../../services/api'
import { renderWithQuery } from '../test-utils'

vi.mock('../../services/api')

const experienceMeta: SectionMeta = {
  key: 'experience',
  label: 'Experience',
  primary_field: 'title',
  unique_field: null,
  insert: 'prepend',
  fields: [
    { name: 'title', label: 'Title', widget: 'text', required: true },
    { name: 'company', label: 'Company', widget: 'text', required: true },
    { name: 'start_date', label: 'Start date', widget: 'text', required: false },
    { name: 'end_date', label: 'End date', widget: 'text', required: false },
    { name: 'location', label: 'Location', widget: 'text', required: false },
    { name: 'highlights', label: 'Highlights', widget: 'bullets', required: false },
  ],
}

const projectMeta: SectionMeta = {
  key: 'projects',
  label: 'Projects',
  primary_field: 'name',
  unique_field: null,
  insert: 'prepend',
  fields: [
    { name: 'name', label: 'Name', widget: 'text', required: true },
    { name: 'description', label: 'Description', widget: 'textarea', required: false },
    { name: 'url', label: 'Url', widget: 'url', required: false },
    { name: 'tech', label: 'Tech', widget: 'tags', required: false },
  ],
}

const entries: ListEntry[] = [
  {
    id: 'id-1',
    title: 'Senior Engineer',
    company: 'Tech Corp',
    start_date: '2020-01',
    end_date: '2023-12',
    location: 'San Francisco, CA',
    highlights: ['Led team of 5', 'Built key features'],
  },
  {
    id: 'id-2',
    title: 'Software Developer',
    company: 'StartupCo',
    start_date: '2018-06',
    end_date: '2020-01',
    location: 'Austin, TX',
    highlights: ['Developed mobile app'],
  },
]

const renderSection = (props: Partial<React.ComponentProps<typeof GenericListSection>> = {}) =>
  renderWithQuery(
    <GenericListSection
      meta={experienceMeta}
      sectionKey="experience"
      title="Experience"
      entries={entries}
      versionId={7}
      {...props}
    />,
  )

describe('GenericListSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('view mode', () => {
    it('renders entries from the registry definition', () => {
      renderSection()
      expect(screen.getByText('Senior Engineer')).toBeInTheDocument()
      expect(screen.getByText(/Tech Corp/)).toBeInTheDocument()
      expect(screen.getByText('Software Developer')).toBeInTheDocument()
      expect(screen.getByText('Led team of 5')).toBeInTheDocument()
    })

    it('shows the layout title and an add button', () => {
      renderSection({ title: 'Work history' })
      expect(screen.getByRole('heading', { name: 'Work history' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /add work history/i })).toBeInTheDocument()
    })

    it('has edit and delete buttons per entry', () => {
      renderSection()
      expect(screen.getAllByRole('button', { name: /edit/i })).toHaveLength(2)
      expect(screen.getAllByRole('button', { name: /delete/i })).toHaveLength(2)
    })

    it('shows a placeholder when empty', () => {
      renderSection({ entries: [] })
      expect(screen.getByText(/nothing here yet/i)).toBeInTheDocument()
    })
  })

  describe('add', () => {
    it('submits the registry fields to the versioned API', async () => {
      const user = userEvent.setup()
      vi.mocked(api.addVersionEntry).mockResolvedValue({ message: 'ok' })
      const onUpdate = vi.fn()
      renderSection({ onUpdate })

      await user.click(screen.getByRole('button', { name: /add experience/i }))
      await user.type(screen.getByLabelText(/title/i), 'New Position')
      await user.type(screen.getByLabelText(/company/i), 'New Company')
      await user.type(screen.getByLabelText(/start date/i), '2024-01')
      await user.click(screen.getByRole('button', { name: /save/i }))

      await waitFor(() => {
        expect(api.addVersionEntry).toHaveBeenCalledWith(7, 'experience', {
          title: 'New Position',
          company: 'New Company',
          start_date: '2024-01',
          end_date: null,
          location: null,
          highlights: [],
        })
      })
      await waitFor(() => expect(onUpdate).toHaveBeenCalled())
    })

    it('requires the fields the registry marks required', async () => {
      const user = userEvent.setup()
      renderSection()
      await user.click(screen.getByRole('button', { name: /add experience/i }))
      await user.click(screen.getByRole('button', { name: /save/i }))
      expect(await screen.findByText(/title is required/i)).toBeInTheDocument()
      expect(api.addVersionEntry).not.toHaveBeenCalled()
    })

    it('shows an error toast when add fails', async () => {
      const user = userEvent.setup()
      vi.mocked(api.addVersionEntry).mockRejectedValue(new Error('boom'))
      renderSection()
      await user.click(screen.getByRole('button', { name: /add experience/i }))
      await user.type(screen.getByLabelText(/title/i), 'T')
      await user.type(screen.getByLabelText(/company/i), 'C')
      await user.click(screen.getByRole('button', { name: /save/i }))
      expect(await screen.findByText(/failed to add/i)).toBeInTheDocument()
    })

    it('cancel returns to view mode', async () => {
      const user = userEvent.setup()
      renderSection()
      await user.click(screen.getByRole('button', { name: /add experience/i }))
      await user.click(screen.getByRole('button', { name: /cancel/i }))
      expect(screen.queryByLabelText(/title/i)).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: /add experience/i })).toBeInTheDocument()
    })
  })

  describe('edit', () => {
    it('pre-fills the form including highlights', async () => {
      const user = userEvent.setup()
      renderSection()
      await user.click(screen.getAllByRole('button', { name: /edit/i })[0])
      expect(screen.getByLabelText(/title/i)).toHaveValue('Senior Engineer')
      expect(screen.getByLabelText(/company/i)).toHaveValue('Tech Corp')
      expect(screen.getByLabelText(/start date/i)).toHaveValue('2020-01')
      const highlights = screen.getAllByPlaceholderText(/highlight/i)
      expect(highlights).toHaveLength(2)
      expect(highlights[0]).toHaveValue('Led team of 5')
    })

    it('updates by stable entry id, not by position', async () => {
      const user = userEvent.setup()
      vi.mocked(api.updateVersionEntry).mockResolvedValue({ message: 'ok' })
      renderSection()
      // Entries render newest first, so the second Edit button is id-2.
      await user.click(screen.getAllByRole('button', { name: /edit/i })[1])
      const title = screen.getByLabelText(/title/i)
      await user.clear(title)
      await user.type(title, 'Updated Title')
      await user.click(screen.getByRole('button', { name: /save/i }))
      await waitFor(() => {
        expect(api.updateVersionEntry).toHaveBeenCalledWith(
          7,
          'experience',
          'id-2',
          expect.objectContaining({ title: 'Updated Title' }),
        )
      })
    })

    it('falls back to the index for entries without an id', async () => {
      const user = userEvent.setup()
      vi.mocked(api.updateVersionEntry).mockResolvedValue({ message: 'ok' })
      renderSection({ entries: [{ title: 'Old', company: 'Co', highlights: [] }] })
      await user.click(screen.getByRole('button', { name: /edit/i }))
      await user.click(screen.getByRole('button', { name: /save/i }))
      await waitFor(() => {
        expect(api.updateVersionEntry).toHaveBeenCalledWith(7, 'experience', 0, expect.anything())
      })
    })

    it('shows an error toast when update fails', async () => {
      const user = userEvent.setup()
      vi.mocked(api.updateVersionEntry).mockRejectedValue(new Error('boom'))
      renderSection()
      await user.click(screen.getAllByRole('button', { name: /edit/i })[0])
      await user.click(screen.getByRole('button', { name: /save/i }))
      expect(await screen.findByText(/failed to update/i)).toBeInTheDocument()
    })
  })

  describe('delete', () => {
    it('confirms, then removes by entry id', async () => {
      const user = userEvent.setup()
      vi.mocked(api.removeVersionEntry).mockResolvedValue({ message: 'ok' })
      const onUpdate = vi.fn()
      renderSection({ onUpdate })

      await user.click(screen.getAllByRole('button', { name: /delete/i })[1])
      expect(screen.getByText(/are you sure/i)).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: /confirm/i }))

      await waitFor(() => {
        expect(api.removeVersionEntry).toHaveBeenCalledWith(7, 'experience', 'id-2')
      })
      await waitFor(() => expect(onUpdate).toHaveBeenCalled())
    })

    it('does nothing when cancelled', async () => {
      const user = userEvent.setup()
      renderSection()
      await user.click(screen.getAllByRole('button', { name: /delete/i })[0])
      await user.click(screen.getByRole('button', { name: /cancel/i }))
      expect(screen.queryByText(/are you sure/i)).not.toBeInTheDocument()
      expect(api.removeVersionEntry).not.toHaveBeenCalled()
    })

    it('shows an error toast when delete fails', async () => {
      const user = userEvent.setup()
      vi.mocked(api.removeVersionEntry).mockRejectedValue(new Error('boom'))
      renderSection()
      await user.click(screen.getAllByRole('button', { name: /delete/i })[0])
      await user.click(screen.getByRole('button', { name: /confirm/i }))
      expect(await screen.findByText(/failed to delete/i)).toBeInTheDocument()
    })
  })

  describe('other field widgets', () => {
    const project: ListEntry = {
      id: 'p1',
      name: 'pktx',
      description: 'An MCP server',
      url: 'https://github.com/x/pktx',
      tech: ['python', 'react'],
    }

    it('renders url as a link, tech as a list and description as text', () => {
      renderSection({ meta: projectMeta, sectionKey: 'projects', title: 'Projects', entries: [project] })
      const link = screen.getByRole('link', { name: 'github.com/x/pktx' })
      expect(link).toHaveAttribute('href', 'https://github.com/x/pktx')
      expect(screen.getByText('python, react')).toBeInTheDocument()
      expect(screen.getByText('An MCP server')).toBeInTheDocument()
    })

    it('converts comma separated tech to an array and rejects non-http urls', async () => {
      const user = userEvent.setup()
      vi.mocked(api.addVersionEntry).mockResolvedValue({ message: 'ok' })
      renderSection({ meta: projectMeta, sectionKey: 'projects', title: 'Projects', entries: [] })

      await user.click(screen.getByRole('button', { name: /add projects/i }))
      await user.type(screen.getByLabelText(/^name/i), 'Tool')
      await user.type(screen.getByLabelText(/url/i), 'javascript:alert(1)')
      await user.click(screen.getByRole('button', { name: /save/i }))
      expect(await screen.findByText(/invalid url|must start with http/i)).toBeInTheDocument()
      expect(api.addVersionEntry).not.toHaveBeenCalled()

      const url = screen.getByLabelText(/url/i)
      await user.clear(url)
      await user.type(url, 'https://example.com')
      await user.type(screen.getByLabelText(/tech/i), 'go, rust ,')
      await user.click(screen.getByRole('button', { name: /save/i }))

      await waitFor(() => {
        expect(api.addVersionEntry).toHaveBeenCalledWith(7, 'projects', {
          name: 'Tool',
          description: null,
          url: 'https://example.com',
          tech: ['go', 'rust'],
        })
      })
    })
  })
})
