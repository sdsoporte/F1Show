import {
  BoothLanguage,
  BoothMode,
  BoothSpeaker,
  DetectedEvent,
  Driver,
  SalienceWindow,
  Turn,
  TurnOutcome,
} from '../types/f1';

export interface DialectVocabulary {
  car: string;
  tyres: string;
  fuel: string;
  pits: string;
  safetyCar: string;
  leadStyle: string;
  colorStyle: string;
}

export const DIALECT_VOCABULARY: Record<BoothLanguage, DialectVocabulary> = {
  'es-AR': {
    car: 'auto',
    tyres: 'neumáticos',
    fuel: 'nafta',
    pits: 'boxes',
    safetyCar: 'auto de seguridad',
    leadStyle: 'voseo', // "¡Mirá cómo viene!", "Tenés que ver la maniobra"
    colorStyle: 'voseo técnico',
  },
  'es-419': {
    car: 'auto',
    tyres: 'neumáticos',
    fuel: 'gasolina',
    pits: 'pits',
    safetyCar: 'auto de seguridad',
    leadStyle: 'tuteo latino neutral',
    colorStyle: 'tuteo táctico',
  },
  'es-MX': {
    car: 'auto',
    tyres: 'llantas',
    fuel: 'gasolina',
    pits: 'pits',
    safetyCar: 'auto de seguridad',
    leadStyle: 'tuteo mexicano',
    colorStyle: 'análisis táctico',
  },
  'es-ES': {
    car: 'coche',
    tyres: 'neumáticos',
    fuel: 'gasolina',
    pits: 'boxes',
    safetyCar: 'coche de seguridad',
    leadStyle: 'tú peninsular',
    colorStyle: 'análisis técnico',
  },
  'en': {
    car: 'car',
    tyres: 'tyres',
    fuel: 'fuel',
    pits: 'pit lane',
    safetyCar: 'safety car',
    leadStyle: 'play-by-play broadcast',
    colorStyle: 'technical analysis',
  },
};

/**
 * Checks if an event is a priority caution or incident
 * that allows the lead commentator to interrupt or take consecutive turns.
 */
export function announcesCaution(event: DetectedEvent): boolean {
  if (event.family === 'race_control') {
    const msg = String(event.evidence.message || '').toUpperCase();
    const cat = String(event.evidence.category || '').toUpperCase();
    const flag = String(event.evidence.flag || '').toUpperCase();
    if (
      cat.includes('SAFETY CAR') ||
      cat.includes('FLAG') ||
      flag === 'RED' ||
      flag === 'YELLOW' ||
      flag === 'DOUBLE YELLOW' ||
      msg.includes('SAFETY CAR') ||
      msg.includes('VSC') ||
      msg.includes('INCIDENT')
    ) {
      return true;
    }
  }
  return false;
}

/**
 * Determines whether a turn is in 'build' or 'climax' mode.
 */
export function determineTurnMode(event: DetectedEvent, previousPosition?: number): BoothMode {
  if (announcesCaution(event)) {
    return 'climax';
  }
  if (event.family === 'pit') {
    return 'climax';
  }
  if (event.family === 'position') {
    const current = event.evidence.position;
    if (typeof current === 'number' && typeof previousPosition === 'number') {
      if (Math.abs(current - previousPosition) >= 2) {
        return 'climax';
      }
    }
  }
  return 'build';
}

/**
 * Validates the evidence citation protocol on a generated commentary response.
 */
export function validateEvidenceProtocol(
  responseText: string,
  suppliedReferences: string[]
): {
  isValid: boolean;
  citedReferences: string[];
  airedText: string;
  refusalReason?: string;
} {
  const lines = responseText.split('\n').map(l => l.trim()).filter(Boolean);
  if (lines.length === 0) {
    return { isValid: false, citedReferences: [], airedText: '', refusalReason: 'EMPTY_RESPONSE' };
  }

  const firstLine = lines[0];
  const citationPrefixMatch = firstLine.match(/^(?:EVIDENCE|CITATIONS?)\s*:\s*(.*)$/i);
  if (!citationPrefixMatch) {
    return {
      isValid: false,
      citedReferences: [],
      airedText: '',
      refusalReason: 'MISSING_EVIDENCE_HEADER',
    };
  }

  // Parse cited references
  const rawCitations = citationPrefixMatch[1].split(',').map(c => c.trim()).filter(Boolean);
  const cleanedCitations: string[] = [];

  for (const raw of rawCitations) {
    // Normalise e.g. "laps[6].lap_duration = 105.091" -> "laps[6].lap_duration"
    const leftPart = raw.split('=')[0].trim();
    cleanedCitations.push(leftPart);
  }

  if (cleanedCitations.length === 0) {
    return {
      isValid: false,
      citedReferences: [],
      airedText: '',
      refusalReason: 'NO_REFERENCES_CITED',
    };
  }

  // Verify all cited references were actually supplied
  const suppliedSet = new Set(suppliedReferences);
  for (const ref of cleanedCitations) {
    if (!suppliedSet.has(ref)) {
      // Check if it's the bare identity e.g. "laps[6]"
      const hasBare = suppliedReferences.some(sr => sr.startsWith(ref + '.'));
      if (!hasBare) {
        return {
          isValid: false,
          citedReferences: cleanedCitations,
          airedText: '',
          refusalReason: `UNSUPPLIED_REFERENCE: ${ref}`,
        };
      }
    }
  }

  // The rest of the lines is the commentary prose
  const commentaryLines = lines.slice(1);
  if (commentaryLines.length === 0) {
    return {
      isValid: false,
      citedReferences: cleanedCitations,
      airedText: '',
      refusalReason: 'NO_COMMENTARY_AFTER_CITATION',
    };
  }

  // Check for second citation line violation
  for (const line of commentaryLines) {
    if (/^(?:EVIDENCE|CITATIONS?)\s*:/i.test(line) && /\[\d+\]/.test(line)) {
      return {
        isValid: false,
        citedReferences: cleanedCitations,
        airedText: '',
        refusalReason: 'MULTIPLE_CITATION_LINES',
      };
    }
  }

  const airedText = commentaryLines.join('\n');
  return {
    isValid: true,
    citedReferences: cleanedCitations,
    airedText,
  };
}

/**
 * Deterministic evidence-grounded commentary generator for simulated booth.
 */
export function generateScriptedTurn(
  event: DetectedEvent,
  speaker: BoothSpeaker,
  mode: BoothMode,
  language: BoothLanguage,
  driver: Driver | null,
  salience: SalienceWindow,
  previousPos?: number
): { text: string; evidence: string[]; outcome: TurnOutcome; refusalReason?: string } {
  const vocab = DIALECT_VOCABULARY[language] || DIALECT_VOCABULARY['es-AR'];
  const driverName = driver ? driver.full_name : `Auto #${event.driverNumber ?? '?'}`;
  const teamName = driver ? driver.team_name : 'Escudería';

  let citedRefs: string[] = [];
  let prose = '';

  switch (event.family) {
    case 'position': {
      const pos = event.evidence.position;
      const posRef = `${event.family}[${event.recordIndex}].position`;
      citedRefs = [posRef];

      const delta = previousPos !== undefined ? previousPos - pos : 0;
      const deltaText = delta > 0 ? `+${delta}` : `${delta}`;

      if (language === 'es-AR') {
        if (speaker === 'lead') {
          if (mode === 'climax') {
            prose = `¡Atención en pista! ${driverName} con el ${vocab.car} de ${teamName} avanza a la posición P${pos} (${deltaText} lugares). ¡Maniobra decisiva en este tramo!`;
          } else {
            prose = `Seguimos la marcha: ${driverName} se acomoda ahora en P${pos}. El ritmo del ${vocab.car} se mantiene sólido.`;
          }
        } else {
          // Color analyst
          if (pos <= 3) {
            prose = `Fijate en la telemetría: ${driverName} está en zona de podio provisional (P${pos}). El desgaste de sus ${vocab.tyres} va a ser la clave cuando llegue la ventana de ${vocab.pits}.`;
          } else {
            prose = `Desde la mesa de análisis: P${pos} para ${driverName}. El delta de ritmo muestra consistencia en el sector medio.`;
          }
        }
      } else if (language === 'en') {
        if (speaker === 'lead') {
          prose = mode === 'climax'
            ? `Tremendous move! ${driverName} for ${teamName} takes position P${pos}! That is a crucial swing on track.`
            : `Tracking ${driverName} in the ${teamName} currently holding P${pos} as the laps tick down.`;
        } else {
          prose = `Looking at that P${pos} position for ${driverName}, the strategic window is opening up. Tyre preservation will dictate whether they can hold this.`;
        }
      } else {
        // es-419 / es-MX / es-ES
        prose = speaker === 'lead'
          ? `¡Ojo a ${driverName}! Se ubica en P${pos} con el ${vocab.car} de ${teamName}.`
          : `Análisis en P${pos}: ${driverName} gestiona la temperatura de los ${vocab.tyres} con precisión.`;
      }
      break;
    }

    case 'laps': {
      const lapNum = event.evidence.lap_number;
      const duration = event.evidence.lap_duration;
      const lapRef = `${event.family}[${event.recordIndex}].lap_number`;
      const durRef = `${event.family}[${event.recordIndex}].lap_duration`;
      citedRefs = [lapRef];
      if (typeof duration === 'number') {
        citedRefs.push(durRef);
      }

      const durStr = typeof duration === 'number' ? `${duration.toFixed(3)}s` : 'tiempo en curso';
      const isFastest = salience.fastestLap && salience.fastestLap.driverNumber === event.driverNumber && salience.fastestLap.lapNumber === lapNum;

      if (language === 'es-AR') {
        if (speaker === 'lead') {
          if (isFastest) {
            prose = `¡Récord de vuelta! ${driverName} clava ${durStr} en la vuelta ${lapNum}. ¡Púrpura absoluto en el clasificador!`;
          } else {
            prose = `Completa la vuelta ${lapNum} ${driverName} registrando ${durStr}. Ritmo constante para ${teamName}.`;
          }
        } else {
          if (isFastest) {
            prose = `Qué registro metió ${driverName}: ${durStr}. Si termina entre los diez primeros se lleva ese punto extra reglamentario del campeonato.`;
          } else {
            prose = `Analizando el giro ${lapNum}: ${durStr}. La degradación de los ${vocab.tyres} está dentro de la ventana esperada por los ingenieros.`;
          }
        }
      } else if (language === 'en') {
        if (speaker === 'lead') {
          prose = isFastest
            ? `Fastest lap of the race! ${driverName} posts a blistering ${durStr} on lap ${lapNum}!`
            : `Lap ${lapNum} completed by ${driverName} in ${durStr} for ${teamName}.`;
        } else {
          prose = isFastest
            ? `That ${durStr} lap from ${driverName} shows the car has pace in clean air. Provisional bonus point territory.`
            : `Steady lap times around ${durStr} for ${driverName}. Clean execution through all three sectors.`;
        }
      } else {
        prose = isFastest
          ? `¡Vuelta rápida para ${driverName} con ${durStr} en la vuelta ${lapNum}!`
          : `Vuelta ${lapNum} completada por ${driverName}: crono de ${durStr}.`;
      }
      break;
    }

    case 'pit': {
      const lapNum = event.evidence.lap_number;
      const laneDur = event.evidence.lane_duration;
      const stopDur = event.evidence.stop_duration;
      citedRefs = [`pit[${event.recordIndex}].lap_number`];
      if (typeof stopDur === 'number') citedRefs.push(`pit[${event.recordIndex}].stop_duration`);
      if (typeof laneDur === 'number') citedRefs.push(`pit[${event.recordIndex}].lane_duration`);

      const stopStr = typeof stopDur === 'number' ? `${stopDur.toFixed(2)}s` : 'parada completada';

      if (language === 'es-AR') {
        if (speaker === 'lead') {
          prose = `¡A los ${vocab.pits}! ${driverName} ingresa al carril en la vuelta ${lapNum}. Detención de ${stopStr}. ¡Salida limpia a pista!`;
        } else {
          prose = `Parada estratégica para ${teamName}. Cronometramos ${stopStr} con el ${vocab.car} detenido. Ahora a calentar el compuesto fresco sin castigarlo.`;
        }
      } else if (language === 'en') {
        prose = speaker === 'lead'
          ? `In to the ${vocab.pits}! ${driverName} stops on lap ${lapNum}. Stationary time of ${stopStr}. Clean release back to the circuit!`
          : `Critical pit stop for ${teamName} on lap ${lapNum}. Clocked at ${stopStr}. The undercut window is now in play.`;
      } else {
        prose = `Parada en ${vocab.pits} para ${driverName} en la vuelta ${lapNum}. Tiempo detenido: ${stopStr}.`;
      }
      break;
    }

    case 'stints': {
      const stintNum = event.evidence.stint_number;
      const compound = event.evidence.compound || 'MEDIO';
      const tyreAge = event.evidence.tyre_age_at_start ?? 0;
      citedRefs = [
        `stints[${event.recordIndex}].stint_number`,
        `stints[${event.recordIndex}].compound`,
      ];

      if (language === 'es-AR') {
        prose = speaker === 'lead'
          ? `Nuevo stint #${stintNum} para ${driverName}: monta compuesto ${compound} (edad de inicio: ${tyreAge} vueltas).`
          : `Estrategia de neumáticos para ${teamName}: optan por el compuesto ${compound} en este relevo #${stintNum}. Clave el calentamiento en los primeros kilómetros.`;
      } else if (language === 'en') {
        prose = speaker === 'lead'
          ? `Stint #${stintNum} underway for ${driverName}, fitting the ${compound} compound.`
          : `Tactical stint #${stintNum}: ${compound} compound fitted to ${driverName}'s car. Let's see how the tyre degradation evolves.`;
      } else {
        prose = `Inicio de relevo #${stintNum} para ${driverName} con neumático ${compound}.`;
      }
      break;
    }

    case 'race_control': {
      const cat = event.evidence.category || 'CONTROL';
      const msg = event.evidence.message || '';
      const flag = event.evidence.flag;
      citedRefs = [`race_control[${event.recordIndex}].message`];
      if (flag) citedRefs.push(`race_control[${event.recordIndex}].flag`);

      if (language === 'es-AR') {
        if (speaker === 'lead') {
          prose = `¡Dirección de carrera comunica! [${cat}] ${msg}. ¡Atención a las banderas y a las pantallas en pista!`;
        } else {
          prose = `Impacto reglamentario de la notificación de control: "${msg}". Los estrategas en el muro de boxes ya recalculan sus márgenes de seguridad.`;
        }
      } else if (language === 'en') {
        prose = speaker === 'lead'
          ? `Race Control notification! [${cat}] ${msg}. Drivers must observe the caution signals!`
          : `Tactical impact of that message: "${msg}". The pit walls will be adjusting their delta targets immediately.`;
      } else {
        prose = `Comunicado de dirección de carrera: ${cat} - ${msg}.`;
      }
      break;
    }

    default: {
      citedRefs = event.references.slice(0, 1);
      prose = `Seguimiento de telemetría para ${driverName} en el evento ${event.eventId}.`;
    }
  }

  const rawSimulated = `EVIDENCE: ${citedRefs.join(', ')}\n${prose}`;
  const validation = validateEvidenceProtocol(rawSimulated, event.references);

  if (!validation.isValid) {
    return {
      text: '',
      evidence: [],
      outcome: 'REFUSED',
      refusalReason: validation.refusalReason,
    };
  }

  return {
    text: validation.airedText,
    evidence: validation.citedReferences,
    outcome: 'AIRED',
  };
}

/**
 * Calls the server-side Gemini 3.8 Flash proxy to generate
 * real-time AI commentary adhering strictly to the evidence citation protocol.
 */
export async function generateGeminiTurn(
  event: DetectedEvent,
  speaker: BoothSpeaker,
  mode: BoothMode,
  language: BoothLanguage,
  driver: Driver | null,
  salience: SalienceWindow,
  previousPos?: number
): Promise<{ text: string; evidence: string[]; outcome: TurnOutcome; refusalReason?: string }> {
  try {
    const res = await fetch('/api/gemini/commentary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event,
        speaker,
        mode,
        language,
        driver,
        salience,
        previousPos,
        suppliedReferences: event.references,
      }),
    });

    if (!res.ok) {
      // If server has no key or errors, fall back to deterministic generator
      return generateScriptedTurn(event, speaker, mode, language, driver, salience, previousPos);
    }

    const data = await res.json();
    const validation = validateEvidenceProtocol(data.text, event.references);

    if (!validation.isValid) {
      return {
        text: '',
        evidence: [],
        outcome: 'REFUSED',
        refusalReason: validation.refusalReason,
      };
    }

    return {
      text: validation.airedText,
      evidence: validation.citedReferences,
      outcome: 'AIRED',
    };
  } catch {
    return generateScriptedTurn(event, speaker, mode, language, driver, salience, previousPos);
  }
}

