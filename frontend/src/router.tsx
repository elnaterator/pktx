import { Navigate, Route, Routes } from 'react-router'
import HomeView from './pages/home'
import ResumeListView from './pages/resumes/ResumeListView'
import ResumeDetailView from './pages/resumes/ResumeDetailView'
import ApplicationListView from './pages/applications/ApplicationListView'
import ApplicationDetailView from './pages/applications/ApplicationDetailView'
import AccomplishmentListView from './pages/accomplishments/AccomplishmentListView'
import AccomplishmentDetailView from './pages/accomplishments/AccomplishmentDetailView'
import NoteListView from './pages/notes/NoteListView'
import NoteDetailView from './pages/notes/NoteDetailView'
import ContactListView from './pages/contacts/ContactListView'
import ContactDetailView from './pages/contacts/ContactDetailView'
import ConnectView from './pages/connect/ConnectView'

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomeView />} />
      <Route path="/resumes" element={<ResumeListView />} />
      <Route path="/resumes/:id" element={<ResumeDetailView />} />
      <Route path="/applications" element={<ApplicationListView />} />
      <Route path="/applications/:id" element={<ApplicationDetailView />} />
      <Route path="/accomplishments" element={<AccomplishmentListView />} />
      <Route path="/accomplishments/:id" element={<AccomplishmentDetailView />} />
      <Route path="/notes" element={<NoteListView />} />
      <Route path="/notes/:id" element={<NoteDetailView />} />
      <Route path="/contacts" element={<ContactListView />} />
      <Route path="/contacts/:id" element={<ContactDetailView />} />
      <Route path="/connect" element={<ConnectView />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
