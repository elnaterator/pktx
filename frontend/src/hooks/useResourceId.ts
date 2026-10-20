import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router'

/**
 * Numeric `:id` route param of a detail page. A malformed id redirects to
 * `listPath` and returns null (render nothing until the redirect lands).
 */
export function useResourceId(listPath: string): number | null {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const numericId = id && /^\d+$/.test(id) ? Number(id) : null

  useEffect(() => {
    if (numericId === null) navigate(listPath, { replace: true })
  }, [numericId, listPath, navigate])

  return numericId
}
