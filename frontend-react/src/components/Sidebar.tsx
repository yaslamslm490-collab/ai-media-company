import { useApp } from '@/context/AppContext';
import type { ViewKey, UserRole } from '@/types';
import {
  Crown,
  LayoutDashboard,
  Bot,
  Users,
  Globe,
  FolderKanban,
  Film,
  Mic,
  Network,
  CheckSquare,
  Archive,
  Brain,
  Shield,
  Rocket,
  CheckCheck,
  FileText,
  X,
} from 'lucide-react';

interface SidebarProps {
  activeView: ViewKey;
  onNavigate: (view: ViewKey) => void;
  isOpen: boolean;
  onClose: () => void;
}

interface NavGroup {
  groupName: string;
  items: {
    key: ViewKey;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    badge?: string;
  }[];
}

export function Sidebar({ activeView, onNavigate, isOpen, onClose }: SidebarProps) {
  const { currentRole, currentUser, switchRole, approvals } = useApp();

  const pendingApprovalsCount = approvals.filter((a) => a.status === 'pending').length;

  const navGroups: NavGroup[] = [
    {
      groupName: 'القيادة والسيادة',
      items: [
        { key: 'owner_center', label: 'مركز المالك', icon: Crown },
        { key: 'dashboard', label: 'لوحة التحكم العامة', icon: LayoutDashboard },
        { key: 'assistant', label: 'المساعد الشخصي NADA', icon: Bot },
        {
          key: 'approvals',
          label: 'مركز الموافقات',
          icon: CheckSquare,
          badge: pendingApprovalsCount > 0 ? `${pendingApprovalsCount}` : undefined,
        },
      ],
    },
    {
      groupName: 'الإنتاج والمحتوى الذكي',
      items: [
        { key: 'characters', label: 'استوديو الشخصيات الـ 11', icon: Users },
        { key: 'universes', label: 'العوالم القصصية', icon: Globe },
        { key: 'content_pipeline', label: 'مسار الإنتاج وبوابة الجودة', icon: Film },
        { key: 'voice_studio', label: 'مختبر الصوت والنطق العربي', icon: Mic },
        { key: 'projects', label: 'المشروعات والميزانيات', icon: FolderKanban },
        { key: 'vault', label: 'خزينة الأصول الرقمية', icon: Archive },
      ],
    },
    {
      groupName: 'الذاكرة والنماذج والأمان',
      items: [
        { key: 'memory', label: 'الذاكرة الدائمة (Instant Reader)', icon: Brain },
        { key: 'omniroute', label: 'توجيه النماذج OmniRoute', icon: Network },
        { key: 'security', label: 'الأمان والنسخ الاحتياطي', icon: Shield },
        { key: 'future_engineer', label: 'مهندس المستقبل 2350', icon: Rocket },
        { key: 'readiness', label: 'مركز الجاهزية والاعتماد', icon: CheckCheck },
        { key: 'daily_report', label: 'التقرير التشغيلي اليومي', icon: FileText },
      ],
    },
  ];

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden backdrop-blur-sm"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed top-0 right-0 h-full w-72 bg-secondary border-l border-default z-50 transform transition-transform duration-300 lg:translate-x-0 lg:static lg:z-0 flex flex-col justify-between ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Logo and Brand Header */}
        <div>
          <div className="flex items-center justify-between p-5 border-b border-default">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-accent flex items-center justify-center glow-accent flex-shrink-0 text-white font-bold text-lg">
                ن
              </div>
              <div className="min-w-0">
                <h1 className="font-display font-bold text-base text-primary leading-tight truncate">
                  NADA AI Media OS
                </h1>
                <p className="text-[10px] text-muted font-mono">الإصدار 3.0 — Hybrid Edition</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="lg:hidden text-muted hover:text-primary transition-colors p-1"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Navigation Links with Groups */}
          <nav className="p-3 space-y-4 max-h-[calc(100vh-170px)] overflow-y-auto">
            {navGroups.map((grp) => (
              <div key={grp.groupName} className="space-y-1">
                <p className="text-[10px] text-muted font-bold px-3 py-1 uppercase tracking-wider">
                  {grp.groupName}
                </p>
                {grp.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = activeView === item.key;
                  return (
                    <button
                      key={item.key}
                      onClick={() => {
                        onNavigate(item.key);
                        onClose();
                      }}
                      className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all duration-200 ${
                        isActive
                          ? 'nav-item-active font-bold shadow-sm'
                          : 'text-secondary hover:bg-elevated hover:text-primary'
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <Icon className="w-4 h-4 flex-shrink-0" />
                        <span className="truncate">{item.label}</span>
                      </div>
                      {item.badge ? (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-500 text-white animate-pulse">
                          {item.badge}
                        </span>
                      ) : isActive ? (
                        <span className="w-1.5 h-1.5 rounded-full bg-accent flex-shrink-0" />
                      ) : null}
                    </button>
                  );
                })}
              </div>
            ))}
          </nav>
        </div>

        {/* User Role Card at bottom */}
        <div className="p-3 border-t border-default bg-elevated/40">
          <div className="card p-3 flex items-center justify-between gap-2.5">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-teal-500 to-emerald-600 flex items-center justify-center text-white text-base shadow flex-shrink-0">
                {currentUser.avatar}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-primary truncate">{currentUser.name}</p>
                <p className="text-[10px] text-muted truncate">{currentUser.role}</p>
              </div>
            </div>
            <button
              onClick={() => {
                const nextRole: Record<UserRole, UserRole> = {
                  OWNER: 'ADMIN',
                  ADMIN: 'AGENT',
                  AGENT: 'GUEST',
                  GUEST: 'OWNER',
                };
                switchRole(nextRole[currentRole]);
              }}
              className="text-[10px] px-2 py-1 rounded bg-elevated hover:bg-elevated/80 border border-default text-accent font-bold"
              title="تبديل الدور السريع"
            >
              تبديل
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
