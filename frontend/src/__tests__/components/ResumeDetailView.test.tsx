import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import ResumeDetailView from '../../pages/resumes/ResumeDetailView'
import * as api from '../../services/api'
import type { ResumeVersion, SectionMeta } from '../../types'
import { renderWithQuery } from '../test-utils'

vi.mock('../../services/api')

const field = (name: string, label: string, required = false) =>
  ({ name, label, widget: 'text', required }) as SectionMeta['fields'][number]

const meta = (key: string, label: string, optional: boolean, primary: string): SectionMeta => ({
  key,
  label,
  optional,
  primary_field: primary,
  unique_field: null,
  insert: 'prepend',
  fields: [field(primary, primary, true)],
})

const sections: SectionMeta[] = [
  meta('experience', 'Experience', false, 'title'),
  meta('education', 'Education', false, 'institution'),
  meta('skills', 'Skills', false, 'name'),
  meta('projects', 'Projects', true, 'name'),
  meta('awards', 'Awards', true, 'title'),
]

function version(enabled: string[]): ResumeVersion {
  return {
    id: 1,
    label: 'Main',
    is_default: true,
    app_count: 0,
    tags: [],
    created_at: '',
    updated_at: '',
    links: {},
    resume_data: {
      contact: { name: 'Jane', email: null, phone: null, location: null, linkedin: null, website: null, github: null, profiles: [] },
      summary: 'About me',
      experience: [{ id: 'e1', title: 'Dev', company: 'Acme', start_date: null, end_date: null, location: null, highlights: [] }],
      education: [],
      skills: [],
      projects: [{ id: 'p1', name: 'pktx', description: null, url: null, tech: [], start_date: null, end_date: null, highlights: [] }],
      certifications: [],
      awards: [],
      publications: [],
      volunteer: [],
      languages: [],
      enabled_sections: enabled,
    },
  }
}

function renderView(enabled: string[]) {
  vi.mocked(api.getResumeVersion).mockResolvedValue(version(enabled))
  vi.mocked(api.listResumeSections).mockResolvedValue(sections)
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

  it('shows core sections in a fixed order and only the optional ones that were added', async () => {
    renderView(['awards', 'projects'])
    await screen.findByText('pktx')
    const order = headings().filter((h) =>
      ['Summary', 'Experience', 'Education', 'Skills', 'Projects', 'Awards'].includes(h ?? ''),
    )
    expect(order).toEqual(['Summary', 'Experience', 'Education', 'Skills', 'Projects', 'Awards'])
  })

  it('offers only the optional sections not yet added', async () => {
    renderView(['projects'])
    await screen.findByText('pktx')
    const bar = await screen.findByTestId('add-section-bar')
    expect(bar).toHaveTextContent('Awards')
    expect(bar).not.toHaveTextContent('Projects')
    expect(screen.queryByRole('heading', { name: 'Awards' })).not.toBeInTheDocument()
  })

  it('adds a section from the list', async () => {
    const user = userEvent.setup()
    vi.mocked(api.setVersionSectionEnabled).mockResolvedValue({ message: 'ok' })
    renderView([])
    await user.click(await screen.findByRole('button', { name: /awards/i }))
    await waitFor(() => {
      expect(api.setVersionSectionEnabled).toHaveBeenCalledWith(1, 'awards', true)
    })
  })

  it('removes an empty optional section but never a core one', async () => {
    const user = userEvent.setup()
    vi.mocked(api.setVersionSectionEnabled).mockResolvedValue({ message: 'ok' })
    renderView(['awards'])
    await screen.findByRole('heading', { name: 'Awards' })
    // Only the empty optional section (Awards) offers removal; Education is core and empty.
    const remove = await screen.findAllByRole('button', { name: /remove section/i })
    expect(remove).toHaveLength(1)
    await user.click(remove[0])
    await waitFor(() => {
      expect(api.setVersionSectionEnabled).toHaveBeenCalledWith(1, 'awards', false)
    })
  })
})
