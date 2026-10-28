import { useEffect, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import type { DragEndEvent, Modifier } from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  rectSortingStrategy,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical } from 'lucide-react'
import { ICON_SIZE } from '../theme'
import styles from './SortableList.module.css'

/** What a row needs to take part in the list: attach `setNodeRef`/`style`, place `handle`. */
export interface SortableRow {
  /** Attach to the row's root element. */
  setNodeRef: (el: HTMLElement | null) => void
  /** Spread on the same element: the drag transform and the lifted look. */
  style: CSSProperties
  /** The grip to drag by. `null` when there is nothing to reorder (one item). */
  handle: ReactNode
  isDragging: boolean
}

export interface SortableListProps<T> {
  items: T[]
  getId: (item: T) => string
  /** Human name of an item, for the grip's label and screen-reader announcements. */
  getLabel: (item: T) => string
  /**
   * Called with the full new order after a drop. The list shows the new order at
   * once; if this rejects it snaps back.
   */
  onReorder: (ids: string[], move: { from: number; to: number }) => void | Promise<void>
  renderItem: (item: T, row: SortableRow) => ReactNode
  /** Class for the element wrapping the rows. */
  className?: string
  /** `vertical`: one column, rows move up and down. `grid`: rows may move in any direction. */
  layout?: 'vertical' | 'grid'
  disabled?: boolean
}

/** In a single column, rows only move up and down. */
const restrictToVerticalAxis: Modifier = ({ transform }) => ({ ...transform, x: 0 })

function Row<T>({
  item,
  id,
  label,
  alone,
  disabled,
  renderItem,
}: {
  item: T
  id: string
  label: string
  alone: boolean
  disabled: boolean
  renderItem: SortableListProps<T>['renderItem']
}) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } =
    useSortable({ id, disabled })

  const handle =
    alone || disabled ? null : (
      <button
        type="button"
        ref={setActivatorNodeRef}
        className={styles.handle}
        aria-label={`Reorder ${label}`}
        {...attributes}
        {...listeners}
      >
        <GripVertical size={ICON_SIZE.md} aria-hidden="true" />
      </button>
    )

  const style: CSSProperties = {
    transform: CSS.Translate.toString(transform),
    transition,
    ...(isDragging ? { position: 'relative', zIndex: 10, opacity: 0.85 } : {}),
  }

  return <>{renderItem(item, { setNodeRef, style, handle, isDragging })}</>
}

/**
 * A list (one column, or a grid) whose rows can be reordered by dragging their grip: with a
 * mouse, by touch, or from the keyboard (focus the grip, Space to pick up, arrows
 * to move, Space to drop). Reordering is the list's only job; what a row looks
 * like, and what a drop does, is up to the caller.
 */
export default function SortableList<T>({
  items,
  getId,
  getLabel,
  onReorder,
  renderItem,
  className,
  layout = 'vertical',
  disabled = false,
}: SortableListProps<T>) {
  const sensors = useSensors(
    // A few pixels of travel before a drag starts, so a plain click still clicks.
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const ids = items.map(getId)
  const key = ids.join('\u0000')
  /** Order shown right after a drop, until the caller's data catches up. */
  const [pending, setPending] = useState<string[] | null>(null)
  useEffect(() => setPending(null), [key])

  const order = pending ?? ids
  const byId = new Map(items.map((item) => [getId(item), item]))
  const shown = order.map((id) => byId.get(id)).filter((item): item is T => item !== undefined)

  const labelOf = (id: string | number) => {
    const item = byId.get(String(id))
    return item === undefined ? 'item' : getLabel(item)
  }

  const handleDragEnd = async ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return
    const from = order.indexOf(String(active.id))
    const to = order.indexOf(String(over.id))
    if (from < 0 || to < 0) return
    const next = arrayMove(order, from, to)
    setPending(next)
    try {
      await onReorder(next, { from, to })
    } catch {
      setPending(null)
    }
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      modifiers={layout === 'vertical' ? [restrictToVerticalAxis] : []}
      onDragEnd={handleDragEnd}
      accessibility={{
        screenReaderInstructions: {
          draggable:
            `To pick up an item, press space or enter. Use the ${
              layout === 'grid' ? 'arrow keys' : 'up and down arrow keys'
            } to move it, then press space or enter to drop it, or escape to cancel.`,
        },
        announcements: {
          onDragStart: ({ active }) => `Picked up ${labelOf(active.id)}.`,
          onDragOver: ({ active, over }) =>
            over
              ? `${labelOf(active.id)} is over position ${order.indexOf(String(over.id)) + 1} of ${order.length}.`
              : undefined,
          onDragEnd: ({ active, over }) =>
            over
              ? `Dropped ${labelOf(active.id)} at position ${order.indexOf(String(over.id)) + 1} of ${order.length}.`
              : `Dropped ${labelOf(active.id)}.`,
          onDragCancel: ({ active }) => `Cancelled. ${labelOf(active.id)} was not moved.`,
        },
      }}
    >
      <SortableContext
        items={order}
        strategy={layout === 'grid' ? rectSortingStrategy : verticalListSortingStrategy}
        disabled={disabled}
      >
        <div className={className}>
          {shown.map((item) => {
            const id = getId(item)
            return (
              <Row
                key={id}
                item={item}
                id={id}
                label={getLabel(item)}
                alone={shown.length < 2}
                disabled={disabled}
                renderItem={renderItem}
              />
            )
          })}
        </div>
      </SortableContext>
    </DndContext>
  )
}
