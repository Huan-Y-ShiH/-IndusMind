import type { AlertItem } from '../types/device';
import { mockDiagnosisResult, mockSolutionResult } from './mock';

const SENSOR_KEYWORD_MAP: Record<string, string[]> = {
  '振动': ['vibration_x', 'vibration_y', 'vibration_z'],
  '轴承': ['bearing_temperature'],
  '油温': ['oil_temperature'],
  '转速': ['rpm'],
  '叶片': ['displacement_x', 'displacement_y', 'displacement_z'],
  '变桨': ['phase_current_l1', 'phase_current_l2', 'phase_current_l3'],
  '偏航': ['torque'],
  '塔筒': ['noise_level'],
};

const FALLBACK_SENSORS = [
  'vibration_x', 'vibration_y', 'vibration_z',
  'bearing_temperature', 'oil_temperature', 'rpm',
  'displacement_x', 'phase_current_l1', 'torque', 'noise_level',
];

export interface ExtendedAlertData {
  deviceId: string;
  riskLevel: string;
  message: string;
  anomalyScore: number;
  abnormalSensors: string[];
  diagnosis: string;
  solution: string[];
  rulHours: number;
}

/** Generate complete alert diagnostic data from riskLevel + message */
export function buildExtendedAlertData(record: AlertItem, deviceRul?: number): ExtendedAlertData {
  // 1. anomalyScore — random within risk-level range
  const scoreRanges: Record<string, [number, number]> = {
    critical: [0.85, 0.98],
    high: [0.70, 0.90],
    medium: [0.40, 0.75],
    low: [0.05, 0.40],
  };
  const [lo, hi] = scoreRanges[record.riskLevel] || [0.05, 0.40];
  const anomalyScore = +(lo + Math.random() * (hi - lo)).toFixed(4);

  // 2. abnormalSensors — infer from message keywords, random 2-4
  const matchedSensors = new Set<string>();
  for (const [keyword, sensors] of Object.entries(SENSOR_KEYWORD_MAP)) {
    if (record.message.includes(keyword)) {
      sensors.forEach((s) => matchedSensors.add(s));
    }
  }
  // If no keyword matched, pick a few random fallback sensors
  if (matchedSensors.size === 0) {
    const shuffled = [...FALLBACK_SENSORS].sort(() => Math.random() - 0.5);
    for (let i = 0; i < Math.min(3, shuffled.length); i++) {
      matchedSensors.add(shuffled[i]);
    }
  }
  // Select 2-4 randomly from matched pool
  const pool = Array.from(matchedSensors).sort(() => Math.random() - 0.5);
  const count = Math.min(4, Math.max(2, pool.length));
  const abnormalSensors = pool.slice(0, count);

  // 3. diagnosis — use mock root_cause, append alert message for context
  const diagnosis = `${mockDiagnosisResult.root_cause}\n\n触发告警: ${record.message}`;

  // 4. solution — use mock steps directly
  const solution = mockSolutionResult.steps;

  // 5. rulHours — use device's actual RUL from store if available, else fallback random
  const rulHours = deviceRul !== undefined ? deviceRul : (() => {
    const rulRanges: Record<string, [number, number]> = {
      critical: [2, 180],
      high: [100, 600],
      medium: [500, 2500],
      low: [2000, 5000],
    };
    const [rLo, rHi] = rulRanges[record.riskLevel] || [2000, 5000];
    return Math.floor(rLo + Math.random() * (rHi - rLo));
  })();

  return {
    deviceId: record.deviceId,
    riskLevel: record.riskLevel,
    message: record.message,
    anomalyScore,
    abnormalSensors,
    diagnosis,
    solution,
    rulHours,
  };
}
