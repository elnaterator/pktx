import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Trash2, Pencil, Check, X, Star } from 'lucide-react'
import { mapGroupedLinks } from '../../services/api'
import {
  resumeKeys,
  useAllTags,
  useResumeDetail,
  useResumeMutations,
  useResumeSchema,
} from '../../hooks/queries'
import { TagsPanel } from '../../components/TagsPanel'
import { resumeUpdateSchema } from '../../schemas/resume'
import BasicsSection from './BasicsSection'
import SkillsSection from './SkillsSection'
import GenericListSection from './GenericListSection'
import AddSectionBar from './AddSectionBar'
import ResumeJsonView from './ResumeJsonView'
import Breadcrumb from '../../components/Breadcrumb'
import NotFound from '../../components/NotFound'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { useToast } from '../../components/toast'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { LinksPanel } from '../../components/LinksPanel'
import DetailLayout from '../../components/DetailLayout'
import { ApiClientError, type ListEntry, type ListSectionKey } from '../../types'
import styles from './ResumeDetailView.module.css'

export default function ResumeDetailView() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const numericId = id && /^\d+$/.test(id) ? Number(id) : null

  const qc = useQueryClient()
  const { success, error } = useToast()
  const [editingLabel, setEditingLabel] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  /** Sections opened from "Add section" but not yet holding an entry. */
  const [opened, setOpened] = useState<string[]>([])
  const [view, setView] = useState<'resume' | 'json'>('resume')
  /** Unsaved JSON text, kept while switching views. */
  const [jsonDraft, setJsonDraft] = useState<string | null>(null)

  const {
    register: registerLabel,
    handleSubmit: handleLabelSubmit,
    reset: resetLabel,
    formState: { isSubmitting: labelSubmitting },
  } = useForm<{ label: string }>({
    resolver: zodResolver(resumeUpdateSchema.pick({ label: true })),
    mode: 'onSubmit',
  })

  useEffect(() => {
    if (numericId === null) {
      navigate('/resumes', { replace: true })
    }
  }, [numericId, navigate])

  const detailQuery = useResumeDetail(numericId ?? undefined)
  const tagsQuery = useAllTags()
  const schemaQuery = useResumeSchema()
  const { remove, setDefault, updateLabelOrTags } = useResumeMutations()

  const version = detailQuery.data ?? null
  const allTags = tagsQuery.data ?? []
  const errStatus = (detailQuery.error as ApiClientError | undefined)?.status
  const notFound = errStatus === 404
  const forbidden = errStatus === 403

  const reloadResume = () => {
    if (numericId !== null) {
      qc.invalidateQueries({ queryKey: resumeKeys.detail(numericId) })
    }
  }

  const handleDelete = async () => {
    if (numericId === null) return
    try {
      await remove.mutateAsync(numericId)
      success('Resume deleted')
      navigate('/resumes')
    } catch {
      setConfirmDelete(false)
      error('Failed to delete resume version')
    }
  }

  const handleSetDefault = async () => {
    if (numericId === null) return
    try {
      await setDefault.mutateAsync(numericId)
      success('Default resume updated')
    } catch {
      error('Failed to set default resume')
    }
  }

  const handleLabelSave = handleLabelSubmit(async (data) => {
    if (numericId === null) return
    try {
      await updateLabelOrTags.mutateAsync({ id: numericId, label: data.label })
      setEditingLabel(false)
    } catch {
      error('Failed to update label')
    }
  })

  if (numericId === null) return null
  if (detailQuery.isPending) return <LoadingSpinner />
  if (notFound) return <NotFound entityName="Resume" backTo="/resumes" backLabel="Back to Resumes" />
  if (forbidden) return <NotFound entityName="Resume" backTo="/resumes" backLabel="Back to Resumes" heading="This resume isn't yours" message="This resume belongs to another account and cannot be accessed." />
  if (!version) return null

  const resume = version.data
  const sections = (schemaQuery.data ?? []).filter((m) => m.kind === 'list')
  const entriesOf = (key: string) =>
    (resume[key as ListSectionKey] ?? []) as unknown as ListEntry[]
  // A section is shown once it has entries; an empty one only while the user is
  // filling in its first entry. Order is fixed by the backend registry.
  const isShown = (key: string) => entriesOf(key).length > 0 || opened.includes(key)
  const shown = sections.filter((m) => isShown(m.key))
  const available = sections.filter((m) => !isShown(m.key))
  const close = (key: string) => setOpened((keys) => keys.filter((k) => k !== key))

  const renderSection = (meta: (typeof sections)[number]) => {
    const entries = entriesOf(meta.key)
    const startAdding = entries.length === 0 && opened.includes(meta.key)
    if (meta.key === 'skills') {
      return (
        <SkillsSection
          key={meta.key}
          skills={resume.skills ?? []}
          versionId={numericId}
          onUpdate={reloadResume}
          onClose={() => close(meta.key)}
        />
      )
    }
    return (
      <GenericListSection
        key={meta.key}
        meta={meta}
        entries={entries}
        versionId={numericId}
        onUpdate={reloadResume}
        startAdding={startAdding}
        onClose={() => close(meta.key)}
      />
    )
  }

  return (
    <div className={styles.container} data-testid="resume-detail-view">
      <Breadcrumb
        items={[
          { label: 'Resumes', to: '/resumes' },
          { label: version.label },
        ]}
      />

      <DetailLayout
        sidebar={
          <>
            <TagsPanel
              tags={version.tags ?? []}
              allTags={allTags}
              onSave={(tags) => updateLabelOrTags.mutateAsync({ id: numericId, tags })}
            />
            <LinksPanel
              resourceType="resume"
              resourceId={numericId}
              links={mapGroupedLinks(version.links as Record<string, unknown[]>)}
              onChange={reloadResume}
            />
          </>
        }
      >
        <div className={styles.topBar}>
          <div className={styles.topBarActions}>
            {!version.is_default && (
              <button className={styles.setDefaultButton} onClick={handleSetDefault}>
                Set as Default
              </button>
            )}
            <button
              className={`${styles.iconBtn} ${styles.deleteButton}`}
              onClick={() => setConfirmDelete(true)}
              aria-label="Delete resume version"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>

        <div className={styles.labelRow}>
          {editingLabel ? (
            <div className={styles.labelEdit}>
              <input
                className={styles.labelInput}
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleLabelSave()
                  if (e.key === 'Escape') setEditingLabel(false)
                }}
                {...registerLabel('label')}
              />
              <button className={`${styles.iconBtn} ${styles.saveIcon}`} onClick={handleLabelSave} disabled={labelSubmitting} aria-label="Save label">
                <Check size={14} />
              </button>
              <button className={`${styles.iconBtn} ${styles.cancelIcon}`} onClick={() => setEditingLabel(false)} aria-label="Cancel editing">
                <X size={14} />
              </button>
            </div>
          ) : (
            <div className={styles.labelDisplay}>
              <h2 className={styles.label}>{version.label}</h2>
              {version.is_default && (
                <span className={styles.defaultBadge}>
                  <Star size={11} fill="currentColor" aria-hidden="true" />
                  Default
                </span>
              )}
              <button className={styles.iconBtn} onClick={() => { resetLabel({ label: version.label }); setEditingLabel(true) }} aria-label="Edit label">
                <Pencil size={14} />
              </button>
            </div>
          )}
        </div>

        <div className={styles.viewSwitch} role="tablist" aria-label="Resume view">
          {(['resume', 'json'] as const).map((v) => (
            <button
              key={v}
              type="button"
              role="tab"
              aria-selected={view === v}
              className={`${styles.viewTab} ${view === v ? styles.viewTabActive : ''}`}
              onClick={() => setView(v)}
            >
              {v === 'resume' ? 'Resume' : 'JSON'}
              {v === 'json' && jsonDraft !== null && <span aria-label="unsaved changes"> •</span>}
            </button>
          ))}
        </div>

        {view === 'json' ? (
          <ResumeJsonView
            versionId={numericId}
            data={resume}
            draft={jsonDraft}
            onDraftChange={setJsonDraft}
          />
        ) : (
          <>
            <div className={styles.document}>
              <BasicsSection
                basics={resume.basics ?? {}}
                onUpdate={reloadResume}
                versionId={numericId}
              />
              {shown.map(renderSection)}
            </div>

            <AddSectionBar
              available={available}
              onAdd={(key) => setOpened((keys) => [...keys, key])}
            />
          </>
        )}
      </DetailLayout>

      {confirmDelete && (
        <ConfirmDialog
          message="Delete this resume version? This cannot be undone."
          onConfirm={handleDelete}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </div>
  )
}
