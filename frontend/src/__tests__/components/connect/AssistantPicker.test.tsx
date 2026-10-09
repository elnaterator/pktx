import { describe, it, expect, vi } from 'vitest'
import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AssistantPicker } from '../../../components/connect/AssistantPicker'
import { buildAssistants } from '../../../components/connect/connectAssistants'

const assistants = buildAssistants('https://pktx.test/mcp')

function Harness({ onChange = vi.fn() }: { onChange?: (id: string) => void }) {
  const [value, setValue] = useState(assistants[0].id)
  return (
    <AssistantPicker
      assistants={assistants}
      value={value}
      label="Assistant"
      onChange={(id) => {
        setValue(id)
        onChange(id)
      }}
    />
  )
}

const trigger = () => screen.getByRole('button', { name: /assistant/i })

describe('AssistantPicker', () => {
  it('opens a listbox with an option per assistant, current one selected', async () => {
    render(<Harness />)
    await userEvent.click(trigger())
    const options = screen.getAllByRole('option')
    expect(options).toHaveLength(assistants.length)
    expect(options[0]).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('listbox')).toHaveFocus()
  })

  it('supports keyboard selection', async () => {
    const onChange = vi.fn()
    render(<Harness onChange={onChange} />)
    trigger().focus()
    await userEvent.keyboard('{ArrowDown}{ArrowDown}{Enter}')
    expect(onChange).toHaveBeenCalledWith(assistants[1].id)
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(trigger()).toHaveFocus()

    await userEvent.keyboard('{Enter}{End}{Enter}')
    expect(onChange).toHaveBeenLastCalledWith(assistants[assistants.length - 1].id)

    await userEvent.keyboard('{Enter}{Home} ')
    expect(onChange).toHaveBeenLastCalledWith(assistants[0].id)
  })

  it('jumps by typed letter', async () => {
    const onChange = vi.fn()
    render(<Harness onChange={onChange} />)
    trigger().focus()
    await userEvent.keyboard('{Enter}z{Enter}')
    expect(onChange).toHaveBeenCalledWith('zed')
  })

  it('closes on Escape without changing the value', async () => {
    const onChange = vi.fn()
    render(<Harness onChange={onChange} />)
    trigger().focus()
    await userEvent.keyboard('{Enter}{ArrowDown}{Escape}')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(onChange).not.toHaveBeenCalled()
    expect(trigger()).toHaveFocus()
  })

  it('closes on outside click', async () => {
    render(
      <>
        <Harness />
        <p>outside</p>
      </>,
    )
    await userEvent.click(trigger())
    await userEvent.click(screen.getByText('outside'))
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })
})
