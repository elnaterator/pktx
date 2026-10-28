import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EntryForm } from '../../components/EntryForm'
import { buildEntrySchema } from '../../schemas/resumeEntry'
import { z } from 'zod'

const simpleSchema = z.object({
  title: z.string().trim().min(1, 'Title is required'),
  company: z.string().trim().min(1, 'Company is required'),
  location: z.string().trim().optional(),
})

describe('EntryForm', () => {
  const mockOnSubmit = vi.fn()
  const mockOnCancel = vi.fn()

  const simpleFieldConfig = [
    { name: 'title', label: 'Title', type: 'text' as const, required: true },
    { name: 'company', label: 'Company', type: 'text' as const, required: true },
    { name: 'location', label: 'Location', type: 'text' as const, required: false },
  ]

  const textareaFieldConfig = [
    { name: 'summary', label: 'Summary', type: 'textarea' as const, required: true },
  ]

  const summarySchema = z.object({
    summary: z.string().trim().min(1, 'Summary is required'),
  })

  const highlightsFieldConfig = [
    { name: 'title', label: 'Title', type: 'text' as const, required: true },
    { name: 'highlights', label: 'Highlights', type: 'highlights' as const, required: false },
  ]

  const highlightsSchema = z.object({
    title: z.string().trim().min(1, 'Title is required'),
  })

  beforeEach(() => {
    mockOnSubmit.mockClear()
    mockOnCancel.mockClear()
  })

  it('renders all fields from configuration', () => {
    render(
      <EntryForm
        fields={simpleFieldConfig}
        schema={simpleSchema}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    )

    expect(screen.getByLabelText(/title/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/company/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/location/i)).toBeInTheDocument()
  })

  it('marks required fields with asterisk', () => {
    render(
      <EntryForm
        fields={simpleFieldConfig}
        schema={simpleSchema}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    )

    const titleLabel = screen.getByText(/title/i)
    const companyLabel = screen.getByText(/company/i)
    const locationLabel = screen.getByText(/location/i)

    expect(titleLabel.textContent).toContain('*')
    expect(companyLabel.textContent).toContain('*')
    expect(locationLabel.textContent).not.toContain('*')
  })

  it('pre-fills form with defaultValues', () => {
    const defaultValues = {
      title: 'Software Engineer',
      company: 'Tech Corp',
      location: 'San Francisco',
    }

    render(
      <EntryForm
        fields={simpleFieldConfig}
        schema={simpleSchema}
        defaultValues={defaultValues}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    )

    expect(screen.getByLabelText(/title/i)).toHaveValue('Software Engineer')
    expect(screen.getByLabelText(/company/i)).toHaveValue('Tech Corp')
    expect(screen.getByLabelText(/location/i)).toHaveValue('San Francisco')
  })

  it('shows zod error messages on submit', async () => {
    const user = userEvent.setup()

    render(
      <EntryForm
        fields={simpleFieldConfig}
        schema={simpleSchema}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    )

    const submitButton = screen.getByRole('button', { name: /save/i })
    await user.click(submitButton)

    await waitFor(() => {
      expect(screen.getByText('Title is required')).toBeInTheDocument()
      expect(screen.getByText('Company is required')).toBeInTheDocument()
    })

    expect(mockOnSubmit).not.toHaveBeenCalled()
  })

  it('error messages have role="alert"', async () => {
    const user = userEvent.setup()

    render(
      <EntryForm
        fields={simpleFieldConfig}
        schema={simpleSchema}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    )

    await user.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => {
      const alerts = screen.getAllByRole('alert')
      expect(alerts.length).toBeGreaterThan(0)
    })
  })

  it('submits valid data with correct shape', async () => {
    const user = userEvent.setup()

    render(
      <EntryForm
        fields={simpleFieldConfig}
        schema={simpleSchema}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    )

    await user.type(screen.getByLabelText(/title/i), 'Senior Engineer')
    await user.type(screen.getByLabelText(/company/i), 'Big Tech')
    await user.type(screen.getByLabelText(/location/i), 'New York')

    await user.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        title: 'Senior Engineer',
        company: 'Big Tech',
        location: 'New York',
      })
    })
  })

  it('calls onCancel when cancel button clicked', async () => {
    const user = userEvent.setup()

    render(
      <EntryForm
        fields={simpleFieldConfig}
        schema={simpleSchema}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    )

    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(mockOnCancel).toHaveBeenCalled()
    expect(mockOnSubmit).not.toHaveBeenCalled()
  })

  it('renders textarea for textarea type fields', () => {
    render(
      <EntryForm
        fields={textareaFieldConfig}
        schema={summarySchema}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    )

    const summaryInput = screen.getByLabelText(/summary/i)
    expect(summaryInput.tagName).toBe('TEXTAREA')
  })

  it('handles highlights field as dynamic list via useFieldArray', async () => {
    const user = userEvent.setup()

    render(
      <EntryForm
        fields={highlightsFieldConfig}
        schema={highlightsSchema}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    )

    expect(screen.getByText(/highlights/i)).toBeInTheDocument()

    const addButton = screen.getByRole('button', { name: /add highlight/i })
    await user.click(addButton)

    const highlightInputs = screen.getAllByPlaceholderText(/highlight/i)
    expect(highlightInputs).toHaveLength(1)

    await user.type(highlightInputs[0], 'Led team of 5 engineers')

    await user.click(addButton)
    const updatedInputs = screen.getAllByPlaceholderText(/highlight/i)
    expect(updatedInputs).toHaveLength(2)
  })

  it('removes highlight from list when remove button clicked', async () => {
    const user = userEvent.setup()

    render(
      <EntryForm
        fields={highlightsFieldConfig}
        schema={highlightsSchema}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    )

    const addButton = screen.getByRole('button', { name: /add highlight/i })
    await user.click(addButton)
    await user.click(addButton)

    let highlightInputs = screen.getAllByPlaceholderText(/highlight/i)
    expect(highlightInputs).toHaveLength(2)

    const removeButtons = screen.getAllByRole('button', { name: /remove/i })
    await user.click(removeButtons[0])

    highlightInputs = screen.getAllByPlaceholderText(/highlight/i)
    expect(highlightInputs).toHaveLength(1)
  })

  it('submits highlights as string array', async () => {
    const user = userEvent.setup()

    render(
      <EntryForm
        fields={highlightsFieldConfig}
        schema={highlightsSchema}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    )

    await user.type(screen.getByLabelText(/title/i), 'Engineer')

    const addButton = screen.getByRole('button', { name: /add highlight/i })
    await user.click(addButton)
    await user.click(addButton)

    const highlightInputs = screen.getAllByPlaceholderText(/highlight/i)
    await user.type(highlightInputs[0], 'First highlight')
    await user.type(highlightInputs[1], 'Second highlight')

    await user.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Engineer',
          highlights: ['First highlight', 'Second highlight'],
        })
      )
    })
  })

  it('pre-fills highlights from defaultValues', () => {
    const defaultValues = {
      title: 'Engineer',
      highlights: ['Highlight one', 'Highlight two', 'Highlight three'],
    }

    render(
      <EntryForm
        fields={highlightsFieldConfig}
        schema={highlightsSchema}
        defaultValues={defaultValues}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    )

    const highlightInputs = screen.getAllByPlaceholderText(/highlight/i)
    expect(highlightInputs).toHaveLength(3)
    expect(highlightInputs[0]).toHaveValue('Highlight one')
    expect(highlightInputs[1]).toHaveValue('Highlight two')
    expect(highlightInputs[2]).toHaveValue('Highlight three')
  })

  it('submits empty highlights array when no highlights added', async () => {
    const user = userEvent.setup()

    render(
      <EntryForm
        fields={highlightsFieldConfig}
        schema={highlightsSchema}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    )

    await user.type(screen.getByLabelText(/title/i), 'Engineer')
    await user.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        title: 'Engineer',
        highlights: [],
      })
    })
  })

  it('works with a schema built from JSON Resume section fields', async () => {
    const user = userEvent.setup()
    const fields = [
      { name: 'position', label: 'Position', type: 'text' as const, required: true },
      { name: 'name', label: 'Company', type: 'text' as const, required: false },
      { name: 'highlights', label: 'Highlights', type: 'highlights' as const, required: false },
    ]
    const schema = buildEntrySchema(
      [
        { name: 'position', label: 'Position', widget: 'text' },
        { name: 'name', label: 'Company', widget: 'text' },
        { name: 'highlights', label: 'Highlights', widget: 'bullets' },
      ],
      'position',
    )

    render(
      <EntryForm
        fields={fields}
        schema={schema}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    )

    await user.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => {
      expect(screen.getByText('Position is required')).toBeInTheDocument()
    })
  })

  it('works with a built schema that has no list field', async () => {
    const user = userEvent.setup()
    const fields = [
      { name: 'language', label: 'Language', type: 'text' as const, required: true, group: 'main' },
      { name: 'fluency', label: 'Fluency', type: 'text' as const, required: false, group: 'main' },
    ]
    const schema = buildEntrySchema(
      [
        { name: 'language', label: 'Language', widget: 'text' },
        { name: 'fluency', label: 'Fluency', widget: 'text' },
      ],
      'language',
    )

    render(
      <EntryForm
        fields={fields}
        schema={schema}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    )

    await user.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => {
      expect(screen.getByText('Language is required')).toBeInTheDocument()
    })
  })

  describe('bullet keyboard editing', () => {
    it('Enter splits the bullet at the caret into a new one', async () => {
      const user = userEvent.setup()
      render(
        <EntryForm
          fields={highlightsFieldConfig}
          schema={highlightsSchema}
          defaultValues={{ title: 'Engineer', highlights: ['Led teamShipped'] }}
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      )

      const first = screen.getByLabelText('Highlight 1') as HTMLTextAreaElement
      await user.click(first)
      first.setSelectionRange(8, 8)
      await user.keyboard('{Enter}')

      const bullets = screen.getAllByPlaceholderText(/highlight/i)
      expect(bullets.map((b) => (b as HTMLTextAreaElement).value)).toEqual(['Led team', 'Shipped'])
      expect(bullets[1]).toHaveFocus()
    })

    it('Backspace in an empty bullet removes it and focuses the previous one', async () => {
      const user = userEvent.setup()
      render(
        <EntryForm
          fields={highlightsFieldConfig}
          schema={highlightsSchema}
          defaultValues={{ title: 'Engineer', highlights: ['One', ''] }}
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      )

      await user.click(screen.getByLabelText('Highlight 2'))
      await user.keyboard('{Backspace}')

      const bullets = screen.getAllByPlaceholderText(/highlight/i)
      expect(bullets).toHaveLength(1)
      expect(bullets[0]).toHaveFocus()
    })
  })

  describe('open-ended end date', () => {
    const dateFields = [
      { name: 'title', label: 'Title', type: 'text' as const, required: true },
      { name: 'endDate', label: 'End date', type: 'date' as const, required: false, openEnded: true },
    ]
    const dateSchema = z.object({ title: z.string().min(1), endDate: z.string().optional() })

    it('starts as Present when blank and disables the date', () => {
      render(
        <EntryForm fields={dateFields} schema={dateSchema} onSubmit={mockOnSubmit} onCancel={mockOnCancel} />
      )
      expect(screen.getByRole('checkbox', { name: /present/i })).toBeChecked()
      expect(screen.getByLabelText('End date')).toBeDisabled()
    })

    it('checking Present clears the end date', async () => {
      const user = userEvent.setup()
      render(
        <EntryForm
          fields={dateFields}
          schema={dateSchema}
          defaultValues={{ title: 'Engineer', endDate: '2023-12' }}
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      )
      const present = screen.getByRole('checkbox', { name: /present/i })
      expect(present).not.toBeChecked()
      await user.click(present)
      await user.click(screen.getByRole('button', { name: /save/i }))

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith({ title: 'Engineer', endDate: '' })
      })
    })
  })

  describe('keyboard shortcuts', () => {
    it('Ctrl+Enter saves', async () => {
      const user = userEvent.setup()
      render(
        <EntryForm
          fields={simpleFieldConfig}
          schema={simpleSchema}
          defaultValues={{ title: 'Engineer', company: 'Acme', location: '' }}
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      )
      await user.click(screen.getByLabelText(/location/i))
      await user.keyboard('{Control>}{Enter}{/Control}')
      await waitFor(() => expect(mockOnSubmit).toHaveBeenCalled())
    })

    it('Escape cancels', async () => {
      const user = userEvent.setup()
      render(
        <EntryForm fields={simpleFieldConfig} schema={simpleSchema} onSubmit={mockOnSubmit} onCancel={mockOnCancel} />
      )
      await user.click(screen.getByLabelText(/title/i))
      await user.keyboard('{Escape}')
      expect(mockOnCancel).toHaveBeenCalled()
    })
  })
})
