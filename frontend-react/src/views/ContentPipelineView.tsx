import { useState } from 'react';
import { useApp } from '@/context/AppContext';
import type { Script, PipelineStage } from '@/types';
import { speakArabic, stopSpeaking } from '@/utils/speech';
import {
  Plus,
  Volume2,
  VolumeX,
  CheckCircle2,
  ArrowRight,
  FileText,
  ShieldCheck,
} from 'lucide-react';

const PIPELINE_STAGES: { key: PipelineStage; label: string; desc: string }[] = [
  { key: 'IDEA', label: 'الفكرة', desc: 'رصد الفكرة' },
  { key: 'RESEARCH', label: 'البحث', desc: 'توثيق المعلومات' },
  { key: 'SCRIPT', label: 'السيناريو', desc: 'صياغة النص' },
  { key: 'REVIEW', label: 'المراجعة', desc: 'مراجعة الأسلوب' },
  { key: 'STORYBOARD', label: 'الستوريبورد', desc: 'تخطيط المشاهد' },
  { key: 'PRODUCTION', label: 'الإنتاج', desc: 'التوليد والتصوير' },
  { key: 'EDITING', label: 'المونتاج', desc: 'المعالجة والميكساج' },
  { key: 'QUALITY_CHECK', label: 'بوابة الجودة', desc: 'الفحص النهائي' },
  { key: 'APPROVAL', label: 'الموافقة', desc: 'اعتماد المالك' },
  { key: 'PUBLISHING', label: 'النشر', desc: 'البث للمنصات' },
  { key: 'ANALYTICS', label: 'التحليلات', desc: 'قياس التفاعل' },
  { key: 'ARCHIVED', label: 'الأرشيف', desc: 'الذاكرة الدائمة' },
];

export function ContentPipelineView() {
  const { scripts, characters, updateScript, addScript } = useApp();

  const [selectedScript, setSelectedScript] = useState<Script | null>(scripts[0] || null);
  const [isSpeakingScript, setIsSpeakingScript] = useState(false);
  const [showNewModal, setShowNewModal] = useState(false);

  // New Script Form
  const [newTitle, setNewTitle] = useState('');
  const [newCharId, setNewCharId] = useState(characters[0]?.id || '');
  const [newPlatform, setNewPlatform] = useState('YouTube Shorts & TikTok');
  const [newHook, setNewHook] = useState('');
  const [newBody, setNewBody] = useState('');
  const [newCta, setNewCta] = useState('');

  const handlePlayScript = (script: Script) => {
    if (isSpeakingScript) {
      stopSpeaking();
      setIsSpeakingScript(false);
      return;
    }

    const fullText = `${script.hook} ... ${script.body} ... ${script.cta}`;
    const char = characters.find((c) => c.id === script.characterId);

    setIsSpeakingScript(true);
    speakArabic(fullText, {
      pitch: char?.bible.voice.pitch || 1.0,
      rate: char?.bible.voice.rate || 1.0,
      voiceGender: char?.bible.voice.gender || 'male',
      onEnd: () => setIsSpeakingScript(false),
      onError: () => setIsSpeakingScript(false),
    });
  };

  const handleAdvanceStage = (script: Script) => {
    const currentIndex = PIPELINE_STAGES.findIndex((s) => s.key === script.stage);
    if (currentIndex < PIPELINE_STAGES.length - 1) {
      const nextStage = PIPELINE_STAGES[currentIndex + 1].key;
      const updated = { ...script, stage: nextStage, updatedAt: 'الآن' };
      updateScript(updated);
      setSelectedScript(updated);
    }
  };

  const handleToggleGate = (criterion: keyof Script['qualityGate']) => {
    if (!selectedScript) return;
    const updated: Script = {
      ...selectedScript,
      qualityGate: {
        ...selectedScript.qualityGate,
        [criterion]: !selectedScript.qualityGate[criterion],
      },
    };
    updateScript(updated);
    setSelectedScript(updated);
  };

  const handleCreateScript = (e: React.FormEvent) => {
    e.preventDefault();
    const char = characters.find((c) => c.id === newCharId) || characters[0];
    const created: Script = {
      id: 'sc-' + Date.now(),
      title: newTitle || 'سكريبت جديد',
      characterId: char.id,
      characterName: char.name,
      platform: newPlatform,
      stage: 'SCRIPT',
      wordCount: (newHook.length + newBody.length + newCta.length) / 5 || 250,
      updatedAt: 'الآن',
      hook: newHook || 'خطاف جذب الانتباه...',
      body: newBody || 'المحتوى الرئيسي...',
      cta: newCta || 'دعوة لاتخاذ إجراء...',
      targetDuration: '60 ثانية',
      qualityGate: {
        languageChecked: true,
        factChecked: false,
        rightsVerified: true,
        audioQualityVerified: false,
        visualConsistencyVerified: true,
        technicalSpecsPassed: false,
      },
    };
    addScript(created);
    setSelectedScript(created);
    setShowNewModal(false);
  };

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header Banner */}
      <div className="card p-6 bg-gradient-to-l from-[var(--bg-card)] to-[var(--bg-elevated)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-accent/20 text-accent font-bold">
              القسم 7 — مسار الإنتاج السينمائي وبوابة الجودة
            </span>
            <span className="text-xs text-muted">12 مرحلة منضبطة</span>
          </div>
          <h1 className="font-display font-bold text-2xl text-primary mt-1">
            استوديو المحتوى والإنتاج وبوابة الجودة (Quality Gate)
          </h1>
          <p className="text-sm text-secondary">
            متابعة مراحل الإنتاج، فحص السكريبتات بالصوت العربي، وتطبيق معايير القبول الصارمة قبل النشر.
          </p>
        </div>

        <button
          onClick={() => setShowNewModal(true)}
          className="px-4 py-2.5 rounded-xl bg-accent text-white text-xs font-bold hover:opacity-90 transition-opacity flex items-center gap-2 self-start md:self-auto shadow glow-accent"
        >
          <Plus className="w-4 h-4" />
          <span>إنشاء سكريبت جديد</span>
        </button>
      </div>

      {/* 12-Stage Pipeline Visualizer */}
      <div className="card p-4 overflow-x-auto">
        <h4 className="text-xs font-bold text-muted mb-3 px-2">مسار الإنتاج المعتمد (12 مرحلة):</h4>
        <div className="flex items-center gap-2 min-w-[900px] px-2">
          {PIPELINE_STAGES.map((stg, idx) => {
            const isSelectedStage = selectedScript?.stage === stg.key;
            const isPast =
              selectedScript &&
              PIPELINE_STAGES.findIndex((s) => s.key === selectedScript.stage) > idx;

            return (
              <div key={stg.key} className="flex-1 flex items-center">
                <div
                  className={`flex-1 p-2.5 rounded-xl border text-center transition-all ${
                    isSelectedStage
                      ? 'bg-accent text-white border-accent shadow-md'
                      : isPast
                      ? 'bg-accent/15 border-accent/30 text-accent'
                      : 'bg-elevated border-default text-muted'
                  }`}
                >
                  <span className="text-[10px] block font-mono font-bold opacity-80">
                    {idx + 1}
                  </span>
                  <span className="text-xs font-bold block truncate">{stg.label}</span>
                </div>
                {idx < PIPELINE_STAGES.length - 1 && (
                  <span className="mx-1 text-muted text-xs">←</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Scripts List (Left Column) */}
        <div className="space-y-3">
          <div className="flex items-center justify-between px-1">
            <h3 className="font-display font-bold text-sm text-primary flex items-center gap-1.5">
              <FileText className="w-4 h-4 text-accent" />
              السكريبتات المسجلة ({scripts.length})
            </h3>
          </div>

          <div className="space-y-2.5 max-h-[640px] overflow-y-auto">
            {scripts.map((sc) => {
              const isSelected = selectedScript?.id === sc.id;
              return (
                <div
                  key={sc.id}
                  onClick={() => setSelectedScript(sc)}
                  className={`card p-4 cursor-pointer transition-all border ${
                    isSelected
                      ? 'border-accent bg-accent/5'
                      : 'hover:border-accent/40 bg-[var(--bg-card)]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <h4 className="text-xs font-bold text-primary truncate leading-snug">
                      {sc.title}
                    </h4>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-elevated border border-default text-accent whitespace-nowrap">
                      {sc.stage}
                    </span>
                  </div>

                  <p className="text-[11px] text-secondary line-clamp-2 mb-3">
                    {sc.hook}
                  </p>

                  <div className="flex items-center justify-between text-[10px] text-muted pt-2 border-t border-default/50">
                    <span className="font-medium text-accent">{sc.characterName}</span>
                    <span>{sc.updatedAt}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Selected Script Detail & Quality Gate (Right Column) */}
        {selectedScript && (
          <div className="lg:col-span-2 space-y-5">
            {/* Script Viewer Card */}
            <div className="card p-6 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-default">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs px-2.5 py-0.5 rounded-full bg-accent/20 text-accent font-bold">
                      شخصية: {selectedScript.characterName}
                    </span>
                    <span className="text-xs text-muted">منصة: {selectedScript.platform}</span>
                  </div>
                  <h2 className="font-display font-bold text-lg text-primary">
                    {selectedScript.title}
                  </h2>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handlePlayScript(selectedScript)}
                    className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shadow ${
                      isSpeakingScript
                        ? 'bg-red-500 text-white animate-pulse'
                        : 'bg-accent/20 text-accent hover:bg-accent/30'
                    }`}
                  >
                    {isSpeakingScript ? (
                      <>
                        <VolumeX className="w-4 h-4" />
                        <span>إيقاف القراءة</span>
                      </>
                    ) : (
                      <>
                        <Volume2 className="w-4 h-4" />
                        <span>قراءة السكريبت بالصوت</span>
                      </>
                    )}
                  </button>

                  <button
                    onClick={() => handleAdvanceStage(selectedScript)}
                    className="px-3.5 py-2 rounded-xl bg-accent text-white text-xs font-bold hover:opacity-90 transition-opacity flex items-center gap-1.5 shadow"
                  >
                    <span>الترقية للمرحلة التالية</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Hook */}
              <div>
                <span className="text-xs font-bold text-accent block mb-1">
                  1. خطاف الانتباه الأول (Hook — أول 3 ثوانٍ):
                </span>
                <div className="p-3.5 rounded-xl bg-elevated border border-default text-xs text-primary leading-relaxed">
                  {selectedScript.hook}
                </div>
              </div>

              {/* Body */}
              <div>
                <span className="text-xs font-bold text-info block mb-1">
                  2. المحتوى والقصة (Body & Value):
                </span>
                <div className="p-3.5 rounded-xl bg-elevated border border-default text-xs text-primary leading-relaxed whitespace-pre-wrap">
                  {selectedScript.body}
                </div>
              </div>

              {/* CTA */}
              <div>
                <span className="text-xs font-bold text-warning block mb-1">
                  3. الخاتمة والدعوة لاتخاذ إجراء (Call to Action):
                </span>
                <div className="p-3.5 rounded-xl bg-elevated border border-default text-xs text-primary leading-relaxed">
                  {selectedScript.cta}
                </div>
              </div>
            </div>

            {/* Quality Gate Checklist Card */}
            <div className="card p-6 border border-emerald-500/20 bg-emerald-500/5 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-default">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-accent" />
                  <h3 className="font-display font-bold text-base text-primary">
                    بوابة الجودة والاعتماد (Quality Gate Checklist)
                  </h3>
                </div>
                <span className="text-xs text-secondary">
                  فحص إلزامي قبل طلب اعتماد المالك
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[
                  {
                    key: 'languageChecked' as const,
                    label: 'سلامة النص واللغة والنبرة',
                    desc: 'مطابقة نبرة Character Bible وخلوه من الركاكة',
                  },
                  {
                    key: 'factChecked' as const,
                    label: 'تدقيق وصحة المعلومات',
                    desc: 'التحقق العلمي والعملي للأرقام والمعلومات',
                  },
                  {
                    key: 'rightsVerified' as const,
                    label: 'حقوق الملكية الفكرية',
                    desc: 'خلو المحتوى والأصول من أي انتهاكات ترخيص',
                  },
                  {
                    key: 'audioQualityVerified' as const,
                    label: 'فحص النطق ومخارج الحروف',
                    desc: 'سلامة التشكيل والإيقاع الصوتي العربي',
                  },
                  {
                    key: 'visualConsistencyVerified' as const,
                    label: 'الاتساق البصري للشخصية',
                    desc: 'المحافظة على الملامح والملابس المعتمدة',
                  },
                  {
                    key: 'technicalSpecsPassed' as const,
                    label: 'المطابقة الفنية للمنصة',
                    desc: 'الأبعاد (9:16 / 16:9) ومعدل البت ومواصفات الفيديو',
                  },
                ].map((item) => {
                  const isChecked = selectedScript.qualityGate[item.key];
                  return (
                    <div
                      key={item.key}
                      onClick={() => handleToggleGate(item.key)}
                      className={`p-3 rounded-xl border cursor-pointer transition-all flex items-start gap-3 ${
                        isChecked
                          ? 'bg-accent/10 border-accent/40 text-primary'
                          : 'bg-elevated border-default text-muted hover:border-accent/20'
                      }`}
                    >
                      <div
                        className={`w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5 ${
                          isChecked ? 'bg-accent text-white' : 'border border-default'
                        }`}
                      >
                        {isChecked && <CheckCircle2 className="w-4 h-4" />}
                      </div>
                      <div>
                        <span className="text-xs font-bold block">{item.label}</span>
                        <span className="text-[10px] text-muted">{item.desc}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* New Script Modal */}
      {showNewModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <form
            onSubmit={handleCreateScript}
            className="card p-6 max-w-lg w-full animate-fade-up space-y-4 max-h-[90vh] overflow-y-auto"
          >
            <div className="flex items-center justify-between pb-3 border-b border-default">
              <h3 className="font-bold text-base text-primary">إنشاء سكريبت جديد</h3>
              <button
                type="button"
                onClick={() => setShowNewModal(false)}
                className="text-muted hover:text-primary font-bold px-2"
              >
                ✕
              </button>
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">عنوان السكريبت:</label>
              <input
                type="text"
                required
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="مثال: سر الصيانة السحرية مع عم حسن..."
                className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted block mb-1">الشخصية المستهدفة:</label>
                <select
                  value={newCharId}
                  onChange={(e) => setNewCharId(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
                >
                  {characters.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs text-muted block mb-1">المنصة:</label>
                <input
                  type="text"
                  value={newPlatform}
                  onChange={(e) => setNewPlatform(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
                />
              </div>
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">1. الخطاف (Hook):</label>
              <textarea
                rows={2}
                value={newHook}
                onChange={(e) => setNewHook(e.target.value)}
                placeholder="جملة قوية تشد الانتباه في أول 3 ثوانٍ..."
                className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
              />
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">2. المحتوى (Body):</label>
              <textarea
                rows={4}
                value={newBody}
                onChange={(e) => setNewBody(e.target.value)}
                placeholder="القصة، الشرح، أو القيمة المعرفية..."
                className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
              />
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">3. الدعوة للعمل (CTA):</label>
              <input
                type="text"
                value={newCta}
                onChange={(e) => setNewCta(e.target.value)}
                placeholder="سؤال للجمهور أو دعوة للمتابعة..."
                className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowNewModal(false)}
                className="px-4 py-2 rounded-xl bg-elevated text-xs font-bold text-muted hover:text-primary"
              >
                إلغاء
              </button>
              <button
                type="submit"
                className="px-5 py-2 rounded-xl bg-accent text-white text-xs font-bold hover:opacity-90"
              >
                حفظ السكريبت
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
