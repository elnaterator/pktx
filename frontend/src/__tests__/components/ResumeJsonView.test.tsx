import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import ResumeJsonView from '../../pages/resumes/ResumeJsonView'
import * as api from '../../services/api'
import type { Resume } from '../../types'
import { renderWithQuery } from '../test-utils'

vi.mock('../../services/api')

const DATA: Resume = { basics: { name: 'Jane' }, work: [{ id: 'w1', position: 'Dev' }] }

function Harness({ data = DATA }: { data?: Resume }) {
  const [draft, setDraft] = useState<string | null>(null)
  return <ResumeJsonView versionId={5} data={data} draft={draft} onDraftChange={setDraft} />
}

const editor = () => screen.getByRole('textbox', { name: 'Resume JSON' }) as HTMLTextAreaElement
const saveButton = () => screen.getByRole('button', { name: /save/i })
/** userEvent.type chokes on `{`; set the text directly. */
const setText = (text: string) => fireEvent.change(editor(), { target: { value: text } })

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.replaceResumeData).mockResolvedValue({} as never)
})

describe('ResumeJsonView', () => {
  it('shows the saved document as formatted JSON, ids included', () => {
    renderWithQuery(<Harness />)
    expect(JSON.parse(editor().value)).toEqual(DATA)
    expect(editor().value).toContain('\n  "basics"')
  })

  it('has Save top right, disabled until something changes', () => {
    renderWithQuery(<Harness />)
    expect(saveButton()).toBeDisabled()
    expect(screen.queryByRole('button', { name: /revert/i })).not.toBeInTheDocument()
  })

  it('saves the edited document through PUT data and confirms', async () => {
    renderWithQuery(<Harness />)
    setText(JSON.stringify({ basics: { name: 'Ada' } }))
    expect(saveButton()).toBeEnabled()
    await userEvent.setup().click(saveButton())

    await waitFor(() =>
      expect(api.replaceResumeData).toHaveBeenCalledWith(5, { basics: { name: 'Ada' } }),
    )
    expect(await screen.findByText('Resume saved')).toBeInTheDocument()
  })

  it('blocks saving invalid JSON and says why', async () => {
    renderWithQuery(<Harness />)
    setText('{ "basics": ')
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(saveButton()).toBeDisabled()
    expect(editor()).toHaveAttribute('aria-invalid', 'true')
    expect(api.replaceResumeData).not.toHaveBeenCalled()
  })

  it.each(['[]', '"text"', 'null', '3'])('rejects %s: a resume is an object', (text) => {
    renderWithQuery(<Harness />)
    setText(text)
    expect(screen.getByRole('alert')).toHaveTextContent('must be a JSON object')
    expect(saveButton()).toBeDisabled()
  })

  it('keeps the text and shows the server message when the save is rejected', async () => {
    vi.mocked(api.replaceResumeData).mockRejectedValue(
      new Error('work.0.startDate: Date must be YYYY, YYYY-MM or YYYY-MM-DD'),
    )
    renderWithQuery(<Harness />)
    const bad = JSON.stringify({ work: [{ startDate: 'May' }] })
    setText(bad)
    await userEvent.setup().click(saveButton())

    expect(await screen.findByText(/work\.0\.startDate/)).toBeInTheDocument()
    expect(editor().value).toBe(bad)
    expect(saveButton()).toBeEnabled()
  })

  it('reverts unsaved edits', async () => {
    renderWithQuery(<Harness />)
    setText('{}')
    await userEvent.setup().click(screen.getByRole('button', { name: /revert/i }))
    expect(JSON.parse(editor().value)).toEqual(DATA)
    expect(saveButton()).toBeDisabled()
  })

  it('treats text identical to the saved document as not dirty', () => {
    renderWithQuery(<Harness />)
    setText(JSON.stringify(DATA, null, 2))
    expect(saveButton()).toBeDisabled()
  })
})
