import '@testing-library/jest-dom'
import { vi } from 'vitest'

vi.mock('@testing-library/react', async () => {
  const actual =
    await vi.importActual<typeof import('@testing-library/react')>('@testing-library/react')
  const React = await vi.importActual<typeof import('react')>('react')
  const { QueryClient, QueryClientProvider } =
    await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query')
  const { ToastProvider } =
    await vi.importActual<typeof import('../components/toast')>('../components/toast')

  type RenderArgs = Parameters<typeof actual.render>
  const render: typeof actual.render = (ui, options) => {
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0, refetchOnWindowFocus: false },
        mutations: { retry: false },
      },
    })
    const ExistingWrapper = options?.wrapper
    const Wrapper = ({ children }: { children: React.ReactNode }) => {
      const inner = ExistingWrapper
        ? React.createElement(ExistingWrapper, null, children)
        : (children as React.ReactElement)
      return React.createElement(
        QueryClientProvider,
        { client },
        React.createElement(ToastProvider, null, inner),
      )
    }
    return actual.render(ui, { ...options, wrapper: Wrapper } as RenderArgs[1])
  }

  return { ...actual, render }
})

// Newer Node ships its own global `localStorage` that shadows jsdom's and is
// unusable without `--localstorage-file`. Swap in an in-memory Storage when so.
if (typeof globalThis.localStorage?.clear !== 'function') {
  class MemoryStorage implements Storage {
    private data = new Map<string, string>()
    get length() {
      return this.data.size
    }
    clear() {
      this.data.clear()
    }
    getItem(key: string) {
      return this.data.get(key) ?? null
    }
    key(index: number) {
      return [...this.data.keys()][index] ?? null
    }
    removeItem(key: string) {
      this.data.delete(key)
    }
    setItem(key: string, value: string) {
      this.data.set(key, String(value))
    }
  }
  Object.defineProperty(globalThis, 'localStorage', {
    value: new MemoryStorage(),
    configurable: true,
  })
}
