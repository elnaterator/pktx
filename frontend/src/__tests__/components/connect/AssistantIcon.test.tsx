import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { AssistantIcon } from '../../../components/connect/AssistantIcon'
import { buildAssistants } from '../../../components/connect/connectAssistants'

describe('AssistantIcon', () => {
  it.each(buildAssistants('https://pktx.test/mcp'))('renders a brand mark for $name', ({ id }) => {
    const { container } = render(<AssistantIcon id={id} />)
    const svg = container.querySelector('svg')
    expect(svg).toHaveAttribute('aria-hidden', 'true')
    expect(svg?.querySelector('path')?.getAttribute('d')).toBeTruthy()
  })
})
