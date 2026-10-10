import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import ResumeDetailView from '../../pages/resumes/ResumeDetailView'
import * as api from '../../services/api'
import type { LayoutItem, ResumeVersion, SectionMeta } from '../../types'
import { renderWithQuery } from '../test-utils'

vi.mock('../../services/api')

const field = (name: string, label: string, required = false) =>
  ({ name, label, widget: 'text', required }) as SectionMeta['fields'][number]

const sections: SectionMeta[] = [
  { key: 'experience', label: 'Experience', primary_field: 'title', unique_field: null, insert: 'prepend', fields: [field('title', 'Title', true), field('company', 'Company', true)] },
  { key: 'projects', label: 'Projects', primary_field: 'name', unique_field: null, insert: 'prepend', fields: [field('name', 'Name', true)] },
  { key: 'custom', label: 'Custom', primary_field: 'heading', unique_field: null, insert: 'append', fields: [field('heading', 'Heading')] },
]

function version(layout: LayoutItem[]): ResumeVersion {
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
      custom_sections: { ab: { title: 'Talks', entries: [{ id: 'c1', heading: 'KubeCon', body: null, highlights: [] }] } },
      layout,
    },
  }
}

function renderView(layout: LayoutItem[]) {
  vi.mocked(api.getResumeVersion).mockResolvedValue(version(layout))
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

describe('ResumeDetailView layout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders visible sections in layout order with title overrides', async () => {
    renderView([
      { section: 'projects', visible: true, title: null },
      { section: 'custom:ab', visible: true, title: 'Speaking' },
      { section: 'experience', visible: true, title: 'Work' },
      { section: 'summary', visible: true, title: null },
    ])
    await screen.findByText('pktx')
    const order = headings().filter((h) => ['Projects', 'Speaking', 'Work', 'Summary'].includes(h ?? ''))
    expect(order).toEqual(['Projects', 'Speaking', 'Work', 'Summary'])
    expect(screen.getByText('KubeCon')).toBeInTheDocument()
  })

  it('omits hidden sections from the page but lists them in Manage sections', async () => {
    renderView([
      { section: 'summary', visible: true, title: null },
      { section: 'experience', visible: false, title: null },
      { section: 'projects', visible: true, title: null },
    ])
    await screen.findByText('pktx')
    expect(screen.queryByText('Dev')).not.toBeInTheDocument()
    expect(await screen.findByLabelText('Show Experience')).not.toBeChecked()
  })
})
