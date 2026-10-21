import { BoothLanguage, BoothSpeaker } from '../types/f1';

class SpeechService {
  private enabled: boolean = false;
  private soundEffects: boolean = true;
  private currentUtterance: SpeechSynthesisUtterance | null = null;
  private audioContext: AudioContext | null = null;
  private isCurrentlySpeaking: boolean = false;
  private speakingListeners: Array<(speaking: boolean, speaker: BoothSpeaker | null) => void> = [];
  private cachedVoices: SpeechSynthesisVoice[] = [];

  constructor() {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      this.loadVoices();
      window.speechSynthesis.onvoiceschanged = () => {
        this.loadVoices();
      };
    }
  }

  private loadVoices() {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      this.cachedVoices = window.speechSynthesis.getVoices();
    }
  }

  public getAvailableVoices(): SpeechSynthesisVoice[] {
    if (this.cachedVoices.length === 0) {
      this.loadVoices();
    }
    return this.cachedVoices;
  }

  public onSpeakingChange(cb: (speaking: boolean, speaker: BoothSpeaker | null) => void) {
    this.speakingListeners.push(cb);
    return () => {
      this.speakingListeners = this.speakingListeners.filter(l => l !== cb);
    };
  }

  private notifySpeaking(speaking: boolean, speaker: BoothSpeaker | null) {
    this.isCurrentlySpeaking = speaking;
    this.speakingListeners.forEach(l => l(speaking, speaker));
  }

  public isSpeaking(): boolean {
    return this.isCurrentlySpeaking;
  }

  public setEnabled(enabled: boolean) {
    this.enabled = enabled;
    if (!enabled && typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
      this.notifySpeaking(false, null);
    }
  }

  public isEnabled(): boolean {
    return this.enabled;
  }

  public setSoundEffects(enabled: boolean) {
    this.soundEffects = enabled;
  }

  public areSoundEffectsEnabled(): boolean {
    return this.soundEffects;
  }

  private initAudioContext() {
    if (!this.audioContext && typeof window !== 'undefined') {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioCtx) {
        this.audioContext = new AudioCtx();
      }
    }
  }

  public playRadioChime() {
    if (!this.soundEffects) return;
    try {
      this.initAudioContext();
      if (!this.audioContext) return;
      if (this.audioContext.state === 'suspended') {
        this.audioContext.resume();
      }

      const osc = this.audioContext.createOscillator();
      const gain = this.audioContext.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, this.audioContext.currentTime); // A5
      osc.frequency.exponentialRampToValueAtTime(1760, this.audioContext.currentTime + 0.08); // A6

      gain.gain.setValueAtTime(0.08, this.audioContext.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.audioContext.currentTime + 0.15);

      osc.connect(gain);
      gain.connect(this.audioContext.destination);

      osc.start();
      osc.stop(this.audioContext.currentTime + 0.15);
    } catch {
      // Audio autoplay policy or unavailable
    }
  }

  public speak(
    text: string,
    speaker: BoothSpeaker,
    language: BoothLanguage,
    onEnd?: () => void
  ) {
    if (!this.enabled || typeof window === 'undefined' || !window.speechSynthesis) {
      if (onEnd) onEnd();
      return;
    }

    // Play subtle broadcast radio chime before speech
    this.playRadioChime();

    // Cancel any ongoing speech and unfreeze Chrome speech queue
    window.speechSynthesis.cancel();
    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
    }

    const utterance = new SpeechSynthesisUtterance(text);
    this.currentUtterance = utterance;
    // Store in global window to prevent Chrome GC bug
    (window as any).__f1Utterance = utterance;

    // Map booth language to BCP 47 tag
    let langCode = 'es-AR';
    if (language === 'es-AR') langCode = 'es-AR';
    else if (language === 'es-MX') langCode = 'es-MX';
    else if (language === 'es-419') langCode = 'es-419';
    else if (language === 'es-ES') langCode = 'es-ES';
    else if (language === 'en') langCode = 'en-GB';

    utterance.lang = langCode;

    // Distinct persona voice tuning:
    // Lead announcer (Carlos): slightly higher pitch, energetic broadcast tempo
    // Color analyst (Alex): slightly deeper pitch, calm telemetry tempo
    if (speaker === 'lead') {
      utterance.pitch = 1.15;
      utterance.rate = 1.08;
    } else {
      utterance.pitch = 0.92;
      utterance.rate = 0.98;
    }

    // Voice selection heuristic with language fallback
    const voices = this.getAvailableVoices();
    if (voices.length > 0) {
      const langPrefix = langCode.slice(0, 2);
      // Try exact language match first, then language prefix
      let matchingVoices = voices.filter(v => v.lang.toLowerCase() === langCode.toLowerCase());
      if (matchingVoices.length === 0) {
        matchingVoices = voices.filter(v => v.lang.toLowerCase().startsWith(langPrefix.toLowerCase()));
      }

      if (matchingVoices.length > 1) {
        if (speaker === 'lead') {
          utterance.voice = matchingVoices[0];
        } else {
          utterance.voice = matchingVoices[matchingVoices.length - 1];
        }
      } else if (matchingVoices.length === 1) {
        utterance.voice = matchingVoices[0];
      }
    }

    this.notifySpeaking(true, speaker);

    utterance.onend = () => {
      this.currentUtterance = null;
      (window as any).__f1Utterance = null;
      this.notifySpeaking(false, null);
      if (onEnd) onEnd();
    };

    utterance.onerror = (e) => {
      console.warn('[SpeechService] Speech synthesis event:', e);
      this.currentUtterance = null;
      (window as any).__f1Utterance = null;
      this.notifySpeaking(false, null);
      if (onEnd) onEnd();
    };

    // Unpause if stuck and speak
    window.speechSynthesis.resume();
    window.speechSynthesis.speak(utterance);
  }

  public stop() {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
      this.currentUtterance = null;
      (window as any).__f1Utterance = null;
      this.notifySpeaking(false, null);
    }
  }
}

export const speechService = new SpeechService();
