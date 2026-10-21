import { BoothLanguage, BoothSpeaker } from '../types/f1';

export interface SpeakOptions {
  immediate?: boolean;
  onEnd?: () => void;
  isRetry?: boolean;
}

interface QueuedTurn {
  text: string;
  speaker: BoothSpeaker;
  language: BoothLanguage;
  onEnd?: () => void;
}

class SpeechService {
  private enabled: boolean = false;
  private soundEffects: boolean = true;
  private currentUtterance: SpeechSynthesisUtterance | null = null;
  private audioContext: AudioContext | null = null;
  private isCurrentlySpeaking: boolean = false;
  private currentSpeaker: BoothSpeaker | null = null;
  private speakingListeners: Array<(speaking: boolean, speaker: BoothSpeaker | null) => void> = [];
  private cachedVoices: SpeechSynthesisVoice[] = [];
  private voicesLoaded: boolean = false;
  private queue: QueuedTurn[] = [];
  private lastChimeTime: number = 0;
  private keepAliveTimer: any = null;

  constructor() {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      this.loadVoices();
      if (window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = () => {
          this.loadVoices();
        };
      }
      // Chrome keepalive: prevent long speech from going silent or stuck in paused state
      this.keepAliveTimer = setInterval(() => {
        if (typeof window !== 'undefined' && window.speechSynthesis && this.isCurrentlySpeaking) {
          if (window.speechSynthesis.paused) {
            window.speechSynthesis.resume();
          }
        }
      }, 3000);
    }
  }

  private loadVoices() {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      const v = window.speechSynthesis.getVoices();
      if (v && v.length > 0) {
        this.cachedVoices = v;
        this.voicesLoaded = true;
      }
    }
  }

  public getAvailableVoices(): SpeechSynthesisVoice[] {
    if (!this.voicesLoaded || this.cachedVoices.length === 0) {
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
    this.currentSpeaker = speaker;
    this.speakingListeners.forEach(l => l(speaking, speaker));
  }

  public isSpeaking(): boolean {
    return this.isCurrentlySpeaking;
  }

  public getCurrentSpeaker(): BoothSpeaker | null {
    return this.currentSpeaker;
  }

  public setEnabled(enabled: boolean) {
    this.enabled = enabled;
    if (!enabled) {
      this.queue = [];
      this.stop();
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
    const now = Date.now();
    // Don't spam chimes if one just played in the last 2.5 seconds
    if (now - this.lastChimeTime < 2500) return;
    this.lastChimeTime = now;

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

      gain.gain.setValueAtTime(0.06, this.audioContext.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.audioContext.currentTime + 0.15);

      osc.connect(gain);
      gain.connect(this.audioContext.destination);

      osc.start();
      osc.stop(this.audioContext.currentTime + 0.15);
    } catch {
      // Audio autoplay policy or unavailable
    }
  }

  /**
   * Intelligently selects the best matching voice and sets utterance.lang to match!
   */
  private selectVoiceAndLang(utterance: SpeechSynthesisUtterance, speaker: BoothSpeaker, language: BoothLanguage) {
    const allVoices = this.getAvailableVoices();

    // Map booth language preference
    let preferredDialect = 'es-AR';
    if (language === 'es-MX') preferredDialect = 'es-MX';
    else if (language === 'es-419') preferredDialect = 'es-419';
    else if (language === 'es-ES') preferredDialect = 'es-ES';
    else if (language === 'en') preferredDialect = 'en-GB';

    if (allVoices.length === 0) {
      // No voices loaded in browser yet, use fallback code
      utterance.lang = language === 'en' ? 'en-US' : 'es-ES';
      return;
    }

    if (language === 'en') {
      const enVoices = allVoices.filter(v => v.lang.toLowerCase().startsWith('en'));
      if (enVoices.length > 0) {
        const chosen = speaker === 'lead' ? enVoices[0] : enVoices[enVoices.length - 1];
        utterance.voice = chosen;
        utterance.lang = chosen.lang;
        return;
      }
    }

    // Spanish selection: find all Spanish voices
    const esVoices = allVoices.filter(v => {
      const l = v.lang.toLowerCase().replace('_', '-');
      const n = v.name.toLowerCase();
      return l.startsWith('es') || n.includes('spanish') || n.includes('español');
    });

    if (esVoices.length > 0) {
      // Check if any voice matches preferred dialect exactly
      const dialectMatch = esVoices.find(v => v.lang.toLowerCase().replace('_', '-') === preferredDialect.toLowerCase());

      let leadVoice = dialectMatch || esVoices[0];
      let analystVoice = esVoices.length > 1 ? esVoices[esVoices.length - 1] : leadVoice;

      // Check for named personas if available
      const maleVoice = esVoices.find(v => {
        const n = v.name.toLowerCase();
        return (
          n.includes('carlos') ||
          n.includes('jorge') ||
          n.includes('diego') ||
          n.includes('pablo') ||
          n.includes('raul') ||
          n.includes('male')
        );
      });
      const altVoice = esVoices.find(v => v !== (maleVoice || leadVoice));

      if (maleVoice) leadVoice = maleVoice;
      if (altVoice) analystVoice = altVoice;

      const chosenVoice = speaker === 'lead' ? leadVoice : analystVoice;
      utterance.voice = chosenVoice;
      // CRITICAL: lang must match the voice's actual lang to prevent 'language-unavailable' error in Chromium!
      utterance.lang = chosenVoice.lang || 'es-ES';
      return;
    }

    // No Spanish voices installed on user's system!
    // Pick the default system voice or first voice so speech DOES NOT ERROR OUT!
    const defaultVoice = allVoices.find(v => v.default) || allVoices[0];
    if (defaultVoice) {
      utterance.voice = defaultVoice;
      utterance.lang = defaultVoice.lang || 'es-ES';
    } else {
      utterance.lang = 'es-ES';
    }
  }

  public speak(
    text: string,
    speaker: BoothSpeaker,
    language: BoothLanguage,
    options: SpeakOptions = {}
  ) {
    if (!this.enabled || typeof window === 'undefined' || !window.speechSynthesis) {
      if (options.onEnd) options.onEnd();
      return;
    }

    // Clean text of markdown or URLs if any
    const cleanText = text.replace(/[*_#`]/g, '').trim();
    if (!cleanText) {
      if (options.onEnd) options.onEnd();
      return;
    }

    const { immediate = false, onEnd, isRetry = false } = options;

    // If something is already speaking and this is not an immediate action, queue it!
    if (this.isCurrentlySpeaking && !immediate) {
      // Keep only up to 1 turn in queue to avoid stale commentary piling up
      this.queue = [{ text: cleanText, speaker, language, onEnd }];
      return;
    }

    // Cancel existing utterance safely
    if (immediate && this.isCurrentlySpeaking) {
      window.speechSynthesis.cancel();
    }

    // Avoid Chrome instant cancel-speak race condition: dispatch in next microtask
    setTimeout(() => {
      this.executeSpeak(cleanText, speaker, language, { onEnd, isRetry });
    }, 40);
  }

  private executeSpeak(
    cleanText: string,
    speaker: BoothSpeaker,
    language: BoothLanguage,
    options: { onEnd?: () => void; isRetry?: boolean }
  ) {
    if (typeof window === 'undefined' || !window.speechSynthesis) return;

    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
    }

    const utterance = new SpeechSynthesisUtterance(cleanText);
    this.currentUtterance = utterance;
    (window as any).__f1Utterance = utterance;

    // Distinct persona voice tuning:
    if (speaker === 'lead') {
      utterance.pitch = 1.08;
      utterance.rate = 1.05;
    } else {
      utterance.pitch = 0.94;
      utterance.rate = 0.98;
    }

    // Select voice and matching language code
    this.selectVoiceAndLang(utterance, speaker, language);

    // Play chime right when audio starts!
    utterance.onstart = () => {
      this.playRadioChime();
      this.notifySpeaking(true, speaker);
    };

    utterance.onend = () => {
      this.currentUtterance = null;
      (window as any).__f1Utterance = null;
      this.notifySpeaking(false, null);
      if (options.onEnd) options.onEnd();

      // Process next queued turn if any
      if (this.queue.length > 0) {
        const next = this.queue.shift();
        if (next) {
          setTimeout(() => {
            this.speak(next.text, next.speaker, next.language, { onEnd: next.onEnd });
          }, 350);
        }
      }
    };

    utterance.onerror = (e: any) => {
      const errorType = e.error || 'unknown';
      this.currentUtterance = null;
      (window as any).__f1Utterance = null;

      if (errorType === 'canceled' || errorType === 'interrupted') {
        // Normal interruption, do not warn or alert
        this.notifySpeaking(false, null);
        if (options.onEnd) options.onEnd();
        return;
      }

      console.warn(`[SpeechService] Speech synthesis event: ${errorType}`);

      // Auto-fallback: if language-unavailable or voice-unavailable, retry once with raw system voice!
      if ((errorType === 'language-unavailable' || errorType === 'voice-unavailable') && !options.isRetry) {
        console.info('[SpeechService] Retrying with generic system default voice...');
        setTimeout(() => {
          this.executeSystemFallback(cleanText, speaker, options.onEnd);
        }, 50);
        return;
      }

      this.notifySpeaking(false, null);
      if (options.onEnd) options.onEnd();
    };

    try {
      window.speechSynthesis.resume();
      window.speechSynthesis.speak(utterance);
    } catch (err) {
      console.warn('[SpeechService] Error calling speechSynthesis.speak:', err);
      this.notifySpeaking(false, null);
      if (options.onEnd) options.onEnd();
    }
  }

  private executeSystemFallback(cleanText: string, speaker: BoothSpeaker, onEnd?: () => void) {
    if (typeof window === 'undefined' || !window.speechSynthesis) return;
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.voice = null;
    utterance.lang = ''; // Use browser default

    utterance.onstart = () => {
      this.notifySpeaking(true, speaker);
    };
    utterance.onend = () => {
      this.notifySpeaking(false, null);
      if (onEnd) onEnd();
    };
    utterance.onerror = (e: any) => {
      console.warn('[SpeechService] Fallback speech error:', e.error || e);
      this.notifySpeaking(false, null);
      if (onEnd) onEnd();
    };

    window.speechSynthesis.speak(utterance);
  }

  public stop() {
    this.queue = [];
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
      this.currentUtterance = null;
      (window as any).__f1Utterance = null;
      this.notifySpeaking(false, null);
    }
  }
}

export const speechService = new SpeechService();
