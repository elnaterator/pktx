import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ExternalLink } from '../../components/ExternalLink'

describe('ExternalLink', () => {
  it('renders a new-tab anchor for an https URL', () => {
    render(<ExternalLink href="https://example.com/job" className="cls">Job</ExternalLink>)
    const link = screen.getByRole('link', { name: 'Job' })
    expect(link).toHaveAttribute('href', 'https://example.com/job')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    expect(link).toHaveClass('cls')
  })

  it.each(['javascript:alert(1)', 'JaVaScRiPt:alert(1)', 'data:text/html,x', 'example.com'])(
    'renders %j as plain text, not a link',
    (href) => {
      const { container } = render(
        <ExternalLink href={href} className="cls">{href}</ExternalLink>,
      )
      expect(screen.queryByRole('link')).not.toBeInTheDocument()
      expect(container.querySelector('a')).toBeNull()
      const text = screen.getByText(href)
      expect(text.tagName).toBe('SPAN')
      expect(text).toHaveClass('cls')
      expect(text).not.toHaveAttribute('href')
    },
  )

  it('renders plain text for null href', () => {
    render(<ExternalLink href={null}>None</ExternalLink>)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText('None')).toBeInTheDocument()
  })

  it('rejects mailto unless allowMailto is set', () => {
    render(<ExternalLink href="mailto:a@example.com">a@example.com</ExternalLink>)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('renders mailto in the same tab when allowMailto is set', () => {
    render(
      <ExternalLink href="mailto:a@example.com" allowMailto>a@example.com</ExternalLink>,
    )
    const link = screen.getByRole('link', { name: 'a@example.com' })
    expect(link).toHaveAttribute('href', 'mailto:a@example.com')
    expect(link).not.toHaveAttribute('target')
  })
})
