import { useState } from 'react';
import { useApp } from '@/context/AppContext';
import type { MemoryComponentKey, MemoryEntry } from '@/types';
import {
  Search,
  Clock,
  Sparkles,
  Plus,
} from 'lucide-react';

const MEMORY_PILLARS: { key: MemoryComponentKey; label: string; icon: string; desc: string }[] = [
  { key: 'core', label: 'الذاكرة التأسيسية (Core)', icon: '🏛️', desc: 'الهوية والرؤية والمبادئ الحاكمة والسيادة' },
  { key: 'project', label: 'ذاكرة المشروعات (Project)', icon: '📁', desc: 'حالة المشروعات والمراحل والاعتماديات' },
  { key: 'character', label: 'ذاكرة الشخصيات (Character)', icon: '🎭', desc: 'هويات الشخصيات الـ 11 والاتساق السردي' },
  { key: 'technical', label: 'الذاكرة التقنية (Technical)', icon: '⚡', desc: 'البنية البرمجية والمنافذ وواجهات API' },
  { key: 'decision', label: 'ذاكرة القرارات (Decision)', icon: '⚖️', desc: 'قرارات المالك الحصرية وأسبابها' },
  { key: 'cost', label: 'ذاكرة التكاليف (Cost)', icon: '💰', desc: 'الميزانيات وترشيد استهلاك النماذج' },
  { key: 'recovery', label: 'ذاكرة التعافي (Recovery)', icon: '🛡️', desc: 'النسخ الاحتياطية وإجراءات الاستعادة' },
  { key: 'future_engineer', label: 'ذاكرة 2350 (Future)', icon: '🚀', desc: 'أبحاث Sandbox والنماذج المستقبلية' },
  { key: 'experience', label: 'ذاكرة الخبرات (Experience)', icon: '🌟', desc: 'النتائج الميدانية وتفاعل الجمهور' },
  { key: 'lessons_learned', label: 'الدروس المستفادة (Lessons)', icon: '💡', desc: 'الدروس التقنية والتشغيلية' },
  { key: 'research', label: 'ذاكرة الأبحاث (Research)', icon: '🔬', desc: 'الأبحاث والتقنيات ومستويات الثقة' },
  { key: 'timeline', label: 'الأرشيف الزمني (Timeline)', icon: '⏳', desc: 'الإصدارات ونقاط الاستئناف التاريخية' },
];

export function MemoryView() {
  const { memoryEntries, queryInstantMemory, addMemoryEntry } = useApp();

  const [activeTab, setActiveTab] = useState<MemoryComponentKey | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [instantQueryResult, setInstantQueryResult] = useState<{
    results: MemoryEntry[];
    executionTimeMs: number;
    summary: string;
  } | null>(null);

  const [showAddModal, setShowAddModal] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newContent, setNewContent] = useState('');
  const [newComponent, setNewComponent] = useState<MemoryComponentKey>('core');
  const [newTags, setNewTags] = useState('دستور, توثيق');

  // Trigger Instant Reader
  const handleRunInstantQuery = (q: string) => {
    setSearchQuery(q);
    const result = queryInstantMemory(q);
    setInstantQueryResult(result);
  };

  const filteredEntries = memoryEntries.filter((m) => {
    const matchesTab = activeTab === 'all' || m.component === activeTab;
    const matchesSearch =
      !searchQuery ||
      m.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.tags.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesTab && matchesSearch;
  });

  const handleAddEntry = (e: React.FormEvent) => {
    e.preventDefault();
    addMemoryEntry({
      component: newComponent,
      title: newTitle || 'سجل جديد',
      content: newContent || 'تفاصيل المحتوى...',
      tags: newTags.split(',').map((t) => t.trim()).filter(Boolean),
      confidence: 0.95,
      author: 'الموثق المسؤول',
    });
    setShowAddModal(false);
    setNewTitle('');
    setNewContent('');
  };

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header Banner */}
      <div className="card p-6 bg-gradient-to-l from-[var(--bg-card)] to-[var(--bg-elevated)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-accent/20 text-accent font-bold">
              القسم 8 — NADA PERMANENT MEMORY SYSTEM
            </span>
            <span className="text-xs text-muted">12 مكوناً رئيسياً</span>
          </div>
          <h1 className="font-display font-bold text-2xl text-primary mt-1">
            الذاكرة الدائمة وقارئ السياق اللحظي (Instant Reader)
          </h1>
          <p className="text-sm text-secondary">
            حفظ المعرفة، قرارات المالك، تاريخ المشروعات، وقواعد الشخصيات مع استرجاع لحظي في أقل من ثانيتين.
          </p>
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2.5 rounded-xl bg-accent text-white text-xs font-bold hover:opacity-90 transition-opacity flex items-center gap-2 self-start md:self-auto shadow"
        >
          <Plus className="w-4 h-4" />
          <span>إضافة سجل ذاكرة جديد</span>
        </button>
      </div>

      {/* NADA Instant Project Reader Search Bar */}
      <div className="card p-5 border border-accent/30 bg-accent/5 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-display font-bold text-sm text-primary flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-accent" />
            NADA Instant Project Reader — محرك الاسترجاع فائق السرعة (&lt; 2s)
          </h3>
          <span className="text-xs text-muted">فهرسة كاملة لذاكرة النظام</span>
        </div>

        <div className="relative">
          <Search className="w-4 h-4 text-muted absolute right-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => handleRunInstantQuery(e.target.value)}
            placeholder="ابحث في الذاكرة: القرارات، المشروعات، السكريبتات، أو قواعد الشخصيات..."
            className="w-full pl-4 pr-10 py-3 rounded-xl bg-elevated border border-default text-sm text-primary placeholder:text-muted outline-none focus:border-accent"
          />
        </div>

        {instantQueryResult && (
          <div className="p-3 rounded-xl bg-elevated border border-default text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <span className="text-secondary">{instantQueryResult.summary}</span>
            <span className="text-accent font-bold font-mono text-[11px] flex items-center gap-1 flex-shrink-0">
              <Clock className="w-3.5 h-3.5" />
              زمن الاسترجاع الفعلي: {instantQueryResult.executionTimeMs}ms
            </span>
          </div>
        )}
      </div>

      {/* 12 Memory Pillars Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        <button
          onClick={() => setActiveTab('all')}
          className={`px-3.5 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-colors ${
            activeTab === 'all'
              ? 'bg-accent text-white shadow'
              : 'bg-elevated border border-default text-secondary hover:text-primary'
          }`}
        >
          كل السجلات ({memoryEntries.length})
        </button>

        {MEMORY_PILLARS.map((p) => {
          const count = memoryEntries.filter((m) => m.component === p.key).length;
          return (
            <button
              key={p.key}
              onClick={() => setActiveTab(p.key)}
              className={`px-3 py-2 rounded-xl text-xs font-medium whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                activeTab === p.key
                  ? 'bg-accent text-white shadow'
                  : 'bg-elevated border border-default text-secondary hover:text-primary'
              }`}
            >
              <span>{p.icon}</span>
              <span>{p.label}</span>
              <span className="text-[10px] opacity-75">({count})</span>
            </button>
          );
        })}
      </div>

      {/* Memory Entries Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filteredEntries.map((entry) => {
          const pillar = MEMORY_PILLARS.find((p) => p.key === entry.component);
          return (
            <div
              key={entry.id}
              className="card p-5 hover:border-accent/40 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{pillar?.icon || '🧠'}</span>
                    <h4 className="font-bold text-sm text-primary leading-snug">{entry.title}</h4>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/15 text-accent font-bold whitespace-nowrap">
                    ثقة {Math.round(entry.confidence * 100)}%
                  </span>
                </div>

                <p className="text-xs text-secondary leading-relaxed mb-4 whitespace-pre-wrap">
                  {entry.content}
                </p>

                <div className="flex flex-wrap gap-1.5 mb-3">
                  {entry.tags.map((tag) => (
                    <span
                      key={tag}
                      className="text-[10px] px-2 py-0.5 rounded bg-elevated border border-default/70 text-muted"
                    >
                      #{tag}
                    </span>
                  ))}
                </div>
              </div>

              <div className="pt-3 border-t border-default/50 flex items-center justify-between text-[11px] text-muted">
                <span>المؤلف: {entry.author}</span>
                <span>{entry.updatedAt}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Add Memory Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <form
            onSubmit={handleAddEntry}
            className="card p-6 max-w-md w-full animate-fade-up space-y-4"
          >
            <div className="flex items-center justify-between pb-3 border-b border-default">
              <h3 className="font-bold text-base text-primary">إضافة سجل إلى الذاكرة الدائمة</h3>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="text-muted hover:text-primary font-bold px-2"
              >
                ✕
              </button>
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">المكون المرجعي (Pillar):</label>
              <select
                value={newComponent}
                onChange={(e) => setNewComponent(e.target.value as MemoryComponentKey)}
                className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
              >
                {MEMORY_PILLARS.map((p) => (
                  <option key={p.key} value={p.key}>
                    {p.icon} {p.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">عنوان السجل:</label>
              <input
                type="text"
                required
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="عنوان واضح..."
                className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
              />
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">المحتوى والتوثيق:</label>
              <textarea
                rows={4}
                required
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
                placeholder="تفاصيل التوثيق المرجعي..."
                className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
              />
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">الوسوم (مفصولة بفاصلة):</label>
              <input
                type="text"
                value={newTags}
                onChange={(e) => setNewTags(e.target.value)}
                className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="px-4 py-2 rounded-xl bg-elevated text-xs font-bold text-muted hover:text-primary"
              >
                إلغاء
              </button>
              <button
                type="submit"
                className="px-5 py-2 rounded-xl bg-accent text-white text-xs font-bold hover:opacity-90"
              >
                حفظ في الذاكرة
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
