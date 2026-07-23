import { create } from 'zustand';
import { historyApi } from '../services/api';
import type { DiagnosisRecord } from '../types/device';

interface DiagnosisHistoryStore {
  records: DiagnosisRecord[];
  loading: boolean;
  error: string | null;
  fetchRecords: () => Promise<void>;
  addRecord: (record: DiagnosisRecord) => Promise<void>;
  removeRecord: (id: string) => Promise<void>;
  clearAll: () => Promise<void>;
  getRecordsByDevice: (deviceId: string) => DiagnosisRecord[];
}

function getErrorMessage(err: unknown): string {
  const axiosErr = err as { response?: { data?: { msg?: string } }; message?: string };
  return axiosErr?.response?.data?.msg || axiosErr?.message || 'Request failed';
}

export const useDiagnosisHistoryStore = create<DiagnosisHistoryStore>((set, get) => ({
  records: [],
  loading: false,
  error: null,

  fetchRecords: async () => {
    set({ loading: true, error: null });
    try {
      const records = await historyApi.list();
      set({ records, loading: false });
    } catch (err) {
      set({ loading: false, error: getErrorMessage(err) });
    }
  },

  addRecord: async (record) => {
    try {
      await historyApi.create(record);
      set((state) => ({
        records: [record, ...state.records.filter((r) => r.id !== record.id)],
      }));
    } catch {
      // Fire-and-forget from diagnosis flow — avoid blocking UI on save failure
    }
  },

  removeRecord: async (id) => {
    try {
      await historyApi.delete(id);
      set((state) => ({
        records: state.records.filter((r) => r.id !== id),
      }));
    } catch (err) {
      set({ error: getErrorMessage(err) });
    }
  },

  clearAll: async () => {
    const { records } = get();
    try {
      await Promise.all(records.map((r) => historyApi.delete(r.id)));
      set({ records: [] });
    } catch (err) {
      set({ error: getErrorMessage(err) });
    }
  },

  getRecordsByDevice: (deviceId) =>
    get().records.filter((r) => r.deviceId === deviceId),
}));
