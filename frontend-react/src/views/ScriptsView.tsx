import { useState } from 'react';
import { scripts, statusLabels } from '@/data';
import type { Script } from '@/types';
import {
  FileText,
  Search,
  Plus,
  Sparkles,
  Eye,
  Lightbulb,
  Target,
  TrendingUp,
} from 'lucide-react';

const statusStyles: Record<string, { bg: string; color: string }> = {
  draft: { bg: 'rgba(100,116,139,0.1)', color: 'var(--text-muted)' },
  review: { bg: 'rgba(251,191,36,0.1)', color: 'var(--warning)' },
  approved: { bg: 'var(--accent-dim)', color: 'var(--accent)' },
  published: { bg: 'rgba(96,165,250,0.1)', color: 'var(--info)' },
};

function ScriptListItem({
  script,
  isSelected,
  onClick,
}: {
  script: Script;
  isSelected: boolean;
  onClick: () => void;
}) {
  const style = statusStyles[script.status] ?? statusStyles.draft;
  return (
    <button
      onClick={onClick}
      className={`w-full text-right p-4 rounded-xl border transition-all duration-200 ${
        isSelected
          ? 'bg-accent-dim border-accent/30'
          : 'bg-card border-default hover:bg-elevated'
      }`}
    >
      <div className="flex items-start justify-between mb-2">
        <h4 className={`text-sm font-medium truncate ${isSelected ? 'text-accent' : 'text-primary'}`}>
          {script.title}
        </h4>
        <span
          className="text-xs px-2 py-0.5 rounded-md font-medium flex-shrink-0 mr-2"
          style={{ backgroundColor: style.bg, color: style.color }}
        >
          {statusLabels[script.status]}
        </span>
      </div>
      <div className="flex items-center gap-3 text-xs text-muted">
        <span>{script.character}</span>
        <span>•</span>
        <span>{script.platform}</span>
        <span>•</span>
        <span>{script.wordCount} كلمة</span>
      </div>
    </button>
  );
}

function ScriptDetail({ script }: { script: Script }) {
  const style = statusStyles[script.status] ?? statusStyles.draft;
  return (
    <div className="card p-6 space-y-6 animate-fade-up">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h2 className="font-display font-bold text-xl text-primary mb-1">{script.title}</h2>
          <div className="flex items-center gap-3 text-xs text-muted">
            <span>{script.character}</span>
            <span>•</span>
            <span>{script.platform}</span>
            <span>•</span>
            <span>{script.updatedAt}</span>
          </div>
        </div>
        <span
          className="text-xs px-3 py-1.5 rounded-lg font-medium"
          style={{ backgroundColor: style.bg, color: style.color }}
        >
          {statusLabels[script.status]}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="bg-elevated rounded-xl p-3 border border-default">
          <div className="flex items-center gap-2 mb-1">
            <FileText className="w-3.5 h-3.5 text-muted" />
            <span className="text-xs text-muted">عدد الكلمات</span>
          </div>
          <p className="font-display font-bold text-lg text-primary">{script.wordCount}</p>
        </div>
        <div className="bg-elevated rounded-xl p-3 border border-default">
          <div className="flex items-center gap-2 mb-1">
            <Target className="w-3.5 h-3.5 text-muted" />
            <span className="text-xs text-muted">المنصة</span>
          </div>
          <p className="font-display font-bold text-sm text-primary">{script.platform}</p>
        </div>
        <div className="bg-elevated rounded-xl p-3 border border-default">
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp className="w-3.5 h-3.5 text-muted" />
            <span className="text-xs text-muted">الشخصية</span>
          </div>
          <p className="font-display font-bold text-sm text-primary truncate">{script.character}</p>
        </div>
      </div>

      <div>
        <div className="flex items-center gap-2 mb-2">
          <Lightbulb className="w-4 h-4 text-warning" />
          <h3 className="text-sm font-bold text-primary">الخطّاف (Hook)</h3>
        </div>
        <div className="bg-elevated rounded-xl p-4 border border-default">
          <p className="text-sm text-secondary leading-relaxed">{script.hook}</p>
        </div>
      </div>

      <div>
        <div className="flex items-center gap-2 mb-2">
          <FileText className="w-4 h-4 text-info" />
          <h3 className="text-sm font-bold text-primary">المتن</h3>
        </div>
        <div className="bg-elevated rounded-xl p-4 border border-default min-h-[120px]">
          <p className="text-sm text-secondary leading-relaxed">{script.body}</p>
        </div>
      </div>

      <div>
        <div className="flex items-center gap-2 mb-2">
          <Target className="w-4 h-4 text-accent" />
          <h3 className="text-sm font-bold text-primary">الدعوة لاتخاذ إجراء (CTA)</h3>
        </div>
        <div className="bg-elevated rounded-xl p-4 border border-default">
          <p className="text-sm text-secondary leading-relaxed">{script.cta}</p>
        </div>
      </div>

      <div className="flex items-center gap-3 flex-wrap pt-4 border-t border-default">
        <button className="flex items-center gap-2 bg-accent text-white px-5 py-2.5 rounded-xl text-sm font-medium hover:opacity-90 transition-opacity">
          <Sparkles className="w-4 h-4" />
          <span>إعادة التوليد بالذكاء الاصطناعي</span>
        </button>
        <button className="flex items-center gap-2 bg-elevated text-secondary px-5 py-2.5 rounded-xl text-sm font-medium border border-default hover:text-primary transition-colors">
          <Eye className="w-4 h-4" />
          <span>معاينة</span>
        </button>
        <button className="flex items-center gap-2 bg-elevated text-secondary px-5 py-2.5 rounded-xl text-sm font-medium border border-default hover:text-primary transition-colors">
          <Plus className="w-4 h-4" />
          <span>إرسال للموافقة</span>
        </button>
      </div>
    </div>
  );
}

export function ScriptsView() {
  const [selectedId, setSelectedId] = useState(scripts[0].id);
  const selected = scripts.find((s) => s.id === selectedId) ?? scripts[0];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <p className="text-sm text-secondary">
          محرر سكريبتات يعمل بالذكاء الاصطناعي — أنشئ، حرّر، واعتمد المحتوى
        </p>
        <button className="flex items-center gap-2 bg-accent text-white px-5 py-2.5 rounded-xl text-sm font-medium hover:opacity-90 transition-opacity glow-accent">
          <Sparkles className="w-4 h-4" />
          <span>توليد سكريبت جديد</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="space-y-3">
          <div className="flex items-center gap-2 bg-elevated rounded-xl px-4 py-2.5 border border-default">
            <Search className="w-4 h-4 text-muted" />
            <input
              type="text"
              placeholder="ابحث في السكريبتات..."
              className="bg-transparent text-sm text-primary placeholder:text-muted outline-none w-full"
            />
          </div>
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {scripts.map((s) => (
              <ScriptListItem
                key={s.id}
                script={s}
                isSelected={s.id === selectedId}
                onClick={() => setSelectedId(s.id)}
              />
            ))}
          </div>
        </div>

        <div className="lg:col-span-2">
          <ScriptDetail script={selected} />
        </div>
      </div>
    </div>
  );
}
