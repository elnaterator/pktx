import { useEffect } from 'react'
import { Controller, useFieldArray, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Trash2 } from 'lucide-react'
import type { Basics } from '../../types'
import { EditableSection } from '../../components/EditableSection'
import SortableList from '../../components/SortableList'
import { AutoResizeTextarea } from '../../components/AutoResizeTextarea'
import { ExternalLink } from '../../components/ExternalLink'
import { FieldError } from '../../components/FieldError'
import { MarkdownContent } from '../../components/MarkdownContent'
import { updateBasics } from '../../services/api'
import {
  NETWORKS,
  basicsSchema,
  type BasicsFormInput,
  type BasicsFormOutput,
} from '../../schemas/resumeEntry'
import styles from './BasicsSection.module.css'

interface BasicsSectionProps {
  basics: Basics
  versionId: number
  /** Called after a save; without it the section is read-only. */
  onUpdate?: () => void
}

function toDefaults(b: Basics): BasicsFormInput {
  return {
    name: b.name ?? '',
    label: b.label ?? '',
    email: b.email ?? '',
    phone: b.phone ?? '',
    url: b.url ?? '',
    city: b.location?.city ?? '',
    region: b.location?.region ?? '',
    countryCode: b.location?.countryCode ?? '',
    summary: b.summary ?? '',
    profiles: (b.profiles ?? []).map((p) => ({
      profileId: p.id,
      network: p.network ?? '',
      username: p.username ?? '',
      url: p.url ?? '',
    })),
  }
}

/** The PATCH body for a saved form. Blank strings clear fields on the backend. */
function toPatch(form: BasicsFormOutput, current: Basics): Basics {
  const location = {
    ...current.location,
    city: form.city ?? '',
    region: form.region ?? '',
    countryCode: form.countryCode ?? '',
  }
  const hasLocation = Object.values(location).some(Boolean)
  return {
    name: form.name ?? '',
    label: form.label ?? '',
    email: form.email ?? '',
    phone: form.phone ?? '',
    url: form.url ?? '',
    summary: form.summary ?? '',
    location: hasLocation ? location : (null as unknown as undefined),
    profiles: form.profiles.map((p) => ({
      id: p.profileId,
      network: p.network,
      username: p.username ?? '',
      url: p.url ?? '',
    })),
  }
}

function place(b: Basics): string {
  const { city, region, countryCode } = b.location ?? {}
  return [city, region, countryCode].filter(Boolean).join(', ')
}

function ReadView({ basics }: { basics: Basics }) {
  const items: React.ReactNode[] = []
  if (basics.email) {
    items.push(
      <ExternalLink
        href={`mailto:${basics.email}`}
        allowMailto
        className={`${styles.contactItem} ${styles.contactLink}`}
      >
        {basics.email}
      </ExternalLink>,
    )
  }
  if (basics.phone) items.push(<span className={styles.contactItem}>{basics.phone}</span>)
  if (place(basics)) items.push(<span className={styles.contactItem}>{place(basics)}</span>)
  if (basics.url) {
    items.push(
      <ExternalLink href={basics.url} className={`${styles.contactItem} ${styles.contactLink}`}>
        Website
      </ExternalLink>,
    )
  }
  const profiles = (basics.profiles ?? []).map((p) =>
    // Links read as their network. An unsafe stored URL renders as plain text.
    (
      p.url ? (
        <ExternalLink href={p.url} className={`${styles.contactItem} ${styles.contactLink}`}>
          {p.network || p.url}
        </ExternalLink>
      ) : (
        <span className={styles.contactItem}>
          {p.network}
          {p.username ? `: ${p.username}` : ''}
        </span>
      )
    ),
  )

  return (
    <div className={styles.readView}>
      {basics.name && <h1 className={styles.nameHeading}>{basics.name}</h1>}
      {basics.label && <p className={styles.headline}>{basics.label}</p>}
      {items.length > 0 && (
        <div className={styles.contactRow}>
          {items.map((item, i) => (
            <span key={i} className={styles.contactCell}>
              {item}
            </span>
          ))}
        </div>
      )}
      {profiles.length > 0 && (
        <div className={styles.profiles}>
          <h3 className={styles.subLabel}>Profiles</h3>
          <div className={styles.contactRow}>
            {profiles.map((profile, i) => (
              <span key={basics.profiles?.[i]?.id ?? i} className={styles.contactCell}>
                {profile}
              </span>
            ))}
          </div>
        </div>
      )}
      {basics.summary && (
        <div className={styles.summaryBlock}>
          <h2 className={styles.sectionLabel}>Summary</h2>
          <MarkdownContent>{basics.summary}</MarkdownContent>
        </div>
      )}
    </div>
  )
}

export default function BasicsSection({ basics, versionId, onUpdate }: BasicsSectionProps) {
  const {
    register,
    control,
    trigger,
    getValues,
    reset,
    formState: { errors },
  } = useForm<BasicsFormInput, unknown, BasicsFormOutput>({
    resolver: zodResolver(basicsSchema),
    mode: 'onChange',
    defaultValues: toDefaults(basics),
  })
  const profiles = useFieldArray({ control, name: 'profiles' })

  useEffect(() => {
    reset(toDefaults(basics))
  }, [basics, reset])

  const handleSave = async () => {
    if (!(await trigger())) throw new Error('Please fix validation errors')
    const parsed = basicsSchema.parse(getValues())
    await updateBasics(versionId, toPatch(parsed, basics))
    onUpdate?.()
  }

  if (!onUpdate) {
    return (
      <section data-testid="basics-section">
        <ReadView basics={basics} />
      </section>
    )
  }

  const empty = Object.keys(basics).length === 0

  return (
    <EditableSection
      title="Basics"
      onSave={handleSave}
      placeholderContent={
        empty ? (
          <p className={styles.placeholder}>Click the pencil icon to add your name and contact details</p>
        ) : undefined
      }
    >
      {({ isEditing }) => (
        <div data-testid="basics-section">
          {isEditing ? (
            <form className={styles.form} onSubmit={(e) => e.preventDefault()}>
              <div className={styles.formField}>
                <label htmlFor="name" className={styles.formLabel}>Name</label>
                <input
                  type="text"
                  id="name"
                  className={`${styles.input} ${styles.inputName}`}
                  {...register('name')}
                />
              </div>
              <div className={styles.formField}>
                <label htmlFor="label" className={styles.formLabel}>Headline</label>
                <input
                  type="text"
                  id="label"
                  className={styles.input}
                  placeholder="e.g. Staff Software Engineer"
                  {...register('label')}
                />
              </div>

              <div className={styles.formRow}>
                <div className={styles.formField}>
                  <label htmlFor="email" className={styles.formLabel}>Email</label>
                  <input
                    type="email"
                    id="email"
                    className={`${styles.input} ${errors.email ? styles.inputError : ''}`}
                    {...register('email')}
                  />
                  <FieldError error={errors.email} />
                </div>
                <div className={styles.formField}>
                  <label htmlFor="phone" className={styles.formLabel}>Phone</label>
                  <input type="tel" id="phone" className={styles.input} {...register('phone')} />
                </div>
              </div>

              <div className={styles.formField}>
                <label htmlFor="url" className={styles.formLabel}>Website</label>
                <input
                  type="text"
                  id="url"
                  className={`${styles.input} ${errors.url ? styles.inputError : ''}`}
                  placeholder="https://…"
                  {...register('url')}
                />
                <FieldError error={errors.url} />
              </div>

              <div className={styles.formRow}>
                <div className={styles.formField}>
                  <label htmlFor="city" className={styles.formLabel}>City</label>
                  <input type="text" id="city" className={styles.input} {...register('city')} />
                </div>
                <div className={styles.formField}>
                  <label htmlFor="region" className={styles.formLabel}>Region</label>
                  <input type="text" id="region" className={styles.input} {...register('region')} />
                </div>
                <div className={styles.formField}>
                  <label htmlFor="countryCode" className={styles.formLabel}>Country</label>
                  <input
                    type="text"
                    id="countryCode"
                    className={styles.input}
                    placeholder="US"
                    {...register('countryCode')}
                  />
                </div>
              </div>

              <div className={styles.subHeader}>
                <h3 className={styles.subLabel}>Profiles</h3>
                <button
                  type="button"
                  className={styles.addProfile}
                  onClick={() => profiles.prepend({ network: '', username: '', url: '' })}
                >
                  + Add profile
                </button>
              </div>
              <SortableList
                className={styles.profileList}
                items={profiles.fields}
                getId={(row) => row.id}
                getLabel={(row) => {
                  const i = profiles.fields.findIndex((f) => f.id === row.id)
                  return getValues(`profiles.${i}.network`) || `profile ${i + 1}`
                }}
                onReorder={(_ids, { from, to }) => profiles.move(from, to)}
                renderItem={(row, sortable) => {
                const index = profiles.fields.findIndex((f) => f.id === row.id)
                const rowErrors = errors.profiles?.[index]
                return (
                  <div ref={sortable.setNodeRef} style={sortable.style} className={styles.profileRow}>
                    {sortable.handle}
                    <div className={styles.formField}>
                      <input
                        type="text"
                        className={`${styles.input} ${rowErrors?.network ? styles.inputError : ''}`}
                        placeholder="Network (e.g. GitHub)"
                        list="networks"
                        aria-label={`Profile ${index + 1} network`}
                        {...register(`profiles.${index}.network` as const)}
                      />
                      <FieldError error={rowErrors?.network} />
                    </div>
                    <div className={styles.formField}>
                      <input
                        type="text"
                        className={styles.input}
                        placeholder="Username"
                        aria-label={`Profile ${index + 1} username`}
                        {...register(`profiles.${index}.username` as const)}
                      />
                    </div>
                    <div className={styles.formField}>
                      <input
                        type="text"
                        className={`${styles.input} ${rowErrors?.url ? styles.inputError : ''}`}
                        placeholder="https://…"
                        aria-label={`Profile ${index + 1} URL`}
                        {...register(`profiles.${index}.url` as const)}
                      />
                      <FieldError error={rowErrors?.url} />
                    </div>
                    <button
                      type="button"
                      className={styles.removeProfile}
                      onClick={() => profiles.remove(index)}
                      aria-label={`Remove profile ${index + 1}`}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                )
                }}
              />
              <datalist id="networks">
                {NETWORKS.map((n) => (
                  <option key={n} value={n} />
                ))}
              </datalist>

              <div className={styles.formField}>
                <label htmlFor="summary" className={styles.formLabel}>Summary</label>
                <Controller
                  control={control}
                  name="summary"
                  render={({ field }) => (
                    <AutoResizeTextarea
                      id="summary"
                      className={styles.textarea}
                      value={field.value ?? ''}
                      onChange={field.onChange}
                      placeholder="Enter your professional summary..."
                    />
                  )}
                />
              </div>
            </form>
          ) : (
            <ReadView basics={basics} />
          )}
        </div>
      )}
    </EditableSection>
  )
}
