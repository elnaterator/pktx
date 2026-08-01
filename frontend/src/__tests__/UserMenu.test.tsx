import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import UserMenu from '../components/UserMenu'
import { ToastProvider } from '../components/toast'

vi.mock('@clerk/clerk-react', () => {
  const UserButton = Object.assign(
    ({
      afterSignOutUrl,
      children,
    }: {
      afterSignOutUrl: string
      children?: ReactNode
    }) => (
      <div data-testid="user-button" data-after-sign-out-url={afterSignOutUrl}>
        {children}
      </div>
    ),
    {
      MenuItems: ({ children }: { children?: ReactNode }) => <>{children}</>,
      Action: ({ label, onClick }: { label: string; onClick: () => void }) => (
        <button onClick={onClick}>{label}</button>
      ),
    }
  )
  return { useAuth: vi.fn(), UserButton }
})

vi.mock('../services/api', () => ({
  fetchDataExport: vi.fn(),
  saveBlob: vi.fn(),
}))

const { useAuth } = await import('@clerk/clerk-react')
const { fetchDataExport, saveBlob } = await import('../services/api')

const signedIn = () =>
  vi.mocked(useAuth).mockReturnValue({
    isSignedIn: true,
    isLoaded: true,
  } as ReturnType<typeof useAuth>)

const renderMenu = () =>
  render(
    <ToastProvider>
      <UserMenu />
    </ToastProvider>
  )

describe('UserMenu', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders UserButton when signed in', () => {
    signedIn()

    renderMenu()

    expect(screen.getByTestId('user-button')).toBeInTheDocument()
  })

  it('renders UserButton with afterSignOutUrl set to /', () => {
    signedIn()

    renderMenu()

    expect(screen.getByTestId('user-button')).toHaveAttribute('data-after-sign-out-url', '/')
  })

  it('renders nothing when signed out', () => {
    vi.mocked(useAuth).mockReturnValue({
      isSignedIn: false,
      isLoaded: true,
    } as ReturnType<typeof useAuth>)

    const { container } = renderMenu()

    expect(screen.queryByTestId('user-button')).not.toBeInTheDocument()
    expect(container.querySelector('button')).toBeNull()
  })
})

describe('UserMenu data export', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    signedIn()
  })

  it('downloads the export and confirms with a toast', async () => {
    const blob = new Blob(['{}'], { type: 'application/json' })
    vi.mocked(fetchDataExport).mockResolvedValue({
      blob,
      filename: 'pktx-export-2026-07-31.json',
    })

    renderMenu()
    await userEvent.click(screen.getByRole('button', { name: 'Export my data' }))

    await waitFor(() => {
      expect(saveBlob).toHaveBeenCalledWith(blob, 'pktx-export-2026-07-31.json')
    })
    expect(await screen.findByText('Export downloaded')).toBeInTheDocument()
  })

  it('surfaces an error toast and saves nothing when the export fails', async () => {
    vi.mocked(fetchDataExport).mockRejectedValue(new Error('Export failed (HTTP 500)'))

    renderMenu()
    await userEvent.click(screen.getByRole('button', { name: 'Export my data' }))

    expect(await screen.findByText('Export failed (HTTP 500)')).toBeInTheDocument()
    expect(saveBlob).not.toHaveBeenCalled()
  })
})
