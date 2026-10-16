import { useState } from 'react';
import { ThemeProvider } from '@/context/ThemeContext';
import { AppProvider } from '@/context/AppContext';
import { Sidebar } from '@/components/Sidebar';
import { Header } from '@/components/Header';
import { OwnerCenterView } from '@/views/OwnerCenterView';
import { DashboardView } from '@/views/DashboardView';
import { AssistantView } from '@/views/AssistantView';
import { CharactersView } from '@/views/CharactersView';
import { UniversesView } from '@/views/UniversesView';
import { ProjectsView } from '@/views/ProjectsView';
import { ContentPipelineView } from '@/views/ContentPipelineView';
import { VoiceStudioView } from '@/views/VoiceStudioView';
import { OmniRouteView } from '@/views/OmniRouteView';
import { ApprovalsView } from '@/views/ApprovalsView';
import { VaultView } from '@/views/VaultView';
import { MemoryView } from '@/views/MemoryView';
import { SecurityView } from '@/views/SecurityView';
import { FutureEngineerView } from '@/views/FutureEngineerView';
import { ReadinessView } from '@/views/ReadinessView';
import { DailyReportView } from '@/views/DailyReportView';
import type { ViewKey } from '@/types';
import { BackendStatusBar, OwnerAuthDialog, useBackendStatus } from '@/backend';

function AppContent() {
  const [activeView, setActiveView] = useState<ViewKey>('owner_center');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const { health, authenticated, setAuthenticated, loading, error, refresh } = useBackendStatus();
  const navigate = (view: ViewKey) => setActiveView(view);

  const renderView = () => {
    switch (activeView) {
      case 'owner_center': return <OwnerCenterView onNavigate={(view) => navigate(view as ViewKey)} />;
      case 'dashboard': return <DashboardView onNavigate={(view) => navigate(view as ViewKey)} />;
      case 'assistant': return <AssistantView onNavigate={(view) => navigate(view as ViewKey)} />;
      case 'characters': return <CharactersView />;
      case 'universes': return <UniversesView />;
      case 'projects': return <ProjectsView />;
      case 'content_pipeline': return <ContentPipelineView />;
      case 'voice_studio': return <VoiceStudioView />;
      case 'omniroute': return <OmniRouteView />;
      case 'approvals': return <ApprovalsView />;
      case 'vault': return <VaultView />;
      case 'memory': return <MemoryView />;
      case 'security': return <SecurityView />;
      case 'future_engineer': return <FutureEngineerView />;
      case 'readiness': return <ReadinessView />;
      case 'daily_report': return <DailyReportView />;
      default: return <OwnerCenterView onNavigate={(view) => navigate(view as ViewKey)} />;
    }
  };

  return (
    <div className="min-h-screen bg-primary" dir="rtl">
      <div className="flex min-h-screen">
        <Sidebar activeView={activeView} onNavigate={navigate} isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className="flex-1 flex flex-col min-w-0">
          <Header activeView={activeView} onMenuClick={() => setSidebarOpen(true)} onNavigate={navigate} />
          <BackendStatusBar health={health} authenticated={authenticated} loading={loading} error={error} />
          <div className="mx-4 mt-2 sm:mx-6 lg:mx-8 flex items-center justify-between gap-3 text-xs">
            <span className="text-muted">واجهة React الموحدة من مشروع 1-2- مع Backend NADA الحقيقي</span>
            <div className="flex items-center gap-2">
              <button onClick={() => void refresh()} className="rounded-lg border border-default bg-elevated px-3 py-1.5 text-secondary hover:text-primary">فحص الاتصال</button>
              {authenticated ? <button onClick={async () => { const { logoutOwner } = await import('@/backend'); await logoutOwner(); setAuthenticated(false); }} className="rounded-lg border border-default bg-elevated px-3 py-1.5 text-secondary hover:text-primary">إنهاء الجلسة</button> : <button onClick={() => setAuthOpen(true)} className="rounded-lg bg-accent px-3 py-1.5 font-bold text-white">دخول المالك</button>}
            </div>
          </div>
          <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-x-hidden">{renderView()}</main>
        </div>
      </div>
      {authOpen && <OwnerAuthDialog onAuthenticated={() => { setAuthenticated(true); void refresh(); }} onClose={() => setAuthOpen(false)} />}
    </div>
  );
}

function App() {
  return <ThemeProvider><AppProvider><AppContent /></AppProvider></ThemeProvider>;
}

export default App;
