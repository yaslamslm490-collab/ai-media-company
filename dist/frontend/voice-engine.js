const ARABIC_LANGUAGE = /^ar(?:[-_].+)?$/i;
const PREFERRED_ARABIC_LOCALES = [
  'ar-SA', 'ar-EG', 'ar-AE', 'ar-MA', 'ar-TN', 'ar-DZ', 'ar-LY', 'ar-IQ',
  'ar-KW', 'ar-QA', 'ar-BH', 'ar-OM', 'ar-YE', 'ar-JO', 'ar-LB', 'ar-SY', 'ar',
];
const SPEECH_CHUNK_LENGTH = 220;

function normalizedLocale(value = '') {
  return String(value).replace('_', '-');
}

export function pickArabicVoice(voices = []) {
  const arabic = voices.filter((voice) => ARABIC_LANGUAGE.test(voice.lang || ''));
  if (!arabic.length) return null;
  return arabic
    .map((voice, index) => {
      const locale = normalizedLocale(voice.lang);
      const preferredIndex = PREFERRED_ARABIC_LOCALES.findIndex((item) => item.toLowerCase() === locale.toLowerCase());
      const languageMatch = preferredIndex >= 0 ? 1000 - preferredIndex * 20 : 400;
      const localBonus = voice.localService ? 12 : 0;
      const defaultBonus = voice.default ? 6 : 0;
      return {voice, score: languageMatch + localBonus + defaultBonus - index / 100};
    })
    .sort((left, right) => right.score - left.score)[0].voice;
}

function splitSpeechText(text, maxLength = SPEECH_CHUNK_LENGTH) {
  const value = String(text || '').trim();
  if (!value) return [];
  const sentences = value.match(/[^.!?؟؛،\n]+[.!?؟؛،]?|\n+/g) || [value];
  const chunks = [];
  let current = '';
  const pushCurrent = () => {
    const chunk = current.trim();
    if (chunk) chunks.push(chunk);
    current = '';
  };
  const appendWords = (sentence) => {
    sentence.split(/\s+/).forEach((word) => {
      if (!word) return;
      const candidate = current ? `${current} ${word}` : word;
      if (candidate.length > maxLength && current) pushCurrent();
      if (word.length > maxLength) {
        for (let index = 0; index < word.length; index += maxLength) {
          const part = word.slice(index, index + maxLength);
          if (part.length === maxLength) chunks.push(part);
          else current = part;
        }
      } else {
        current = current ? `${current} ${word}` : word;
      }
    });
  };
  sentences.forEach((sentence) => {
    const clean = sentence.trim();
    if (!clean) return pushCurrent();
    if ((current ? `${current} ${clean}` : clean).length <= maxLength) {
      current = current ? `${current} ${clean}` : clean;
    } else {
      pushCurrent();
      appendWords(clean);
    }
  });
  pushCurrent();
  return chunks;
}

export class SpeechReader {
  constructor({onState, onError} = {}) {
    this.onState = onState || (() => {});
    this.onError = onError || (() => {});
    this.utterance = null;
    this.state = 'ready';
    this.voice = null;
    this.chunks = [];
    this.chunkIndex = 0;
    this.runId = 0;
    this.paused = false;
    this.refreshVoices = this.refreshVoices.bind(this);
    if (this.supported()) {
      this.refreshVoices();
      window.speechSynthesis.addEventListener?.('voiceschanged', this.refreshVoices);
      if ('onvoiceschanged' in window.speechSynthesis && !window.speechSynthesis.addEventListener) {
        window.speechSynthesis.onvoiceschanged = this.refreshVoices;
      }
    }
  }

  supported() {
    return typeof window !== 'undefined'
      && 'speechSynthesis' in window
      && 'SpeechSynthesisUtterance' in window;
  }

  refreshVoices() {
    if (this.supported()) this.voice = pickArabicVoice(window.speechSynthesis.getVoices());
    return this.voice;
  }

  setState(next) {
    this.state = next;
    this.onState(next);
  }

  speak(text) {
    if (!this.supported()) throw new Error('القراءة الصوتية غير مدعومة في هذا المتصفح أو الجهاز.');
    const value = String(text || '').trim();
    if (!value) throw new Error('اكتب نصاً في مربع الكتابة أولاً.');
    this.stop(false);
    this.refreshVoices();
    this.chunks = splitSpeechText(value);
    this.chunkIndex = 0;
    this.paused = false;
    const runId = ++this.runId;
    this.setState('playing');
    this.speakNext(runId);
  }

  speakNext(runId) {
    if (this.paused) return;
    if (runId !== this.runId || !this.chunks.length || this.chunkIndex >= this.chunks.length) {
      if (runId === this.runId) this.finish();
      return;
    }
    const utterance = new SpeechSynthesisUtterance(this.chunks[this.chunkIndex]);
    utterance.lang = this.voice?.lang || 'ar-SA';
    utterance.rate = 1;
    utterance.pitch = 1;
    if (this.voice) utterance.voice = this.voice;
    this.utterance = utterance;
    utterance.onstart = () => {
      if (runId === this.runId) this.setState('playing');
    };
    utterance.onpause = () => {
      if (runId === this.runId) this.setState('paused');
    };
    utterance.onresume = () => {
      if (runId === this.runId) this.setState('playing');
    };
    utterance.onend = () => {
      if (runId !== this.runId) return;
      this.utterance = null;
      this.chunkIndex += 1;
      if (this.chunkIndex < this.chunks.length) {
        window.setTimeout(() => this.speakNext(runId), 0);
      } else {
        this.finish();
      }
    };
    utterance.onerror = (event) => {
      if (runId !== this.runId) return;
      this.utterance = null;
      if (event.error !== 'canceled' && event.error !== 'interrupted') {
        this.onError('تعذر تشغيل القراءة الصوتية العربية.');
      }
      this.finish();
    };
    window.speechSynthesis.speak(utterance);
  }

  finish() {
    this.utterance = null;
    this.chunks = [];
    this.chunkIndex = 0;
    this.paused = false;
    this.setState('ready');
  }

  pause() {
    if (!this.supported() || this.state !== 'playing') return;
    this.paused = true;
    window.speechSynthesis.pause();
    this.setState('paused');
  }

  resume() {
    if (!this.supported() || this.state !== 'paused') return;
    this.paused = false;
    window.speechSynthesis.resume();
    if (!this.utterance) this.speakNext(this.runId);
    this.setState('playing');
  }

  stop(updateState = true) {
    this.runId += 1;
    if (this.supported()) window.speechSynthesis.cancel();
    this.utterance = null;
    this.chunks = [];
    this.chunkIndex = 0;
    this.paused = false;
    if (updateState) this.setState('ready');
  }

  destroy() {
    this.stop();
    if (this.supported()) window.speechSynthesis.removeEventListener?.('voiceschanged', this.refreshVoices);
  }
}

export class VoiceEngine {
  constructor({onState, onTranscript, onError} = {}) {
    this.onState = onState || (() => {});
    this.onTranscript = onTranscript || (() => {});
    this.onError = onError || (() => {});
    this.recognition = null;
    this.stream = null;
    this.running = false;
    this.processing = false;
    this.speaking = false;
    this.muted = false;
    this.restartTimer = null;
  }
  supported() {
    return Boolean((window.SpeechRecognition || window.webkitSpeechRecognition) && navigator.mediaDevices?.getUserMedia && window.speechSynthesis);
  }
  async start() {
    if (!this.supported()) throw new Error('المحادثة الصوتية تحتاج متصفحاً يدعم Speech Recognition وSpeech Synthesis.');
    if (this.running) return;
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true, autoGainControl: true}});
      const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      this.recognition = new Recognition();
      this.recognition.lang = 'ar-SA';
      this.recognition.continuous = false;
      this.recognition.interimResults = false;
      this.recognition.maxAlternatives = 1;
      this.recognition.onresult = (event) => {
        const text = event.results?.[0]?.[0]?.transcript?.trim();
        if (text && this.running && !this.processing && !this.speaking) {
          this.processing = true;
          this.onState('processing');
          this.onTranscript(text);
        }
      };
      this.recognition.onerror = (event) => {
        if (!this.running) return;
        if (event.error === 'not-allowed' || event.error === 'service-not-allowed') this.onError('تم رفض صلاحية الميكروفون. اسمح بالوصول من إعدادات المتصفح ثم أعد المحاولة.');
        else if (event.error !== 'aborted' && event.error !== 'no-speech') this.onError(`انقطع الاستماع الصوتي (${event.error}).`);
      };
      this.recognition.onend = () => {
        if (this.running && !this.processing && !this.speaking) this.scheduleListen();
      };
      this.running = true;
      this.onState('ready');
      this.listen();
    } catch (error) {
      this.stop();
      if (error?.name === 'NotAllowedError' || error?.name === 'SecurityError') throw new Error('تم رفض صلاحية الميكروفون. اسمح بالوصول من إعدادات المتصفح ثم أعد المحاولة.');
      throw error;
    }
  }
  listen() {
    if (!this.running || this.processing || this.speaking || !this.recognition) return;
    try { this.onState('listening'); this.recognition.start(); } catch (error) { if (error.name !== 'InvalidStateError') this.onError('تعذر بدء الاستماع؛ ستتم إعادة المحاولة بأمان.'); }
  }
  scheduleListen() { clearTimeout(this.restartTimer); this.restartTimer = setTimeout(() => this.listen(), 350); }
  completeProcessing() { this.processing = false; if (this.running && !this.speaking) this.scheduleListen(); }
  speak(text) {
    if (!this.running || this.muted || !text || !window.speechSynthesis) { this.completeProcessing(); return; }
    this.speaking = true;
    try { this.recognition?.abort(); } catch {}
    this.onState('speaking');
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(String(text).slice(0, 6000));
    utterance.lang = 'ar-SA'; utterance.rate = 1; utterance.pitch = 1;
    utterance.onend = () => { this.speaking = false; this.completeProcessing(); };
    utterance.onerror = () => { this.speaking = false; this.onError('تعذر تشغيل الرد الصوتي؛ سيستمر وضع الاستماع.'); this.completeProcessing(); };
    window.speechSynthesis.speak(utterance);
  }
  mute() {
    this.muted = true;
    window.speechSynthesis?.cancel();
    if (this.speaking) { this.speaking = false; this.completeProcessing(); }
    this.onState(this.running ? 'listening' : 'ready');
  }
  unmute() { this.muted = false; }
  stop() {
    this.running = false; this.processing = false; this.speaking = false;
    clearTimeout(this.restartTimer);
    try { this.recognition?.abort(); } catch {}
    this.recognition = null;
    this.stream?.getTracks?.().forEach((track) => track.stop()); this.stream = null;
    window.speechSynthesis?.cancel();
    this.onState('ready');
  }
}
