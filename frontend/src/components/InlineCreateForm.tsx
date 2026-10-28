import { useEffect, useRef } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { FieldError } from './FieldError'
import { Button } from './Button'
import styles from './InlineCreateForm.module.css'

type NameValues = { name: string }

const defaultSchema = z.object({
  name: z.string().trim().min(1, 'Name cannot be empty'),
})

interface InlineCreateFormProps {
  onConfirm: (label: string) => Promise<void>
  onCancel: () => void
  placeholder?: string
  confirmLabel?: string
  /** Validates `{ name }`; defaults to a non-empty trimmed name. */
  schema?: z.ZodType<NameValues, NameValues>
}

export function InlineCreateForm({
  onConfirm,
  onCancel,
  placeholder = 'Enter name...',
  confirmLabel = 'Create',
  schema = defaultSchema,
}: InlineCreateFormProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  const { register, handleSubmit, formState: { errors, isSubmitting }, setError } =
    useForm<NameValues>({
      resolver: zodResolver(schema),
      mode: 'onSubmit',
    })

  const { ref: registerRef, ...registerRest } = register('name')

  const mergedRef = (el: HTMLInputElement | null) => {
    registerRef(el)
    ;(inputRef as React.MutableRefObject<HTMLInputElement | null>).current = el
  }

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onCancel])

  const onSubmit = async (data: NameValues) => {
    try {
      await onConfirm(data.name)
    } catch (err) {
      setError('name', { message: err instanceof Error ? err.message : 'Failed to create' })
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit(onSubmit)} data-testid="inline-create-form" noValidate>
      <input
        ref={mergedRef}
        type="text"
        {...registerRest}
        placeholder={placeholder}
        className={`${styles.input}${errors.name ? ` ${styles.inputError}` : ''}`}
        disabled={isSubmitting}
        aria-label="Name"
      />
      <div className={styles.buttons}>
        <Button type="submit" variant="link" size="sm" disabled={isSubmitting}>
          {isSubmitting ? 'Creating...' : confirmLabel}
        </Button>
        <Button type="button" size="sm" onClick={onCancel} disabled={isSubmitting}>
          Cancel
        </Button>
      </div>
      {errors.name && <FieldError error={errors.name} />}
    </form>
  )
}
