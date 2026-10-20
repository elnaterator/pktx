import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import GenericListSection from '../../pages/resumes/GenericListSection'
import type { ListEntry, SectionMeta } from '../../types'
import * as api from '../../services/api'
import { renderWithQuery } from '../test-utils'
import { drop, resetDnd } from '../dnd-test-utils'

vi.mock('../../services/api')
vi.mock('@dnd-kit/core', async () => (await import('../dnd-test-utils')).mockDndKit())

const workMeta: SectionMeta = {
  key: 'work',
  label: 'Experience',
  kind: 'list',
  primaryField: 'position',
  schema: {
    properties: {
      id: { title: 'Id', type: 'string' },
      name: { title: 'Company' },
      location: { title: 'Location' },
      position: { title: 'Position' },
      url: { title: 'URL', widget: 'url' },
      startDate: { title: 'Start date', widget: 'date' },
      endDate: { title: 'End date', widget: 'date' },
      summary: { title: 'Summary', widget: 'textarea' },
      highlights: { title: 'Highlights', widget: 'bullets', type: 'array' },
    },
  },
}

const awardMeta: SectionMeta = {
  key: 'awards',
  label: 'Awards',
  kind: 'list',
  primaryField: 'title',
  schema: {
    properties: {
      id: { title: 'Id', type: 'string' },
      title: { title: 'Title' },
      date: { title: 'Date', widget: 'date' },
    },
  },
}

const projectMeta: SectionMeta = {
  key: 'projects',
  label: 'Projects',
  kind: 'list',
  primaryField: 'name',
  schema: {
    properties: {
      id: { title: 'Id', type: 'string' },
      name: { title: 'Name' },
      description: { title: 'Description', widget: 'textarea' },
      url: { title: 'URL', widget: 'url' },
      keywords: { title: 'Technologies', widget: 'tags', type: 'array' },
    },
  },
}

const educationMeta: SectionMeta = {
  key: 'education',
  label: 'Education',
  kind: 'list',
  primaryField: 'institution',
  schema: {
    properties: {
      id: { title: 'Id', type: 'string' },
      institution: { title: 'Institution' },
      studyType: { title: 'Degree' },
      score: { title: 'Score / GPA' },
      courses: { title: 'Courses', widget: 'tags', type: 'array' },
    },
  },
}

const entries: ListEntry[] = [
  {
    id: 'id-1',
    position: 'Senior Engineer',
    name: 'Tech Corp',
    startDate: '2020-01',
    endDate: '2023-12',
    location: 'San Francisco, CA',
    highlights: ['Led team of 5', 'Built key features'],
  },
  {
    id: 'id-2',
    position: 'Software Developer',
    name: 'StartupCo',
    startDate: '2018-06',
    location: 'Austin, TX',
    highlights: ['Developed mobile app'],
  },
]

const renderSection = (props: Partial<React.ComponentProps<typeof GenericListSection>> = {}) =>
  renderWithQuery(
    <GenericListSection meta={workMeta} entries={entries} versionId={7} {...props} />,
  )

describe('GenericListSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetDnd()
  })

  describe('view mode', () => {
    it('renders entries from the schema', () => {
      renderSection()
      expect(screen.getByText('Senior Engineer')).toBeInTheDocument()
      expect(screen.getByText(/Tech Corp/)).toBeInTheDocument()
      expect(screen.getByText('Software Developer')).toBeInTheDocument()
      expect(screen.getByText('Led team of 5')).toBeInTheDocument()
    })

    it('shows the date range, with Present for an open end', () => {
      renderSection()
      expect(screen.getByText('2020-01 – 2023-12')).toBeInTheDocument()
      expect(screen.getByText('2018-06 – Present')).toBeInTheDocument()
    })

    it('keeps the order it is given (no date sorting)', () => {
      renderSection({ entries: [entries[1], entries[0]] })
      const titles = screen.getAllByText(/Engineer|Developer/).map((e) => e.textContent)
      expect(titles).toEqual(['Software Developer', 'Senior Engineer'])
    })

    it('shows the section label and an add button', () => {
      renderSection()
      expect(screen.getByRole('heading', { name: 'Experience' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /add experience/i })).toBeInTheDocument()
    })

    it('offers dismissal only while the section is empty', async () => {
      const user = userEvent.setup()
      const onClose = vi.fn()
      const { unmount } = renderSection({ entries: [], onClose })
      await user.click(screen.getByRole('button', { name: /remove section/i }))
      expect(onClose).toHaveBeenCalled()
      unmount()

      renderSection({ onClose })
      expect(screen.queryByRole('button', { name: /remove section/i })).not.toBeInTheDocument()
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

    it('opens the add form immediately with startAdding', () => {
      renderSection({ entries: [], startAdding: true })
      expect(screen.getByLabelText(/position/i)).toBeInTheDocument()
    })
  })

  describe('section header', () => {
    it('puts Add at the top right of the section, not at the bottom', () => {
      renderSection()
      const section = screen.getByTestId('work-section')
      const heading = within(section).getByRole('heading', { name: 'Experience' })
      const add = within(section).getByRole('button', { name: /add experience/i })
      expect(heading.parentElement).toContainElement(add)
      const lastEntry = within(section).getByText('Software Developer')
      expect(heading.compareDocumentPosition(add) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
      expect(add.compareDocumentPosition(lastEntry) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })

    it('hides Add while a form is open', async () => {
      const user = userEvent.setup()
      renderSection()
      await user.click(screen.getByRole('button', { name: /add experience/i }))
      expect(screen.queryByRole('button', { name: /add experience/i })).not.toBeInTheDocument()
    })

    it('keeps Remove section next to Add for an empty section', () => {
      renderSection({ entries: [], onClose: vi.fn() })
      const add = screen.getByRole('button', { name: /add experience/i })
      expect(add.parentElement).toContainElement(screen.getByRole('button', { name: /remove section/i }))
    })
  })

  describe('date fields', () => {
    it('gives every date field a calendar picker', async () => {
      const user = userEvent.setup()
      renderSection()
      await user.click(screen.getByRole('button', { name: /add experience/i }))
      // Start date and end date
      expect(screen.getAllByRole('button', { name: 'Choose date' })).toHaveLength(2)
    })

    it('saves a date picked from the calendar', async () => {
      const user = userEvent.setup()
      vi.mocked(api.addEntry).mockResolvedValue({ id: 'new' })
      renderSection()
      await user.click(screen.getByRole('button', { name: /add experience/i }))
      await user.type(screen.getByLabelText(/position/i), 'Dev')
      await user.click(screen.getAllByRole('button', { name: 'Choose date' })[0])
      await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: /^May \d{4}$/ }))
      expect(screen.getByLabelText(/start date/i)).toHaveValue(`${new Date().getFullYear()}-05`)
      await user.click(screen.getByRole('button', { name: /save/i }))
      await waitFor(() =>
        expect(api.addEntry).toHaveBeenCalledWith(
          7,
          'work',
          expect.objectContaining({
            position: 'Dev',
            startDate: `${new Date().getFullYear()}-05`,
          }),
          0,
        ),
      )
    })

    it('periods choose a month; single dates can choose a day', async () => {
      const user = userEvent.setup()
      renderSection({ meta: awardMeta, entries: [] })
      await user.click(screen.getByRole('button', { name: /add awards/i }))
      await user.click(screen.getByRole('button', { name: 'Choose date' }))
      await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: /^March \d{4}$/ }))
      // a month alone does not close it: days follow
      expect(screen.getByRole('button', { name: /^March 1, \d{4}$/ })).toBeInTheDocument()
    })
  })

  describe('add form position', () => {
    it('opens the add form directly under the header, above the entries', async () => {
      const user = userEvent.setup()
      renderSection()
      await user.click(screen.getByRole('button', { name: /add experience/i }))
      const section = screen.getByTestId('work-section')
      const form = section.querySelector('form') as HTMLElement
      const firstEntry = within(section).getByText('Senior Engineer')
      const heading = within(section).getByRole('heading', { name: 'Experience' })
      expect(heading.compareDocumentPosition(form) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
      expect(form.compareDocumentPosition(firstEntry) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })

    it('shows the form above the empty-section placeholder too', async () => {
      const user = userEvent.setup()
      renderSection({ entries: [] })
      await user.click(screen.getByRole('button', { name: /add experience/i }))
      expect(screen.queryByText(/nothing here yet/i)).not.toBeInTheDocument()
      expect(screen.getByTestId('work-section').querySelector('form')).toBeInTheDocument()
    })
  })

  describe('add', () => {
    it('submits schema fields and puts dated entries first', async () => {
      const user = userEvent.setup()
      vi.mocked(api.addEntry).mockResolvedValue({ id: 'new' })
      const onUpdate = vi.fn()
      renderSection({ onUpdate })

      await user.click(screen.getByRole('button', { name: /add experience/i }))
      await user.type(screen.getByLabelText(/position/i), 'New Position')
      await user.type(screen.getByLabelText(/company/i), 'New Company')
      await user.type(screen.getByLabelText(/start date/i), '2024-01')
      await user.click(screen.getByRole('button', { name: /save/i }))

      await waitFor(() => {
        expect(api.addEntry).toHaveBeenCalledWith(
          7,
          'work',
          {
            position: 'New Position',
            name: 'New Company',
            startDate: '2024-01',
            endDate: null,
            location: null,
            url: null,
            summary: null,
            highlights: [],
          },
          0,
        )
      })
      await waitFor(() => expect(onUpdate).toHaveBeenCalled())
    })

    it('appends entries of sections without a period', async () => {
      const user = userEvent.setup()
      vi.mocked(api.addEntry).mockResolvedValue({ id: 'new' })
      renderSection({ meta: projectMeta, entries: [] })
      await user.click(screen.getByRole('button', { name: /add projects/i }))
      await user.type(screen.getByLabelText(/^name/i), 'Tool')
      await user.click(screen.getByRole('button', { name: /save/i }))
      await waitFor(() => {
        expect(api.addEntry).toHaveBeenCalledWith(7, 'projects', expect.anything(), undefined)
      })
    })

    it('requires the primary field only', async () => {
      const user = userEvent.setup()
      renderSection()
      await user.click(screen.getByRole('button', { name: /add experience/i }))
      await user.click(screen.getByRole('button', { name: /save/i }))
      expect(await screen.findByText(/position is required/i)).toBeInTheDocument()
      expect(api.addEntry).not.toHaveBeenCalled()
    })

    it('rejects dates that are not partial ISO', async () => {
      const user = userEvent.setup()
      renderSection()
      await user.click(screen.getByRole('button', { name: /add experience/i }))
      await user.type(screen.getByLabelText(/position/i), 'P')
      await user.type(screen.getByLabelText(/start date/i), 'March 2024')
      await user.click(screen.getByRole('button', { name: /save/i }))
      expect(await screen.findByText(/use yyyy, yyyy-mm or yyyy-mm-dd/i)).toBeInTheDocument()
      expect(api.addEntry).not.toHaveBeenCalled()
    })

    it('shows an error toast when add fails', async () => {
      const user = userEvent.setup()
      vi.mocked(api.addEntry).mockRejectedValue(new Error('boom'))
      renderSection()
      await user.click(screen.getByRole('button', { name: /add experience/i }))
      await user.type(screen.getByLabelText(/position/i), 'T')
      await user.click(screen.getByRole('button', { name: /save/i }))
      expect(await screen.findByText(/failed to add/i)).toBeInTheDocument()
    })

    it('cancel returns to view mode', async () => {
      const user = userEvent.setup()
      renderSection()
      await user.click(screen.getByRole('button', { name: /add experience/i }))
      await user.click(screen.getByRole('button', { name: /cancel/i }))
      expect(screen.queryByLabelText(/position/i)).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: /add experience/i })).toBeInTheDocument()
    })

    it('cancelling the first entry of an empty section dismisses it', async () => {
      const user = userEvent.setup()
      const onClose = vi.fn()
      renderSection({ entries: [], startAdding: true, onClose })
      await user.click(screen.getByRole('button', { name: /cancel/i }))
      expect(onClose).toHaveBeenCalled()
    })
  })

  describe('edit', () => {
    it('pre-fills the form including highlights', async () => {
      const user = userEvent.setup()
      renderSection()
      await user.click(screen.getAllByRole('button', { name: /edit/i })[0])
      expect(screen.getByLabelText(/position/i)).toHaveValue('Senior Engineer')
      expect(screen.getByLabelText(/company/i)).toHaveValue('Tech Corp')
      expect(screen.getByLabelText(/start date/i)).toHaveValue('2020-01')
      const highlights = screen.getAllByPlaceholderText(/highlight/i)
      expect(highlights).toHaveLength(2)
      expect(highlights[0]).toHaveValue('Led team of 5')
    })

    it('updates by stable entry id; blank fields are sent as null to clear them', async () => {
      const user = userEvent.setup()
      vi.mocked(api.updateEntry).mockResolvedValue({ id: 'id-2' })
      renderSection()
      await user.click(screen.getAllByRole('button', { name: /edit/i })[1])
      const position = screen.getByLabelText(/position/i)
      await user.clear(position)
      await user.type(position, 'Updated Title')
      await user.click(screen.getByRole('button', { name: /save/i }))
      await waitFor(() => {
        expect(api.updateEntry).toHaveBeenCalledWith(
          7,
          'work',
          'id-2',
          expect.objectContaining({ position: 'Updated Title', endDate: null }),
        )
      })
    })

    it('shows an error toast when update fails', async () => {
      const user = userEvent.setup()
      vi.mocked(api.updateEntry).mockRejectedValue(new Error('boom'))
      renderSection()
      await user.click(screen.getAllByRole('button', { name: /edit/i })[0])
      await user.click(screen.getByRole('button', { name: /save/i }))
      expect(await screen.findByText(/failed to update/i)).toBeInTheDocument()
    })
  })

  describe('delete', () => {
    it('confirms, then removes by entry id', async () => {
      const user = userEvent.setup()
      vi.mocked(api.removeEntry).mockResolvedValue(undefined)
      const onUpdate = vi.fn()
      renderSection({ onUpdate })

      await user.click(screen.getAllByRole('button', { name: /delete/i })[1])
      expect(screen.getByText(/are you sure/i)).toBeInTheDocument()
      await user.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Delete' }))

      await waitFor(() => {
        expect(api.removeEntry).toHaveBeenCalledWith(7, 'work', 'id-2')
      })
      await waitFor(() => expect(onUpdate).toHaveBeenCalled())
    })

    it('does nothing when cancelled', async () => {
      const user = userEvent.setup()
      renderSection()
      await user.click(screen.getAllByRole('button', { name: /delete/i })[0])
      await user.click(screen.getByRole('button', { name: /cancel/i }))
      expect(screen.queryByText(/are you sure/i)).not.toBeInTheDocument()
      expect(api.removeEntry).not.toHaveBeenCalled()
    })

    it('shows an error toast when delete fails', async () => {
      const user = userEvent.setup()
      vi.mocked(api.removeEntry).mockRejectedValue(new Error('boom'))
      renderSection()
      await user.click(screen.getAllByRole('button', { name: /delete/i })[0])
      await user.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Delete' }))
      expect(await screen.findByText(/failed to delete/i)).toBeInTheDocument()
    })
  })

  describe('reorder', () => {
    it('offers a drag grip per entry, labelled with its title, and no arrow buttons', () => {
      renderSection()
      expect(screen.getByRole('button', { name: 'Reorder Senior Engineer' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Reorder Software Developer' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /move experience/i })).not.toBeInTheDocument()
    })

    it('saves the new order after a drop, by entry id', async () => {
      vi.mocked(api.reorderEntries).mockResolvedValue([])
      const onUpdate = vi.fn()
      renderSection({ onUpdate })
      await drop('id-1', 'id-2')
      await waitFor(() => expect(api.reorderEntries).toHaveBeenCalledWith(7, 'work', ['id-2', 'id-1']))
      await waitFor(() => expect(onUpdate).toHaveBeenCalled())
      const titles = screen.getAllByText(/Engineer|Developer/).map((e) => e.textContent)
      expect(titles).toEqual(['Software Developer', 'Senior Engineer'])
    })

    it('offers no grip for a single entry', () => {
      renderSection({ entries: [entries[0]] })
      expect(screen.queryByRole('button', { name: /reorder/i })).not.toBeInTheDocument()
    })

    it('shows an error toast and puts the entry back when saving fails', async () => {
      vi.mocked(api.reorderEntries).mockRejectedValue(new Error('boom'))
      renderSection()
      await drop('id-1', 'id-2')
      expect(await screen.findByText(/failed to reorder/i)).toBeInTheDocument()
      await waitFor(() => {
        const titles = screen.getAllByText(/Engineer|Developer/).map((e) => e.textContent)
        expect(titles).toEqual(['Senior Engineer', 'Software Developer'])
      })
    })

    it('does not offer a grip on the entry being edited', async () => {
      const user = userEvent.setup()
      renderSection()
      await user.click(screen.getAllByRole('button', { name: /edit/i })[0])
      expect(screen.queryByRole('button', { name: 'Reorder Senior Engineer' })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Reorder Software Developer' })).toBeInTheDocument()
    })
  })

  describe('courses', () => {
    const school: ListEntry = {
      id: 'e1',
      institution: 'WWU',
      studyType: 'BS',
      score: '3.9',
      courses: ['Quantum Mechanics', 'Optics'],
    }

    it('shows courses on their own line below the other details', () => {
      renderSection({ meta: educationMeta, entries: [school] })
      const details = screen.getByText((_, el) => el?.textContent === 'BS · 3.9')
      const courses = screen.getByText('Courses: Quantum Mechanics, Optics')
      expect(courses).not.toBe(details)
      expect(details.contains(courses)).toBe(false)
      expect(details.compareDocumentPosition(courses) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })

    it('omits the line when there are no courses', () => {
      renderSection({ meta: educationMeta, entries: [{ ...school, courses: [] }] })
      expect(screen.queryByText(/^Courses:/)).not.toBeInTheDocument()
    })

    it('puts the courses field in its own row, after the shared details row', async () => {
      const user = userEvent.setup()
      renderSection({ meta: educationMeta, entries: [school] })
      await user.click(screen.getByRole('button', { name: /edit education/i }))

      const courses = screen.getByLabelText(/courses/i)
      const degree = screen.getByLabelText(/degree/i)
      const score = screen.getByLabelText(/score/i)
      expect(degree.closest('div')?.parentElement).toBe(score.closest('div')?.parentElement)
      expect(degree.closest('div')?.parentElement?.contains(courses)).toBe(false)
      expect(degree.compareDocumentPosition(courses) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })
  })

  describe('other field widgets', () => {
    const project: ListEntry = {
      id: 'p1',
      name: 'pktx',
      description: 'An MCP server',
      url: 'https://github.com/x/pktx',
      keywords: ['python', 'react'],
    }

    it('renders url as a link, keywords as a list and description as text', () => {
      renderSection({ meta: projectMeta, entries: [project] })
      const link = screen.getByRole('link', { name: 'github.com/x/pktx' })
      expect(link).toHaveAttribute('href', 'https://github.com/x/pktx')
      expect(screen.getByText('python, react')).toBeInTheDocument()
      expect(screen.getByText('An MCP server')).toBeInTheDocument()
    })

    it('converts comma separated keywords to an array and rejects non-http urls', async () => {
      const user = userEvent.setup()
      vi.mocked(api.addEntry).mockResolvedValue({ id: 'new' })
      renderSection({ meta: projectMeta, entries: [] })

      await user.click(screen.getByRole('button', { name: /add projects/i }))
      await user.type(screen.getByLabelText(/^name/i), 'Tool')
      await user.type(screen.getByLabelText(/url/i), 'javascript:alert(1)')
      await user.click(screen.getByRole('button', { name: /save/i }))
      expect(await screen.findByText(/valid http\(s\) url/i)).toBeInTheDocument()
      expect(api.addEntry).not.toHaveBeenCalled()

      const url = screen.getByLabelText(/url/i)
      await user.clear(url)
      await user.type(url, 'example.com')
      await user.type(screen.getByLabelText(/technologies/i), 'go, rust ,')
      await user.click(screen.getByRole('button', { name: /save/i }))

      await waitFor(() => {
        expect(api.addEntry).toHaveBeenCalledWith(
          7,
          'projects',
          {
            name: 'Tool',
            description: null,
            url: 'https://example.com',
            keywords: ['go', 'rust'],
          },
          undefined,
        )
      })
    })
  })
})
