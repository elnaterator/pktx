import { act } from '@testing-library/react'
import type { DndContextProps, DragEndEvent } from '@dnd-kit/core'

/**
 * jsdom has no layout, so a real pointer drag cannot work. These helpers wrap the
 * real `DndContext` and let a test fire the drop it would produce, exercising the
 * app's own handler end to end.
 *
 * Use in a test file:
 *   vi.mock('@dnd-kit/core', async () => (await import('../dnd-test-utils')).mockDndKit())
 *
 * (A hoisted `vi.mock` cannot reference a top-level import, hence the dynamic import.)
 */
let contexts: DndContextProps[] = []

export async function mockDndKit() {
  const actual = await vi.importActual<typeof import('@dnd-kit/core')>('@dnd-kit/core')
  return {
    ...actual,
    DndContext: (props: DndContextProps) => {
      const Real = actual.DndContext
      contexts = [...contexts.filter((c) => c !== props), props]
      return <Real {...props} />
    },
  }
}

/** Forget contexts from earlier renders; call in `beforeEach`. */
export function resetDnd() {
  contexts = []
}

/** Drops row `activeId` onto row `overId` in the most recently rendered list. */
export async function drop(activeId: string, overId: string | null, which = -1) {
  const ctx = contexts.at(which)
  if (!ctx?.onDragEnd) throw new Error('No DndContext rendered')
  await act(async () => {
    await ctx.onDragEnd!({
      active: { id: activeId },
      over: overId === null ? null : { id: overId },
    } as unknown as DragEndEvent)
  })
}
