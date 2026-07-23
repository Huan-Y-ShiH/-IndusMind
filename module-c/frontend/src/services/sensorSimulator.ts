import type { SensorPoint } from './api';

/**
 * Generate `count` realistic CMAPSS FD001-like sensor points.
 *
 * Sensor meanings (from the API contract):
 *   s1  — Fan inlet temperature (°R)         ~518.67
 *   s2  — LPC outlet temperature (°R)        ~642
 *   s3  — HPC outlet temperature (°R)        ~1590
 *   s4  — LPT outlet temperature (°R)        ~1400
 *   s5  — Fan inlet pressure (psia)          ~14.7
 *   s6  — Bypass duct pressure (psia)        ~21.6
 *   s7  — HPC outlet pressure (psia)         ~554
 *   s8  — Physical fan speed (rpm)           ~2388
 *   s9  — Physical core speed (rpm)          ~9046
 *   s10 — Engine pressure ratio              ~1.02
 *   s11 — HPC outlet static pressure (psia)  ~48
 *   s12 — Fuel flow ratio (pps/psia)         ~521
 *   s13 — Corrected fan speed (rpm)          ~2388
 *   s14 — Corrected core speed (rpm)         ~9046
 *   s15 — Bypass ratio                       ~8.4
 *   s16 — Bleed enthalpy                     ~393
 *   s17 — Demanded fan speed (rpm)           ~2388
 *   s18 — Demanded corrected fan speed (rpm) ~2388
 *   s19 — HPT coolant bleed                  ~39
 *   s20 — LPT coolant bleed                  ~23
 *   s21 — Ambient temp (F)                   ~65
 *
 * Life stage: per-device cumulative offset on s3/s4/s7/s12 plus small per-step drift.
 */
export function generateCmapssSensorData(count: number = 30, deviceId?: string, mockRulHours?: number): SensorPoint[] {
  let lifeStage: number;

  if (mockRulHours !== undefined) {
    // Use mock RUL hours to derive life stage — keeps Dashboard list and diagnosis consistent
    // mock RUL range: 5–5000 cycles → lifeStage = 1 − rulHours/5000
    lifeStage = 1 - Math.max(0, Math.min(mockRulHours, 5000)) / 5000;
  } else {
    // Fallback: deterministic hash from device ID
    let seed = 1;
    if (deviceId) {
      const match = deviceId.match(/(\d+)/);
      if (match) seed = parseInt(match[1], 10);
    }
    const hash = (seed * 17 + 31) % 100;
    lifeStage = hash / 100;
  }

  const points: SensorPoint[] = [];
  const baseTime = Date.now() - count * 2000; // 2s intervals

  // Base values (FD001 nominal operating range)
  const base: Record<string, number> = {
    s1: 518.67,
    s2: 642.0,
    s3: 1588.0,
    s4: 1398.0,
    s5: 14.7,
    s6: 21.6,
    s7: 554.0,
    s8: 2388.0,
    s9: 9046.0,
    s10: 1.02,
    s11: 48.0,
    s12: 521.0,
    s13: 2388.0,
    s14: 9046.0,
    s15: 8.4,
    s16: 393.0,
    s17: 2388.0,
    s18: 2388.0,
    s19: 39.0,
    s20: 23.0,
    s21: 65.0,
  };

  // Noise scale per sensor
  const noise: Record<string, number> = {
    s1: 0.3,
    s2: 0.5,
    s3: 2.0,
    s4: 2.0,
    s5: 0.05,
    s6: 0.1,
    s7: 2.0,
    s8: 2.0,
    s9: 5.0,
    s10: 0.01,
    s11: 0.5,
    s12: 1.0,
    s13: 2.0,
    s14: 5.0,
    s15: 0.02,
    s16: 1.0,
    s17: 2.0,
    s18: 2.0,
    s19: 0.2,
    s20: 0.2,
    s21: 0.3,
  };

  // Key sensors with their degradation ranges at end-of-life
  // Offset + drift caps keep values within FD001 training distribution
  const maxBaseOffset: Record<string, number> = {
    s3: 20,  // HPC outlet temp: max ~1630 (FD001 training max ~1640)
    s4: 12,  // LPT outlet temp: max ~1420
    s7: 4,   // HPC pressure: max ~558
    s11: 4,  // HPC static pressure
    s12: 15, // Fuel flow: max ~550
    s15: -1, // Bypass ratio (decreases)
    s20: 3,  // LPT coolant bleed
  };

  // Apply baseline offset (lifeStage controls the starting point)
  const adjustedBase: Record<string, number> = { ...base };
  for (const [key, maxDrift] of Object.entries(maxBaseOffset)) {
    adjustedBase[key] = base[key] + maxDrift * lifeStage;
  }

  // Per-step degradation rate scaled by lifeStage
  // lifeStage 0.02: driftScale ~0.5 → flat
  // lifeStage 0.95: driftScale ~5.0 → ~40 units s3 drift over 30 steps
  // s3 range: healthy ~1588→1590, alert ~1608→1648 (within FD001)
  const driftScale = 0.5 + lifeStage * 5;

  const drift: Record<string, number> = {
    s2: 0.05 * driftScale,
    s3: 0.25 * driftScale,
    s4: 0.18 * driftScale,
    s7: 0.05 * driftScale,
    s11: 0.08 * driftScale,
    s12: 0.15 * driftScale,
    s15: -0.02 * driftScale,
    s20: 0.04 * driftScale,
  };

  for (let i = 0; i < count; i++) {
    const sensor = {} as Record<string, number>;
    for (let j = 1; j <= 21; j++) {
      const key = `s${j}`;
      const b = adjustedBase[key] || base[key] || 0;
      const n = noise[key] || 0.5;
      const d = (drift[key] || 0) * i;
      sensor[key] = +(b + d + (Math.random() - 0.5) * 2 * n).toFixed(4);
    }

    points.push({
      timestamp: new Date(baseTime + i * 2000).toISOString(),
      s1: sensor.s1,
      s2: sensor.s2,
      s3: sensor.s3,
      s4: sensor.s4,
      s5: sensor.s5,
      s6: sensor.s6,
      s7: sensor.s7,
      s8: sensor.s8,
      s9: sensor.s9,
      s10: sensor.s10,
      s11: sensor.s11,
      s12: sensor.s12,
      s13: sensor.s13,
      s14: sensor.s14,
      s15: sensor.s15,
      s16: sensor.s16,
      s17: sensor.s17,
      s18: sensor.s18,
      s19: sensor.s19,
      s20: sensor.s20,
      s21: sensor.s21,
    });
  }

  return points;
}
