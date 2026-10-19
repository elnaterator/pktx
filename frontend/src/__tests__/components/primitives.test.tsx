import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Pencil } from 'lucide-react'
import { Button } from '../../components/Button'
import { Chip } from '../../components/Chip'
import { EditActions } from '../../components/EditActions'
import { IconButton } from '../../components/IconButton'
import { PanelHeader } from '../../components/PanelHeader'
import { TagList } from '../../components/TagList'

describe('Button', () => {
  it('defaults to type="button" and forwards clicks', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Go</Button>)
    const btn = screen.getByRole('button', { name: 'Go' })
    expect(btn).toHaveAttribute('type', 'button')
    await userEvent.click(btn)
    expect(onClick).toHaveBeenCalledOnce()
  })
})

describe('IconButton', () => {
  it('uses the label as its accessible name', () => {
    render(<IconButton icon={Pencil} label="Edit thing" />)
    expect(screen.getByRole('button', { name: 'Edit thing' })).toBeInTheDocument()
  })
})

describe('EditActions', () => {
  it('shows edit and delete in view mode', () => {
    render(<EditActions editing={false} onEdit={() => {}} onDelete={() => {}} editLabel="Edit note" deleteLabel="Delete note" />)
    expect(screen.getByRole('button', { name: 'Edit note' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Delete note' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument()
  })

  it('omits delete when no handler is given', () => {
    render(<EditActions editing={false} onEdit={() => {}} />)
    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
  })

  it('shows save and cancel in edit mode and disables save while saving', async () => {
    const onCancel = vi.fn()
    render(<EditActions editing saving onSave={() => {}} onCancel={onCancel} />)
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalledOnce()
  })
})

describe('PanelHeader', () => {
  it('renders the title as a heading in view mode', () => {
    render(<PanelHeader editing={false} title="My note" titleEditor={<input />} entity="note" onEdit={() => {}} />)
    expect(screen.getByRole('heading', { name: 'My note' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit note' })).toBeInTheDocument()
  })

  it('renders the editor instead of the heading in edit mode', () => {
    render(<PanelHeader editing title="My note" titleEditor={<input aria-label="Title" />} entity="note" />)
    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Title' })).toBeInTheDocument()
  })
})

describe('TagList', () => {
  it('renders each tag and nothing when empty', () => {
    const { container, rerender } = render(<TagList tags={['a', 'b']} />)
    expect(screen.getByText('a')).toBeInTheDocument()
    expect(screen.getByText('b')).toBeInTheDocument()
    rerender(<TagList tags={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('Chip', () => {
  it('calls onRemove from its remove button', async () => {
    const onRemove = vi.fn()
    render(<Chip label="python" onRemove={onRemove} />)
    await userEvent.click(screen.getByRole('button', { name: 'Remove python' }))
    expect(onRemove).toHaveBeenCalledOnce()
  })

  it('has no remove button without a handler', () => {
    render(<Chip label="python" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
