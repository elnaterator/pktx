import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ClerkProvider } from '@clerk/clerk-react'
import { QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import './index.css'
import App from './App.tsx'
import { queryClient } from './services/queryClient'
import { ToastProvider } from './components/toast'
import { clerkAppearance } from './theme/clerk'
import { resolveClerkPublishableKey } from './utils/clerkPublishableKey'

const publishableKey = resolveClerkPublishableKey()

if (!publishableKey) {
  throw new Error(
    'Clerk publishable key missing: set CLERK_PUBLISHABLE_KEY (server) or VITE_CLERK_PUBLISHABLE_KEY (vite dev)',
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ClerkProvider
        publishableKey={publishableKey}
        signInFallbackRedirectUrl={window.location.pathname + window.location.search}
        appearance={clerkAppearance}
      >
        <ToastProvider>
          <App />
        </ToastProvider>
      </ClerkProvider>
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  </StrictMode>,
)
