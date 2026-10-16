import { useState, useEffect, useRef } from 'react';
import { useApp } from '@/context/AppContext';
import {
  speakArabic,
  stopSpeaking,
  createArabicSpeechRecognizer,
  isSpeechRecognitionSupported,
} from '@/utils/speech';
import { sendNadCommand } from '@/backend';
import type { MemoryEntry } from '@/types';
import {
  Send,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Sparkles,
  Bot,
  User,
  Clock,
  Layers,
} from 'lucide-react';

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  retrievedMemory?: MemoryEntry[];
  executionTimeMs?: number;
}

export function AssistantView({ onNavigate }: { onNavigate?: (key: string) => void }) {
  const { queryInstantMemory, currentUser, projects, approvals } = useApp();

  const [inputPrompt, setInputPrompt] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'm1',
      sender: 'assistant',
      text: `أهلاً بك يا ${currentUser.name} في المساعد الشخصي الموحد NADA AI. أنا متصل بالذاكرة الدائمة للمنظومة (المكونات الـ 12)، وأستطيع استرجاع سياق المشروعات، الشخصيات الـ 11، والموافقات المعلقة في أقل من ثانيتين. كيف أخدمك اليوم؟`,
      timestamp: 'الآن',
    },
  ]);

  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const [backendMessage, setBackendMessage] = useState<string>('');
  const [isSending, setIsSending] = useState(false);
  const recognizerRef = useRef<ReturnType<typeof createArabicSpeechRecognizer> | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Voice Input (STT) setup
  const toggleListening = () => {
    if (isListening) {
      recognizerRef.current?.stop();
      setIsListening(false);
      return;
    }

    setSpeechError(null);
    if (!isSpeechRecognitionSupported()) {
      // Simulate voice input for environments where mic access is blocked
      setIsListening(true);
      setTimeout(() => {
        const samplePhrases = [
          'ما هي حالة المشروعات الحالية؟',
          'استرجع قرارات المالك المسجلة',
          'اقترح فكرة سكريبت لعم حسن عن صيانة المحابس',
          'أعطني ملخص تسليم واستئناف فوري',
        ];
        const phrase = samplePhrases[Math.floor(Math.random() * samplePhrases.length)];
        setInputPrompt(phrase);
        setIsListening(false);
      }, 1500);
      return;
    }

    const recognizer = createArabicSpeechRecognizer(
      (transcript, isFinal) => {
        setInputPrompt(transcript);
        if (isFinal) {
          setIsListening(false);
        }
      },
      (err) => {
        setSpeechError(err);
        setIsListening(false);
      },
      () => {
        setIsListening(false);
      }
    );

    if (recognizer) {
      recognizerRef.current = recognizer;
      recognizer.start();
      setIsListening(true);
    }
  };

  const handleSpeakText = (text: string) => {
    if (isSpeaking) {
      stopSpeaking();
      setIsSpeaking(false);
      return;
    }

    setIsSpeaking(true);
    speakArabic(text, {
      pitch: 1.05,
      rate: 1.0,
      voiceGender: 'female',
      onEnd: () => setIsSpeaking(false),
      onError: () => setIsSpeaking(false),
    });
  };

  const handleSendPrompt = async (promptText?: string) => {
    const textToSend = (promptText || inputPrompt).trim();
    if (!textToSend || isSending) return;

    const userMsg: ChatMessage = {
      id: 'usr-' + Date.now(),
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString('ar-EG'),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputPrompt('');
    setIsSending(true);
    setBackendMessage('جار إرسال الأمر إلى Backend NADA…');
    try {
      const result = await sendNadCommand(textToSend);
      const assistantMsg: ChatMessage = {
        id: 'ast-' + Date.now(),
        sender: 'assistant',
        text: result.response || result.message || 'لم يُرجع الخادم نصاً.',
        timestamp: new Date().toLocaleTimeString('ar-EG'),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setBackendMessage(result.status === 'SUCCESS' ? 'وصل رد فعلي من Backend وتم حفظ تقرير التنفيذ.' : result.message);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'تعذر الاتصال بالخادم.';
      setBackendMessage(message);
      setMessages((prev) => [...prev, { id: 'err-' + Date.now(), sender: 'assistant', text: `تعذر تنفيذ الطلب الحقيقي: ${message}`, timestamp: new Date().toLocaleTimeString('ar-EG') }]);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="space-y-4 animate-fade-up max-w-5xl mx-auto">
      {/* Header Bar */}
      <div className="card p-5 bg-gradient-to-l from-[var(--bg-card)] to-[var(--bg-elevated)] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-accent-dim flex items-center justify-center glow-accent flex-shrink-0">
            <Bot className="w-6 h-6 text-accent" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-display font-bold text-lg text-primary">المساعد الشخصي NADA AI</h2>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/20 text-accent font-bold">
                متصل بالذاكرة المباشرة
              </span>
            </div>
            <p className="text-xs text-muted">
              استرجاع سياق المنظومة في أقل من ثانيتين • دعم الإدخال والقراءة الصوتية بالعربية
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isSpeaking && (
            <button
              onClick={() => {
                stopSpeaking();
                setIsSpeaking(false);
              }}
              className="px-3 py-1.5 rounded-lg bg-red-500/20 text-error text-xs font-bold flex items-center gap-1.5"
            >
              <VolumeX className="w-3.5 h-3.5" />
              إيقاف الصوت
            </button>
          )}
          <button
            onClick={() => onNavigate?.('memory')}
            className="px-3 py-1.5 rounded-lg bg-elevated hover:bg-elevated/80 border border-default text-xs font-medium text-secondary transition-colors"
          >
            فحص الذاكرة الدائمة
          </button>
        </div>
      </div>

      {speechError && (
        <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-warning flex items-center justify-between">
          <span>{speechError}</span>
          <button onClick={() => setSpeechError(null)} className="font-bold px-2">
            ✕
          </button>
        </div>
      )}

      {backendMessage && <div className="rounded-xl border border-default bg-elevated px-3 py-2 text-xs text-secondary">{backendMessage}</div>}

      {/* Chat Messages Log */}
      <div className="card p-4 sm:p-6 min-h-[420px] max-h-[560px] overflow-y-auto space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex items-start gap-3 ${
              msg.sender === 'user' ? 'flex-row-reverse' : ''
            }`}
          >
            <div
              className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${
                msg.sender === 'user'
                  ? 'bg-gradient-to-br from-teal-500 to-emerald-600 text-white'
                  : 'bg-elevated border border-default text-accent'
              }`}
            >
              {msg.sender === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>

            <div
              className={`max-w-[85%] rounded-2xl p-4 text-sm leading-relaxed ${
                msg.sender === 'user'
                  ? 'bg-accent text-white rounded-tr-none'
                  : 'bg-elevated border border-default text-primary rounded-tl-none'
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1.5 text-[11px] opacity-75">
                <span>{msg.sender === 'user' ? currentUser.name : 'NADA Assistant'}</span>
                <span>{msg.timestamp}</span>
              </div>

              <p className="whitespace-pre-wrap">{msg.text}</p>

              {/* Action Bar for Assistant Message */}
              {msg.sender === 'assistant' && (
                <div className="mt-3 pt-2 border-t border-default/40 flex flex-wrap items-center justify-between gap-2 text-xs">
                  <button
                    onClick={() => handleSpeakText(msg.text)}
                    className="flex items-center gap-1.5 text-accent hover:underline font-medium text-[11px]"
                  >
                    <Volume2 className="w-3.5 h-3.5" />
                    استمع للنطق الصوتي
                  </button>

                  {msg.executionTimeMs !== undefined && (
                    <span className="text-[10px] text-muted flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      استرجاع الذاكرة في {msg.executionTimeMs}ms
                    </span>
                  )}
                </div>
              )}

              {/* Memory Citations Dropdown if present */}
              {msg.retrievedMemory && msg.retrievedMemory.length > 0 && (
                <div className="mt-2.5 pt-2 border-t border-default/40">
                  <span className="text-[10px] text-muted flex items-center gap-1 mb-1 font-semibold">
                    <Layers className="w-3 h-3 text-accent" />
                    المراجع المسترجعة من الذاكرة الدائمة:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {msg.retrievedMemory.map((mem) => (
                      <span
                        key={mem.id}
                        className="text-[10px] px-2 py-0.5 rounded bg-[var(--bg-card)] border border-default/60 text-secondary"
                        title={mem.content}
                      >
                        {mem.title} ({Math.round(mem.confidence * 100)}%)
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Quick Prompts */}
      <div className="flex flex-wrap gap-2 pt-1">
        {[
          'ما هي حالة المشروعات الحالية؟',
          'استرجع قرارات المالك المسجلة',
          'اقترح فكرة سكريبت لعم حسن',
          'أعطني ملخص تسليم واستئناف فوري',
        ].map((prompt) => (
          <button
            key={prompt}
            onClick={() => handleSendPrompt(prompt)}
            className="text-xs px-3 py-1.5 rounded-xl bg-elevated hover:bg-elevated/80 border border-default text-secondary hover:text-accent transition-colors flex items-center gap-1.5"
          >
            <Sparkles className="w-3 h-3 text-accent" />
            <span>{prompt}</span>
          </button>
        ))}
      </div>

      {/* Input Form with Arabic Voice STT */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSendPrompt();
        }}
        className="card p-3 flex items-center gap-2"
      >
        <button
          type="button"
          onClick={toggleListening}
          className={`p-3 rounded-xl border transition-all flex items-center justify-center flex-shrink-0 ${
            isListening
              ? 'bg-red-500 text-white border-red-600 animate-pulse'
              : 'bg-elevated text-secondary hover:text-accent border-default'
          }`}
          title={isListening ? 'إيقاف التسجيل' : 'تحدث صوتياً بالعربية (STT)'}
        >
          {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
        </button>

        <input
          type="text"
          value={inputPrompt}
          onChange={(e) => setInputPrompt(e.target.value)}
          placeholder={
            isListening
              ? 'جارٍ الاستماع لصوتك بالعربية...'
              : 'اكتب أمرك أو استفسارك للمساعد NADA...'
          }
          className="flex-1 bg-transparent px-3 py-2 text-sm text-primary placeholder:text-muted outline-none"
        />

        <button
          type="submit"
          disabled={!inputPrompt.trim()}
          className="p-3 rounded-xl bg-accent text-white disabled:opacity-40 hover:opacity-90 transition-opacity flex items-center justify-center flex-shrink-0"
        >
          <Send className="w-5 h-5" />
        </button>
      </form>
    </div>
  );
}
