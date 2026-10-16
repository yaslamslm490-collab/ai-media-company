import { useState } from 'react';
import { useTheme } from '@/context/ThemeContext';
import { useApp } from '@/context/AppContext';
import type { ViewKey, UserRole } from '@/types';
import {
  Menu,
  Moon,
  Sun,
  Bell,
  Search,
  Mic,
  CheckCircle2,
} from 'lucide-react';

interface HeaderProps {
  activeView: ViewKey;
  onMenuClick: () => void;
  onNavigate: (view: ViewKey) => void;
}

const VIEW_TITLES: Record<ViewKey, string> = {
  owner_center: 'مركز المالك — القيادة والسيادة',
  dashboard: 'لوحة التحكم العامة ومراقب الوكلاء',
  assistant: 'المساعد الشخصي NADA AI',
  characters: 'استوديو الشخصيات الافتراضية والـ Bible',
  universes: 'العوالم القصصية والسلاسل الزمنية',
  projects: 'إدارة المشروعات والميزانيات',
  content_pipeline: 'مسار الإنتاج وبوابة الجودة (Quality Gate)',
  voice_studio: 'مختبر الصوت والنطق العربي (STT / TTS)',
  omniroute: 'توجيه النماذج الذكية OmniRoute',
  approvals: 'مركز الموافقات والقرارات السيادية',
  vault: 'خزينة الأصول الرقمية والإعلامية',
  memory: 'الذاكرة الدائمة وقارئ السياق (Instant Reader)',
  security: 'الأمان والصلاحيات والنسخ الاحتياطي',
  future_engineer: 'مهندس المستقبل 2350 (Isolated Sandbox)',
  readiness: 'مركز الجاهزية والاعتماد قبل التنفيذ',
  daily_report: 'التقرير التشغيلي اليومي الموحد',
};

export function Header({ activeView, onMenuClick, onNavigate }: HeaderProps) {
  const { theme, toggleTheme } = useTheme();
  const { currentRole, switchRole, currentUser, approvals, characters, scripts } = useApp();

  const [showRoleDropdown, setShowRoleDropdown] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showSearchModal, setShowSearchModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const pendingApprovals = approvals.filter((a) => a.status === 'pending');

  const filteredCharacters = characters.filter((c) =>
    c.name.includes(searchQuery) || c.code.toLowerCase().includes(searchQuery.toLowerCase())
  );
  const filteredScripts = scripts.filter((s) => s.title.includes(searchQuery));

  return (
    <header className="sticky top-0 z-30 bg-secondary/80 backdrop-blur-xl border-b border-default">
      <div className="flex items-center justify-between px-4 sm:px-6 py-3.5 gap-4">
        {/* Left Section: Mobile Menu & View Title */}
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={onMenuClick}
            className="lg:hidden text-secondary hover:text-primary transition-colors flex-shrink-0 p-1"
          >
            <Menu className="w-6 h-6" />
          </button>
          <div className="min-w-0">
            <h2 className="font-display font-bold text-base sm:text-lg text-primary truncate">
              {VIEW_TITLES[activeView] || 'NADA AI Media OS'}
            </h2>
            <p className="text-[11px] text-muted hidden sm:block">
              {new Date().toLocaleDateString('ar-EG', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </p>
          </div>
        </div>

        {/* Right Section: Actions & Controls */}
        <div className="flex items-center gap-2 sm:gap-2.5 flex-shrink-0">
          {/* Global Search Button */}
          <button
            onClick={() => setShowSearchModal(true)}
            className="flex items-center gap-2 bg-elevated rounded-xl px-3.5 py-2 border border-default text-xs text-muted hover:text-primary hover:border-accent transition-colors"
          >
            <Search className="w-4 h-4 text-muted" />
            <span className="hidden md:inline">بحث في النظام...</span>
          </button>

          {/* Quick Voice Assistant Trigger */}
          <button
            onClick={() => onNavigate('assistant')}
            className="p-2 rounded-xl bg-accent/15 border border-accent/30 text-accent hover:bg-accent/25 transition-colors"
            title="فتح المساعد الصوتي NADA"
          >
            <Mic className="w-4 h-4" />
          </button>

          {/* Notifications Button */}
          <div className="relative">
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className="relative p-2 rounded-xl bg-elevated border border-default text-secondary hover:text-primary transition-colors"
              title="مركز الإشعارات والتنبيهات"
            >
              <Bell className="w-4 h-4" />
              {pendingApprovals.length > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center animate-pulse">
                  {pendingApprovals.length}
                </span>
              )}
            </button>

            {/* Notifications Dropdown */}
            {showNotifications && (
              <div className="absolute left-0 sm:left-auto sm:right-0 mt-2 w-80 rounded-2xl bg-secondary border border-default shadow-2xl p-4 z-50 animate-fade-up">
                <div className="flex items-center justify-between pb-2 border-b border-default mb-2">
                  <h4 className="font-bold text-xs text-primary">تنبيهات المنظومة</h4>
                  <button
                    onClick={() => setShowNotifications(false)}
                    className="text-xs text-muted hover:text-primary"
                  >
                    ✕
                  </button>
                </div>
                {pendingApprovals.length > 0 ? (
                  <div className="space-y-2">
                    {pendingApprovals.slice(0, 4).map((item) => (
                      <div
                        key={item.id}
                        onClick={() => {
                          onNavigate('approvals');
                          setShowNotifications(false);
                        }}
                        className="p-2.5 rounded-xl bg-elevated hover:bg-elevated/80 border border-default cursor-pointer text-xs"
                      >
                        <span className="font-bold text-primary block truncate">{item.title}</span>
                        <span className="text-[10px] text-warning">{item.submittedAt}</span>
                      </div>
                    ))}
                    <button
                      onClick={() => {
                        onNavigate('approvals');
                        setShowNotifications(false);
                      }}
                      className="w-full text-center text-xs text-accent hover:underline font-bold pt-1"
                    >
                      عرض جميع الموافقات ({pendingApprovals.length})
                    </button>
                  </div>
                ) : (
                  <p className="text-xs text-muted text-center py-4">لا توجد تنبيهات عاجلة حالياً.</p>
                )}
              </div>
            )}
          </div>

          {/* Role Switcher Button */}
          <div className="relative">
            <button
              onClick={() => setShowRoleDropdown(!showRoleDropdown)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-elevated border border-default hover:border-accent text-xs font-bold text-primary transition-colors"
            >
              <span>{currentUser.avatar}</span>
              <span className="hidden sm:inline">{currentUser.name}</span>
            </button>

            {/* Role Switcher Dropdown */}
            {showRoleDropdown && (
              <div className="absolute left-0 mt-2 w-56 rounded-2xl bg-secondary border border-default shadow-2xl p-2 z-50 animate-fade-up">
                <span className="text-[10px] text-muted font-bold px-3 py-1 block">
                  تبديل صلاحية المستخدم:
                </span>
                {(['OWNER', 'ADMIN', 'AGENT', 'GUEST'] as UserRole[]).map((r) => (
                  <button
                    key={r}
                    onClick={() => {
                      switchRole(r);
                      setShowRoleDropdown(false);
                    }}
                    className={`w-full text-right px-3 py-2 rounded-xl text-xs font-bold flex items-center justify-between ${
                      currentRole === r
                        ? 'bg-accent text-white'
                        : 'text-secondary hover:bg-elevated hover:text-primary'
                    }`}
                  >
                    <span>{r}</span>
                    {currentRole === r && <CheckCircle2 className="w-3.5 h-3.5" />}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Theme Toggle Button */}
          <button
            onClick={toggleTheme}
            className="p-2 rounded-xl bg-elevated border border-default text-secondary hover:text-primary transition-colors"
            aria-label="تبديل الوضع"
          >
            {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Global Search Modal */}
      {showSearchModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-start justify-center pt-20 p-4">
          <div className="card p-5 max-w-xl w-full animate-fade-up space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-default">
              <div className="flex items-center gap-2 flex-1">
                <Search className="w-4 h-4 text-accent" />
                <input
                  type="text"
                  autoFocus
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="ابحث عن شخصية، سكريبت، أو أمر في المنظومة..."
                  className="w-full bg-transparent text-sm text-primary placeholder:text-muted outline-none"
                />
              </div>
              <button
                onClick={() => setShowSearchModal(false)}
                className="text-muted hover:text-primary px-2 font-bold"
              >
                ✕
              </button>
            </div>

            {searchQuery && (
              <div className="space-y-3 max-h-72 overflow-y-auto">
                {filteredCharacters.length > 0 && (
                  <div>
                    <span className="text-[10px] text-muted font-bold block mb-1">الشخصيات:</span>
                    <div className="space-y-1">
                      {filteredCharacters.map((c) => (
                        <div
                          key={c.id}
                          onClick={() => {
                            onNavigate('characters');
                            setShowSearchModal(false);
                          }}
                          className="p-2 rounded-lg bg-elevated hover:bg-elevated/80 cursor-pointer text-xs flex items-center justify-between"
                        >
                          <span className="font-bold text-primary">{c.name}</span>
                          <span className="text-[10px] text-accent font-mono">{c.code}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {filteredScripts.length > 0 && (
                  <div>
                    <span className="text-[10px] text-muted font-bold block mb-1">السكريبتات:</span>
                    <div className="space-y-1">
                      {filteredScripts.map((s) => (
                        <div
                          key={s.id}
                          onClick={() => {
                            onNavigate('content_pipeline');
                            setShowSearchModal(false);
                          }}
                          className="p-2 rounded-lg bg-elevated hover:bg-elevated/80 cursor-pointer text-xs flex items-center justify-between"
                        >
                          <span className="font-bold text-primary truncate">{s.title}</span>
                          <span className="text-[10px] text-muted">{s.characterName}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
