import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { FieldError } from '../../components/FieldError'
import { TagInput } from '../../components/TagInput'
import { AutoResizeTextarea } from '../../components/AutoResizeTextarea'
import { SectionCard } from '../../components/SectionCard'
import { MarkdownContent } from '../../components/MarkdownContent'
import { applicationCreateSchema, APPLICATION_STATUSES } from '../../schemas/application'
import type { ApplicationCreateInput } from '../../schemas/application'
import type { Application } from '../../types'
import { ExternalLink } from '../../components/ExternalLink'
import { PanelHeader } from '../../components/PanelHeader'
import panelHeaderStyles from '../../components/PanelHeader.module.css'
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

export function ApplicationPanel({
  mode,
  application,
  allTags = [],
  onSave,
  onCancel,
  onEdit,
  onDelete,
}: ApplicationPanelProps) {
  const isEditable = mode !== 'view'

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
    <div className={mode === 'create' ? styles.panelCreate : undefined}>
      {/* Top bar: labels row above values/inputs row */}
      <PanelHeader
        editing={isEditable}
        entity="application"
        title={
          <>
            {application?.position}
            <span className={styles.titleAt}> @ </span>
            {application?.company}
          </>
        }
        titleEditor={
          <div className={styles.titleEdit}>
            <div className={styles.titleField}>
              <input
                className={panelHeaderStyles.titleInput}
                type="text"
                placeholder="Position"
                aria-label="Position *"
                aria-invalid={!!errors.position}
                autoFocus={mode === 'create'}
                {...register('position')}
              />
              <FieldError error={errors.position} />
            </div>
            <span className={styles.titleAt}>@</span>
            <div className={styles.titleField}>
              <input
                className={panelHeaderStyles.titleInput}
                type="text"
                placeholder="Company"
                aria-label="Company *"
                aria-invalid={!!errors.company}
                {...register('company')}
              />
              <FieldError error={errors.company} />
            </div>
          </div>
        }
        onEdit={onEdit}
        onDelete={onDelete}
        onSave={handleFormSave}
        onCancel={onCancel}
        saving={isSubmitting}
      />

      {/* Meta: tags + date */}
      {isEditable ? (
        mode === 'create' && <div className={styles.metaEdit}>
          <div className={styles.metaField}>
            <span className={styles.metaLabel}>Tags</span>
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
          </div>
        </div>
      ) : (
        <div className={styles.meta}>
          {application?.updated_at && (
            <span className={styles.updatedDate}>
              Updated {formatDate(application.updated_at)}
            </span>
          )}
        </div>
      )}

      {/* Section cards */}
      <div className={styles.sections}>
        <SectionCard label="Details">
          <div className={styles.detailsRow}>
            <div className={styles.detailsField}>
              {isEditable ? (
                <>
                  <label className={styles.detailsLabel} htmlFor="ap-status">Status</label>
                  <select id="ap-status" className={styles.select} {...register('status')}>
                    {APPLICATION_STATUSES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </>
              ) : (
                <>
                  <span className={styles.detailsLabel}>Status</span>
                  {application && <StatusBadge status={application.status} />}
                </>
              )}
            </div>
            <div className={styles.detailsField}>
              {isEditable ? (
                <>
                  <label className={styles.detailsLabel} htmlFor="ap-url">URL</label>
                  <input
                    id="ap-url"
                    type="url"
                    className={styles.input}
                    placeholder="https://..."
                    aria-invalid={!!errors.url}
                    {...register('url')}
                  />
                  <FieldError error={errors.url} />
                </>
              ) : (
                <>
                  <span className={styles.detailsLabel}>URL</span>
                  {application?.url ? (
                    <ExternalLink href={application.url} className={styles.urlLink}>
                      {application.url}
                    </ExternalLink>
                  ) : (
                    <span className={styles.emptyText}>—</span>
                  )}
                </>
              )}
            </div>
          </div>
        </SectionCard>

        <SectionCard label="Description">
          {isEditable ? (
            <Controller
              name="description"
              control={control}
              render={({ field }) => (
                <AutoResizeTextarea
                  id="ap-description"
                  className={styles.sectionTextarea}
                  value={field.value ?? ''}
                  onChange={field.onChange}
                  placeholder="Job description, requirements…"
                />
              )}
            />
          ) : application?.description ? (
            <MarkdownContent>{application.description}</MarkdownContent>
          ) : (
            <p className={styles.placeholderText}>Job description, requirements…</p>
          )}
        </SectionCard>

        <SectionCard label="Notes">
          {isEditable ? (
            <Controller
              name="notes"
              control={control}
              render={({ field }) => (
                <AutoResizeTextarea
                  id="ap-notes"
                  className={styles.sectionTextarea}
                  value={field.value ?? ''}
                  onChange={field.onChange}
                  placeholder="Personal notes…"
                />
              )}
            />
          ) : application?.notes ? (
            <MarkdownContent>{application.notes}</MarkdownContent>
          ) : (
            <p className={styles.placeholderText}>Personal notes…</p>
          )}
        </SectionCard>

      </div>
    </div>
  )
}
