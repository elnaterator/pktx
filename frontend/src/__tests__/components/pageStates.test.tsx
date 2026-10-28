import { describe, it, expect, vi } from 'vitest'
import { act, render, renderHook, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { useState } from 'react'
import { Modal } from '../../components/Modal'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { ListPage } from '../../components/ListPage'
import { DetailFallback } from '../../components/DetailFallback'
import { useDebouncedSearch } from '../../hooks/useDebouncedSearch'

const ROUTE = { listPath: '/notes', singular: 'Note', plural: 'Notes' }

function ModalHarness() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button onClick={() => setOpen(true)}>Open</button>
      {open && (
        <Modal label="Test dialog" onClose={() => setOpen(false)}>
          <button>First</button>
          <button>Last</button>
        </Modal>
      )}
    </>
  )
}

describe('Modal', () => {
  it('is a labelled modal dialog that focuses its first control', async () => {
    render(<ModalHarness />)
    await userEvent.click(screen.getByRole('button', { name: 'Open' }))
    const dialog = screen.getByRole('dialog', { name: 'Test dialog' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByRole('button', { name: 'First' })).toHaveFocus()
  })

  it('keeps Tab inside the dialog', async () => {
    render(<ModalHarness />)
    await userEvent.click(screen.getByRole('button', { name: 'Open' }))
    await userEvent.tab()
    expect(screen.getByRole('button', { name: 'Last' })).toHaveFocus()
    await userEvent.tab()
    expect(screen.getByRole('button', { name: 'First' })).toHaveFocus()
    await userEvent.tab({ shift: true })
    expect(screen.getByRole('button', { name: 'Last' })).toHaveFocus()
  })

  it('closes on Escape and returns focus to the opener', async () => {
    render(<ModalHarness />)
    const opener = screen.getByRole('button', { name: 'Open' })
    await userEvent.click(opener)
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })
})

describe('ConfirmDialog', () => {
  it('starts on Cancel and labels the confirm button with the action', async () => {
    const onConfirm = vi.fn()
    render(<ConfirmDialog message="Delete this note?" confirmLabel="Delete" onConfirm={onConfirm} onCancel={() => {}} />)
    const dialog = screen.getByRole('alertdialog')
    expect(dialog).toHaveAccessibleDescription('Delete this note?')
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus()
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(onConfirm).toHaveBeenCalledOnce()
  })
})

function renderList(query: { isPending: boolean; isError: boolean }, items: string[], isFiltered = false) {
  const refetch = vi.fn()
  render(
    <ListPage
      title="Notes"
      noun="notes"
      filters={null}
      query={{ ...query, refetch }}
      items={items}
      getKey={(i) => i}
      renderItem={(i) => <li>{i}</li>}
      emptyMessage="No notes yet."
      isFiltered={isFiltered}
    />,
  )
  return refetch
}

describe('ListPage', () => {
  it('shows a spinner, not the empty message, while loading', () => {
    renderList({ isPending: true, isError: false }, [])
    expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument()
    expect(screen.queryByText('No notes yet.')).not.toBeInTheDocument()
  })

  it('distinguishes "none yet" from "no matches"', () => {
    renderList({ isPending: false, isError: false }, [], true)
    expect(screen.getByText('No notes match your search.')).toBeInTheDocument()
  })

  it('offers a retry when loading fails', async () => {
    const refetch = renderList({ isPending: false, isError: true }, [])
    expect(screen.getByText(/couldn't load notes/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(refetch).toHaveBeenCalled()
  })

  it('renders items', () => {
    renderList({ isPending: false, isError: false }, ['a', 'b'])
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
  })
})

describe('DetailFallback', () => {
  const renderFallback = (error: unknown, isPending = false) =>
    render(
      <MemoryRouter>
        <DetailFallback query={{ isPending, error, refetch: () => {} }} route={ROUTE} />
      </MemoryRouter>,
    )

  it('shows not found for a 404', () => {
    renderFallback({ status: 404 })
    expect(screen.getByRole('heading', { name: 'Note not found' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to Notes' })).toHaveAttribute('href', '/notes')
  })

  it('shows not-yours for a 403', () => {
    renderFallback({ status: 403 })
    expect(screen.getByRole('heading', { name: "This note isn't yours" })).toBeInTheDocument()
  })

  it('offers a retry for other errors', () => {
    renderFallback(new Error('boom'))
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })
})

describe('useDebouncedSearch', () => {
  it('updates search immediately and debounced after the delay', () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useDebouncedSearch(300))
    act(() => result.current.setSearch({ tags: [], text: 'py' }))
    expect(result.current.search.text).toBe('py')
    expect(result.current.isFiltered).toBe(true)
    expect(result.current.debounced.text).toBe('')
    act(() => vi.advanceTimersByTime(300))
    expect(result.current.debounced.text).toBe('py')
    vi.useRealTimers()
  })
})
