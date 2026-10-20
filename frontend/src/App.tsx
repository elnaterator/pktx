import { useLayoutEffect } from 'react'
import { BrowserRouter, Link } from 'react-router'
import { SignedIn, SignedOut, useAuth } from '@clerk/clerk-react'
import Navigation from './components/Navigation'
import UserMenu from './components/UserMenu'
import ConnectAssistantPanel from './components/ConnectAssistantPanel'
import { setTokenGetter } from './services/api'
import LandingPage from './components/LandingPage'
import AppRoutes from './router'

function AuthenticatedApp() {
  const { getToken } = useAuth()

  // useLayoutEffect runs in the layout phase (synchronous, before browser paint),
  // which completes before any child useEffect hooks run in the passive phase.
  // This ensures _getToken is set before child components make their first API calls.
  useLayoutEffect(() => {
    setTokenGetter(() => getToken())
    return () => setTokenGetter(null)
  }, [getToken])

  return (
    <div className="app">
      <ConnectAssistantPanel />
      <div className="app-shell">
        <header className="app-header">
          <div className="app-header-inner">
            <h1 className="logo">
              <Link to="/" className="logo-link">
                <span className="logo-p">p</span>ktx
              </Link>
            </h1>
            <Navigation />
            <UserMenu />
          </div>
        </header>
        <main>
          <AppRoutes />
        </main>
      </div>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <SignedIn>
        <AuthenticatedApp />
      </SignedIn>
      <SignedOut>
        <LandingPage />
      </SignedOut>
    </BrowserRouter>
  )
}

export default App
