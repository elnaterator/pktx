import { useState } from 'react'
import { useNavigate } from 'react-router'
import { mapGroupedLinks } from '../../services/api'
import {
  useAccomplishmentDetail,
  useAccomplishmentMutations,
  useAllTags,
} from '../../hooks/queries'
import { LinksPanel } from '../../components/LinksPanel'
import { TagsPanel } from '../../components/TagsPanel'
import DetailLayout from '../../components/DetailLayout'
import Breadcrumb from '../../components/Breadcrumb'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { useToast } from '../../components/toast'
import { AccomplishmentPanel } from './AccomplishmentPanel'
import type { AccomplishmentCreateInput } from '../../schemas/accomplishment'
import { useResourceId } from '../../hooks/useResourceId'
import { DetailFallback, type ResourceRoute } from '../../components/DetailFallback'
import styles from './AccomplishmentDetailView.module.css'

const ROUTE: ResourceRoute = { listPath: '/accomplishments', singular: 'Accomplishment', plural: 'Accomplishments' }

export default function AccomplishmentDetailView() {
  const navigate = useNavigate()

  const numericId = useResourceId(ROUTE.listPath)

  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const { success, error } = useToast()

  const detailQuery = useAccomplishmentDetail(numericId ?? undefined)
  const tagsQuery = useAllTags()
  const { update, remove } = useAccomplishmentMutations()

  const acc = detailQuery.data ?? null
  const allTags = tagsQuery.data ?? []

  if (numericId === null) return null
  if (!acc) return <DetailFallback query={detailQuery} route={ROUTE} />

  const handleSave = async (data: AccomplishmentCreateInput) => {
    await update.mutateAsync({
      id: numericId,
      data: {
        title: data.title,
        situation: data.situation,
        task: data.task,
        action: data.action,
        result: data.result,
        accomplishment_date: data.accomplishment_date ?? null,
        tags: acc.tags ?? [],
      },
    })
    setEditing(false)
    success('Saved')
  }

  const handleDelete = async () => {
    try {
      await remove.mutateAsync(numericId)
      success('Accomplishment deleted')
      navigate('/accomplishments')
    } catch {
      setConfirmDelete(false)
      error('Failed to delete accomplishment')
    }
  }

  return (
    <div className={styles.container}>
      <Breadcrumb
        items={[
          { label: 'Accomplishments', to: '/accomplishments' },
          { label: acc.title },
        ]}
      />

      <DetailLayout
        sidebar={
          <>
            <TagsPanel
              tags={acc.tags ?? []}
              allTags={allTags}
              onSave={(tags) => update.mutateAsync({ id: numericId, data: { tags } })}
            />
            <LinksPanel
              resourceType="accomplishment"
              resourceId={numericId}
              links={mapGroupedLinks(acc.links as Record<string, unknown[]>)}
              onChange={() => detailQuery.refetch()}
            />
          </>
        }
      >
        {editing ? (
          <AccomplishmentPanel
            key="edit"
            mode="edit"
            accomplishment={acc}
            allTags={allTags}
            onSave={handleSave}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <AccomplishmentPanel
            key="view"
            mode="view"
            accomplishment={acc}
            onEdit={() => setEditing(true)}
            onDelete={() => setConfirmDelete(true)}
          />
        )}
      </DetailLayout>

      {confirmDelete && (
        <ConfirmDialog
          confirmLabel="Delete"
          message="Delete this accomplishment? This cannot be undone."
          onConfirm={handleDelete}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </div>
  )
}
