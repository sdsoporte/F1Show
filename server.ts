import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { resolveGeminiProvider } from './server/geminiProvider';
import { loadPrivateEnv } from './server/loadPrivateEnv';
import { spawn } from 'child_process';
import fs from 'fs';
import os from 'os';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3000;

app.use(express.json());

// Initialize Google Gen AI client: direct key or CLIproxy, per GEMINI_PROVIDER.
// The startup log names the active provider (never a key value).
// Definitive config: the operator's gitignored private env loads automatically —
// no manual sourcing needed. Real environment values always win over the file.
const privateVarsLoaded = loadPrivateEnv(process.cwd());
const resolved = resolveGeminiProvider(process.env as Record<string, string | undefined>);
console.log(`[env] private variables loaded: ${privateVarsLoaded}`);
const ai = resolved.client;
console.log(`[Gemini] provider: ${resolved.detail}`);

/**
 * Route: POST /api/gemini/commentary
 * Generates an evidence-grounded commentary line using Gemini 3.8 Flash.
 */
app.post('/api/gemini/commentary', async (req, res) => {
  try {
    const {
      event,
      speaker,
      mode,
      language,
      driver,
      salience,
      previousPos,
      suppliedReferences,
    } = req.body;

    if (!ai) {
      return res.status(503).json({
        error: 'GEMINI_API_KEY is not configured on the server.',
        isConfigured: false,
      });
    }

    const driverName = driver ? driver.full_name : `Car #${event.driverNumber ?? '?'}`;
    const teamName = driver ? driver.team_name : 'Team';

    // Build persona & dialect instructions
    let dialectRule = '';
    if (language === 'es-AR') {
      dialectRule = `IDIOMA Y REGISTRO: Español Argentino (es-AR) con voseo obligatorio (usar "vos", "tenés", "podés", "mirá", "fijate"). Vocabulario motorsport argentino obligatorio: usar "auto", "neumáticos", "nafta", "boxes", "auto de seguridad".`;
    } else if (language === 'es-419') {
      dialectRule = `IDIOMA Y REGISTRO: Español Latino neutro (es-419) con tuteo. Vocabulario: "auto", "neumáticos", "gasolina", "pits", "auto de seguridad".`;
    } else if (language === 'es-MX') {
      dialectRule = `IDIOMA Y REGISTRO: Español Mexicano (es-MX) con tuteo. Vocabulario: "auto", "llantas", "gasolina", "pits", "auto de seguridad".`;
    } else if (language === 'es-ES') {
      dialectRule = `IDIOMA Y REGISTRO: Español de España (es-ES) con tú/vosotros. Vocabulario: "coche", "neumáticos", "gasolina", "boxes", "coche de seguridad".`;
    } else {
      dialectRule = `LANGUAGE: English (en). Motorsport terms: "car", "tyres", "fuel", "pit lane", "safety car".`;
    }

    const speakerRole =
      speaker === 'lead'
        ? 'Lead Play-by-Play Announcer (relator principal de transmisiones de F1: enérgico, directo, enfocado en el momento de acción inmediata)'
        : 'Color Analyst (analista técnico y táctico de F1: analítico, enfocado en telemetría, desgaste de compuestos, deltas y estrategia)';

    const systemInstruction = `You are a professional Formula 1 broadcast commentator in a two-person simulated booth.
Your seat role: ${speakerRole}.
Turn mode: ${mode.toUpperCase()} (${mode === 'climax' ? 'high energy, crucial moment' : 'measured build, steady pace'}).

CRITICAL GROUNDING PROTOCOL RULES:
1. You may ONLY make claims that are strictly backed by the supplied evidence references.
2. YOUR FIRST LINE MUST BE EXACTLY:
EVIDENCE: <reference>[, <reference>...]
listing one or more references chosen ONLY from the list of SUPPLIED REFERENCES below. Do not add any text before this line.
3. Your commentary prose MUST start on line 2, immediately following the EVIDENCE line.
4. DO NOT write a second line that starts with EVIDENCE or citations.
5. Never invent or speculate about unrecorded mechanical failures, driver emotions, or overtakes on lap 1.
6. ${dialectRule}
7. Keep your commentary natural, punchy, and television-broadcast ready (1-3 sentences max).`;

    const referencesList = Array.isArray(suppliedReferences) ? suppliedReferences.join(', ') : '';

    const prompt = `SUPPLIED REFERENCES PERMITTED TO CITE:
${referencesList}

CURRENT EVENT DATA:
- Family: ${event.family}
- Event Type: ${event.eventType}
- Driver: ${driverName} (#${event.driverNumber}) - ${teamName}
- Telemetry Evidence: ${JSON.stringify(event.evidence)}
- Previous Position: ${previousPos ?? 'N/A'}
- Current Lap: ${event.evidence.lap_number ?? 'In progress'}

RACE CONTEXT / SALIENCE:
- Fastest lap so far: ${salience?.fastestLap ? `${salience.fastestLap.duration.toFixed(3)}s by #${salience.fastestLap.driverNumber}` : 'None'}
- Mode: ${mode}

Generate your response following the EVIDENCE protocol on line 1, followed by your commentary.`;

    const response = await ai.models.generateContent({
      model: 'gemini-3.8-flash',
      contents: prompt,
      config: {
        systemInstruction,
        temperature: 0.7,
      },
    });

    const generatedText = response.text || '';

    return res.json({
      text: generatedText,
      modelId: 'gemini-3.8-flash',
      isConfigured: resolved.provider !== 'none',
    });
  } catch (error: any) {
    console.error('Error generating Gemini commentary:', error);
    return res.status(500).json({
      error: error?.message || 'Failed to generate commentary with Gemini',
      isConfigured: resolved.provider !== 'none',
    });
  }
});

/**
 * Route: GET /api/gemini/status
 * Returns whether Gemini is configured on the server.
 */
app.get('/api/gemini/status', (_req, res) => {
  res.json({
    available: resolved.provider !== 'none',
    provider: resolved.provider,
    model: 'gemini-3.8-flash',
  });
});

/**
 * Route: POST /api/tts
 * Synthesizes booth voice audio with Edge neural voices (msedge-tts), using the
 * voice map recorded by F15 (Engram obs 6046): lead -> es-AR-TomasNeural,
 * colour -> es-UY-MateoNeural, es-419 fallbacks -> Jorge/Alonso. No key needed.
 */
const BOOTH_VOICES: Record<string, { lead: string; colour: string }> = {
  'es-AR': { lead: 'es-AR-TomasNeural', colour: 'es-UY-MateoNeural' },
  'es-419': { lead: 'es-MX-JorgeNeural', colour: 'es-PE-AlexNeural' },
  'es-MX': { lead: 'es-MX-JorgeNeural', colour: 'es-MX-DaliaNeural' },
  'es-ES': { lead: 'es-ES-AlvaroNeural', colour: 'es-ES-ElviraNeural' },
};
const DEFAULT_BOOTH_VOICES = { lead: 'es-MX-JorgeNeural', colour: 'es-MX-AlonsoNeural' };

const EDGE_TTS_BIN = path.resolve(process.cwd(), '.venv', 'bin', 'edge-tts');

app.post('/api/tts', async (req, res) => {
  try {
    const { text, speaker, language } = req.body;
    if (!text || typeof text !== 'string') {
      return res.status(400).json({ error: 'Missing or invalid text parameter' });
    }
    const voices = BOOTH_VOICES[language] ?? DEFAULT_BOOTH_VOICES;
    const voiceName = speaker === 'color' ? voices.colour : voices.lead;

    if (!fs.existsSync(EDGE_TTS_BIN)) {
      return res.status(503).json({ error: 'edge-tts binary not found — provision the repo venv (uv sync)', available: false });
    }

    const outFile = path.join(os.tmpdir(), `f1show-tts-${Date.now()}-${Math.random().toString(16).slice(2)}.mp3`);
    await new Promise<void>((resolve, reject) => {
      const proc = spawn(EDGE_TTS_BIN, ['--voice', voiceName, '--text', text, '--write-media', outFile], { timeout: 15000 });
      proc.on('error', reject);
      proc.on('close', (code) => (code === 0 ? resolve() : reject(new Error(`edge-tts exited with code ${code}`))));
    });
    const audio = await fs.promises.readFile(outFile);
    await fs.promises.unlink(outFile).catch(() => {});

    res.set('Content-Type', 'audio/mpeg');
    res.send(audio);
  } catch (error: any) {
    console.warn('[Edge TTS] Error generating audio:', error?.message || error);
    return res.status(500).json({ error: error?.message || 'TTS generation failed', available: false });
  }
});

import { f1SignalR } from './server/f1SignalR.ts';

/**
 * Route: GET /api/f1-live/status
 * Returns current status of connection to official F1 Live Timing stream.
 */
app.get('/api/f1-live/status', (_req, res) => {
  res.json(f1SignalR.getStatus());
});

/**
 * Route: POST /api/f1-live/connect
 * Starts connection to F1 Live Timing SignalR.
 */
app.post('/api/f1-live/connect', async (_req, res) => {
  try {
    await f1SignalR.connect();
    res.json({ success: true, status: f1SignalR.getStatus() });
  } catch (err: any) {
    res.status(500).json({ success: false, error: err.message });
  }
});

/**
 * Route: POST /api/f1-live/disconnect
 */
app.post('/api/f1-live/disconnect', (_req, res) => {
  f1SignalR.disconnect();
  res.json({ success: true, status: f1SignalR.getStatus() });
});

/**
 * Route: POST /api/f1-live/simulate
 * Starts live SignalR packet simulation for testing/demo when no active GP is on track.
 */
app.post('/api/f1-live/simulate', (_req, res) => {
  f1SignalR.startSimulation();
  res.json({ success: true, status: f1SignalR.getStatus() });
});

/**
 * Route: POST /api/f1-live/stop-simulate
 */
app.post('/api/f1-live/stop-simulate', (_req, res) => {
  f1SignalR.stopSimulation();
  res.json({ success: true, status: f1SignalR.getStatus() });
});

/**
 * Route: GET /api/f1-live/stream
 * Server-Sent Events (SSE) stream delivering real-time F1 timing updates to browser.
 */
app.get('/api/f1-live/stream', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  // Send initial snapshot
  const initialPayload = {
    type: 'snapshot',
    status: f1SignalR.getStatus(),
    sessionInfo: f1SignalR.sessionInfo,
    driverList: f1SignalR.driverList,
    timingData: f1SignalR.timingData,
    trackStatus: f1SignalR.trackStatus,
  };
  res.write(`data: ${JSON.stringify(initialPayload)}\n\n`);

  // Listener for live updates
  const updateListener = (update: any) => {
    res.write(`data: ${JSON.stringify({ type: 'update', ...update })}\n\n`);
  };

  f1SignalR.on('liveUpdate', updateListener);

  req.on('close', () => {
    f1SignalR.off('liveUpdate', updateListener);
    res.end();
  });
});

// Auto-start F1 SignalR connection in background
f1SignalR.connect().catch(() => {
  // Graceful handling if no live session is streaming
});

// Setup Vite middleware in dev or static files in production
async function startServer() {
  if (process.env.NODE_ENV !== 'production') {
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true, host: '0.0.0.0', port: PORT },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    app.use(express.static(path.join(__dirname, 'dist')));
    app.use((_req, res) => {
      res.sendFile(path.join(__dirname, 'dist', 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`F1Show Full-Stack Server running at http://0.0.0.0:${PORT}`);
  });
}

startServer();
