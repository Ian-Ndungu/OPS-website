import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import '@fontsource-variable/bricolage-grotesque'
import '@fontsource-variable/instrument-sans'
import './index.css'
import { AuthProvider } from './lib/auth'
import { AdminLayout, RequireAuth, SiteLayout } from './components/Layout'
import { AnnouncementDetail, Announcements, Home, Login, ResultDetail, Results } from './pages/Public'
import { MythicDashboard, MythicLanding } from './pages/Mythic'
import { Cohorts, Contributions, MythicOverview, Payouts, Verification } from './pages/admin/MythicAdmin'
import ResultsAdmin from './pages/admin/ResultsAdmin'
import AnnouncementsAdmin from './pages/admin/AnnouncementsAdmin'

/* In the existing OPS app: mount these <Route>s inside your router and reuse your layouts. */
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<SiteLayout />}>
            <Route path="/" element={<Home />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Login register />} />
            <Route path="/mythic-circle" element={<MythicLanding />} />
            <Route path="/dashboard/mythic-circle" element={<RequireAuth><MythicDashboard /></RequireAuth>} />
            <Route path="/results" element={<Results />} />
            <Route path="/results/:id" element={<ResultDetail />} />
            <Route path="/announcements" element={<Announcements />} />
            <Route path="/announcements/:slug" element={<AnnouncementDetail />} />
          </Route>
          <Route element={<AdminLayout />}>
            <Route path="/admin/mythic-circle" element={<MythicOverview />} />
            <Route path="/admin/mythic-circle/verification" element={<Verification />} />
            <Route path="/admin/mythic-circle/cohorts" element={<Cohorts />} />
            <Route path="/admin/mythic-circle/contributions" element={<Contributions />} />
            <Route path="/admin/mythic-circle/payouts" element={<Payouts />} />
            <Route path="/admin/results" element={<ResultsAdmin />} />
            <Route path="/admin/announcements" element={<AnnouncementsAdmin />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
