import { Suspense, lazy } from "react";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import { Route, Switch } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import { AuthProvider } from "./contexts/AuthContext";
import { BrandingProvider } from "./contexts/BrandingContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
const Login = lazy(() => import("./pages/auth/Login"));
const MfaVerification = lazy(() => import("./pages/auth/MfaVerification"));
const MfaSettings = lazy(() => import("./pages/settings/MfaSettings"));
const Dashboard = lazy(() => import("./pages/dashboard/Dashboard"));
const DashboardIA = lazy(() => import("./pages/dashboard/DashboardIA"));
const WorkflowEngine = lazy(() => import("./pages/workflow/WorkflowEngine"));
const CopiloteCRM = lazy(() => import("./pages/crm/CopiloteCRM"));
const BusinessIntelligence = lazy(() => import("./pages/analytics/BusinessIntelligence"));
const AgendaView = lazy(() => import("./pages/agenda/AgendaView"));
const PatientsList = lazy(() => import("./pages/patients/PatientsList"));
const MedicalFile = lazy(() => import("./pages/patients/MedicalFile"));
const StockPage = lazy(() => import("./pages/stock/StockPage"));
const InvoicesPage = lazy(() => import("./pages/invoices/InvoicesPage"));
const CommissionsPage = lazy(() => import("./pages/commissions/CommissionsPage"));
const LoyaltyPage = lazy(() => import("./pages/loyalty/LoyaltyPage"));
const TeleconsultationPage = lazy(() => import("./pages/teleconsultation/TeleconsultationPage"));
const RecruitmentPage = lazy(() => import("./pages/recruitment/RecruitmentPage"));
const SocialPage = lazy(() => import("./pages/social/SocialPage"));
const EquipeMessages = lazy(() => import("./pages/equipe/EquipeMessages"));
const SettingsPage = lazy(() => import("./pages/settings/SettingsPage"));
const ActesPage = lazy(() => import("./pages/settings/ActesPage"));
const DeleguesPage = lazy(() => import("./pages/delegues/DeleguesPage"));
const LandingPage = lazy(() => import("./pages/public/LandingPage"));

function Router() {
  return (
    <Suspense fallback={<div className="min-h-screen grid place-items-center bg-background text-foreground">Chargement…</div>}>
      <Switch>
      <Route path="/login" component={Login} />
      <Route path="/mfa-verify">{() => <MfaVerification />}</Route>
      <Route path="/settings/mfa">
        <ProtectedRoute requiredRoles={['directrice', 'admin']}>
          <MfaSettings />
        </ProtectedRoute>
      </Route>
      <Route path="/dashboard">
        <ProtectedRoute>
          <Dashboard />
        </ProtectedRoute>
      </Route>
      <Route path="/dashboard-ia">
        <ProtectedRoute>
          <DashboardIA />
        </ProtectedRoute>
      </Route>
      <Route path="/workflows">
        <ProtectedRoute requiredRoles={['directrice', 'admin']}>
          <WorkflowEngine />
        </ProtectedRoute>
      </Route>
      <Route path="/copilote-crm">
        <ProtectedRoute requiredRoles={['directrice', 'medecin', 'estheticienne', 'admin']}>
          <CopiloteCRM />
        </ProtectedRoute>
      </Route>
      <Route path="/analytics">
        <ProtectedRoute requiredRoles={['directrice', 'admin']}>
          <BusinessIntelligence />
        </ProtectedRoute>
      </Route>
      <Route path="/agenda">
        <ProtectedRoute>
          <AgendaView />
        </ProtectedRoute>
      </Route>
      <Route path="/patients">
        <ProtectedRoute>
          <PatientsList />
        </ProtectedRoute>
      </Route>
      <Route path="/patients/:id">
        {(params) => (
          <ProtectedRoute requiredRoles={['directrice', 'medecin', 'estheticienne', 'admin']}>
            <MedicalFile patientId={Number(params.id)} />
          </ProtectedRoute>
        )}
      </Route>
      <Route path="/stock">
        <ProtectedRoute>
          <StockPage />
        </ProtectedRoute>
      </Route>
      <Route path="/invoices">
        <ProtectedRoute>
          <InvoicesPage />
        </ProtectedRoute>
      </Route>
      <Route path="/commissions">
        <ProtectedRoute requiredRoles={['directrice', 'admin', 'commercial']}>
          <CommissionsPage />
        </ProtectedRoute>
      </Route>
      <Route path="/delegues">
        <ProtectedRoute requiredRoles={['directrice', 'medecin', 'admin']}>
          <DeleguesPage />
        </ProtectedRoute>
      </Route>
      <Route path="/loyalty">
        <ProtectedRoute>
          <LoyaltyPage />
        </ProtectedRoute>
      </Route>
      <Route path="/teleconsultation/:rdvId">
        {(params) => (
          <ProtectedRoute requiredRoles={['directrice', 'medecin', 'admin']}>
            <TeleconsultationPage rdvId={Number(params.rdvId)} />
          </ProtectedRoute>
        )}
      </Route>
      <Route path="/recruitment">
        <ProtectedRoute requiredRoles={['directrice', 'assistante', 'admin']}>
          <RecruitmentPage />
        </ProtectedRoute>
      </Route>
      <Route path="/social">
        <ProtectedRoute>
          <SocialPage />
        </ProtectedRoute>
      </Route>
      <Route path="/equipe">
        <ProtectedRoute>
          <EquipeMessages />
        </ProtectedRoute>
      </Route>
      <Route path="/settings">
        <ProtectedRoute requiredRoles={['directrice', 'admin']}>
          <SettingsPage />
        </ProtectedRoute>
      </Route>
      <Route path="/settings/actes">
        <ProtectedRoute requiredRoles={['directrice', 'admin']}>
          <ActesPage />
        </ProtectedRoute>
      </Route>
      <Route path="/" component={LandingPage} />
      <Route path="/404" component={NotFound} />
      {/* Final fallback route */}
      <Route component={NotFound} />
      </Switch>
    </Suspense>
  );
}

// NOTE: About Theme
// - First choose a default theme according to your design style (dark or light bg), than change color palette in index.css
//   to keep consistent foreground/background color across components
// - If you want to make theme switchable, pass `switchable` ThemeProvider and use `useTheme` hook

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider
        defaultTheme="light"
        // switchable
      >
        <BrandingProvider>
          <AuthProvider>
            <TooltipProvider>
              <Toaster />
              <Router />
            </TooltipProvider>
          </AuthProvider>
        </BrandingProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
