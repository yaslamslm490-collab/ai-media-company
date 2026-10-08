function pickArabicVoice(voices = []) {
  const arabic = voices.filter((voice) => /^ar(?:-|_|$)/i.test(voice.lang || ''));
  if (!arabic.length) return null;
  const preferred = arabic.find((voice) => /^ar-SA/i.test(voice.lang))
    || arabic.find((voice) => /^ar-AE/i.test(voice.lang))
    || arabic.find((voice) => voice.default)
    || arabic[0];
  return preferred;
}

export class SpeechReader {
  constructor({onState, onError} = {}) {
    this.onState = onState || (() => {});
    this.onError = onError || (() => {});
    this.utterance = null;
    this.state = 'ready';
    this.voice = null;
    this.refreshVoices = this.refreshVoices.bind(this);
    if (this.supported()) {
      this.refreshVoices();
      window.speechSynthesis.addEventListener('voiceschanged', this.refreshVoices);
    }
  }
  supported() { return typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window; }
  refreshVoices() { this.voice = pickArabicVoice(window.speechSynthesis.getVoices()); }
  setState(next) { this.state = next; this.onState(next); }
  speak(text) {
    if (!this.supported()) throw new Error('القراءة الصوتية غير مدعومة في هذا المتصفح أو الجهاز.');
    const value = String(text || '').trim();
    if (!value) throw new Error('اكتب نصاً في مربع الكتابة أولاً.');
    this.stop(false);
    this.refreshVoices();
    const utterance = new SpeechSynthesisUtterance(value.slice(0, 6000));
    utterance.lang = 'ar-SA';
    utterance.rate = 1;
    utterance.pitch = 1;
    if (this.voice) utterance.voice = this.voice;
    utterance.onstart = () => this.setState('playing');
    utterance.onpause = () => this.setState('paused');
    utterance.onresume = () => this.setState('playing');
    utterance.onend = () => { this.utterance = null; this.setState('ready'); };
    utterance.onerror = (event) => {
      this.utterance = null;
      if (event.error !== 'canceled' && event.error !== 'interrupted') this.onError('تعذر تشغيل القراءة الصوتية العربية.');
      this.setState('ready');
    };
    this.utterance = utterance;
    this.setState('playing');
    window.speechSynthesis.speak(utterance);
  }
  pause() {
    if (!this.supported() || !window.speechSynthesis.speaking) return;
    window.speechSynthesis.pause();
    this.setState('paused');
  }
  resume() {
    if (!this.supported() || !window.speechSynthesis.paused) return;
    window.speechSynthesis.resume();
    this.setState('playing');
  }
  stop(updateState = true) {
    if (this.supported()) window.speechSynthesis.cancel();
    this.utterance = null;
    if (updateState) this.setState('ready');
  }
  destroy() {
    this.stop();
    if (this.supported()) window.speechSynthesis.removeEventListener('voiceschanged', this.refreshVoices);
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
