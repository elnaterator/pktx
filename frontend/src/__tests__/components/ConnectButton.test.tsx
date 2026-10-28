import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import ConnectButton from '../../components/ConnectButton'

describe('ConnectButton', () => {
  it('links to the connect page', () => {
    render(
      <MemoryRouter>
        <ConnectButton />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Connect AI' })).toHaveAttribute('href', '/connect')
  })

  it('marks itself current on /connect', () => {
    render(
      <MemoryRouter initialEntries={['/connect']}>
        <ConnectButton />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Connect AI' })).toHaveAttribute('aria-current', 'page')
  })
})
