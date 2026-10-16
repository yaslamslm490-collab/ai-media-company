import { useState } from 'react';
import { useApp } from '@/context/AppContext';
import type { AgentInfo } from '@/types';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Cpu,
  Clock,
  ArrowLeft,
  RotateCcw,
  Play,
  Pause,
  Film,
  Users,
  FolderKanban,
  CheckSquare,
  Sparkles,
  Zap,
} from 'lucide-react';

export function DashboardView({ onNavigate }: { onNavigate?: (key: string) => void }) {
  const {
    agents,
    restartAgent,
    updateAgentStatus,
    characters,
    scripts,
    projects,
    approvals,
    lastSaved,
  } = useApp();

  const [selectedAgent, setSelectedAgent] = useState<AgentInfo | null>(null);
  const [platformMetrics, setPlatformMetrics] = useState([
    { name: 'يوتيوب', engagement: '15.4%', views: '240K', up: true },
    { name: 'إنستغرام', engagement: '12.8%', views: '185K', up: true },
    { name: 'تيك توك', engagement: '19.2%', views: '490K', up: true },
    { name: 'فيسبوك', engagement: '8.6%', views: '95K', up: true },
    { name: 'إكس (تويتر)', engagement: '6.1%', views: '64K', up: false },
    { name: 'لينكدإن', engagement: '11.3%', views: '42K', up: true },
  ]);

  const [refreshingMetrics, setRefreshingMetrics] = useState(false);

  const handleRefreshMetrics = () => {
    setRefreshingMetrics(true);
    setTimeout(() => {
      setPlatformMetrics((prev) =>
        prev.map((p) => {
          const change = (Math.random() * 2 - 0.8).toFixed(1);
          const current = parseFloat(p.engagement);
          const next = Math.max(2, current + parseFloat(change)).toFixed(1);
          return {
            ...p,
            engagement: `${next}%`,
            up: parseFloat(change) >= 0,
          };
        })
      );
      setRefreshingMetrics(false);
    }, 600);
  };

  const activeAgents = agents.filter((a) => a.status === 'active').length;
  const errorAgents = agents.filter((a) => a.status === 'error').length;
  const pendingApprovalsCount = approvals.filter((a) => a.status === 'pending').length;

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Executive Quick Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {/* Stat 1: Characters */}
        <div
          onClick={() => onNavigate?.('characters')}
          className="card p-5 cursor-pointer hover:border-accent transition-all group"
        >
          <div className="flex items-start justify-between mb-4">
            <div className="w-12 h-12 rounded-xl bg-accent-dim flex items-center justify-center">
              <Users className="w-6 h-6 text-accent group-hover:scale-110 transition-transform" />
            </div>
            <span className="text-xs font-bold text-accent px-2 py-0.5 rounded-full bg-accent/10">
              100% نشط
            </span>
          </div>
          <p className="text-xs text-muted mb-1">الشخصيات المعتمدة</p>
          <p className="font-display font-bold text-3xl text-primary mb-1">
            {characters.length} شخصية
          </p>
          <p className="text-xs text-secondary">من CHAR-001 إلى CHAR-011 بملفات كاملة</p>
        </div>

        {/* Stat 2: Scripts & Content */}
        <div
          onClick={() => onNavigate?.('content_pipeline')}
          className="card p-5 cursor-pointer hover:border-info transition-all group"
        >
          <div className="flex items-start justify-between mb-4">
            <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center">
              <Film className="w-6 h-6 text-info group-hover:scale-110 transition-transform" />
            </div>
            <div className="flex items-center gap-1 text-xs font-medium text-accent">
              <TrendingUp className="w-3.5 h-3.5" />
              <span>+18%</span>
            </div>
          </div>
          <p className="text-xs text-muted mb-1">مسار إنتاج السكريبتات</p>
          <p className="font-display font-bold text-3xl text-primary mb-1">
            {scripts.length} سكريبت
          </p>
          <p className="text-xs text-secondary">مع فحص الجودة الشامل Quality Gate</p>
        </div>

        {/* Stat 3: Projects */}
        <div
          onClick={() => onNavigate?.('projects')}
          className="card p-5 cursor-pointer hover:border-warning transition-all group"
        >
          <div className="flex items-start justify-between mb-4">
            <div className="w-12 h-12 rounded-xl bg-amber-500/10 flex items-center justify-center">
              <FolderKanban className="w-6 h-6 text-warning group-hover:scale-110 transition-transform" />
            </div>
            <span className="text-xs font-bold text-warning px-2 py-0.5 rounded-full bg-amber-500/10">
              4 مشاريع
            </span>
          </div>
          <p className="text-xs text-muted mb-1">المشروعات الإنتاجية</p>
          <p className="font-display font-bold text-3xl text-primary mb-1">
            {projects.length} مشاريع
          </p>
          <p className="text-xs text-secondary">إجمالي الميزانية $63,000</p>
        </div>

        {/* Stat 4: Approvals */}
        <div
          onClick={() => onNavigate?.('approvals')}
          className="card p-5 cursor-pointer hover:border-error transition-all group"
        >
          <div className="flex items-start justify-between mb-4">
            <div className="w-12 h-12 rounded-xl bg-red-500/10 flex items-center justify-center">
              <CheckSquare className="w-6 h-6 text-error group-hover:scale-110 transition-transform" />
            </div>
            <span className="text-xs font-bold text-error px-2 py-0.5 rounded-full bg-red-500/10">
              قرار المالك
            </span>
          </div>
          <p className="text-xs text-muted mb-1">الموافقات المعلقة</p>
          <p className="font-display font-bold text-3xl text-primary mb-1">
            {pendingApprovalsCount} طلبات
          </p>
          <p className="text-xs text-secondary">بانتظار الاعتماد أو التوجيه</p>
        </div>
      </div>

      {/* Main Grid: Agent Monitor & Platforms */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Interactive Agents Supervisor */}
        <div className="lg:col-span-2 space-y-4">
          <div className="card p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-accent-dim flex items-center justify-center">
                  <Activity className="w-5 h-5 text-accent" />
                </div>
                <div>
                  <h3 className="font-display font-bold text-base text-primary">
                    مراقب وكلاء الذكاء الاصطناعي — AI Agents Fleet
                  </h3>
                  <p className="text-xs text-muted">تحكم فوري، إعادة تشغيل، وتعيين المهام</p>
                </div>
              </div>

              <div className="flex items-center gap-3 text-xs">
                <span className="flex items-center gap-1.5 text-secondary">
                  <span className="status-dot status-active" /> {activeAgents} نشط
                </span>
                {errorAgents > 0 && (
                  <span className="flex items-center gap-1.5 text-error">
                    <span className="status-dot status-error" /> {errorAgents} خطأ
                  </span>
                )}
                <span className="text-muted">|</span>
                <span className="text-xs text-muted">{lastSaved}</span>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              {agents.map((agent) => (
                <div
                  key={agent.id}
                  className={`card p-4 transition-all border ${
                    agent.status === 'error'
                      ? 'border-red-500/30 bg-red-500/5'
                      : 'hover:border-accent/40 bg-[var(--bg-card)]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="relative flex-shrink-0">
                        <div className="w-10 h-10 rounded-xl bg-elevated flex items-center justify-center border border-default">
                          <Cpu className="w-5 h-5 text-secondary" />
                        </div>
                        <span
                          className={`status-dot status-${agent.status} absolute -bottom-0.5 -left-0.5 ring-2 ring-[var(--bg-card)]`}
                        />
                      </div>
                      <div className="min-w-0">
                        <h4 className="text-sm font-bold text-primary truncate">{agent.name}</h4>
                        <p className="text-xs text-muted truncate">{agent.role}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-1 flex-shrink-0">
                      {agent.status === 'error' ? (
                        <button
                          onClick={() => restartAgent(agent.id)}
                          title="إعادة تشغيل فوري"
                          className="p-1.5 rounded-lg bg-accent text-white text-xs hover:opacity-90 transition-opacity flex items-center gap-1 shadow"
                        >
                          <RotateCcw className="w-3.5 h-3.5 animate-spin" />
                          <span className="text-[11px] font-bold">إصلاح</span>
                        </button>
                      ) : agent.status === 'active' ? (
                        <button
                          onClick={() => updateAgentStatus(agent.id, 'idle', 'تم الإيقاف المؤقت بواسطة المشرف')}
                          title="إيقاف مؤقت"
                          className="p-1.5 rounded-lg bg-elevated hover:bg-elevated/80 text-muted hover:text-warning border border-default transition-colors"
                        >
                          <Pause className="w-3.5 h-3.5" />
                        </button>
                      ) : (
                        <button
                          onClick={() => updateAgentStatus(agent.id, 'active', 'تم الاستئناف والتنشيط')}
                          title="استئناف وتشغيل"
                          className="p-1.5 rounded-lg bg-accent/20 hover:bg-accent/30 text-accent border border-accent/30 transition-colors"
                        >
                          <Play className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>

                  <p className="text-xs text-secondary mb-3 line-clamp-2 h-8 leading-relaxed">
                    {agent.task}
                  </p>

                  {agent.progress > 0 && (
                    <div className="mb-2">
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${agent.progress}%` }} />
                      </div>
                    </div>
                  )}

                  <div className="flex items-center justify-between text-[11px] text-muted pt-1 border-t border-default/50">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {agent.lastActive}
                    </span>
                    <button
                      onClick={() => setSelectedAgent(agent)}
                      className="text-accent hover:underline font-medium"
                    >
                      إدارة الوكيل
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Action Buttons Matrix */}
          <div className="card p-5">
            <h4 className="font-display font-bold text-sm text-primary mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-accent" />
              أوامر التحكم السريع بالمنظومة
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              <button
                onClick={() => onNavigate?.('assistant')}
                className="p-3 rounded-xl bg-elevated hover:bg-elevated/80 border border-default text-center transition-all group"
              >
                <Sparkles className="w-5 h-5 text-accent mx-auto mb-1 group-hover:scale-110 transition-transform" />
                <span className="text-xs font-bold text-primary block">مساعد NADA</span>
                <span className="text-[10px] text-muted">صوت ونص</span>
              </button>

              <button
                onClick={() => onNavigate?.('voice_studio')}
                className="p-3 rounded-xl bg-elevated hover:bg-elevated/80 border border-default text-center transition-all group"
              >
                <div className="w-5 h-5 text-info mx-auto mb-1 flex items-center justify-center font-bold text-sm">
                  🎙️
                </div>
                <span className="text-xs font-bold text-primary block">استوديو الصوت</span>
                <span className="text-[10px] text-muted">فحص النطق العربي</span>
              </button>

              <button
                onClick={() => onNavigate?.('omniroute')}
                className="p-3 rounded-xl bg-elevated hover:bg-elevated/80 border border-default text-center transition-all group"
              >
                <div className="w-5 h-5 text-warning mx-auto mb-1 flex items-center justify-center font-bold text-sm">
                  🌐
                </div>
                <span className="text-xs font-bold text-primary block">توجيه OmniRoute</span>
                <span className="text-[10px] text-muted">فحص النماذج</span>
              </button>

              <button
                onClick={() => onNavigate?.('daily_report')}
                className="p-3 rounded-xl bg-elevated hover:bg-elevated/80 border border-default text-center transition-all group"
              >
                <div className="w-5 h-5 text-purple-400 mx-auto mb-1 flex items-center justify-center font-bold text-sm">
                  📑
                </div>
                <span className="text-xs font-bold text-primary block">التقرير الشامل</span>
                <span className="text-[10px] text-muted">تصدير وطباعة</span>
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Platform Analytics & System Health */}
        <div className="space-y-6">
          {/* Platform Performance with Refresh */}
          <div className="card p-5 bg-gradient-to-br from-[var(--bg-card)] to-[var(--bg-elevated)]">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-accent-dim flex items-center justify-center">
                  <TrendingUp className="w-4 h-4 text-accent" />
                </div>
                <div>
                  <h3 className="font-display font-bold text-sm text-primary">أداء منصات النشر</h3>
                  <p className="text-[11px] text-muted">معدلات التفاعل والمشاهدات الحية</p>
                </div>
              </div>
              <button
                onClick={handleRefreshMetrics}
                disabled={refreshingMetrics}
                className="p-2 rounded-lg bg-elevated border border-default text-muted hover:text-primary transition-colors"
                title="تحديث البيانات"
              >
                <RotateCcw className={`w-3.5 h-3.5 ${refreshingMetrics ? 'animate-spin text-accent' : ''}`} />
              </button>
            </div>

            <div className="space-y-3">
              {platformMetrics.map((p) => (
                <div
                  key={p.name}
                  className="p-2.5 rounded-lg bg-[var(--bg-card)]/60 border border-default/50 flex items-center justify-between"
                >
                  <div>
                    <span className="text-xs font-bold text-primary block">{p.name}</span>
                    <span className="text-[10px] text-muted">{p.views} مشاهدة هذا الأسبوع</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold text-primary">{p.engagement}</span>
                    {p.up ? (
                      <TrendingUp className="w-3.5 h-3.5 text-accent" />
                    ) : (
                      <TrendingDown className="w-3.5 h-3.5 text-error" />
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* System Production Pipeline Health */}
          <div className="card p-5">
            <h4 className="font-display font-bold text-sm text-primary mb-3">حالة خطوط الإنتاج</h4>
            <div className="space-y-3">
              {[
                { label: 'محتوى منشور خلال الشهر', value: '184', pct: 82 },
                { label: 'سكريبتات قيد المراجعة', value: '6', pct: 45 },
                { label: 'جلسات صوت مسجلة', value: '48', pct: 90 },
                { label: 'موافقات مكتملة للمالك', value: '29', pct: 96 },
              ].map((item) => (
                <div key={item.label}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs text-secondary">{item.label}</span>
                    <span className="text-xs font-bold text-primary">{item.value}</span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${item.pct}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Go to Daily Report Action Button */}
          <button
            onClick={() => onNavigate?.('daily_report')}
            className="card p-4 w-full flex items-center justify-between hover:bg-elevated transition-colors group border border-accent/20"
          >
            <span className="text-sm font-bold text-accent">عرض التقرير التشغيلي الكامل 3.0</span>
            <ArrowLeft className="w-4 h-4 text-accent group-hover:-translate-x-1 transition-transform" />
          </button>
        </div>
      </div>

      {/* Modal for managing individual agent */}
      {selectedAgent && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="card p-6 max-w-md w-full animate-fade-up">
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-default">
              <div className="flex items-center gap-2">
                <Cpu className="w-5 h-5 text-accent" />
                <h3 className="font-bold text-base text-primary">إدارة الوكيل: {selectedAgent.name}</h3>
              </div>
              <button
                onClick={() => setSelectedAgent(null)}
                className="text-muted hover:text-primary text-sm font-bold px-2"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <span className="text-xs text-muted block mb-1">الدور والقسم</span>
                <p className="text-sm font-bold text-primary">{selectedAgent.role} • {selectedAgent.department}</p>
              </div>

              <div>
                <span className="text-xs text-muted block mb-1">المهمة الحالية</span>
                <p className="text-xs text-secondary p-3 rounded-lg bg-elevated border border-default">
                  {selectedAgent.task}
                </p>
              </div>

              <div className="flex items-center gap-2 pt-2">
                <button
                  onClick={() => {
                    restartAgent(selectedAgent.id);
                    setSelectedAgent(null);
                  }}
                  className="flex-1 py-2.5 rounded-xl bg-accent text-white text-xs font-bold hover:opacity-90 transition-opacity flex items-center justify-center gap-1.5"
                >
                  <RotateCcw className="w-4 h-4" />
                  إعادة تشغيل الوكيل
                </button>
                <button
                  onClick={() => {
                    updateAgentStatus(
                      selectedAgent.id,
                      selectedAgent.status === 'active' ? 'idle' : 'active'
                    );
                    setSelectedAgent(null);
                  }}
                  className="py-2.5 px-4 rounded-xl bg-elevated border border-default text-primary text-xs font-bold hover:bg-elevated/80 transition-colors"
                >
                  {selectedAgent.status === 'active' ? 'إيقاف مؤقت' : 'تفعيل'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
