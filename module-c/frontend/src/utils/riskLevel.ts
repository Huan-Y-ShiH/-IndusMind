import { RUL_CRITICAL_THRESHOLD, RUL_HIGH_THRESHOLD, RUL_MEDIUM_THRESHOLD } from '../constants/devices';

export type RiskLevel = 'critical' | 'high' | 'medium' | 'low';

export function rulToRiskLevel(rulHours: number): RiskLevel {
  if (rulHours < RUL_CRITICAL_THRESHOLD) return 'critical';
  if (rulHours < RUL_HIGH_THRESHOLD) return 'high';
  if (rulHours < RUL_MEDIUM_THRESHOLD) return 'medium';
  return 'low';
}
