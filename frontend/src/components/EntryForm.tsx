import { FormEvent } from 'react'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Check, X, Trash2 } from 'lucide-react'
import { AutoResizeTextarea } from './AutoResizeTextarea'
import { DateInput } from './DateInput'
import SortableList from './SortableList'
import { FieldError } from './FieldError'
import styles from './EntryForm.module.css'

export interface FieldConfig {
  name: string
  label: string
  type: 'text' | 'textarea' | 'highlights' | 'date'
  required: boolean
  group?: string
  /** `date` fields only: let the calendar choose a day, not just a month. */
  days?: boolean
  placeholder?: string
}

interface EntryFormProps {
  fields: FieldConfig[]
  schema: z.ZodTypeAny
  defaultValues?: Record<string, string | string[]>
  onSubmit: (data: Record<string, string | string[]>) => void
  onCancel: () => void
}

type HighlightItem = { value: string }
type InternalValues = Record<string, string | HighlightItem[]>

function buildInternalDefaults(
  defaults: Record<string, string | string[]>,
  fields: FieldConfig[],
): InternalValues {
  const result: InternalValues = {}
  for (const field of fields) {
    if (field.type === 'highlights') {
      const arr = (defaults[field.name] as string[]) ?? []
      result[field.name] = arr.map((v) => ({ value: v }))
    } else {
      result[field.name] = (defaults[field.name] as string) ?? ''
    }
  }
  return result
}

function buildExternalData(
  data: InternalValues,
  fields: FieldConfig[],
): Record<string, string | string[]> {
  const result: Record<string, string | string[]> = {}
  for (const field of fields) {
    if (field.type === 'highlights') {
      const arr = data[field.name] as HighlightItem[] | undefined
      result[field.name] = (arr ?? []).map((h) => h.value)
    } else {
      result[field.name] = (data[field.name] as string) ?? ''
    }
  }
  return result
}

export function EntryForm({ fields, schema, defaultValues = {}, onSubmit, onCancel }: EntryFormProps) {
  const highlightsField = fields.find((f) => f.type === 'highlights')

  const augmentedSchema = highlightsField
    ? (schema as z.ZodObject<z.ZodRawShape>).extend({
        [highlightsField.name]: z.array(z.object({ value: z.string() })).default([]),
      })
    : schema

  const form = useForm<InternalValues>({
    resolver: zodResolver(augmentedSchema),
    defaultValues: buildInternalDefaults(defaultValues, fields),
    mode: 'onBlur',
  })

  const highlightsArray = useFieldArray({
    control: form.control,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    name: (highlightsField?.name ?? '__highlights') as any,
  }) as unknown as {
    fields: { id: string; value: string }[]
    append: (v: { value: string }) => void
    remove: (i: number) => void
    move: (from: number, to: number) => void
  }

  const handleSubmit = (data: InternalValues) => {
    onSubmit(buildExternalData(data, fields))
  }

  const handleFormSubmit = (e: FormEvent) => {
    e.preventDefault()
    form.handleSubmit(handleSubmit)(e)
  }

  const renderTextField = (field: FieldConfig, inGroup = false) => (
    <div key={field.name} className={`${styles.fieldGroup} ${inGroup ? styles.fieldGroupInline : ''}`}>
      <label htmlFor={field.name} className={styles.label}>
        {field.label}
        {field.required && <span className={styles.required}>*</span>}
      </label>
      {field.type === 'date' ? (
        <DateInput
          id={field.name}
          className={styles.input}
          placeholder={field.placeholder}
          value={(form.watch(field.name as keyof InternalValues) as string) ?? ''}
          onChange={(value) =>
            form.setValue(field.name as keyof InternalValues, value as InternalValues[keyof InternalValues], {
              shouldDirty: true,
            })
          }
          invalid={!!form.formState.errors[field.name]}
          days={field.days}
        />
      ) : (
        <input
          type="text"
          id={field.name}
          className={styles.input}
          placeholder={inGroup ? (field.placeholder ?? field.label) : field.placeholder}
          aria-invalid={!!form.formState.errors[field.name]}
          {...form.register(field.name)}
        />
      )}
      <FieldError error={form.formState.errors[field.name] as import('react-hook-form').FieldError | undefined} />
    </div>
  )

  // Consecutive fields sharing the same `group` key render in one flex row
  const rows: (FieldConfig | FieldConfig[])[] = []
  let i = 0
  while (i < fields.length) {
    const field = fields[i]
    if (field.group) {
      const group: FieldConfig[] = [field]
      i++
      while (i < fields.length && fields[i].group === field.group) {
        group.push(fields[i])
        i++
      }
      rows.push(group)
    } else {
      rows.push(field)
      i++
    }
  }

  return (
    <form className={styles.form} onSubmit={handleFormSubmit} noValidate>
      <div className={styles.formHeader}>
        <button type="submit" className={styles.saveIconButton} aria-label="Save">
          <Check size={14} />
        </button>
        <button type="button" className={styles.cancelIconButton} onClick={onCancel} aria-label="Cancel">
          <X size={14} />
        </button>
      </div>
      {rows.map((row) => {
        if (Array.isArray(row)) {
          return (
            <div key={row.map((f) => f.name).join('-')} className={styles.fieldRow}>
              {row.map((field) => renderTextField(field, true))}
            </div>
          )
        }

        const field = row

        if (field.type === 'highlights') {
          return (
            <div key={field.name} className={styles.fieldGroup}>
              <label className={styles.label}>
                {field.label}
                {field.required && <span className={styles.required}>*</span>}
              </label>
              <div className={styles.highlightsList}>
                <SortableList
                  className={styles.highlightsList}
                  items={highlightsArray.fields}
                  getId={(item) => item.id}
                  getLabel={(item) => `highlight ${highlightsArray.fields.findIndex((f) => f.id === item.id) + 1}`}
                  onReorder={(_ids, { from, to }) => highlightsArray.move(from, to)}
                  renderItem={(item, sortable) => {
                    const index = highlightsArray.fields.findIndex((f) => f.id === item.id)
                    return (
                      <div ref={sortable.setNodeRef} style={sortable.style} className={styles.highlightItem}>
                        {sortable.handle}
                        <AutoResizeTextarea
                          className={styles.highlightTextarea}
                          placeholder="Highlight"
                          value={form.watch(`${field.name}.${index}.value` as keyof InternalValues) as string ?? ''}
                          onChange={(value) => form.setValue(`${field.name}.${index}.value` as keyof InternalValues, value as InternalValues[keyof InternalValues])}
                        />
                        <button
                          type="button"
                          className={styles.removeButton}
                          onClick={() => highlightsArray.remove(index)}
                          aria-label="Remove"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    )
                  }}
                />
                <button
                  type="button"
                  className={styles.addButton}
                  onClick={() => highlightsArray.append({ value: '' })}
                  aria-label="Add highlight"
                >
                  Add Highlight
                </button>
              </div>
            </div>
          )
        }

        if (field.type === 'textarea') {
          return (
            <div key={field.name} className={styles.fieldGroup}>
              <label htmlFor={field.name} className={styles.label}>
                {field.label}
                {field.required && <span className={styles.required}>*</span>}
              </label>
              <AutoResizeTextarea
                id={field.name}
                className={styles.textarea}
                value={form.watch(field.name as keyof InternalValues) as string ?? ''}
                onChange={(value) => form.setValue(field.name as keyof InternalValues, value as InternalValues[keyof InternalValues])}
                placeholder={field.placeholder}
              />
              <FieldError error={form.formState.errors[field.name] as import('react-hook-form').FieldError | undefined} />
            </div>
          )
        }

        return renderTextField(field)
      })}
    </form>
  )
}
