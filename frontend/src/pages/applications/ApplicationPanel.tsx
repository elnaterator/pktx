import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { TagInput } from '../../components/TagInput'
import { AutoResizeTextarea } from '../../components/AutoResizeTextarea'
import { SectionCard } from '../../components/SectionCard'
import { MarkdownContent } from '../../components/MarkdownContent'
import { EditForm, FormField } from '../../components/EditForm'
import form from '../../components/EditForm.module.css'
import { applicationCreateSchema, APPLICATION_STATUSES } from '../../schemas/application'
import type { ApplicationCreateInput } from '../../schemas/application'
import type { Application } from '../../types'
import { ExternalLink } from '../../components/ExternalLink'
import { PanelHeader } from '../../components/PanelHeader'
import { StatusBadge } from './StatusBadge'
import { formatDate } from '../../utils/formatDate'
import styles from './ApplicationPanel.module.css'

export type ApplicationPanelInput = ApplicationCreateInput

interface ApplicationPanelProps {
  mode: 'view' | 'edit' | 'create'
  application?: Application
  allTags?: string[]
  onSave?: (data: ApplicationPanelInput) => Promise<void>
  onCancel?: () => void
  onEdit?: () => void
  onDelete?: () => void
}

/** Edit and create: every field in one form. Tags are edited here only on create (the detail sidebar owns them). */
function ApplicationForm({
  mode,
  application,
  allTags = [],
  onSave,
  onCancel,
}: Omit<ApplicationPanelProps, 'onEdit' | 'onDelete'>) {
  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<ApplicationPanelInput>({
    resolver: zodResolver(applicationCreateSchema),
    mode: 'onBlur',
    defaultValues: {
      company: application?.company ?? '',
      position: application?.position ?? '',
      status: (application?.status as ApplicationPanelInput['status']) ?? 'Interested',
      url: application?.url ?? '',
      tags: application?.tags ?? [],
      description: application?.description ?? '',
      notes: application?.notes ?? '',
    },
  })

  const handleFormSave = handleSubmit(async (data) => {
    await onSave?.(data)
  })

  return (
    <EditForm
      heading={
        mode === 'create'
          ? 'New application'
          : `Editing ${application?.position} @ ${application?.company}`
      }
      onSubmit={handleFormSave}
      onCancel={() => onCancel?.()}
      saving={isSubmitting}
    >
      <div className={form.fields}>
        <FormField label="Position" htmlFor="ap-position" required half error={errors.position}>
          <input
            id="ap-position"
            className={form.inputTitle}
            type="text"
            placeholder="Position"
            aria-invalid={!!errors.position}
            autoFocus={mode === 'create'}
            {...register('position')}
          />
        </FormField>
        <FormField label="Company" htmlFor="ap-company" required half error={errors.company}>
          <input
            id="ap-company"
            className={form.inputTitle}
            type="text"
            placeholder="Company"
            aria-invalid={!!errors.company}
            {...register('company')}
          />
        </FormField>
        <FormField label="Status" htmlFor="ap-status" half>
          <select id="ap-status" className={form.select} {...register('status')}>
            {APPLICATION_STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </FormField>
        <FormField label="URL" htmlFor="ap-url" half error={errors.url}>
          <input
            id="ap-url"
            type="url"
            className={form.input}
            placeholder="https://…"
            aria-invalid={!!errors.url}
            {...register('url')}
          />
        </FormField>
        {mode === 'create' && (
          <FormField label="Tags">
            <Controller
              name="tags"
              control={control}
              render={({ field }) => (
                <TagInput
                  value={field.value ?? []}
                  onChange={field.onChange}
                  availableTags={allTags}
                  allowCreate
                  placeholder="Add tag..."
                />
              )}
            />
          </FormField>
        )}
        <FormField label="Description" htmlFor="ap-description">
          <Controller
            name="description"
            control={control}
            render={({ field }) => (
              <AutoResizeTextarea
                id="ap-description"
                className={form.textarea}
                value={field.value ?? ''}
                onChange={field.onChange}
                placeholder="Job description, requirements…"
              />
            )}
          />
        </FormField>
        <FormField label="Notes" htmlFor="ap-notes">
          <Controller
            name="notes"
            control={control}
            render={({ field }) => (
              <AutoResizeTextarea
                id="ap-notes"
                className={form.textarea}
                value={field.value ?? ''}
                onChange={field.onChange}
                placeholder="Personal notes…"
              />
            )}
          />
        </FormField>
      </div>
    </EditForm>
  )
}

export function ApplicationPanel(props: ApplicationPanelProps) {
  const { mode, application, onEdit, onDelete } = props
  if (mode !== 'view') return <ApplicationForm {...props} />

  return (
    <div>
      <PanelHeader
        entity="application"
        title={
          <>
            {application?.position}
            <span className={styles.titleAt}> @ </span>
            {application?.company}
          </>
        }
       
        onEdit={onEdit}
        onDelete={onDelete}
      />

      <div className={styles.meta}>
        {application?.updated_at && (
          <span className={styles.updatedDate}>
            Updated {formatDate(application.updated_at)}
          </span>
        )}
      </div>

      <div className={styles.sections}>
        <SectionCard label="Details">
          <div className={styles.detailsRow}>
            <div className={styles.detailsField}>
              <span className={styles.detailsLabel}>Status</span>
              {application && <StatusBadge status={application.status} />}
            </div>
            <div className={styles.detailsField}>
              <span className={styles.detailsLabel}>URL</span>
              {application?.url ? (
                <ExternalLink href={application.url} className={styles.urlLink}>
                  {application.url}
                </ExternalLink>
              ) : (
                <span className={styles.emptyText}>—</span>
              )}
            </div>
          </div>
        </SectionCard>

        <SectionCard label="Description">
          {application?.description ? (
            <MarkdownContent>{application.description}</MarkdownContent>
          ) : (
            <p className={styles.placeholderText}>Job description, requirements…</p>
          )}
        </SectionCard>

        <SectionCard label="Notes">
          {application?.notes ? (
            <MarkdownContent>{application.notes}</MarkdownContent>
          ) : (
            <p className={styles.placeholderText}>Personal notes…</p>
          )}
        </SectionCard>
      </div>
    </div>
  )
}
