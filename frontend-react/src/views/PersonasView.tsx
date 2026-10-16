import { useState } from 'react';
import { personas, personaStatusLabels, platformOptions } from '@/data';
import type { Persona } from '@/types';
import {
  Plus,
  Pencil,
  Pause,
  Play,
  FlaskConical,
  X,
  Send,
  Bot,
  Sparkles,
  Loader2,
  TrendingUp,
  FileText,
  CircleDot,
  BookOpen,
  Check,
  XCircle,
  Code2,
  User,
  ScrollText,
  Lightbulb,
  Users,
  Heart,
} from 'lucide-react';

interface PersonaFormData {
  name: string;
  tone: string;
  platform: string;
  systemPrompt: string;
}

const emptyForm: PersonaFormData = {
  name: '',
  tone: '',
  platform: platformOptions[0],
  systemPrompt: '',
};

const statusStyles: Record<string, { bg: string; color: string }> = {
  active: { bg: 'var(--accent-dim)', color: 'var(--accent)' },
  paused: { bg: 'rgba(100,116,139,0.12)', color: 'var(--text-muted)' },
};

interface ChatMessage {
  role: 'user' | 'persona';
  text: string;
}

type CardTab = 'overview' | 'bible';
type BibleTab = 'identity' | 'rules' | 'prompts';

function BibleIdentitySection({ persona }: { persona: Persona }) {
  const id = persona.bible!.identity;
  const fields = [
    { icon: User, label: 'الاسم', value: id.name },
    { icon: Code2, label: 'الكود', value: id.code },
    { icon: Heart, label: 'الدور', value: id.role },
    { icon: Sparkles, label: 'النبرة', value: id.tone },
    { icon: Users, label: 'الجمهور', value: id.audience },
    { icon: Lightbulb, label: 'الشخصية', value: id.personality },
  ];
  return (
    <div className="space-y-3">
      {fields.map((f) => {
        const Icon = f.icon;
        return (
          <div key={f.label} className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-elevated flex items-center justify-center flex-shrink-0 border border-default">
              <Icon className="w-4 h-4 text-accent" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs text-muted mb-0.5">{f.label}</p>
              <p className="text-sm text-primary leading-relaxed">{f.value}</p>
            </div>
          </div>
        );
      })}
      <div className="flex items-start gap-3 pt-3 border-t border-default">
        <div className="w-8 h-8 rounded-lg bg-elevated flex items-center justify-center flex-shrink-0 border border-default">
          <ScrollText className="w-4 h-4 text-accent" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs text-muted mb-0.5">القصة الخلفية</p>
          <p className="text-sm text-secondary leading-relaxed">{id.backstory}</p>
        </div>
      </div>
    </div>
  );
}

function BibleRulesSection({ persona }: { persona: Persona }) {
  const rules = persona.bible!.rules;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div>
        <div className="flex items-center gap-2 mb-3">
          <div className="w-7 h-7 rounded-lg bg-accent-dim flex items-center justify-center">
            <Check className="w-3.5 h-3.5 text-accent" />
          </div>
          <h4 className="text-sm font-bold text-accent">قواعد Do</h4>
        </div>
        <ul className="space-y-2">
          {rules.do.map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-xs text-secondary leading-relaxed">
              <Check className="w-3.5 h-3.5 text-accent flex-shrink-0 mt-0.5" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <div className="flex items-center gap-2 mb-3">
          <div className="w-7 h-7 rounded-lg bg-red-500/10 flex items-center justify-center">
            <XCircle className="w-3.5 h-3.5 text-error" />
          </div>
          <h4 className="text-sm font-bold text-error">قواعد Don't</h4>
        </div>
        <ul className="space-y-2">
          {rules.dont.map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-xs text-secondary leading-relaxed">
              <XCircle className="w-3.5 h-3.5 text-error flex-shrink-0 mt-0.5" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function BiblePromptsSection({ persona }: { persona: Persona }) {
  const prompts = persona.bible!.prompts;
  return (
    <div className="space-y-3">
      {prompts.map((p, i) => (
        <div key={i} className="bg-elevated rounded-xl p-4 border border-default">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-7 h-7 rounded-lg bg-accent-dim flex items-center justify-center">
              <Sparkles className="w-3.5 h-3.5 text-accent" />
            </div>
            <h4 className="text-sm font-medium text-primary">{p.name}</h4>
          </div>
          <p className="text-xs text-secondary leading-relaxed pr-9">{p.template}</p>
        </div>
      ))}
    </div>
  );
}

function PersonaCard({
  persona,
  onEdit,
  onTogglePause,
  onTest,
}: {
  persona: Persona;
  onEdit: (p: Persona) => void;
  onTogglePause: (id: string) => void;
  onTest: (p: Persona) => void;
}) {
  const style = statusStyles[persona.status] ?? statusStyles.paused;
  const [cardTab, setCardTab] = useState<CardTab>('overview');
  const [bibleTab, setBibleTab] = useState<BibleTab>('identity');
  const hasBible = !!persona.bible;

  const bibleTabs: { key: BibleTab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { key: 'identity', label: 'الهوية', icon: User },
    { key: 'rules', label: "Do/Don't", icon: Check },
    { key: 'prompts', label: 'القوالب', icon: Sparkles },
  ];

  return (
    <div className="card overflow-hidden group flex flex-col">
      <div className="relative h-32 bg-gradient-to-br from-[var(--bg-elevated)] to-[var(--bg-card)]">
        <div className="absolute inset-0 opacity-30"
          style={{ background: `radial-gradient(circle at 70% 50%, var(--accent-glow), transparent 60%)` }}
        />
        {persona.code && (
          <div className="absolute top-3 right-3">
            <span className="text-xs px-2.5 py-1 rounded-lg font-mono font-medium bg-black/30 text-accent backdrop-blur-sm">
              {persona.code}
            </span>
          </div>
        )}
        <div className="absolute top-3 left-3">
          <span
            className="text-xs px-3 py-1 rounded-lg font-medium flex items-center gap-1.5"
            style={{ backgroundColor: style.bg, color: style.color }}
          >
            <CircleDot className="w-3 h-3" />
            {personaStatusLabels[persona.status]}
          </span>
        </div>
      </div>

      <div className="px-5 pb-5 -mt-12 flex-1 flex flex-col">
        <div className="flex items-end justify-between mb-3">
          <img
            src={persona.image}
            alt={persona.name}
            className="w-20 h-20 rounded-2xl object-cover border-4 border-[var(--bg-card)] shadow-lg"
          />
          <div className="flex items-center gap-1.5 mb-1">
            <Bot className="w-4 h-4 text-accent" />
            <span className="text-xs text-muted">وكيل ذكي</span>
          </div>
        </div>

        <h3 className="font-display font-bold text-base text-primary mb-1">{persona.name}</h3>
        <p className="text-xs text-secondary mb-3 line-clamp-1">{persona.role}</p>

        {cardTab === 'overview' && (
          <>
            <div className="flex flex-wrap gap-1.5 mb-4">
              {persona.platforms.map((p) => (
                <span
                  key={p}
                  className="text-xs px-2.5 py-1 rounded-lg bg-elevated text-secondary border border-default"
                >
                  {p}
                </span>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-2 mb-4">
              <div className="bg-elevated rounded-xl p-3 border border-default text-center">
                <FileText className="w-4 h-4 text-muted mx-auto mb-1" />
                <p className="font-display font-bold text-sm text-primary">{persona.contentCount}</p>
                <p className="text-xs text-muted">محتوى</p>
              </div>
              <div className="bg-elevated rounded-xl p-3 border border-default text-center">
                <TrendingUp className="w-4 h-4 text-muted mx-auto mb-1" />
                <p className="font-display font-bold text-sm text-primary">{persona.engagement}%</p>
                <p className="text-xs text-muted">تفاعل</p>
              </div>
            </div>
          </>
        )}

        {cardTab === 'bible' && hasBible && (
          <div className="mb-4 animate-fade-up">
            <div className="flex items-center gap-1 mb-3 bg-elevated rounded-xl p-1 border border-default">
              {bibleTabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.key}
                    onClick={() => setBibleTab(tab.key)}
                    className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-2 rounded-lg text-xs font-medium transition-all ${
                      bibleTab === tab.key
                        ? 'bg-accent-dim text-accent'
                        : 'text-muted hover:text-primary'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>

            <div className="max-h-[280px] overflow-y-auto pl-1">
              {bibleTab === 'identity' && <BibleIdentitySection persona={persona} />}
              {bibleTab === 'rules' && <BibleRulesSection persona={persona} />}
              {bibleTab === 'prompts' && <BiblePromptsSection persona={persona} />}
            </div>
          </div>
        )}

        <div className="mt-auto space-y-3">
          {hasBible && (
            <div className="flex items-center gap-1 bg-elevated rounded-xl p-1 border border-default">
              <button
                onClick={() => setCardTab('overview')}
                className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-2 rounded-lg text-xs font-medium transition-all ${
                  cardTab === 'overview'
                    ? 'bg-accent-dim text-accent'
                    : 'text-muted hover:text-primary'
                }`}
              >
                <CircleDot className="w-3.5 h-3.5" />
                <span>نظرة عامة</span>
              </button>
              <button
                onClick={() => setCardTab('bible')}
                className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-2 rounded-lg text-xs font-medium transition-all ${
                  cardTab === 'bible'
                    ? 'bg-accent-dim text-accent'
                    : 'text-muted hover:text-primary'
                }`}
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>Character Bible</span>
              </button>
            </div>
          )}

          <div className="flex items-center gap-2">
            <button
              onClick={() => onEdit(persona)}
              className="flex-1 flex items-center justify-center gap-1.5 bg-elevated text-secondary px-3 py-2 rounded-lg text-xs font-medium border border-default hover:text-primary hover:border-accent/30 transition-all"
            >
              <Pencil className="w-3.5 h-3.5" />
              <span>تعديل</span>
            </button>
            <button
              onClick={() => onTogglePause(persona.id)}
              className="flex-1 flex items-center justify-center gap-1.5 bg-elevated text-secondary px-3 py-2 rounded-lg text-xs font-medium border border-default hover:text-primary transition-all"
            >
              {persona.status === 'active' ? (
                <>
                  <Pause className="w-3.5 h-3.5" />
                  <span>إيقاف</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  <span>تفعيل</span>
                </>
              )}
            </button>
            <button
              onClick={() => onTest(persona)}
              className="flex-1 flex items-center justify-center gap-1.5 bg-accent-dim text-accent px-3 py-2 rounded-lg text-xs font-medium hover:bg-accent hover:text-white transition-all"
            >
              <FlaskConical className="w-3.5 h-3.5" />
              <span>اختبار</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function AddPersonaModal({
  isOpen,
  onClose,
  onSubmit,
  editingPersona,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: PersonaFormData) => void;
  editingPersona: Persona | null;
}) {
  const [form, setForm] = useState<PersonaFormData>(emptyForm);

  const handleOpen = () => {
    if (editingPersona) {
      setForm({
        name: editingPersona.name,
        tone: editingPersona.tone,
        platform: editingPersona.platforms[0] ?? platformOptions[0],
        systemPrompt: editingPersona.systemPrompt,
      });
    } else {
      setForm(emptyForm);
    }
  };

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    onSubmit(form);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div
        className="relative w-full max-w-lg bg-card rounded-2xl border border-default shadow-2xl animate-fade-up max-h-[90vh] overflow-y-auto"
        ref={(el) => {
          if (el && isOpen) handleOpen();
        }}
      >
        <div className="flex items-center justify-between p-6 border-b border-default">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-accent-dim flex items-center justify-center">
              {editingPersona ? <Pencil className="w-4 h-4 text-accent" /> : <Plus className="w-4 h-4 text-accent" />}
            </div>
            <h2 className="font-display font-bold text-base text-primary">
              {editingPersona ? 'تعديل الشخصية' : 'إضافة شخصية جديدة'}
            </h2>
          </div>
          <button onClick={onClose} className="text-muted hover:text-primary transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-secondary mb-2">اسم الشخصية</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="مثال: المحلل التقني"
              className="w-full bg-elevated rounded-xl px-4 py-3 text-sm text-primary placeholder:text-muted border border-default outline-none focus:border-accent/40 transition-colors"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-secondary mb-2">النبرة الصوتية (Tone)</label>
            <input
              type="text"
              value={form.tone}
              onChange={(e) => setForm({ ...form, tone: e.target.value })}
              placeholder="مثال: احترافي وودود"
              className="w-full bg-elevated rounded-xl px-4 py-3 text-sm text-primary placeholder:text-muted border border-default outline-none focus:border-accent/40 transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-secondary mb-2">المنصة المستهدفة</label>
            <select
              value={form.platform}
              onChange={(e) => setForm({ ...form, platform: e.target.value })}
              className="w-full bg-elevated rounded-xl px-4 py-3 text-sm text-primary border border-default outline-none focus:border-accent/40 transition-colors"
            >
              {platformOptions.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-secondary mb-2">
              الأوامر الأساسية (System Prompt)
            </label>
            <textarea
              value={form.systemPrompt}
              onChange={(e) => setForm({ ...form, systemPrompt: e.target.value })}
              placeholder="اكتب تعليمات الشخصية الأساسية: دورها، أسلوبها، جمهورها..."
              rows={5}
              className="w-full bg-elevated rounded-xl px-4 py-3 text-sm text-primary placeholder:text-muted border border-default outline-none focus:border-accent/40 transition-colors resize-none leading-relaxed"
            />
          </div>

          <div className="flex items-center gap-3 pt-2">
            <button
              type="submit"
              className="flex items-center gap-2 bg-accent text-white px-6 py-3 rounded-xl text-sm font-medium hover:opacity-90 transition-opacity glow-accent"
            >
              <Sparkles className="w-4 h-4" />
              <span>{editingPersona ? 'حفظ التعديلات' : 'إنشاء الشخصية'}</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex items-center gap-2 bg-elevated text-secondary px-6 py-3 rounded-xl text-sm font-medium border border-default hover:text-primary transition-colors"
            >
              <span>إلغاء</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function TestInteractionModal({
  persona,
  onClose,
}: {
  persona: Persona | null;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  if (!persona) return null;

  const handleSend = () => {
    const text = input.trim();
    if (!text) return;

    setMessages((prev) => [...prev, { role: 'user', text }]);
    setInput('');
    setIsTyping(true);

    setTimeout(() => {
      const responses = [
        `بصفتي "${persona.name}"، أرى أن سؤالك يلامس جوهر دوري. ${persona.tone} — وهذا ما يجعلني أجيبك بأن: الأمر يتطلب نظرة أعمق تتجاوز السطح.`,
        `سؤال ممتاز! بأسلوبي ${persona.tone}، أقول لك: الفكرة التي تطرحها تستحق التأمل. دعني أحللها من زاوية جمهوري على ${persona.platforms[0]}.`,
        `كممثل لشخصية "${persona.name}"، أتفاعل مع رسالتك بنبرة ${persona.tone}. النقطة المحورية هنا هي التوازن بين الأصالة والجاذبية.`,
      ];
      const response = responses[Math.floor(Math.random() * responses.length)];
      setMessages((prev) => [...prev, { role: 'persona', text: response }]);
      setIsTyping(false);
    }, 1200);
  };

  const handleClose = () => {
    setMessages([]);
    setInput('');
    setIsTyping(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={handleClose} />
      <div className="relative w-full max-w-lg bg-card rounded-2xl border border-default shadow-2xl animate-fade-up flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between p-5 border-b border-default">
          <div className="flex items-center gap-3">
            <img
              src={persona.image}
              alt={persona.name}
              className="w-10 h-10 rounded-xl object-cover"
            />
            <div>
              <h2 className="font-display font-bold text-sm text-primary">{persona.name}</h2>
              <p className="text-xs text-muted">اختبار التفاعل المباشر</p>
            </div>
          </div>
          <button onClick={handleClose} className="text-muted hover:text-primary transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-3 min-h-[250px]">
          {messages.length === 0 && (
            <div className="text-center py-10">
              <FlaskConical className="w-10 h-10 text-accent mx-auto mb-3 opacity-50" />
              <p className="text-sm text-secondary mb-1">جرّب التفاعل مع {persona.name}</p>
              <p className="text-xs text-muted">أرسل رسالة لاختبار نبرة الشخصية وأسلوبها</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-start' : 'justify-end'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-elevated text-primary rounded-bl-md'
                    : 'bg-accent-dim text-primary rounded-br-md border border-accent/20'
                }`}
              >
                {msg.text}
              </div>
            </div>
          ))}
          {isTyping && (
            <div className="flex justify-end">
              <div className="bg-accent-dim rounded-2xl rounded-br-md px-4 py-3 flex items-center gap-1.5">
                <Loader2 className="w-3.5 h-3.5 text-accent animate-spin" />
                <span className="text-xs text-muted">يكتب...</span>
              </div>
            </div>
          )}
        </div>

        <div className="p-4 border-t border-default flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="اكتب رسالة للاختبار..."
            className="flex-1 bg-elevated rounded-xl px-4 py-2.5 text-sm text-primary placeholder:text-muted border border-default outline-none focus:border-accent/40 transition-colors"
            autoFocus
          />
          <button
            onClick={handleSend}
            className="flex items-center justify-center w-10 h-10 rounded-xl bg-accent text-white hover:opacity-90 transition-opacity flex-shrink-0"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export function PersonasView() {
  const [personaList, setPersonaList] = useState<Persona[]>(personas);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingPersona, setEditingPersona] = useState<Persona | null>(null);
  const [testPersona, setTestPersona] = useState<Persona | null>(null);

  const handleAddClick = () => {
    setEditingPersona(null);
    setModalOpen(true);
  };

  const handleEdit = (p: Persona) => {
    setEditingPersona(p);
    setModalOpen(true);
  };

  const handleTogglePause = (id: string) => {
    setPersonaList((prev) =>
      prev.map((p) =>
        p.id === id ? { ...p, status: p.status === 'active' ? 'paused' : 'active' } : p
      )
    );
  };

  const handleSubmit = (data: PersonaFormData) => {
    if (editingPersona) {
      setPersonaList((prev) =>
        prev.map((p) =>
          p.id === editingPersona.id
            ? {
                ...p,
                name: data.name,
                tone: data.tone,
                systemPrompt: data.systemPrompt,
                platforms: [data.platform, ...p.platforms.slice(1)],
              }
            : p
        )
      );
    } else {
      const newPersona: Persona = {
        id: `p${Date.now()}`,
        name: data.name,
        role: 'وكيل ذكي جديد',
        image: `https://api.dicebear.com/7.x/initials/svg?seed=${encodeURIComponent(data.name)}&backgroundColor=00d9a3`,
        platforms: [data.platform],
        status: 'active',
        tone: data.tone || 'مرن',
        systemPrompt: data.systemPrompt,
        contentCount: 0,
        engagement: 0,
      };
      setPersonaList((prev) => [...prev, newPersona]);
    }
  };

  const activeCount = personaList.filter((p) => p.status === 'active').length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <p className="text-sm text-secondary">
            إدارة شخصيات الوكلاء الذكيين — أنشئ، خصّص، واختبر شخصيات الذكاء الاصطناعي
          </p>
          <p className="text-xs text-muted mt-1">
            {personaList.length} شخصية إجمالاً — {activeCount} نشطة
          </p>
        </div>
        <button
          onClick={handleAddClick}
          className="flex items-center gap-2 bg-accent text-white px-5 py-2.5 rounded-xl text-sm font-medium hover:opacity-90 transition-opacity glow-accent"
        >
          <Plus className="w-4 h-4" />
          <span>إضافة شخصية جديدة</span>
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
        {personaList.map((p) => (
          <PersonaCard
            key={p.id}
            persona={p}
            onEdit={handleEdit}
            onTogglePause={handleTogglePause}
            onTest={setTestPersona}
          />
        ))}
      </div>

      <AddPersonaModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleSubmit}
        editingPersona={editingPersona}
      />

      <TestInteractionModal persona={testPersona} onClose={() => setTestPersona(null)} />
    </div>
  );
}
