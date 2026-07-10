import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { Nav } from "./components/Nav";
import { Notifications } from "./components/Notifications";
import { AudioDetailPage } from "./pages/AudioDetailPage";
import { AudioListPage } from "./pages/AudioListPage";
import { LoginPage } from "./pages/LoginPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { AuditLogPage } from "./pages/AuditLogPage";
import { SettingsPage } from "./pages/SettingsPage";
import { UploadPage } from "./pages/UploadPage";
import { UsersPage } from "./pages/UsersPage";
import { CallsListPage } from "./pages/CallsListPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />

            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <div className="min-h-screen bg-gray-50">
                    <Nav />
                    <main>
                      <Routes>
                        <Route path="/upload" element={<UploadPage />} />
                        <Route path="/audio" element={<AudioListPage />} />
                        <Route path="/audio/:jobId" element={<AudioDetailPage />} />
                        <Route path="/calls" element={<CallsListPage />} />
                        <Route path="/analytics" element={<AnalyticsPage />} />
                        <Route path="/users" element={<UsersPage />} />
                        <Route path="/audit-log" element={<AuditLogPage />} />
                        <Route path="/settings" element={<SettingsPage />} />
                        <Route path="*" element={<Navigate to="/audio" replace />} />
                      </Routes>
                    </main>
                    <Notifications />
                  </div>
                </ProtectedRoute>
              }
            />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
