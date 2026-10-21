# F1Show - Replay & Live Commentary System (React)

F1Show is a replay-testable, real-time Formula 1 commentary and telemetry dashboard system. It turns public OpenF1 timing and telemetry data into an evidence-grounded broadcast commentary stream delivered by a simulated two-person commentary booth.

Every claim a commentator makes is backed by a deterministic observation or provenance record from OpenF1 (`position[x].position`, `laps[x].lap_duration`, etc.), eliminating hallucinations and ungrounded statements.

---

## Architecture & Features

### 1. Deterministic Event Collector
- Normalizes recorded OpenF1 session payloads across five families in strict deterministic total order:
  - `position` → position updates
  - `laps` → lap completions and sector durations
  - `pit` → pit stops, lane and stop durations
  - `stints` → tyre compound and stint age
  - `race_control` → flags, cautions, safety car deployments
- Unknowns and null values stay explicit; no fabricated values.

### 2. Two-Person Commentary Booth Simulation
- **Lead Announcer (Play-by-play)**: Energetic race calls, lap starts, pit stops, caution announcements.
- **Color Analyst (Tactical Expert)**: Tyre degradation, stint strategy, delta pace, championship impact.
- **Alternation with Priority Overrides**: Seats alternate strictly, with safety cars, red flags, or major incidents granting priority to the Lead seat.
- **Turn Modes**: Explicitly tagged `BUILD` (routine pacing) and `CLIMAX` (passes, pit stops, crashes, safety car).
- **Strict Evidence Citation Protocol**: Every turn carries citation tokens validated against supplied non-null evidence fields.
- **Audience Dialect Registers**:
  - `es-AR` (Argentine Spanish default): *voseo (vos tenés/podés), auto, neumáticos, nafta, boxes, auto de seguridad*
  - `es-419` (Neutral Latin American): *tuteo, auto, neumáticos, gasolina, pits, auto de seguridad*
  - `es-MX` (Mexican Spanish): *tuteo, auto, llantas, gasolina, pits*
  - `es-ES` (Spain): *coche, neumáticos, gasolina, boxes, coche de seguridad*
  - `en` (English): *car, tyres, fuel, pit lane, safety car*

### 3. Live F1 TV Timing Tower
- Running order 1 through 20 with position changes (+/- delta relative to grid).
- Driver numbers, 3-letter acronyms, team colors, and team affiliations.
- Tyre compound pills (Soft 🔴, Medium 🟡, Hard ⚪, Intermediate 🟢, Wet 🔵) with stint age.
- Gap to leader (`LEADER`, `+2.415s`, `+1 LAP`) and interval to the car ahead.
- Fastest lap purple badge indicator and last lap times.
- Real-time search and driver spotlight filter.

### 4. Window Salience & Race Stories
- Evaluates the window starting from race start (first completed lap) to current instant:
  - Fastest Lap derivation (evaluated over laps ≥ 2) with 2024 top-10 eligibility condition.
  - Pace outlier detection (fast < 0.75x median, slow > 1.25x median).
  - Biggest Gainers and Biggest Losers with all ties reported.
  - Busiest Driver (most position changes/updates in window).
  - Pit stop durations and active race control directives.

### 5. Provisional Championship Standings (WDC & WCC)
- Live in-race points calculation based on current running order:
  - 2024 FIA point scale: `[25, 18, 15, 12, 10, 8, 6, 4, 2, 1]`.
  - Base points from pre-race championship standings + current provisional points.
  - Drivers' Championship standings with tie-breaker conventions.
  - Constructors' Championship standings aggregated from driver points.

### 6. Interactive Telemetry & Evidence Inspector
- Click any evidence citation tag in the commentary transcript (`laps[4].lap_duration`, `position[0].position`) to inspect raw OpenF1 provenance records, observation timestamps, and audit verification.

### 7. Dual-Voice Audio Commentary (Web Speech API)
- Realistic dual-commentator text-to-speech with distinct pitch and rate profiles for Lead and Color analysts.
- Broadcast radio chime effects when new commentary airs.

---

## Running the Application

### Development
```bash
npm run dev
```
Listens on `http://0.0.0.0:3000`.

### Build
```bash
npm run build
```
Creates an optimized production bundle with TypeScript type-checking and Vite.
