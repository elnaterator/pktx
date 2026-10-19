/**
 * Shared API client: fetch wrapper, auth token management, and error handling.
 */

import type { ApiError, ApiValidationError } from '../../types'
import { ApiClientError } from '../../types/api'

export { ApiClientError }

let _getToken: (() => Promise<string | null>) | null = null

export function setTokenGetter(getter: (() => Promise<string | null>) | null): void {
  _getToken = getter
}

export const API_BASE = '/api'

/**
 * Handle fetch response and extract JSON or error
 */
export async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `HTTP ${response.status}: ${response.statusText}`

    try {
      const errorData = (await response.json()) as ApiError
      if (errorData.detail) {
        if (Array.isArray(errorData.detail)) {
          detail = (errorData.detail as ApiValidationError[])
            .map((e) => {
              const field = e.loc?.filter((s) => s !== 'body').slice(-1)[0]
              return field ? `${field}: ${e.msg}` : e.msg
            })
            .join('; ')
        } else {
          detail = errorData.detail
        }
      }
    } catch {
      // If JSON parsing fails, use the status text
    }

    throw new ApiClientError(detail, response.status, detail)
  }

  // 204 No Content (e.g. deleting a resume entry) has no body to parse.
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

/**
 * Wrapper to handle network errors (TypeError from fetch).
 * Converts network failures into user-friendly error messages.
 * Attaches a Bearer token from the token getter if one is configured.
 */
export async function fetchWithErrorHandling(
  url: string,
  options?: RequestInit
): Promise<Response> {
  try {
    let fetchOptions: RequestInit | undefined = options
    if (_getToken) {
      const token = await _getToken()
      if (token) {
        const headers: Record<string, string> = {
          ...(options?.headers as Record<string, string> | undefined),
          Authorization: `Bearer ${token}`,
        }
        fetchOptions = { ...options, headers }
      } else {
        // User signed out — redirect to home
        window.location.href = '/'
        throw new ApiClientError('Not authenticated', 401, 'Not authenticated')
      }
    }
    return await fetch(url, fetchOptions)
  } catch (error) {
    if (error instanceof ApiClientError) throw error
    if (error instanceof TypeError) {
      throw new ApiClientError(
        'Network error: Unable to connect to server. Please check your connection and try again.',
        0,
        'Network error: Failed to fetch'
      )
    }
    throw error
  }
}
