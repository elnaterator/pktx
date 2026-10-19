import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SkillsSection from '../../pages/resumes/SkillsSection'
import * as api from '../../services/api'
import type { Skill } from '../../types'
import { renderWithQuery } from '../test-utils'
import { drop, resetDnd } from '../dnd-test-utils'

vi.mock('../../services/api')
vi.mock('@dnd-kit/core', async () => (await import('../dnd-test-utils')).mockDndKit())

const VERSION = 7
const groups: Skill[] = [
  { id: 'g-lang', name: 'Languages', keywords: ['TypeScript', 'Python'] },
  { id: 'g-fw', name: 'Frameworks', keywords: ['React'] },
]

function renderSection(list: Skill[] = groups, extra: { onClose?: () => void } = {}) {
  const onUpdate = vi.fn()
  const ui = (skills: Skill[]) => (
    <SkillsSection skills={skills} versionId={VERSION} onUpdate={onUpdate} {...extra} />
  )
  const { rerender } = renderWithQuery(ui(list))
  /** Stands in for the parent refetch that follows a write. */
  const refetch = (next: Skill[]) => rerender(ui(next))
  return Object.assign(onUpdate, { refetch })
}

/** Enters edit mode for a persisted skill and returns its keyword input. */
async function openAdder(user: ReturnType<typeof userEvent.setup>, skill: string) {
  await user.click(screen.getByRole('button', { name: `Edit ${skill} skill` }))
  return screen.getByRole('textbox', { name: `Add keyword to ${skill}` })
}

beforeEach(() => {
  vi.clearAllMocks()
  resetDnd()
  vi.mocked(api.addEntry).mockResolvedValue({ id: 'new' })
  vi.mocked(api.updateEntry).mockResolvedValue({ id: 'g-lang' })
  vi.mocked(api.removeEntry).mockResolvedValue(undefined)
})

describe('SkillsSection — reorder', () => {
  it('has a drag grip per skill, labelled with its name', () => {
    renderSection()
    expect(screen.getByRole('button', { name: 'Reorder Languages' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reorder Frameworks' })).toBeInTheDocument()
  })

  it('saves the new order of the skills after a drop', async () => {
    vi.mocked(api.reorderEntries).mockResolvedValue([])
    const onUpdate = renderSection()
    await drop('g-lang', 'g-fw')
    await waitFor(() =>
      expect(api.reorderEntries).toHaveBeenCalledWith(VERSION, 'skills', ['g-fw', 'g-lang']),
    )
    await waitFor(() => expect(onUpdate).toHaveBeenCalled())
    const labels = screen.getAllByText(/^(Languages|Frameworks)$/).map((e) => e.textContent)
    expect(labels).toEqual(['Frameworks', 'Languages'])
  })

  it('puts the skill back and says so when saving fails', async () => {
    vi.mocked(api.reorderEntries).mockRejectedValue(new Error('boom'))
    renderSection()
    await drop('g-lang', 'g-fw')
    expect(await screen.findByText('Failed to reorder skills')).toBeInTheDocument()
    await waitFor(() => {
      const labels = screen.getAllByText(/^(Languages|Frameworks)$/).map((e) => e.textContent)
      expect(labels).toEqual(['Languages', 'Frameworks'])
    })
  })

  it('has no grip for a single skill', () => {
    renderSection([groups[0]])
    expect(screen.queryByRole('button', { name: /reorder/i })).not.toBeInTheDocument()
  })
})

describe('SkillsSection — header', () => {
  it('puts Add Skill at the top right of the section', () => {
    renderSection()
    const heading = screen.getByRole('heading', { name: 'Skills' })
    const add = screen.getByRole('button', { name: '+ Add Skill' })
    expect(heading.parentElement).toContainElement(add)
    expect(heading.compareDocumentPosition(add) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('hides Add Skill while a new skill is being drafted', async () => {
    const user = userEvent.setup()
    renderSection()
    await user.click(screen.getByRole('button', { name: '+ Add Skill' }))
    expect(screen.queryByRole('button', { name: '+ Add Skill' })).not.toBeInTheDocument()
  })
})

describe('SkillsSection — new skill position', () => {
  it('opens the draft skill above the existing ones', async () => {
    const user = userEvent.setup()
    renderSection()
    await user.click(screen.getByRole('button', { name: '+ Add Skill' }))
    const draft = screen.getByTestId('draft-skill')
    const first = screen.getByText('Languages')
    expect(draft.compareDocumentPosition(first) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})


describe('SkillsSection — draft skill', () => {
  it('tells you the next step, following what you have typed', async () => {
    const user = userEvent.setup()
    renderSection()
    await user.click(screen.getByRole('button', { name: '+ Add Skill' }))
    expect(screen.getByText('Name your skill, then add its keywords.')).toBeInTheDocument()

    await user.type(screen.getByLabelText('New skill name'), '  Cloud ')
    expect(screen.getByText('Add a keyword to save “Cloud”.')).toBeInTheDocument()
    expect(screen.queryByText(/name your skill/i)).not.toBeInTheDocument()
  })

  it('adds a client-only skill that persists nothing on its own', async () => {
    const user = userEvent.setup()
    const onUpdate = renderSection()

    await user.click(screen.getByRole('button', { name: '+ Add Skill' }))
    await user.type(screen.getByLabelText('New skill name'), 'Cloud')

    expect(screen.getByTestId('draft-skill')).toBeInTheDocument()
    expect(api.addEntry).not.toHaveBeenCalled()
    expect(onUpdate).not.toHaveBeenCalled()
  })

  it('creates the group once its first keyword is added', async () => {
    const user = userEvent.setup()
    const onUpdate = renderSection()

    await user.click(screen.getByRole('button', { name: '+ Add Skill' }))
    await user.type(screen.getByLabelText('New skill name'), 'Cloud')
    await user.type(screen.getByLabelText('Add keyword to new skill'), 'Terraform{Enter}')

    await waitFor(() =>
      expect(api.addEntry).toHaveBeenCalledWith(VERSION, 'skills', {
        name: 'Cloud',
        keywords: ['Terraform'],
      }),
    )
    await waitFor(() => expect(onUpdate).toHaveBeenCalled())
  })

  it('keeps the draft mounted until the refetch shows the skill', async () => {
    const user = userEvent.setup()
    const onUpdate = renderSection()

    await user.click(screen.getByRole('button', { name: '+ Add Skill' }))
    await user.type(screen.getByLabelText('New skill name'), 'Cloud')
    await user.type(screen.getByLabelText('Add keyword to new skill'), 'Terraform{Enter}')
    await waitFor(() => expect(onUpdate).toHaveBeenCalled())

    // Write is done but the new group hasn't arrived yet — draft still holds focus
    expect(screen.getByTestId('draft-skill')).toBeInTheDocument()
    expect(screen.getByLabelText('Add keyword to new skill')).toHaveFocus()

    onUpdate.refetch([...groups, { id: 'g-cloud', name: 'Cloud', keywords: ['Terraform'] }])

    // Draft hands over to the real group, which stays in edit mode
    expect(screen.queryByTestId('draft-skill')).not.toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Add keyword to Cloud' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove Terraform' })).toBeInTheDocument()
  })

  it('moves focus from the name field to the keyword input on Enter', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(screen.getByRole('button', { name: '+ Add Skill' }))
    await user.type(screen.getByLabelText('New skill name'), 'Cloud{Enter}')

    expect(screen.getByLabelText('Add keyword to new skill')).toHaveFocus()
  })

  it('moves focus from the name field to the keyword input on Tab', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(screen.getByRole('button', { name: '+ Add Skill' }))
    await user.type(screen.getByLabelText('New skill name'), 'Cloud')
    await user.tab()

    expect(screen.getByLabelText('Add keyword to new skill')).toHaveFocus()
  })

  it('keeps focus on the name field when it is still empty', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(screen.getByRole('button', { name: '+ Add Skill' }))
    const nameInput = screen.getByLabelText('New skill name')
    await user.type(nameInput, '{Enter}')

    expect(nameInput).toHaveFocus()
    expect(await screen.findByText('Name the skill first')).toBeInTheDocument()
  })

  it('types a whole skill without leaving the keyboard', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(screen.getByRole('button', { name: '+ Add Skill' }))
    await user.keyboard('Cloud{Enter}Terraform{Enter}')

    await waitFor(() => expect(api.addEntry).toHaveBeenCalledTimes(1))
    expect(api.addEntry).toHaveBeenCalledWith(VERSION, 'skills', {
      name: 'Cloud',
      keywords: ['Terraform'],
    })
  })

  it('discards the draft on Escape in the name field', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(screen.getByRole('button', { name: '+ Add Skill' }))
    await user.type(screen.getByLabelText('New skill name'), 'Cloud{Escape}')

    expect(screen.queryByTestId('draft-skill')).not.toBeInTheDocument()
    expect(api.addEntry).not.toHaveBeenCalled()
  })

  it('refuses to add a keyword before the skill is named', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(screen.getByRole('button', { name: '+ Add Skill' }))
    await user.type(screen.getByLabelText('Add keyword to new skill'), 'Terraform{Enter}')

    expect(await screen.findByText('Name the skill first')).toBeInTheDocument()
    expect(api.addEntry).not.toHaveBeenCalled()
    expect(screen.getByTestId('draft-skill')).toBeInTheDocument()
  })

  it('discards the draft without persisting anything', async () => {
    const user = userEvent.setup()
    renderSection()

    await user.click(screen.getByRole('button', { name: '+ Add Skill' }))
    await user.type(screen.getByLabelText('New skill name'), 'Cloud')
    await user.click(screen.getByRole('button', { name: 'Discard new skill' }))

    expect(screen.queryByTestId('draft-skill')).not.toBeInTheDocument()
    expect(api.addEntry).not.toHaveBeenCalled()
  })

  it('shows a draft group even when the resume has no skills yet', async () => {
    const user = userEvent.setup()
    renderSection([])

    await user.click(screen.getByRole('button', { name: '+ Add Skill' }))

    expect(screen.getByTestId('draft-skill')).toBeInTheDocument()
    expect(screen.getByLabelText('Add keyword to new skill')).toBeInTheDocument()
  })

  it('offers dismissal only while there are no groups', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    const { unmount } = renderWithQuery(
      <SkillsSection skills={[]} versionId={VERSION} onClose={onClose} />,
    )
    await user.click(screen.getByRole('button', { name: /remove section/i }))
    expect(onClose).toHaveBeenCalled()
    unmount()

    renderSection(groups, { onClose })
    expect(screen.queryByRole('button', { name: /remove section/i })).not.toBeInTheDocument()
  })
})

describe('SkillsSection — view mode', () => {
  it('shows edit and delete icons per skill, and no chip remove buttons', () => {
    renderSection()
    for (const n of ['Languages', 'Frameworks']) {
      expect(screen.getByRole('button', { name: `Edit ${n} skill` })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: `Delete ${n} skill` })).toBeInTheDocument()
    }
    expect(screen.queryByRole('button', { name: 'Remove TypeScript' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument()
  })
})

describe('SkillsSection — edit with Save / Cancel', () => {
  it('shows Save and Cancel plus removable chips for that skill only', async () => {
    const user = userEvent.setup()
    renderSection()
    await openAdder(user, 'Languages')
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove TypeScript' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remove React' })).not.toBeInTheDocument()
  })

  it('writes name and keywords in one update on Save', async () => {
    const user = userEvent.setup()
    const onUpdate = renderSection()
    const input = await openAdder(user, 'Languages')
    const name = screen.getByRole('textbox', { name: 'Languages skill name' })
    await user.clear(name)
    await user.type(name, 'Langs')
    await user.click(screen.getByRole('button', { name: 'Remove Python' }))
    await user.type(input, 'Go{Enter}')
    expect(api.updateEntry).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() =>
      expect(api.updateEntry).toHaveBeenCalledWith(VERSION, 'skills', 'g-lang', {
        name: 'Langs',
        keywords: ['TypeScript', 'Go'],
      }),
    )
    await waitFor(() => expect(onUpdate).toHaveBeenCalled())
    expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument()
  })

  it('skips keywords already present, case-insensitively', async () => {
    const user = userEvent.setup()
    renderSection()
    const input = await openAdder(user, 'Languages')
    await user.type(input, 'python{Enter}')
    expect(await screen.findByText('Skipped 1 already in Languages')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() =>
      expect(api.updateEntry).toHaveBeenCalledWith(VERSION, 'skills', 'g-lang', {
        name: 'Languages',
        keywords: ['TypeScript', 'Python'],
      }),
    )
  })

  it('refuses a blank name', async () => {
    const user = userEvent.setup()
    renderSection()
    await openAdder(user, 'Languages')
    await user.clear(screen.getByRole('textbox', { name: 'Languages skill name' }))
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('A skill needs a name')).toBeInTheDocument()
    expect(api.updateEntry).not.toHaveBeenCalled()
  })

  it('writes nothing on Cancel and restores the keywords', async () => {
    const user = userEvent.setup()
    renderSection()
    await openAdder(user, 'Languages')
    await user.click(screen.getByRole('button', { name: 'Remove Python' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(api.updateEntry).not.toHaveBeenCalled()
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument()
  })

  it('reports a failed save and stays in edit mode', async () => {
    const user = userEvent.setup()
    vi.mocked(api.updateEntry).mockRejectedValue(new Error('boom'))
    renderSection()
    await openAdder(user, 'Languages')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Failed to update skill')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument()
  })
})

describe('SkillsSection — delete', () => {
  it('asks to confirm, then removes the skill', async () => {
    const user = userEvent.setup()
    const onUpdate = renderSection()
    await user.click(screen.getByRole('button', { name: 'Delete Frameworks skill' }))
    expect(api.removeEntry).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Confirm' }))
    await waitFor(() => expect(api.removeEntry).toHaveBeenCalledWith(VERSION, 'skills', 'g-fw'))
    await waitFor(() => expect(onUpdate).toHaveBeenCalled())
  })
})
