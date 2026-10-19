import { describe, it, expect, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { DateInput } from '../../components/DateInput'

function Harness({
  initial = '',
  days = false,
  onChange = vi.fn(),
}: {
  initial?: string
  days?: boolean
  onChange?: (v: string) => void
}) {
  const [value, setValue] = useState(initial)
  return (
    <div>
      <DateInput
        id="d"
        value={value}
        days={days}
        onChange={(v) => {
          setValue(v)
          onChange(v)
        }}
      />
      <button type="button">outside</button>
    </div>
  )
}

const field = () => document.getElementById('d') as HTMLInputElement
const openCalendar = async (user: ReturnType<typeof userEvent.setup>) =>
  user.click(screen.getByRole('button', { name: 'Choose date' }))
const dialog = () => screen.getByRole('dialog', { name: 'Choose date' })

describe('DateInput', () => {
  it('still accepts a typed partial ISO date', async () => {
    const onChange = vi.fn()
    render(<Harness onChange={onChange} />)
    await userEvent.setup().type(field(), '2024')
    expect(field()).toHaveValue('2024')
    expect(onChange).toHaveBeenLastCalledWith('2024')
  })

  it('opens an in-page calendar from the button and closes it again', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await openCalendar(user)
    expect(dialog()).toBeInTheDocument()
    await openCalendar(user)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('closes on Escape and on a click outside', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await openCalendar(user)
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await openCalendar(user)
    await user.click(screen.getByRole('button', { name: 'outside' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('picks a month: writes YYYY-MM and closes', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Harness initial="2021-03" onChange={onChange} />)
    await openCalendar(user)
    await user.click(within(dialog()).getByRole('button', { name: 'July 2021' }))
    expect(field()).toHaveValue('2021-07')
    expect(onChange).toHaveBeenCalledWith('2021-07')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens on the typed year and steps years with the arrows', async () => {
    const user = userEvent.setup()
    render(<Harness initial="2015-05" />)
    await openCalendar(user)
    expect(within(dialog()).getByRole('spinbutton', { name: 'Year' })).toHaveValue(2015)
    await user.click(within(dialog()).getByRole('button', { name: 'Previous year' }))
    await user.click(within(dialog()).getByRole('button', { name: 'Previous year' }))
    await user.click(within(dialog()).getByRole('button', { name: 'Next year' }))
    await user.click(within(dialog()).getByRole('button', { name: 'February 2014' }))
    expect(field()).toHaveValue('2014-02')
  })

  it('lets you type a year in the calendar', async () => {
    const user = userEvent.setup()
    render(<Harness initial="2015" />)
    await openCalendar(user)
    fireEvent.change(within(dialog()).getByRole('spinbutton', { name: 'Year' }), {
      target: { value: '1999' },
    })
    await user.click(within(dialog()).getByRole('button', { name: 'Year only' }))
    expect(field()).toHaveValue('1999')
  })

  it('marks the current month as selected', async () => {
    const user = userEvent.setup()
    render(<Harness initial="2021-03" />)
    await openCalendar(user)
    const march = within(dialog()).getByRole('button', { name: 'March 2021' })
    expect(march.className).toMatch(/selected/)
    expect(within(dialog()).getByRole('button', { name: 'April 2021' }).className).not.toMatch(
      /selected/,
    )
  })

  it('picks a year only', async () => {
    const user = userEvent.setup()
    render(<Harness initial="2008-01" />)
    await openCalendar(user)
    await user.click(within(dialog()).getByRole('button', { name: 'Year only' }))
    expect(field()).toHaveValue('2008')
  })

  it('clears the field', async () => {
    const user = userEvent.setup()
    render(<Harness initial="2008-01" />)
    await openCalendar(user)
    await user.click(within(dialog()).getByRole('button', { name: 'Clear' }))
    expect(field()).toHaveValue('')
  })

  it('falls back to the current year for an unparseable value', async () => {
    const user = userEvent.setup()
    render(<Harness initial="March 2021" />)
    await openCalendar(user)
    expect(within(dialog()).getByRole('spinbutton', { name: 'Year' })).toHaveValue(
      new Date().getFullYear(),
    )
  })

  describe('with days', () => {
    it('goes on to a day grid after choosing a month', async () => {
      const user = userEvent.setup()
      const onChange = vi.fn()
      render(<Harness initial="2024-02" days onChange={onChange} />)
      await openCalendar(user)
      await user.click(within(dialog()).getByRole('button', { name: 'February 2024' }))
      expect(onChange).not.toHaveBeenCalled()
      expect(within(dialog()).getByText('February 2024')).toBeInTheDocument()
      // 2024 is a leap year
      expect(within(dialog()).getByRole('button', { name: 'February 29, 2024' })).toBeInTheDocument()
      expect(
        within(dialog()).queryByRole('button', { name: 'February 30, 2024' }),
      ).not.toBeInTheDocument()

      await user.click(within(dialog()).getByRole('button', { name: 'February 14, 2024' }))
      expect(field()).toHaveValue('2024-02-14')
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('can keep just the month, or go back to the months', async () => {
      const user = userEvent.setup()
      render(<Harness initial="2023-05" days />)
      await openCalendar(user)
      await user.click(within(dialog()).getByRole('button', { name: 'May 2023' }))
      await user.click(within(dialog()).getByRole('button', { name: 'Months' }))
      await user.click(within(dialog()).getByRole('button', { name: 'June 2023' }))
      await user.click(within(dialog()).getByRole('button', { name: 'Month only' }))
      expect(field()).toHaveValue('2023-06')
    })

    it('steps between months, rolling the year over', async () => {
      const user = userEvent.setup()
      render(<Harness initial="2023-12" days />)
      await openCalendar(user)
      await user.click(within(dialog()).getByRole('button', { name: 'December 2023' }))
      await user.click(within(dialog()).getByRole('button', { name: 'Next month' }))
      expect(within(dialog()).getByText('January 2024')).toBeInTheDocument()
      await user.click(within(dialog()).getByRole('button', { name: 'January 1, 2024' }))
      expect(field()).toHaveValue('2024-01-01')
    })

    it('highlights the day already chosen', async () => {
      const user = userEvent.setup()
      render(<Harness initial="2023-05-09" days />)
      await openCalendar(user)
      await user.click(within(dialog()).getByRole('button', { name: 'May 2023' }))
      expect(
        within(dialog()).getByRole('button', { name: 'May 9, 2023' }).className,
      ).toMatch(/selected/)
    })
  })

  it('never offers days unless asked', async () => {
    const user = userEvent.setup()
    render(<Harness initial="2023-05" />)
    await openCalendar(user)
    await user.click(within(dialog()).getByRole('button', { name: 'May 2023' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(field()).toHaveValue('2023-05')
  })
})
