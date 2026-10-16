// Speech Recognition and Text-to-Speech Utilities for NADA AI Media OS

export interface SpeechOptions {
  pitch?: number;
  rate?: number;
  volume?: number;
  voiceGender?: 'male' | 'female';
  onStart?: () => void;
  onEnd?: () => void;
  onError?: (err: unknown) => void;
}

// Check speech capabilities
export function isSpeechSynthesisSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window;
}

export function isSpeechRecognitionSupported(): boolean {
  if (typeof window === 'undefined') return false;
  const win = window as unknown as { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown };
  return Boolean(win.SpeechRecognition || win.webkitSpeechRecognition);
}

// Get available Arabic voices
export function getArabicVoices(): SpeechSynthesisVoice[] {
  if (!isSpeechSynthesisSupported()) return [];
  const voices = window.speechSynthesis.getVoices();
  const arabic = voices.filter(
    (v) => v.lang.startsWith('ar') || v.name.toLowerCase().includes('arabic') || v.lang.includes('AR')
  );
  return arabic.length > 0 ? arabic : voices;
}

// Synthesize and speak Arabic text
export function speakArabic(text: string, options: SpeechOptions = {}): boolean {
  if (!isSpeechSynthesisSupported()) {
    playFallbackAudioTone(options.pitch || 1.0);
    return false;
  }

  try {
    // Cancel any ongoing speech
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'ar-SA';
    utterance.pitch = options.pitch ?? 1.0;
    utterance.rate = options.rate ?? 1.0;
    utterance.volume = options.volume ?? 1.0;

    const voices = getArabicVoices();
    if (voices.length > 0) {
      if (options.voiceGender === 'female') {
        const femaleVoice = voices.find(
          (v) =>
            v.name.toLowerCase().includes('female') ||
            v.name.toLowerCase().includes('salma') ||
            v.name.toLowerCase().includes('layla') ||
            v.name.toLowerCase().includes('zeina')
        );
        utterance.voice = femaleVoice || voices[0];
      } else {
        const maleVoice = voices.find(
          (v) =>
            v.name.toLowerCase().includes('male') ||
            v.name.toLowerCase().includes('tariq') ||
            v.name.toLowerCase().includes('maged') ||
            v.name.toLowerCase().includes('naif')
        );
        utterance.voice = maleVoice || voices[0];
      }
    }

    if (options.onStart) utterance.onstart = options.onStart;
    if (options.onEnd) utterance.onend = options.onEnd;
    if (options.onError) {
      utterance.onerror = (e) => {
        options.onError?.(e);
        playFallbackAudioTone(options.pitch || 1.0);
      };
    }

    window.speechSynthesis.speak(utterance);
    return true;
  } catch (err) {
    console.warn('Speech synthesis failed, playing tone fallback:', err);
    playFallbackAudioTone(options.pitch || 1.0);
    options.onError?.(err);
    return false;
  }
}

export function stopSpeaking(): void {
  if (isSpeechSynthesisSupported()) {
    window.speechSynthesis.cancel();
  }
}

// Fallback pleasant Web Audio chime if browser voice is muted or missing
export function playFallbackAudioTone(pitch: number = 1.0): void {
  if (typeof window === 'undefined') return;
  try {
    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) return;
    const ctx = new AudioContextClass();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    const baseFreq = 440 * pitch;
    osc.type = 'sine';
    osc.frequency.setValueAtTime(baseFreq, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(baseFreq * 1.5, ctx.currentTime + 0.15);

    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.35);
  } catch {
    // Ignore audio context errors
  }
}

// Arabic Speech Recognition interface
export interface SpeechRecognitionController {
  start: () => void;
  stop: () => void;
  abort: () => void;
}

export function createArabicSpeechRecognizer(
  onResult: (text: string, isFinal: boolean) => void,
  onError: (errorMsg: string) => void,
  onEnd: () => void
): SpeechRecognitionController | null {
  if (typeof window === 'undefined') return null;

  const win = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionInstance;
    webkitSpeechRecognition?: new () => SpeechRecognitionInstance;
  };

  const RecognitionClass = win.SpeechRecognition || win.webkitSpeechRecognition;
  if (!RecognitionClass) return null;

  try {
    const recognizer = new RecognitionClass();
    recognizer.lang = 'ar-SA';
    recognizer.continuous = false;
    recognizer.interimResults = true;

    recognizer.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = '';
      let interimTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const item = event.results[i];
        if (item.isFinal) {
          finalTranscript += item[0].transcript;
        } else {
          interimTranscript += item[0].transcript;
        }
      }

      if (finalTranscript) {
        onResult(finalTranscript, true);
      } else if (interimTranscript) {
        onResult(interimTranscript, false);
      }
    };

    recognizer.onerror = (event: { error: string }) => {
      let msg = 'خطأ في التعرف على الصوت: ' + event.error;
      if (event.error === 'not-allowed') {
        msg = 'تم رفض الإذن للوصول إلى الميكروفون. يرجى تفعيل إذن الميكروفون في المتصفح.';
      } else if (event.error === 'no-speech') {
        msg = 'لم يتم رصد أي صوت. حاول التحدث مجددًا.';
      }
      onError(msg);
    };

    recognizer.onend = () => {
      onEnd();
    };

    return {
      start: () => recognizer.start(),
      stop: () => recognizer.stop(),
      abort: () => recognizer.abort(),
    };
  } catch (err) {
    console.error('Failed to initialize speech recognition:', err);
    return null;
  }
}

// Minimal TS definitions for SpeechRecognition
interface SpeechRecognitionInstance {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: (event: SpeechRecognitionEvent) => void;
  onerror: (event: { error: string }) => void;
  onend: () => void;
}

interface SpeechRecognitionEvent {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: {
      isFinal: boolean;
      0: {
        transcript: string;
      };
    };
  };
}
