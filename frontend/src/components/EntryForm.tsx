import { KeyboardEvent, useEffect, useRef, useState } from 'react'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, Trash2 } from 'lucide-react'
import { ICON_SIZE } from '../theme'
import { cx } from '../utils/cx'
import { AutoResizeTextarea } from './AutoResizeTextarea'
import { DateInput } from './DateInput'
import SortableList from './SortableList'
import { Button } from './Button'
import { EditForm, FormField } from './EditForm'
import { IconButton } from './IconButton'
import formStyles from './EditForm.module.css'
import styles from './EntryForm.module.css'

export interface FieldConfig {
  name: string
  label: string
  type: 'text' | 'textarea' | 'highlights' | 'date'
  required: boolean
  /** Short field: consecutive fields with the same group pair up two to a row (one on phones). */
  group?: string
  /** `date` fields only: let the calendar choose a day, not just a month. */
  days?: boolean
  /** `date` fields only: empty means ongoing; offer a "Present" checkbox. */
  openEnded?: boolean
  placeholder?: string
}

interface EntryFormProps {
  fields: FieldConfig[]
  schema: z.ZodTypeAny
  defaultValues?: Record<string, string | string[]>
  /** Shown above the fields, e.g. "Editing Senior Engineer". */
  heading?: string
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

/**
 * Field -> grid width. Grouped fields pair up two to a row; a group's odd one
 * out (and every other field) takes the full row.
 */
function layoutOf(fields: FieldConfig[]): Map<string, 'half' | 'full'> {
  const widths = new Map<string, 'half' | 'full'>()
  let i = 0
  while (i < fields.length) {
    const group = fields[i].group
    let j = i + 1
    while (group && j < fields.length && fields[j].group === group) j++
    const run = fields.slice(i, j)
    run.forEach((f, k) => {
      const paired = run.length > 1 && !(k === run.length - 1 && run.length % 2 === 1)
      widths.set(f.name, paired ? 'half' : 'full')
    })
    i = j
  }
  return widths
}

export function EntryForm({
  fields,
  schema,
  defaultValues = {},
  heading,
  onSubmit,
  onCancel,
}: EntryFormProps) {
  const highlightsField = fields.find((f) => f.type === 'highlights')
  const widths = layoutOf(fields)

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
    insert: (i: number, v: { value: string }) => void
    remove: (i: number) => void
    move: (from: number, to: number) => void
  }

  /** Open-ended date fields currently marked "Present" (their value is blank). */
  const [present, setPresent] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(
      fields.filter((f) => f.openEnded).map((f) => [f.name, !defaultValues[f.name]]),
    ),
  )

  /** Bullet last focused; on phones only its grip and delete show (kept on blur so a tap on them lands). */
  const [activeBullet, setActiveBullet] = useState<string | null>(null)

  const formRef = useRef<HTMLFormElement>(null)
  /** Bullet to focus once the list re-renders, and where to put the caret. */
  const focusNext = useRef<{ index: number; caret: 'start' | 'end' } | null>(null)
  useEffect(() => {
    const next = focusNext.current
    if (!next) return
    focusNext.current = null
    const el = formRef.current?.querySelectorAll<HTMLTextAreaElement>('[data-bullet]')[next.index]
    if (!el) return
    el.focus()
    const pos = next.caret === 'start' ? 0 : el.value.length
    el.setSelectionRange(pos, pos)
  })

  const handleSubmit = (data: InternalValues) => {
    onSubmit(buildExternalData(data, fields))
  }

  const submit = () => form.handleSubmit(handleSubmit)()

  const bulletPath = (index: number) => `${highlightsField?.name}.${index}.value` as keyof InternalValues
  const setBullet = (index: number, value: string) =>
    form.setValue(bulletPath(index), value as InternalValues[keyof InternalValues], { shouldDirty: true })

  // Enter splits the bullet at the caret (Shift+Enter is a line break);
  // Backspace at the start of an empty bullet removes it.
  const handleBulletKeyDown = (index: number, e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.nativeEvent.isComposing || e.metaKey || e.ctrlKey) return
    const el = e.currentTarget
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      const value = el.value
      setBullet(index, value.slice(0, el.selectionStart))
      highlightsArray.insert(index + 1, { value: value.slice(el.selectionEnd) })
      focusNext.current = { index: index + 1, caret: 'start' }
    } else if (e.key === 'Backspace' && el.value === '' && highlightsArray.fields.length > 0) {
      e.preventDefault()
      highlightsArray.remove(index)
      if (index > 0) focusNext.current = { index: index - 1, caret: 'end' }
    }
  }

  const fieldError = (name: string) =>
    form.formState.errors[name] as import('react-hook-form').FieldError | undefined

  const renderField = (field: FieldConfig) => {
    if (field.type === 'highlights') {
      return (
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
                <div
                  ref={sortable.setNodeRef}
                  style={sortable.style}
                  className={cx(styles.highlightItem, item.id === activeBullet && styles.active)}
                  onFocus={() => setActiveBullet(item.id)}
                >
                  {sortable.handle && <span className={styles.bulletTool}>{sortable.handle}</span>}
                  <AutoResizeTextarea
                    className={styles.highlightTextarea}
                    placeholder="Highlight"
                    aria-label={`Highlight ${index + 1}`}
                    data-bullet
                    value={(form.watch(bulletPath(index)) as string) ?? ''}
                    onChange={(value) => setBullet(index, value)}
                    onKeyDown={(e) => handleBulletKeyDown(index, e)}
                  />
                  <span className={styles.bulletTool}>
                    <IconButton
                      icon={Trash2}
                      label="Remove"
                      tone="danger"
                      onClick={() => highlightsArray.remove(index)}
                    />
                  </span>
                </div>
              )
            }}
          />
          <Button
            size="sm"
            className={styles.addButton}
            onClick={() => {
              highlightsArray.append({ value: '' })
              focusNext.current = { index: highlightsArray.fields.length, caret: 'start' }
            }}
          >
            <Plus size={ICON_SIZE.sm} aria-hidden="true" /> Add highlight
          </Button>
          {highlightsArray.fields.length > 0 && (
            <p className={styles.hint}>Enter adds a bullet · Shift+Enter breaks the line</p>
          )}
        </div>
      )
    }

    if (field.type === 'textarea') {
      return (
        <AutoResizeTextarea
          id={field.name}
          className={formStyles.textarea}
          value={(form.watch(field.name as keyof InternalValues) as string) ?? ''}
          onChange={(value) =>
            form.setValue(field.name as keyof InternalValues, value as InternalValues[keyof InternalValues])
          }
          placeholder={field.placeholder}
        />
      )
    }

    if (field.type === 'date') {
      const isPresent = !!present[field.name]
      return (
        <DateInput
          id={field.name}
          className={formStyles.input}
          placeholder={isPresent ? 'Present' : field.placeholder}
          disabled={isPresent}
          value={(form.watch(field.name as keyof InternalValues) as string) ?? ''}
          onChange={(value) =>
            form.setValue(field.name as keyof InternalValues, value as InternalValues[keyof InternalValues], {
              shouldDirty: true,
            })
          }
          invalid={!!form.formState.errors[field.name]}
          days={field.days}
        />
      )
    }

    return (
      <input
        type="text"
        id={field.name}
        className={formStyles.input}
        placeholder={field.placeholder}
        aria-invalid={!!form.formState.errors[field.name]}
        {...form.register(field.name)}
      />
    )
  }

  /** "Present" checkbox beside an open-ended date's label. */
  const presentToggle = (field: FieldConfig) => (
    <label className={styles.present}>
      <input
        type="checkbox"
        checked={!!present[field.name]}
        onChange={(e) => {
          const checked = e.target.checked
          setPresent((p) => ({ ...p, [field.name]: checked }))
          if (checked) {
            form.setValue(field.name as keyof InternalValues, '', { shouldDirty: true })
          }
        }}
      />
      Present
    </label>
  )

  return (
    <EditForm ref={formRef} heading={heading} onSubmit={submit} onCancel={onCancel}>
      <div className={formStyles.fields}>
        {fields.map((field) => (
          <FormField
            key={field.name}
            label={field.label}
            htmlFor={field.type === 'highlights' ? undefined : field.name}
            required={field.required}
            error={fieldError(field.name)}
            half={widths.get(field.name) === 'half'}
            aside={field.type === 'date' && field.openEnded ? presentToggle(field) : undefined}
          >
            {renderField(field)}
          </FormField>
        ))}
      </div>
    </EditForm>
  )
}
