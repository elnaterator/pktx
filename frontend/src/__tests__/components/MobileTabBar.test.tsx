import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router'
import MobileTabBar from '../../components/MobileTabBar'

let currentPath = ''
function LocationProbe() {
  currentPath = useLocation().pathname
  return null
}

function renderBar(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <MobileTabBar />
      <LocationProbe />
    </MemoryRouter>,
  )
}

const bar = () => within(screen.getByRole('navigation', { name: 'Main navigation' }))

describe('MobileTabBar', () => {
  it('shows Home, Applications, Resumes and Contacts, then More', () => {
    renderBar()
    expect(bar().getAllByRole('link').map((l) => l.getAttribute('aria-label'))).toEqual([
      'Home',
      'Applications',
      'Resumes',
      'Contacts',
    ])
    expect(bar().getByRole('link', { name: 'Applications' })).toHaveTextContent('Jobs')
    expect(bar().getByRole('button', { name: 'More' })).toBeInTheDocument()
  })

  it('marks the current section', () => {
    renderBar('/applications/3')
    expect(bar().getByRole('link', { name: 'Applications' })).toHaveAttribute('aria-current', 'page')
    expect(bar().getByRole('link', { name: 'Home' })).not.toHaveAttribute('aria-current')
  })

  it('opens a sheet with Accomplishments and Notes, and closes it on navigation', async () => {
    const user = userEvent.setup()
    renderBar()
    await user.click(bar().getByRole('button', { name: 'More' }))
    const sheet = screen.getByRole('dialog', { name: 'More sections' })
    expect(within(sheet).getAllByRole('link').map((l) => l.textContent)).toEqual(['Accomplishments', 'Notes'])
    await user.click(within(sheet).getByRole('link', { name: 'Notes' }))
    expect(currentPath).toBe('/notes')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('highlights More while on a section inside it', () => {
    renderBar('/accomplishments/7')
    expect(bar().getByRole('button', { name: 'More' })).toHaveAttribute('aria-current', 'page')
  })
})
