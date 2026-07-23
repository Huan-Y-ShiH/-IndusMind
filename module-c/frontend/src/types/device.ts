export interface DeviceInfo {
  id: string;
  name: string;
  farm: string;
  model: string;
  status: 'running' | 'alert' | 'stopped';
  lastMaintenance: string;
  rulHours?: number;
}

export interface AlertItem {
  id: string;
  deviceId: string;
  deviceName: string;
  type: 'alert' | 'workflow_update' | 'device_status';
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  timestamp: string;
  acknowledged: boolean;
}

export interface SensorSnapshot {
  timestamp: string;
  vibration_x: number;
  vibration_y: number;
  vibration_z: number;
  temperature: number;
  rpm: number;
  pressure: number;
  flow_rate: number;
  current: number;
  voltage: number;
  power: number;
  noise_level: number;
  humidity: number;
  oil_temperature: number;
  bearing_temperature: number;
  displacement_x: number;
  displacement_y: number;
  displacement_z: number;
  torque: number;
  load: number;
  status_code: number;
  phase_current_l1: number;
  phase_current_l2: number;
  phase_current_l3: number;
}
