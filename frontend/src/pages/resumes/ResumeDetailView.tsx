import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Trash2, Pencil, Check, X } from 'lucide-react'
import { mapGroupedLinks } from '../../services/api'
import {
  resumeKeys,
  useAllTags,
  useResumeDetail,
  useResumeMutations,
  useResumeSections,
} from '../../hooks/queries'
import { TagInput } from '../../components/TagInput'
import { resumeUpdateSchema } from '../../schemas/resume'
import ContactSection from './ContactSection'
import SummarySection from './SummarySection'
import SkillsSection from './SkillsSection'
import GenericListSection from './GenericListSection'
import ManageSections from './ManageSections'
import { CUSTOM_PREFIX, displayTitle } from './layout'
import Breadcrumb from '../../components/Breadcrumb'
import NotFound from '../../components/NotFound'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { useToast } from '../../components/toast'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { LinksPanel } from '../../components/LinksPanel'
import DetailLayout from '../../components/DetailLayout'
import {
  ApiClientError,
  type LayoutItem,
  type ListEntry,
  type SectionMeta,
} from '../../types'
import styles from './ResumeDetailView.module.css'

export default function ResumeDetailView() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const numericId = id && /^\d+$/.test(id) ? Number(id) : null

  const qc = useQueryClient()
  const { success, error } = useToast()
  const [editingTags, setEditingTags] = useState(false)
  const [tagsForm, setTagsForm] = useState<string[]>([])
  const [editingLabel, setEditingLabel] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

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
  const sectionsQuery = useResumeSections()
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

  const handleTagsEdit = () => {
    if (!version) return
    setTagsForm(version.tags ?? [])
    setEditingTags(true)
  }

  const handleTagsSave = async () => {
    if (numericId === null || !version) return
    try {
      await updateLabelOrTags.mutateAsync({
        id: numericId,
        label: version.label,
        tags: tagsForm,
      })
      setEditingTags(false)
    } catch {
      error('Failed to update tags')
    }
  }

  if (numericId === null) return null
  if (detailQuery.isPending) return <LoadingSpinner />
  if (notFound) return <NotFound entityName="Resume" backTo="/resumes" backLabel="Back to Resumes" />
  if (forbidden) return <NotFound entityName="Resume" backTo="/resumes" backLabel="Back to Resumes" heading="This resume isn't yours" message="This resume belongs to another account and cannot be accessed." />
  if (!version) return null

  const resume = version.resume_data
  const sections = sectionsQuery.data ?? []
  const customSections = resume.custom_sections ?? {}
  const layout = resume.layout ?? []

  const renderSection = (item: LayoutItem) => {
    const title = displayTitle(item, sections, customSections)
    if (item.section === 'summary') {
      return (
        <SummarySection
          key={item.section}
          summary={resume.summary}
          title={title}
          onUpdate={reloadResume}
          versionId={numericId}
        />
      )
    }
    if (item.section === 'skills') {
      return (
        <SkillsSection
          key={item.section}
          skills={resume.skills}
          title={title}
          onUpdate={reloadResume}
          versionId={numericId}
        />
      )
    }
    const isCustom = item.section.startsWith(CUSTOM_PREFIX)
    const meta: SectionMeta | undefined = sections.find(
      (s) => s.key === (isCustom ? 'custom' : item.section),
    )
    if (!meta) return null
    const entries = isCustom
      ? (customSections[item.section.slice(CUSTOM_PREFIX.length)]?.entries as unknown as
          | ListEntry[]
          | undefined)
      : (resume as unknown as Record<string, ListEntry[]>)[item.section]
    return (
      <GenericListSection
        key={item.section}
        meta={meta}
        sectionKey={item.section}
        title={title}
        entries={entries ?? []}
        versionId={numericId}
        onUpdate={reloadResume}
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
          <LinksPanel
            resourceType="resume"
            resourceId={numericId}
            links={mapGroupedLinks(version.links as Record<string, unknown[]>)}
            onChange={reloadResume}
          />
        }
      >
        <div className={styles.topBar}>
          {version.is_default && (
            <span className={styles.defaultBadge}>Default</span>
          )}
          <div className={styles.topBarActions}>
            {!version.is_default && (
              <button className={styles.setDefaultButton} onClick={handleSetDefault}>
                Set as Default
              </button>
            )}
            <button
              className={styles.deleteButton}
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
              <button className={styles.iconBtn} onClick={() => { resetLabel({ label: version.label }); setEditingLabel(true) }} aria-label="Edit label">
                <Pencil size={14} />
              </button>
            </div>
          )}
        </div>

        <div className={styles.tagsRow}>
          {editingTags ? (
            <div className={styles.tagsEdit}>
              <TagInput
                value={tagsForm}
                onChange={setTagsForm}
                availableTags={allTags}
                allowCreate={true}
                placeholder="Add tag..."
              />
              <button className={`${styles.iconBtn} ${styles.saveIcon}`} onClick={handleTagsSave} aria-label="Save tags">
                <Check size={14} />
              </button>
              <button className={`${styles.iconBtn} ${styles.cancelIcon}`} onClick={() => setEditingTags(false)} aria-label="Cancel">
                <X size={14} />
              </button>
            </div>
          ) : (
            <div className={styles.tagsDisplay}>
              {version.tags && version.tags.length > 0 ? (
                <div className={styles.tagList}>
                  {version.tags.map((tag) => (
                    <span key={tag} className={styles.tagBadge}>{tag}</span>
                  ))}
                </div>
              ) : (
                <span className={styles.tagsPlaceholder}>No tags</span>
              )}
              <button className={styles.iconBtn} onClick={handleTagsEdit} aria-label="Edit tags">
                <Pencil size={14} />
              </button>
            </div>
          )}
        </div>

        <div className={styles.document}>
          <ContactSection
            contact={resume.contact}
            onUpdate={reloadResume}
            versionId={numericId}
          />
          {layout.filter((item) => item.visible).map(renderSection)}
        </div>

        {sectionsQuery.isSuccess && (
          <ManageSections
            versionId={numericId}
            layout={layout}
            customSections={customSections}
            sections={sections}
          />
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
