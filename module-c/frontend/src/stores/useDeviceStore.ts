import { create } from 'zustand';
import type { DeviceInfo, AlertItem } from '../types/device';

// ── Store ─────────────────────────────────────────────────────────

interface DeviceStore {
  devices: DeviceInfo[];
  selectedDeviceId: string | null;
  alerts: AlertItem[];
  setDevices: (devices: DeviceInfo[]) => void;
  selectDevice: (id: string | null) => void;
  addAlert: (alert: AlertItem) => void;
  acknowledgeAlert: (id: string) => void;
  clearAlerts: () => void;
}

export const useDeviceStore = create<DeviceStore>((set) => ({
  devices: [],
  selectedDeviceId: null,
  alerts: [],

  setDevices: (devices) => set({ devices }),

  selectDevice: (id) => set({ selectedDeviceId: id }),

  addAlert: (alert) =>
    set((state) => ({
      alerts: [alert, ...state.alerts].slice(0, 200), // 保留最近200条
    })),

  acknowledgeAlert: (id) =>
    set((state) => ({
      alerts: state.alerts.map((a) =>
        a.id === id ? { ...a, acknowledged: true } : a,
      ),
    })),

  clearAlerts: () => set({ alerts: [] }),
}));
