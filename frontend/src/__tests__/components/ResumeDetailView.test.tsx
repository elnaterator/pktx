import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import ResumeDetailView from '../../pages/resumes/ResumeDetailView'
import * as api from '../../services/api'
import type { Resume, ResumeVersion, SectionMeta } from '../../types'
import { renderWithQuery } from '../test-utils'

vi.mock('../../services/api')

const meta = (key: string, label: string, primaryField: string): SectionMeta => ({
  key,
  label,
  kind: 'list',
  primaryField,
  schema: {
    properties: {
      id: { title: 'Id', type: 'string' },
      [primaryField]: { title: primaryField, type: 'string' },
    },
  },
})

const schema: SectionMeta[] = [
  {
    key: 'basics',
    label: 'Basics',
    kind: 'object',
    primaryField: 'name',
    schema: { properties: {} },
  },
  meta('work', 'Experience', 'position'),
  meta('education', 'Education', 'institution'),
  meta('skills', 'Skills', 'name'),
  meta('projects', 'Projects', 'name'),
  meta('awards', 'Awards', 'title'),
]

function version(data: Resume): ResumeVersion {
  return {
    id: 1,
    label: 'Main',
    is_default: true,
    tags: [],
    created_at: '',
    updated_at: '',
    links: {},
    data,
  }
}

const DATA: Resume = {
  basics: { name: 'Jane', summary: 'About me' },
  work: [{ id: 'w1', position: 'Dev', name: 'Acme' }],
  projects: [{ id: 'p1', name: 'pktx' }],
}

function renderView(data: Resume = DATA) {
  vi.mocked(api.getResumeVersion).mockResolvedValue(version(data))
  vi.mocked(api.getResumeSchema).mockResolvedValue(schema)
  vi.mocked(api.listAllTags).mockResolvedValue([])
  return renderWithQuery(
    <MemoryRouter initialEntries={['/resumes/1']}>
      <Routes>
        <Route path="/resumes/:id" element={<ResumeDetailView />} />
      </Routes>
    </MemoryRouter>,
  )
}

const headings = () => screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)

describe('ResumeDetailView sections', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows the summary, then only sections that have entries, in registry order', async () => {
    renderView({ ...DATA, awards: [{ id: 'a1', title: 'Best' }] })
    await screen.findByText('pktx')
    const order = headings().filter((h) =>
      ['Summary', 'Experience', 'Education', 'Skills', 'Projects', 'Awards'].includes(h ?? ''),
    )
    expect(order).toEqual(['Summary', 'Experience', 'Projects', 'Awards'])
  })

  it('offers every section that has no entries yet', async () => {
    renderView()
    await screen.findByText('pktx')
    const bar = await screen.findByTestId('add-section-bar')
    for (const label of ['Education', 'Skills', 'Awards']) expect(bar).toHaveTextContent(label)
    expect(bar).not.toHaveTextContent('Projects')
    expect(bar).not.toHaveTextContent('Experience')
    expect(screen.queryByRole('heading', { name: 'Awards' })).not.toBeInTheDocument()
  })

  it('opens an empty section straight into its first-entry form', async () => {
    const user = userEvent.setup()
    renderView()
    await user.click(await screen.findByRole('button', { name: /awards/i }))
    expect(await screen.findByRole('heading', { name: 'Awards' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /title/i })).toBeInTheDocument()
    // The section is client-only until it holds an entry, so nothing is written.
    expect(api.addEntry).not.toHaveBeenCalled()
  })

  it('dismisses an opened-but-empty section when the form is cancelled', async () => {
    const user = userEvent.setup()
    renderView()
    await user.click(await screen.findByRole('button', { name: /awards/i }))
    await screen.findByRole('heading', { name: 'Awards' })
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: 'Awards' })).not.toBeInTheDocument()
    })
    expect(screen.getByTestId('add-section-bar')).toHaveTextContent('Awards')
  })

  it('opens the skills section with an Add Skill prompt', async () => {
    const user = userEvent.setup()
    renderView()
    await user.click(await screen.findByRole('button', { name: /skills/i }))
    expect(await screen.findByTestId('skills-section')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /add skill/i })).toBeInTheDocument()
  })

  it('shows an empty resume as just the Add section bar', async () => {
    renderView({})
    const bar = await screen.findByTestId('add-section-bar')
    for (const label of ['Experience', 'Education', 'Skills', 'Projects', 'Awards']) {
      expect(bar).toHaveTextContent(label)
    }
  })

  it('sets the default through PATCH is_default', async () => {
    const user = userEvent.setup()
    vi.mocked(api.getResumeVersion).mockResolvedValue({ ...version(DATA), is_default: false })
    vi.mocked(api.getResumeSchema).mockResolvedValue(schema)
    vi.mocked(api.listAllTags).mockResolvedValue([])
    vi.mocked(api.updateResume).mockResolvedValue(version(DATA))
    renderWithQuery(
      <MemoryRouter initialEntries={['/resumes/1']}>
        <Routes>
          <Route path="/resumes/:id" element={<ResumeDetailView />} />
        </Routes>
      </MemoryRouter>,
    )
    await user.click(await screen.findByRole('button', { name: /set as default/i }))
    await waitFor(() => {
      expect(api.updateResume).toHaveBeenCalledWith(1, { is_default: true })
    })
  })

  it('switches to the JSON view and back, keeping unsaved JSON in between', async () => {
    const user = userEvent.setup()
    renderView()
    await screen.findByText('pktx')
    await user.click(screen.getByRole('tab', { name: 'JSON' }))

    const editor = await screen.findByRole('textbox', { name: 'Resume JSON' })
    expect(JSON.parse((editor as HTMLTextAreaElement).value)).toEqual(DATA)
    expect(screen.queryByTestId('add-section-bar')).not.toBeInTheDocument()

    fireEvent.change(editor, { target: { value: '{"basics":{"name":"Z"}}' } })
    await user.click(screen.getByRole('tab', { name: /^Resume/ }))
    expect(await screen.findByText('pktx')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /JSON/ })).toHaveTextContent('•')

    await user.click(screen.getByRole('tab', { name: /JSON/ }))
    expect(screen.getByRole('textbox', { name: 'Resume JSON' })).toHaveValue('{"basics":{"name":"Z"}}')
  })
})
