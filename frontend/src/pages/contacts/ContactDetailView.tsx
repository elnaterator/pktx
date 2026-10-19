import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router'
import { mapGroupedLinks } from '../../services/api'
import { useAllTags, useContactDetail, useContactMutations } from '../../hooks/queries'
import { LinksPanel } from '../../components/LinksPanel'
import { TagsPanel } from '../../components/TagsPanel'
import DetailLayout from '../../components/DetailLayout'
import Breadcrumb from '../../components/Breadcrumb'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { useToast } from '../../components/toast'
import CommunicationsPanel from '../../components/CommunicationsPanel'
import { ContactPanel } from './ContactPanel'
import type { ContactCreateInput } from '../../schemas/contact'
import { useResourceId } from '../../hooks/useResourceId'
import { DetailFallback, type ResourceRoute } from '../../components/DetailFallback'
import styles from './ContactDetailView.module.css'

const ROUTE: ResourceRoute = { listPath: '/contacts', singular: 'Contact', plural: 'Contacts' }

export default function ContactDetailView() {
  const navigate = useNavigate()
  const location = useLocation()
  const expandCommId = (location.state as { expandCommId?: number } | null)?.expandCommId

  const numericId = useResourceId(ROUTE.listPath)

  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const { success, error } = useToast()

  const detailQuery = useContactDetail(numericId ?? undefined)
  const tagsQuery = useAllTags()
  const { update, remove } = useContactMutations()

  const contact = detailQuery.data ?? null
  const allTags = tagsQuery.data ?? []
  const reloadContact = () => detailQuery.refetch()

  if (numericId === null) return null
  if (!contact) return <DetailFallback query={detailQuery} route={ROUTE} />

  const handleSave = async (data: ContactCreateInput) => {
    await update.mutateAsync({
      id: numericId,
      data: {
        name: data.name,
        email: data.email ?? null,
        phone: data.phone ?? null,
        company: data.company ?? null,
        title: data.title ?? null,
        relationship: data.relationship ?? null,
        linkedin_url: data.linkedin_url ?? null,
        location: data.location ?? null,
        last_contacted_date: data.last_contacted_date ?? null,
        followup_date: data.followup_date ?? null,
        notes: data.notes,
        tags: contact.tags ?? [],
      },
    })
    setEditing(false)
    success('Saved')
  }

  const handleDelete = async () => {
    try {
      await remove.mutateAsync(numericId)
      success('Contact deleted')
      navigate('/contacts')
    } catch {
      setConfirmDelete(false)
      error('Failed to delete contact')
    }
  }

  return (
    <div className={styles.container}>
      <Breadcrumb
        items={[
          { label: 'Contacts', to: '/contacts' },
          { label: contact.name },
        ]}
      />

      <DetailLayout
        sidebar={
          <>
            <TagsPanel
              tags={contact.tags ?? []}
              allTags={allTags}
              onSave={(tags) => update.mutateAsync({ id: numericId, data: { tags } })}
            />
            <LinksPanel
              resourceType="contact"
              resourceId={numericId}
              links={mapGroupedLinks(contact.links as Record<string, unknown[]>)}
              onChange={reloadContact}
            />
          </>
        }
      >
        {editing ? (
          <ContactPanel
            key="edit"
            mode="edit"
            contact={contact}
            allTags={allTags}
            onSave={handleSave}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <>
            <ContactPanel
              key="view"
              mode="view"
              contact={contact}
              onEdit={() => setEditing(true)}
              onDelete={() => setConfirmDelete(true)}
            />
            <CommunicationsPanel contactId={contact.id} initialExpandId={expandCommId} />
          </>
        )}
      </DetailLayout>

      {confirmDelete && (
        <ConfirmDialog
          confirmLabel="Delete"
          message="Delete this contact? This cannot be undone."
          onConfirm={handleDelete}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </div>
  )
}
