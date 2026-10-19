import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import SortableList from '../../components/SortableList'
import { drop, resetDnd } from '../dnd-test-utils'

vi.mock('@dnd-kit/core', async () => (await import('../dnd-test-utils')).mockDndKit())

interface Item {
  id: string
  name: string
}
const ITEMS: Item[] = [
  { id: 'a', name: 'Alpha' },
  { id: 'b', name: 'Bravo' },
  { id: 'c', name: 'Charlie' },
]

function List({
  items = ITEMS,
  onReorder = vi.fn(),
  ...rest
}: {
  items?: Item[]
  onReorder?: (ids: string[], move: { from: number; to: number }) => void | Promise<void>
  disabled?: boolean
  layout?: 'vertical' | 'grid'
}) {
  return (
    <SortableList
      items={items}
      getId={(i) => i.id}
      getLabel={(i) => i.name}
      onReorder={onReorder}
      renderItem={(item, row) => (
        <div ref={row.setNodeRef} style={row.style} data-testid="row">
          {row.handle}
          <span>{item.name}</span>
        </div>
      )}
      {...rest}
    />
  )
}

const names = () => screen.getAllByTestId('row').map((r) => r.textContent)

beforeEach(() => {
  resetDnd()
})

describe('SortableList', () => {
  it('renders every row in order with a labelled grip each', () => {
    render(<List />)
    expect(names()).toEqual(['Alpha', 'Bravo', 'Charlie'])
    for (const n of ['Alpha', 'Bravo', 'Charlie']) {
      expect(screen.getByRole('button', { name: `Reorder ${n}` })).toBeInTheDocument()
    }
  })

  it('grips are keyboard-reachable sortable handles', () => {
    render(<List />)
    const grip = screen.getByRole('button', { name: 'Reorder Alpha' })
    expect(grip).toHaveAttribute('aria-roledescription', 'sortable')
    expect(grip).toHaveAttribute('tabindex', '0')
  })

  it('offers no grip when there is nothing to reorder', () => {
    render(<List items={[ITEMS[0]]} />)
    expect(screen.queryByRole('button', { name: /reorder/i })).not.toBeInTheDocument()
    expect(names()).toEqual(['Alpha'])
  })

  it('offers no grip while disabled', () => {
    render(<List disabled />)
    expect(screen.queryByRole('button', { name: /reorder/i })).not.toBeInTheDocument()
  })

  it('reports the full new order and shows it at once after a drop', async () => {
    const onReorder = vi.fn()
    render(<List onReorder={onReorder} />)
    await drop('a', 'c')
    expect(onReorder).toHaveBeenCalledWith(['b', 'c', 'a'], { from: 0, to: 2 })
    expect(names()).toEqual(['Bravo', 'Charlie', 'Alpha'])
  })

  it('moves an item up as well as down', async () => {
    const onReorder = vi.fn()
    render(<List onReorder={onReorder} />)
    await drop('c', 'a')
    expect(onReorder).toHaveBeenCalledWith(['c', 'a', 'b'], { from: 2, to: 0 })
  })

  it.each([
    ['dropped on itself', 'b', 'b'],
    ['dropped outside the list', 'b', null],
    ['dropped on an unknown row', 'b', 'zzz'],
  ])('ignores an item %s', async (_name, active, over) => {
    const onReorder = vi.fn()
    render(<List onReorder={onReorder} />)
    await drop(active, over)
    expect(onReorder).not.toHaveBeenCalled()
    expect(names()).toEqual(['Alpha', 'Bravo', 'Charlie'])
  })

  it('snaps back to the original order when saving fails', async () => {
    const onReorder = vi.fn().mockRejectedValue(new Error('nope'))
    render(<List onReorder={onReorder} />)
    await drop('a', 'b')
    await waitFor(() => expect(names()).toEqual(['Alpha', 'Bravo', 'Charlie']))
  })

  it('takes the new order from the data once it arrives', async () => {
    const { rerender } = render(<List />)
    await drop('a', 'c')
    rerender(<List items={[ITEMS[1], ITEMS[2], ITEMS[0]]} />)
    expect(names()).toEqual(['Bravo', 'Charlie', 'Alpha'])
  })

  it('follows items added or removed by the data', () => {
    const { rerender } = render(<List />)
    rerender(<List items={[ITEMS[0], { id: 'd', name: 'Delta' }]} />)
    expect(names()).toEqual(['Alpha', 'Delta'])
  })

  it('works as a grid too', async () => {
    const onReorder = vi.fn()
    render(<List layout="grid" onReorder={onReorder} />)
    await drop('b', 'a')
    expect(onReorder).toHaveBeenCalledWith(['b', 'a', 'c'], { from: 1, to: 0 })
  })
})
