import { useState } from 'react'
import { useNavigate } from 'react-router'
import { mapGroupedLinks } from '../../services/api'
import {
  useAllTags,
  useApplicationDetail,
  useApplicationMutations,
} from '../../hooks/queries'
import { LinksPanel } from '../../components/LinksPanel'
import { TagsPanel } from '../../components/TagsPanel'
import DetailLayout from '../../components/DetailLayout'
import Breadcrumb from '../../components/Breadcrumb'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { useToast } from '../../components/toast'
import { ApplicationPanel } from './ApplicationPanel'
import type { ApplicationPanelInput } from './ApplicationPanel'
import { useResourceId } from '../../hooks/useResourceId'
import { DetailFallback, type ResourceRoute } from '../../components/DetailFallback'
import styles from './ApplicationDetailView.module.css'

const ROUTE: ResourceRoute = { listPath: '/applications', singular: 'Application', plural: 'Applications' }

export default function ApplicationDetailView() {
  const navigate = useNavigate()

  const numericId = useResourceId(ROUTE.listPath)

  const [editing, setEditing] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const { success, error } = useToast()

  const detailQuery = useApplicationDetail(numericId ?? undefined)
  const tagsQuery = useAllTags()
  const { update, remove } = useApplicationMutations()

  const app = detailQuery.data ?? null
  const allTags = tagsQuery.data ?? []

  const handleSave = async (data: ApplicationPanelInput) => {
    if (!app || numericId === null) return
    try {
      await update.mutateAsync({
        id: numericId,
        data: {
          company: data.company,
          position: data.position,
          status: data.status,
          url: data.url ?? null,
          description: data.description ?? undefined,
          notes: data.notes ?? undefined,
          tags: app.tags ?? [],
        },
      })
      setEditing(false)
      success('Saved')
    } catch {
      error('Failed to save')
    }
  }

  const handleDelete = async () => {
    if (numericId === null) return
    try {
      await remove.mutateAsync(numericId)
      success('Application deleted')
      navigate('/applications')
    } catch {
      error('Failed to delete application')
      setShowDeleteConfirm(false)
    }
  }

  if (numericId === null) return null
  if (!app) return <DetailFallback query={detailQuery} route={ROUTE} />

  return (
    <div className={styles.container} data-testid="application-detail-view">
      <Breadcrumb
        items={[
          { label: 'Applications', to: '/applications' },
          { label: `${app.position} @ ${app.company}` },
        ]}
      />

      <DetailLayout
        sidebar={
          <>
            <TagsPanel
              tags={app.tags ?? []}
              allTags={allTags}
              onSave={(tags) => update.mutateAsync({ id: numericId, data: { tags } })}
            />
            <LinksPanel
              resourceType="application"
              resourceId={numericId}
              links={mapGroupedLinks(app.links as Record<string, unknown[]>)}
              onChange={() => detailQuery.refetch()}
            />
          </>
        }
      >
        {editing ? (
          <ApplicationPanel
            key="edit"
            mode="edit"
            application={app}
            allTags={allTags}
            onSave={handleSave}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <ApplicationPanel
            key="view"
            mode="view"
            application={app}
            onEdit={() => setEditing(true)}
            onDelete={() => setShowDeleteConfirm(true)}
          />
        )}
      </DetailLayout>

      {showDeleteConfirm && (
        <ConfirmDialog
          confirmLabel="Delete"
          message={`Delete the application for "${app.position}" at "${app.company}"? This cannot be undone.`}
          onConfirm={handleDelete}
          onCancel={() => setShowDeleteConfirm(false)}
        />
      )}
    </div>
  )
}
