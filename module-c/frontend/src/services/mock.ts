/**
 * Mock data for development and testing.
 * Provides realistic data for devices, sensor readings, alerts, and diagnosis results.
 */

import type { DeviceInfo, AlertItem, SensorSnapshot } from '../types/device';
import { FARMS, MODELS } from '../constants/devices';
import { rulToRiskLevel } from '../utils/riskLevel';

// ── Device list: 200 wind turbines ─────────────────────────────────

function generateRUL(deviceId: number): number {
  // 使用 deviceId 作为 seed 生成确定性但多样化的 RUL
  // 大部分设备健康(55%在 1500-5000)，少部分预警(25%在 200-1500)，极少数危险(15%在 0-200)
  const seed = (deviceId * 17 + 31) % 100;
  if (seed < 15) {
    // 15% critical: 5-200 cycles
    return 5 + Math.floor((seed / 15) * 195);
  } else if (seed < 40) {
    // 25% warning: 200-1500 cycles
    return 200 + Math.floor(((seed - 15) / 25) * 1300);
  } else if (seed < 45) {
    // 5% stopped (over-maintenance, no need to monitor): RUL > 4000
    return 4000 + Math.floor(((seed - 40) / 5) * 1000);
  } else {
    // 55% healthy: 1500-5000 cycles
    return 1500 + Math.floor(((seed - 45) / 55) * 3500);
  }
}

function generateDevice(id: number): DeviceInfo {
  const farmIdx = Math.floor((id - 1) / 50);
  const rul = generateRUL(id);
  // 根据 RUL 推导 status
  let status: DeviceInfo['status'];
  if (rul < 200) {
    status = 'alert';  // 危险: RUL < 4%
  } else if (rul < 800) {
    status = 'alert';  // 预警: RUL 4%-16%
  } else if (rul > 3500) {
    status = 'stopped';  // 超健康/停维
  } else {
    status = 'running';
  }
  return {
    id: `WT-${String(id).padStart(3, '0')}`,
    name: `风机 WT-${String(id).padStart(3, '0')}`,
    farm: FARMS[farmIdx],
    model: MODELS[id % MODELS.length],
    status,
    rulHours: rul,
    lastMaintenance: `2025-${String((id % 12) + 1).padStart(2, '0')}-${String((id % 28) + 1).padStart(2, '0')}`,
  };
}

export const mockDevices: DeviceInfo[] = Array.from({ length: 200 }, (_, i) =>
  generateDevice(i + 1),
);

// ── Sensor snapshot generator (21 fields) ──────────────────────────

export function generateSensorSnapshot(deviceId: string, rulHours?: number): SensorSnapshot {
  const seed = parseInt(deviceId.replace('WT-', ''), 10) || 1;
  const now = new Date().toISOString();
  const lifeStage = rulHours !== undefined ? 1 - Math.max(0, Math.min(rulHours, 5000)) / 5000 : 0;
  const degrade = 1 + lifeStage * 4; // 0→1x, 100%→5x for vibration/temp
  const rnd = () => Math.random();

  return {
    timestamp: now,
    vibration_x: +(0.05 * degrade + (seed % 10) * 0.02 * degrade + rnd() * 0.1 * degrade).toFixed(4),
    vibration_y: +(0.04 * degrade + (seed % 8) * 0.02 * degrade + rnd() * 0.08 * degrade).toFixed(4),
    vibration_z: +(0.03 * degrade + (seed % 6) * 0.02 * degrade + rnd() * 0.06 * degrade).toFixed(4),
    temperature: +(60 + lifeStage * 30 + (seed % 30) + rnd() * 5).toFixed(1),
    rpm: +(1400 - lifeStage * 300 + (seed % 200) + rnd() * 50).toFixed(0),
    pressure: 2.2 + Math.random() * 0.4,
    flow_rate: 10 + Math.random() * 5,
    current: 4.0 + Math.random() * 1.5,
    voltage: 378 + Math.random() * 4,
    power: 1.5 + Math.random() * 0.5,
    noise_level: 70 + Math.random() * 15,
    humidity: 40 + Math.random() * 20,
    oil_temperature: 50 + Math.random() * 10,
    bearing_temperature: 55 + (seed % 20) + Math.random() * 5,
    displacement_x: Math.random() * 0.005,
    displacement_y: Math.random() * 0.005,
    displacement_z: Math.random() * 0.005,
    torque: 10 + Math.random() * 3,
    load: 0.5 + Math.random() * 0.4,
    status_code: seed % 7 === 0 ? 1 : 0,
    phase_current_l1: 4.0 + Math.random() * 1.0,
    phase_current_l2: 4.0 + Math.random() * 1.0,
    phase_current_l3: 4.0 + Math.random() * 1.0,
  };
}

// ── Alert generator ────────────────────────────────────────────────

const ALERT_MESSAGES = [
  '振动幅值超过阈值3倍，建议检查轴承状态',
  '轴承温度异常升高，可能存在润滑不足',
  '发电机转速波动异常，建议检查变频器',
  '齿轮箱油温偏高，散热系统可能堵塞',
  '叶片角度偏差超出允许范围',
  '变桨系统响应延迟，需校准',
  '偏航系统累计偏差过大',
  '塔筒振动频率接近共振点',
];

/** Generate alerts FROM actual device state — unified with Device List status and RUL. */
export function generateAlertsFromDevices(devices: DeviceInfo[]): AlertItem[] {
  const alertDevices = devices.filter((d) => d.status === 'alert');
  if (alertDevices.length === 0) return [];

  return alertDevices
    .map((device) => {
      const rul = device.rulHours ?? 500;
      const riskLevel = rulToRiskLevel(rul);

      // Deterministic message from device ID
      const idNum = parseInt(device.id.replace(/\D/g, ''), 10) || 1;
      const msgIdx = idNum % ALERT_MESSAGES.length;

      // Deterministic timestamp offset: more critical = more recent
      const offsetMinutes = rul < 50 ? idNum % 5 : rul < 200 ? 5 + (idNum % 15) : 15 + (idNum % 30);
      const ts = new Date(Date.now() - offsetMinutes * 60000).toISOString();

      return {
        id: `ALT-${device.id}-${rul}`,
        deviceId: device.id,
        deviceName: device.name,
        type: 'alert' as const,
        riskLevel,
        message: ALERT_MESSAGES[msgIdx],
        timestamp: ts,
        acknowledged: false,
      } satisfies AlertItem;
    })
    .sort((a, b) => {
      // Sort: critical first, then by RUL ascending (most dangerous first)
      const order = { critical: 0, high: 1, medium: 2, low: 3 };
      const ra = order[a.riskLevel] ?? 99;
      const rb = order[b.riskLevel] ?? 99;
      if (ra !== rb) return ra - rb;
      return (parseInt(a.deviceId.replace(/\D/g, ''), 10) || 0) - (parseInt(b.deviceId.replace(/\D/g, ''), 10) || 0);
    });
}

/** Legacy alias — kept for backward compat in AlertCenter fallback. Now uses device-aware generation. */
export function generateAlert(): AlertItem {
  const device = mockDevices[Math.floor(Math.random() * mockDevices.length)];
  const idNum = parseInt(device.id.replace(/\D/g, ''), 10) || 1;
  const msgIdx = idNum % ALERT_MESSAGES.length;
  const rul = device.rulHours ?? 500;
  const riskLevel = rulToRiskLevel(rul);

  return {
    id: `ALT-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    deviceId: device.id,
    deviceName: device.name,
    type: 'alert',
    riskLevel,
    message: ALERT_MESSAGES[msgIdx],
    timestamp: new Date().toISOString(),
    acknowledged: false,
  };
}

// ── Diagnosis mock ─────────────────────────────────────────────────

export const mockDiagnosisResult = {
  root_cause: '轴承内圈疲劳剥落，导致三轴振动异常升高，伴随温度持续上升。初步判断为润滑脂老化引起的金属表面接触疲劳。',
  confidence: 0.88,
  evidence: [
    '三轴振动幅值均超过正常范围 3 倍',
    '轴承温度在过去 2 小时内上升 14°C',
    '噪声频谱分析显示 1x~3x 轴承特征频率',
    '润滑油光谱分析显示铁含量超标',
  ],
  related_cases: ['CASE-2024-0321', 'CASE-2024-0876', 'CASE-2025-0142'],
};

export const mockSolutionResult = {
  solution_id: `SOL-${new Date().toISOString().slice(0, 10)}-001`,
  steps: [
    '停机并锁定电源，悬挂检修牌',
    '拆卸联轴器护罩及联轴器',
    '拆卸轴承端盖，取出旧轴承',
    '清洁轴承座并检查轴颈磨损',
    '安装新轴承 6205-2RS，加注 SKF LGHP2 润滑脂',
    '回装并检查轴对中（径向偏差 < 0.05mm）',
    '试运行30分钟，监测振动和温度',
  ],
  parts_needed: [
    '6205-2RS 深沟球轴承 × 2 (NSK/SKF)',
    'SKF LGHP2 高温润滑脂 400g',
    '轴承端盖密封垫 × 2',
  ],
  estimated_hours: 4.0,
  priority: 'high' as const,
};
