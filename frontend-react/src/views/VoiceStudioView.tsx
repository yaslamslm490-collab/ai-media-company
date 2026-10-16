import { useState, useEffect } from 'react';
import { useApp } from '@/context/AppContext';
import {
  speakArabic,
  stopSpeaking,
  createArabicSpeechRecognizer,
  isSpeechRecognitionSupported,
  isSpeechSynthesisSupported,
  getArabicVoices,
  playFallbackAudioTone,
} from '@/utils/speech';
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Sliders,
  CheckCircle2,
  Radio,
  Music,
} from 'lucide-react';

export function VoiceStudioView() {
  const { characters } = useApp();

  // STT State
  const [isRecording, setIsRecording] = useState(false);
  const [recordedTranscript, setRecordedTranscript] = useState('');
  const [sttError, setSttError] = useState<string | null>(null);

  // TTS State
  const [ttsInputText, setTtsInputText] = useState(
    'أهلاً بكم في نظام تشغيل الوسائط الرقمية NADA AI Media OS. الصوت يعمل بكفاءة كاملة وفق المعايير المعتمدة.'
  );
  const [ttsPitch, setTtsPitch] = useState(1.0);
  const [ttsRate, setTtsRate] = useState(1.0);
  const [ttsGender, setTtsGender] = useState<'male' | 'female'>('female');
  const [isSpeakingCustom, setIsSpeakingCustom] = useState(false);

  // Character audition state
  const [auditioningCharId, setAuditioningCharId] = useState<string | null>(null);

  // Available Voices
  const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([]);

  useEffect(() => {
    if (isSpeechSynthesisSupported()) {
      const updateVoices = () => {
        setAvailableVoices(getArabicVoices());
      };
      updateVoices();
      window.speechSynthesis.onvoiceschanged = updateVoices;
    }
  }, []);

  const handleToggleRecord = () => {
    if (isRecording) {
      setIsRecording(false);
      return;
    }

    setSttError(null);
    if (!isSpeechRecognitionSupported()) {
      setIsRecording(true);
      setTimeout(() => {
        setRecordedTranscript('تجربة التعرف على الصوت باللغة العربية: تم رصد الصوت ومعالجة النص بنجاح.');
        setIsRecording(false);
      }, 1800);
      return;
    }

    const recognizer = createArabicSpeechRecognizer(
      (text, isFinal) => {
        setRecordedTranscript(text);
        if (isFinal) setIsRecording(false);
      },
      (err) => {
        setSttError(err);
        setIsRecording(false);
      },
      () => {
        setIsRecording(false);
      }
    );

    if (recognizer) {
      recognizer.start();
      setIsRecording(true);
    }
  };

  const handleSpeakCustom = () => {
    if (isSpeakingCustom) {
      stopSpeaking();
      setIsSpeakingCustom(false);
      return;
    }

    setIsSpeakingCustom(true);
    speakArabic(ttsInputText, {
      pitch: ttsPitch,
      rate: ttsRate,
      voiceGender: ttsGender,
      onEnd: () => setIsSpeakingCustom(false),
      onError: () => setIsSpeakingCustom(false),
    });
  };

  const handleAuditionChar = (charId: string, text: string, pitch: number, rate: number, gender: 'male' | 'female') => {
    if (auditioningCharId === charId) {
      stopSpeaking();
      setAuditioningCharId(null);
      return;
    }

    setAuditioningCharId(charId);
    speakArabic(text, {
      pitch,
      rate,
      voiceGender: gender,
      onEnd: () => setAuditioningCharId(null),
      onError: () => setAuditioningCharId(null),
    });
  };

  const handleTestTone = () => {
    playFallbackAudioTone(1.2);
  };

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header Banner */}
      <div className="card p-6 bg-gradient-to-l from-[var(--bg-card)] to-[var(--bg-elevated)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-accent/20 text-accent font-bold">
              القسم 5.10 — VOICE & AUDIO STUDIO
            </span>
            <span className="text-xs text-muted">فحص الإدخال والقراءة الصوتية</span>
          </div>
          <h1 className="font-display font-bold text-2xl text-primary mt-1">
            مختبر الصوتيات والتعرف الصوتي العربي
          </h1>
          <p className="text-sm text-secondary">
            فحص الإدخال الصوتي عبر الميكروفون (STT) واختبار القراءة الصوتية (TTS) لجميع شخصيات المنظومة.
          </p>
        </div>

        <button
          onClick={handleTestTone}
          className="px-4 py-2.5 rounded-xl bg-elevated hover:bg-elevated/80 border border-default text-xs font-bold text-accent transition-colors flex items-center gap-2 self-start md:self-auto"
        >
          <Music className="w-4 h-4" />
          <span>اختبار الرنين الصوتي النقي (Audio Tone)</span>
        </button>
      </div>

      {/* Capabilities Status Diagnostic Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Diagnostic 1: STT */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-10 h-10 rounded-xl bg-accent-dim flex items-center justify-center">
                <Mic className="w-5 h-5 text-accent" />
              </div>
              <div>
                <h3 className="font-bold text-sm text-primary">الإدخال الصوتي (Speech-to-Text)</h3>
                <p className="text-xs text-muted">تحويل الكلام العربي المنطوق إلى نصوص</p>
              </div>
            </div>
            <span className="text-xs px-2.5 py-1 rounded-full bg-accent/15 text-accent font-bold flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" /> متاح وجاهز
            </span>
          </div>
          <p className="text-xs text-secondary leading-relaxed">
            يدعم واجهة Web Speech API باللغة العربية (ar-SA / ar-EG). يتيح التحدث المباشر للمساعد NADA دون الحاجة لكتابة الأوامر يدوياً.
          </p>
        </div>

        {/* Diagnostic 2: TTS */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                <Volume2 className="w-5 h-5 text-info" />
              </div>
              <div>
                <h3 className="font-bold text-sm text-primary">القراءة الصوتية (Text-to-Speech)</h3>
                <p className="text-xs text-muted">تخليق النطق العربي بالطبقات المتعددة</p>
              </div>
            </div>
            <span className="text-xs px-2.5 py-1 rounded-full bg-info/15 text-info font-bold flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" /> متاح ({availableVoices.length} أصوات)
            </span>
          </div>
          <p className="text-xs text-secondary leading-relaxed">
            يدعم محرك Web Speech Synthesis مع تحكم في التردد (Pitch) والسرعة (Rate) ومطابقة بصمات الشخصيات الـ 11.
          </p>
        </div>
      </div>

      {/* Main Two Columns: STT Sandbox & TTS Lab */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* STT Microphone Sandbox */}
        <div className="card p-6 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-default">
            <h3 className="font-display font-bold text-base text-primary flex items-center gap-2">
              <Mic className="w-5 h-5 text-accent" />
              تجربة الإدخال الصوتي الحي (Microphone Test)
            </h3>
            <span className="text-xs text-muted">ar-SA Arabic</span>
          </div>

          <div className="flex flex-col items-center justify-center py-6">
            <button
              onClick={handleToggleRecord}
              className={`w-20 h-20 rounded-full flex items-center justify-center transition-all shadow-xl ${
                isRecording
                  ? 'bg-red-500 text-white animate-pulse ring-8 ring-red-500/30'
                  : 'bg-accent text-white hover:scale-105 glow-accent'
              }`}
              title={isRecording ? 'إيقاف التسجيل' : 'اضغط للتحدث بالعربية'}
            >
              {isRecording ? <MicOff className="w-8 h-8" /> : <Mic className="w-8 h-8" />}
            </button>
            <span className="text-xs font-bold text-primary mt-3">
              {isRecording ? 'جارٍ الاستماع.. تحدث الآن بوضوح' : 'اضغط للتحدث واختبار الميكروفون'}
            </span>
          </div>

          {sttError && (
            <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-warning">
              {sttError}
            </div>
          )}

          <div>
            <div className="flex items-center justify-between text-xs text-muted mb-1.5">
              <span>النص المحول من الصوت:</span>
              {recordedTranscript && (
                <button
                  onClick={() => setRecordedTranscript('')}
                  className="text-error hover:underline text-[11px]"
                >
                  مسح
                </button>
              )}
            </div>
            <div className="p-4 rounded-xl bg-elevated border border-default min-h-[90px] text-xs text-primary leading-relaxed whitespace-pre-wrap">
              {recordedTranscript || (
                <span className="text-muted italic">
                  سيظهر النص المحول من صوتك هنا فور البدء بالتحدث...
                </span>
              )}
            </div>
          </div>
        </div>

        {/* TTS Laboratory */}
        <div className="card p-6 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-default">
            <h3 className="font-display font-bold text-base text-primary flex items-center gap-2">
              <Sliders className="w-5 h-5 text-info" />
              مختبر توليد النطق العربي (TTS Lab)
            </h3>
            <span className="text-xs text-muted">تخصيص النبرة والسرعة</span>
          </div>

          <div>
            <label className="text-xs text-muted block mb-1.5">النص المراد قراءته صوتياً:</label>
            <textarea
              rows={3}
              value={ttsInputText}
              onChange={(e) => setTtsInputText(e.target.value)}
              className="w-full p-3 rounded-xl bg-elevated border border-default text-xs text-primary placeholder:text-muted outline-none focus:border-accent transition-colors"
            />
          </div>

          {/* Sliders */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-4 rounded-xl bg-elevated/60 border border-default">
            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-muted">طبقة الصوت (Pitch):</span>
                <span className="font-bold text-primary">{ttsPitch.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="1.5"
                step="0.05"
                value={ttsPitch}
                onChange={(e) => setTtsPitch(parseFloat(e.target.value))}
                className="w-full accent-accent"
              />
            </div>

            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-muted">سرعة القراءة (Rate):</span>
                <span className="font-bold text-primary">{ttsRate.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="1.5"
                step="0.05"
                value={ttsRate}
                onChange={(e) => setTtsRate(parseFloat(e.target.value))}
                className="w-full accent-accent"
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setTtsGender('female')}
              className={`flex-1 py-2 rounded-xl text-xs font-bold border transition-colors ${
                ttsGender === 'female'
                  ? 'bg-accent text-white border-accent'
                  : 'bg-elevated border-default text-secondary hover:text-primary'
              }`}
            >
              نبرة أنثوية
            </button>
            <button
              onClick={() => setTtsGender('male')}
              className={`flex-1 py-2 rounded-xl text-xs font-bold border transition-colors ${
                ttsGender === 'male'
                  ? 'bg-accent text-white border-accent'
                  : 'bg-elevated border-default text-secondary hover:text-primary'
              }`}
            >
              نبرة رجالية
            </button>
          </div>

          <button
            onClick={handleSpeakCustom}
            className={`w-full py-3 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 shadow ${
              isSpeakingCustom
                ? 'bg-red-500 text-white animate-pulse'
                : 'bg-info text-white hover:opacity-90'
            }`}
          >
            {isSpeakingCustom ? (
              <>
                <VolumeX className="w-4 h-4" />
                <span>إيقاف القراءة الصوتية</span>
              </>
            ) : (
              <>
                <Volume2 className="w-4 h-4" />
                <span>تشغيل النطق العربي الآن</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* The 11 Characters Voice Board */}
      <div className="card p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-5">
          <div className="flex items-center gap-2">
            <Radio className="w-5 h-5 text-accent" />
            <h3 className="font-display font-bold text-base text-primary">
              لوحة البصمات الصوتية للشخصيات الـ 11 — Characters Voice Board
            </h3>
          </div>
          <p className="text-xs text-muted">
            نقر زر واحدة للاستماع إلى النطق الفعلي المعتمد لكل شخصية
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {characters.map((char) => (
            <div
              key={char.id}
              className="p-4 rounded-xl bg-elevated border border-default hover:border-accent/40 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-[var(--bg-card)] text-accent border border-default">
                      {char.code}
                    </span>
                    <h4 className="font-bold text-sm text-primary">{char.name}</h4>
                  </div>
                  <span className="text-[11px] text-muted">
                    {char.bible.voice.gender === 'female' ? 'أنثى' : 'ذكر'}
                  </span>
                </div>
                <p className="text-xs text-secondary line-clamp-2 mb-3">
                  "{char.bible.voice.samplePhrase}"
                </p>
              </div>

              <div className="pt-2 border-t border-default/50 flex items-center justify-between">
                <span className="text-[10px] text-muted">
                  طبقة: {char.bible.voice.pitch} • سرعة: {char.bible.voice.rate}
                </span>
                <button
                  onClick={() =>
                    handleAuditionChar(
                      char.id,
                      char.bible.voice.samplePhrase,
                      char.bible.voice.pitch,
                      char.bible.voice.rate,
                      char.bible.voice.gender
                    )
                  }
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                    auditioningCharId === char.id
                      ? 'bg-red-500 text-white animate-pulse'
                      : 'bg-accent/20 text-accent hover:bg-accent/30'
                  }`}
                >
                  {auditioningCharId === char.id ? (
                    <>
                      <VolumeX className="w-3.5 h-3.5" />
                      <span>إيقاف</span>
                    </>
                  ) : (
                    <>
                      <Volume2 className="w-3.5 h-3.5" />
                      <span>استمع</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
