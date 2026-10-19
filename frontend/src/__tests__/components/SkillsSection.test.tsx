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

/** A promise you resolve by hand, to hold a write in flight. */
function deferred<T>() {
  let resolve!: (v: T) => void
  const promise = new Promise<T>((r) => {
    resolve = r
  })
  return { promise, resolve }
}

describe('SkillsSection — typing keywords in a row', () => {
  it('keeps focus in the keyword field while a keyword is saving', async () => {
    const user = userEvent.setup()
    const write = deferred<{ id: string }>()
    vi.mocked(api.updateEntry).mockReturnValueOnce(write.promise)
    renderSection()

    const input = await openAdder(user, 'Languages')
    await user.type(input, 'Go{Enter}')

    expect(api.updateEntry).toHaveBeenCalledTimes(1)
    expect(input).toBeEnabled()
    expect(input).toHaveFocus()

    write.resolve({ id: 'g-lang' })
    await waitFor(() => expect(api.updateEntry).toHaveBeenCalledTimes(1))
    await user.type(input, 'Rust{Enter}')
    await waitFor(() => expect(api.updateEntry).toHaveBeenCalledTimes(2))
    expect(input).toHaveFocus()
  })

  it('takes the next keyword while the last one is still saving, and writes them in order', async () => {
    const user = userEvent.setup()
    const first = deferred<{ id: string }>()
    vi.mocked(api.updateEntry).mockReturnValueOnce(first.promise)
    renderSection()

    const input = await openAdder(user, 'Languages')
    await user.type(input, 'Go{Enter}Rust{Enter}Zig{Enter}')

    // Everything typed, one write in flight, the rest queued behind it.
    expect(input).toHaveValue('')
    expect(api.updateEntry).toHaveBeenCalledTimes(1)
    expect(api.updateEntry).toHaveBeenLastCalledWith(VERSION, 'skills', 'g-lang', {
      keywords: ['TypeScript', 'Python', 'Go'],
    })

    first.resolve({ id: 'g-lang' })
    await waitFor(() => expect(api.updateEntry).toHaveBeenCalledTimes(3))
    expect(api.updateEntry).toHaveBeenNthCalledWith(2, VERSION, 'skills', 'g-lang', {
      keywords: ['TypeScript', 'Python', 'Go', 'Rust'],
    })
    expect(api.updateEntry).toHaveBeenNthCalledWith(3, VERSION, 'skills', 'g-lang', {
      keywords: ['TypeScript', 'Python', 'Go', 'Rust', 'Zig'],
    })
    expect(input).toHaveFocus()
  })

  it('does not create a new skill twice when keywords are typed before the first save lands', async () => {
    const user = userEvent.setup()
    const create = deferred<{ id: string }>()
    vi.mocked(api.addEntry).mockReturnValueOnce(create.promise)
    renderSection()

    await user.click(screen.getByRole('button', { name: '+ Add Skill' }))
    await user.type(screen.getByLabelText('New skill name'), 'Cloud')
    const input = screen.getByLabelText('Add keyword to new skill')
    await user.type(input, 'Terraform{Enter}Pulumi{Enter}')

    expect(api.addEntry).toHaveBeenCalledTimes(1)
    expect(input).toHaveFocus()

    create.resolve({ id: 'g-cloud' })
    await waitFor(() => expect(api.updateEntry).toHaveBeenCalledTimes(1))
    expect(api.addEntry).toHaveBeenCalledTimes(1)
    expect(api.updateEntry).toHaveBeenCalledWith(VERSION, 'skills', 'g-cloud', {
      keywords: ['Terraform', 'Pulumi'],
    })
  })
})

describe('SkillsSection — skill edit mode', () => {
  it('offers one edit button per skill, and no per-skill controls in view mode', () => {
    renderSection()

    expect(screen.getByRole('button', { name: 'Edit Languages skill' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit Frameworks skill' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Remove / })).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('lists groups in the order given, with their keywords', () => {
    renderSection([
      { id: 'a', name: 'Zeta', keywords: ['z'] },
      { id: 'b', name: 'Alpha', keywords: ['a'] },
    ])
    const labels = screen.getAllByText(/^(Zeta|Alpha)$/).map((el) => el.textContent)
    expect(labels).toEqual(['Zeta', 'Alpha'])
    expect(screen.getByText('z')).toBeInTheDocument()
  })

  it('reveals removable chips and an adder for that skill only', async () => {
    const user = userEvent.setup()
    renderSection()

    await openAdder(user, 'Languages')

    expect(screen.getByRole('button', { name: 'Remove TypeScript' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remove React' })).not.toBeInTheDocument()
    // skill name input + keyword adder
    expect(screen.getAllByRole('textbox')).toHaveLength(2)
  })

  it('leaves edit mode via the check icon, not a text button', async () => {
    const user = userEvent.setup()
    renderSection()

    await openAdder(user, 'Languages')
    const done = screen.getByRole('button', { name: 'Done editing Languages' })
    expect(done).not.toHaveTextContent(/done/i)
    expect(done.querySelector('svg')).toBeInTheDocument()
    await user.click(done)

    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remove TypeScript' })).not.toBeInTheDocument()
  })

  it('edits one skill at a time', async () => {
    const user = userEvent.setup()
    renderSection()

    await openAdder(user, 'Languages')
    await openAdder(user, 'Frameworks')

    expect(screen.getByRole('button', { name: 'Remove React' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remove TypeScript' })).not.toBeInTheDocument()
  })

  it('appends a keyword to its group in one update', async () => {
    const user = userEvent.setup()
    const onUpdate = renderSection()

    const input = await openAdder(user, 'Languages')
    await user.type(input, 'Go{Enter}')

    await waitFor(() =>
      expect(api.updateEntry).toHaveBeenCalledWith(VERSION, 'skills', 'g-lang', {
        keywords: ['TypeScript', 'Python', 'Go'],
      }),
    )
    await waitFor(() => expect(onUpdate).toHaveBeenCalled())
  })

  it('builds consecutive writes on the last one before the refetch lands', async () => {
    const user = userEvent.setup()
    renderSection()

    const input = await openAdder(user, 'Languages')
    await user.type(input, 'Go,Rust,')

    await waitFor(() => expect(api.updateEntry).toHaveBeenCalledTimes(2))
    expect(api.updateEntry).toHaveBeenNthCalledWith(2, VERSION, 'skills', 'g-lang', {
      keywords: ['TypeScript', 'Python', 'Go', 'Rust'],
    })
    expect(screen.getByLabelText('Add keyword to Languages')).toBeInTheDocument()
  })

  it('writes a pasted separated list as a single update', async () => {
    const user = userEvent.setup()
    renderSection()

    const input = await openAdder(user, 'Languages')
    await user.click(input)
    await user.paste('Go, Rust; Zig\nElixir')

    await waitFor(() => expect(api.updateEntry).toHaveBeenCalledTimes(1))
    expect(api.updateEntry).toHaveBeenCalledWith(VERSION, 'skills', 'g-lang', {
      keywords: ['TypeScript', 'Python', 'Go', 'Rust', 'Zig', 'Elixir'],
    })
  })

  it('preserves keyword casing', async () => {
    const user = userEvent.setup()
    renderSection()

    const input = await openAdder(user, 'Languages')
    await user.type(input, 'GraphQL{Enter}')

    await waitFor(() =>
      expect(api.updateEntry).toHaveBeenCalledWith(
        VERSION,
        'skills',
        'g-lang',
        expect.objectContaining({ keywords: expect.arrayContaining(['GraphQL']) }),
      ),
    )
  })

  it('commits typed text on blur', async () => {
    const user = userEvent.setup()
    renderSection()

    const input = await openAdder(user, 'Languages')
    await user.type(input, 'Go')
    await user.tab()

    await waitFor(() => expect(api.updateEntry).toHaveBeenCalledTimes(1))
  })

  it('skips keywords already in the group, case-insensitively', async () => {
    const user = userEvent.setup()
    renderSection()

    const input = await openAdder(user, 'Languages')
    await user.click(input)
    await user.paste('typescript, Go')

    await waitFor(() => expect(api.updateEntry).toHaveBeenCalledTimes(1))
    expect(api.updateEntry).toHaveBeenCalledWith(VERSION, 'skills', 'g-lang', {
      keywords: ['TypeScript', 'Python', 'Go'],
    })
    expect(await screen.findByText('Skipped 1 already in Languages')).toBeInTheDocument()
  })

  it('writes nothing when every pasted keyword is a repeat', async () => {
    const user = userEvent.setup()
    renderSection()

    const input = await openAdder(user, 'Languages')
    await user.click(input)
    await user.paste('python, TYPESCRIPT')

    expect(await screen.findByText('Skipped 2 already in Languages')).toBeInTheDocument()
    expect(api.updateEntry).not.toHaveBeenCalled()
  })

  it('skips repeats within one pasted list', async () => {
    const user = userEvent.setup()
    renderSection()

    const input = await openAdder(user, 'Languages')
    await user.click(input)
    await user.paste('Go, go, GO')

    await waitFor(() => expect(api.updateEntry).toHaveBeenCalledTimes(1))
    expect(api.updateEntry).toHaveBeenCalledWith(VERSION, 'skills', 'g-lang', {
      keywords: ['TypeScript', 'Python', 'Go'],
    })
  })

  it('reports a failed write', async () => {
    const user = userEvent.setup()
    renderSection()
    vi.mocked(api.updateEntry).mockRejectedValueOnce(new Error('boom'))

    const input = await openAdder(user, 'Languages')
    await user.click(input)
    await user.paste('Go, Rust')

    expect(await screen.findByText('Failed to add: Go, Rust')).toBeInTheDocument()
  })

  it('leaves edit mode on Escape', async () => {
    const user = userEvent.setup()
    renderSection()

    const input = await openAdder(user, 'Languages')
    await user.type(input, '{Escape}')

    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit Languages skill' })).toBeInTheDocument()
    expect(api.updateEntry).not.toHaveBeenCalled()
  })

  it('renames a skill when its name field loses focus', async () => {
    const user = userEvent.setup()
    renderSection()

    await openAdder(user, 'Languages')
    const name = screen.getByRole('textbox', { name: 'Languages skill name' })
    await user.clear(name)
    await user.type(name, 'Programming{Enter}')

    await waitFor(() =>
      expect(api.updateEntry).toHaveBeenCalledWith(VERSION, 'skills', 'g-lang', {
        name: 'Programming',
      }),
    )
  })

  it('does not rename to a blank name', async () => {
    const user = userEvent.setup()
    renderSection()

    await openAdder(user, 'Languages')
    const name = screen.getByRole('textbox', { name: 'Languages skill name' })
    await user.clear(name)
    await user.tab()

    expect(await screen.findByText('A skill needs a name')).toBeInTheDocument()
    expect(api.updateEntry).not.toHaveBeenCalled()
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

describe('SkillsSection — remove with undo', () => {
  it('removes a keyword immediately with no confirmation dialog', async () => {
    const user = userEvent.setup()
    const onUpdate = renderSection()

    await openAdder(user, 'Languages')
    await user.click(screen.getByRole('button', { name: 'Remove Python' }))

    await waitFor(() =>
      expect(api.updateEntry).toHaveBeenCalledWith(VERSION, 'skills', 'g-lang', {
        keywords: ['TypeScript'],
      }),
    )
    await waitFor(() => expect(onUpdate).toHaveBeenCalled())
  })

  it('offers an Undo action that puts the keyword back', async () => {
    const user = userEvent.setup()
    renderSection()

    await openAdder(user, 'Languages')
    await user.click(screen.getByRole('button', { name: 'Remove Python' }))
    await user.click(await screen.findByRole('button', { name: 'Undo' }))

    await waitFor(() => expect(api.updateEntry).toHaveBeenCalledTimes(2))
    expect(api.updateEntry).toHaveBeenLastCalledWith(VERSION, 'skills', 'g-lang', {
      keywords: ['TypeScript', 'Python'],
    })
  })

  it('surfaces an error and skips the undo toast when removal fails', async () => {
    const user = userEvent.setup()
    const onUpdate = renderSection()
    vi.mocked(api.updateEntry).mockRejectedValue(new Error('nope'))

    await openAdder(user, 'Frameworks')
    await user.click(screen.getByRole('button', { name: 'Remove React' }))

    expect(await screen.findByText('nope')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Undo' })).not.toBeInTheDocument()
    expect(onUpdate).not.toHaveBeenCalled()
  })

  it('deletes a whole skill, with Undo restoring it in place', async () => {
    const user = userEvent.setup()
    const onUpdate = renderSection()

    await openAdder(user, 'Frameworks')
    await user.click(screen.getByRole('button', { name: 'Delete Frameworks skill' }))

    await waitFor(() =>
      expect(api.removeEntry).toHaveBeenCalledWith(VERSION, 'skills', 'g-fw'),
    )
    await waitFor(() => expect(onUpdate).toHaveBeenCalled())

    await user.click(await screen.findByRole('button', { name: 'Undo' }))
    await waitFor(() =>
      expect(api.addEntry).toHaveBeenCalledWith(
        VERSION,
        'skills',
        { name: 'Frameworks', keywords: ['React'] },
        1,
      ),
    )
  })
})
