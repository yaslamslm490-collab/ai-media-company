import { useState } from 'react';
import { useApp } from '@/context/AppContext';
import type { Character } from '@/types';
import { speakArabic, stopSpeaking } from '@/utils/speech';
import {
  Search,
  Volume2,
  VolumeX,
  CheckCircle2,
  XCircle,
  BookOpen,
  Sliders,
  Sparkles,
  FileText,
} from 'lucide-react';

export function CharactersView() {
  const { characters } = useApp();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(null);
  const [isSpeakingId, setIsSpeakingId] = useState<string | null>(null);
  const [filterPlatform, setFilterPlatform] = useState<string>('all');

  const filteredCharacters = characters.filter((c) => {
    const matchesSearch =
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.archetype.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesPlatform =
      filterPlatform === 'all' ||
      c.platforms.some((p) => p.toLowerCase().includes(filterPlatform.toLowerCase()));
    return matchesSearch && matchesPlatform;
  });

  const handlePlayVoice = (char: Character) => {
    if (isSpeakingId === char.id) {
      stopSpeaking();
      setIsSpeakingId(null);
      return;
    }

    setIsSpeakingId(char.id);
    speakArabic(char.bible.voice.samplePhrase, {
      pitch: char.bible.voice.pitch,
      rate: char.bible.voice.rate,
      voiceGender: char.bible.voice.gender,
      onEnd: () => setIsSpeakingId(null),
      onError: () => setIsSpeakingId(null),
    });
  };

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header Banner */}
      <div className="card p-6 bg-gradient-to-l from-[var(--bg-card)] to-[var(--bg-elevated)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-accent/20 text-accent font-bold">
              القسم 6 — CHARACTER SYSTEM
            </span>
            <span className="text-xs text-muted">11 شخصية رسمية معتمدة</span>
          </div>
          <h1 className="font-display font-bold text-2xl text-primary mt-1">
            استوديو الشخصيات الافتراضية وCharacter Bible
          </h1>
          <p className="text-sm text-secondary">
            إدارة الهوية، البصمة الصوتية، قواعد الاستمرارية، وقوالب الإنتاج لجميع شخصيات NADA OS.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-left px-4 py-2 rounded-xl bg-elevated border border-default">
            <span className="text-xs text-muted block">إجمالي المحتوى</span>
            <span className="text-sm font-bold text-primary">
              {characters.reduce((acc, c) => acc + c.contentCount, 0)} فيديو/منشور
            </span>
          </div>
        </div>
      </div>

      {/* Search and Filters Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-muted absolute right-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="بحث بالاسم أو الكود (مثال: عم حسن أو CHAR-001)..."
            className="w-full pl-4 pr-10 py-2.5 rounded-xl bg-elevated border border-default text-sm text-primary placeholder:text-muted outline-none focus:border-accent transition-colors"
          />
        </div>

        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
          {['all', 'YouTube', 'TikTok', 'Instagram', 'Facebook', 'LinkedIn'].map((p) => (
            <button
              key={p}
              onClick={() => setFilterPlatform(p)}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-colors ${
                filterPlatform === p
                  ? 'bg-accent text-white'
                  : 'bg-elevated border border-default text-secondary hover:text-primary'
              }`}
            >
              {p === 'all' ? 'جميع المنصات' : p}
            </button>
          ))}
        </div>
      </div>

      {/* Characters Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {filteredCharacters.map((char) => (
          <div
            key={char.id}
            className="card p-5 hover:border-accent/40 transition-all duration-300 flex flex-col justify-between"
          >
            <div>
              {/* Card Header */}
              <div className="flex items-start justify-between gap-3 mb-4">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${char.avatarColor} flex items-center justify-center text-white font-display font-bold text-lg shadow-md flex-shrink-0`}
                  >
                    {char.name.slice(0, 2)}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-elevated border border-default text-accent">
                        {char.code}
                      </span>
                      <span className="status-dot status-active" />
                    </div>
                    <h3 className="font-display font-bold text-base text-primary truncate mt-0.5">
                      {char.name}
                    </h3>
                    <p className="text-xs text-muted truncate">{char.archetype}</p>
                  </div>
                </div>
              </div>

              {/* Character Details */}
              <div className="space-y-2 text-xs mb-4 p-3 rounded-xl bg-elevated/60 border border-default/50">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-muted flex-shrink-0">النبرة:</span>
                  <span className="text-secondary font-medium text-left">{char.tone}</span>
                </div>
                <div className="flex items-start justify-between gap-2">
                  <span className="text-muted flex-shrink-0">الجمهور:</span>
                  <span className="text-secondary font-medium text-left truncate">{char.audience}</span>
                </div>
              </div>

              {/* Platforms */}
              <div className="flex flex-wrap gap-1.5 mb-4">
                {char.platforms.map((p) => (
                  <span
                    key={p}
                    className="text-[11px] px-2.5 py-0.5 rounded-lg bg-elevated text-secondary border border-default"
                  >
                    {p}
                  </span>
                ))}
              </div>
            </div>

            {/* Bottom Actions & Voice Preview */}
            <div className="pt-3 border-t border-default space-y-3">
              <div className="flex items-center justify-between text-xs text-muted">
                <span>{char.contentCount} محتوى منشور</span>
                <span className="font-bold text-accent">{char.engagement}% تفاعل</span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => handlePlayVoice(char)}
                  className={`flex-1 py-2 px-3 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                    isSpeakingId === char.id
                      ? 'bg-red-500 text-white animate-pulse'
                      : 'bg-accent/15 text-accent hover:bg-accent/25 border border-accent/30'
                  }`}
                  title="استمع للبصمة الصوتية للشخصية"
                >
                  {isSpeakingId === char.id ? (
                    <>
                      <VolumeX className="w-4 h-4" />
                      <span>إيقاف الصوت</span>
                    </>
                  ) : (
                    <>
                      <Volume2 className="w-4 h-4" />
                      <span>سماع بصمة الصوت</span>
                    </>
                  )}
                </button>

                <button
                  onClick={() => {
                    setSelectedCharacter(char);
                  }}
                  className="py-2 px-3 rounded-xl bg-elevated hover:bg-elevated/80 border border-default text-xs font-bold text-primary transition-colors flex items-center gap-1"
                >
                  <BookOpen className="w-4 h-4 text-secondary" />
                  <span>ملف الـ Bible</span>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Character Bible Full Modal */}
      {selectedCharacter && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4 overflow-y-auto">
          <div className="card p-6 max-w-3xl w-full my-8 max-h-[90vh] overflow-y-auto animate-fade-up">
            {/* Modal Header */}
            <div className="flex items-start justify-between pb-4 border-b border-default mb-5">
              <div className="flex items-center gap-3">
                <div
                  className={`w-12 h-12 rounded-xl bg-gradient-to-br ${selectedCharacter.avatarColor} flex items-center justify-center text-white font-bold text-lg`}
                >
                  {selectedCharacter.name.slice(0, 2)}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-accent/20 text-accent">
                      {selectedCharacter.code}
                    </span>
                    <h2 className="font-display font-bold text-xl text-primary">
                      {selectedCharacter.name} — Character Bible
                    </h2>
                  </div>
                  <p className="text-xs text-muted">{selectedCharacter.archetype}</p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => handlePlayVoice(selectedCharacter)}
                  className="px-3 py-1.5 rounded-lg bg-accent/20 text-accent text-xs font-bold hover:bg-accent/30 transition-colors flex items-center gap-1"
                >
                  <Volume2 className="w-3.5 h-3.5" />
                  تشغيل الصوت
                </button>
                <button
                  onClick={() => setSelectedCharacter(null)}
                  className="text-muted hover:text-primary text-base font-bold px-2"
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="space-y-6 text-sm">
              {/* Backstory & Role */}
              <div className="p-4 rounded-xl bg-elevated border border-default">
                <h4 className="font-bold text-primary text-sm mb-2 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-accent" />
                  الهوية والخلفية الدرامية (Backstory)
                </h4>
                <p className="text-xs text-secondary leading-relaxed">
                  {selectedCharacter.bible.identity.backstory}
                </p>
              </div>

              {/* Rules: DO & DON'T */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                  <h4 className="font-bold text-accent text-xs mb-3 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4" />
                    قواعد المحتوى المقبول (DO)
                  </h4>
                  <ul className="space-y-2 text-xs text-secondary">
                    {selectedCharacter.bible.rules.do.map((item, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-accent font-bold">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20">
                  <h4 className="font-bold text-error text-xs mb-3 flex items-center gap-1.5">
                    <XCircle className="w-4 h-4" />
                    المحظورات والخطوط الحمراء (DON'T)
                  </h4>
                  <ul className="space-y-2 text-xs text-secondary">
                    {selectedCharacter.bible.rules.dont.map((item, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-error font-bold">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Voice Signature */}
              <div className="p-4 rounded-xl bg-elevated border border-default">
                <h4 className="font-bold text-primary text-xs mb-2 flex items-center gap-2">
                  <Volume2 className="w-4 h-4 text-info" />
                  البصمة الصوتية (Voice Signature)
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs mb-3">
                  <div>
                    <span className="text-muted block">النوع:</span>
                    <span className="font-bold text-secondary">
                      {selectedCharacter.bible.voice.gender === 'female' ? 'أنثى' : 'ذكر'}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted block">طبقة الصوت (Pitch):</span>
                    <span className="font-bold text-secondary">{selectedCharacter.bible.voice.pitch}</span>
                  </div>
                  <div>
                    <span className="text-muted block">سرعة النطق (Rate):</span>
                    <span className="font-bold text-secondary">{selectedCharacter.bible.voice.rate}</span>
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-[var(--bg-card)] border border-default text-xs">
                  <span className="text-muted block mb-1">الجملة النموذجية:</span>
                  <p className="font-medium text-primary">
                    "{selectedCharacter.bible.voice.samplePhrase}"
                  </p>
                </div>
              </div>

              {/* Visual & Continuity Rules */}
              <div className="p-4 rounded-xl bg-elevated border border-default">
                <h4 className="font-bold text-primary text-xs mb-2 flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-warning" />
                  السمات البصرية وقواعد الاستمرارية (Continuity)
                </h4>
                <div className="space-y-2 text-xs text-secondary">
                  <div>
                    <span className="text-muted block mb-1 font-semibold">المظهر والملابس:</span>
                    <ul className="list-disc list-inside space-y-1">
                      {selectedCharacter.bible.visualTraits.map((t, i) => (
                        <li key={i}>{t}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="pt-2 border-t border-default/50">
                    <span className="text-muted block mb-1 font-semibold">قواعد الاتساق السردي:</span>
                    <ul className="list-disc list-inside space-y-1">
                      {selectedCharacter.bible.continuityRules.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>

              {/* Prompt Templates */}
              <div className="p-4 rounded-xl bg-elevated border border-default">
                <h4 className="font-bold text-primary text-xs mb-2 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-purple-400" />
                  قوالب الأوامر والسكريبتات (Prompt Templates)
                </h4>
                <div className="space-y-2.5">
                  {selectedCharacter.bible.prompts.map((p, idx) => (
                    <div key={idx} className="p-3 rounded-lg bg-[var(--bg-card)] border border-default text-xs">
                      <span className="font-bold text-primary block mb-1">{p.name}</span>
                      <p className="text-secondary leading-relaxed">{p.template}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="mt-6 pt-4 border-t border-default flex items-center justify-end gap-2">
              <button
                onClick={() => setSelectedCharacter(null)}
                className="px-5 py-2.5 rounded-xl bg-elevated text-primary text-xs font-bold hover:bg-elevated/80 transition-colors"
              >
                إغلاق
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
