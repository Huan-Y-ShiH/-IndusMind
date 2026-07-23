import axios from 'axios';
import type { DiagnosisRecord } from '../types/device';

// ═══════════════════════════════════════════════════════════════════
//  Shared axios instance — still used by mock-based pages
// ═══════════════════════════════════════════════════════════════════

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export default apiClient;

// ═══════════════════════════════════════════════════════════════════
//  Module A — Monitor API (RUL Prediction)
//  Goes through Vite proxy → nginx → remote server
// ═══════════════════════════════════════════════════════════════════

const monitorClient = axios.create({
  baseURL: '/api/v1/monitor',
  timeout: 60000,
});

// ═══════════════════════════════════════════════════════════════════
//  Module B — Diagnose API (via Vite proxy → Cloudflare Tunnel)
//  Avoids CORS — browser sees same-origin /diagnose
// ═══════════════════════════════════════════════════════════════════

function getDiagnoseApiKey(): string {
  try {
    const stored = localStorage.getItem('indusmind_diagnose_api_key');
    if (stored) return stored;
  } catch {}
  return '43489d90737e386c979d5278224a1e018f7b68e0d1bb1265';
}

function createDiagnoseClient() {
  return axios.create({
    baseURL: '/diagnose',
    timeout: 120000,
    headers: {
      'X-Api-Key': getDiagnoseApiKey(),
      'Content-Type': 'application/json',
    },
  });
}

let _diagnoseClient: ReturnType<typeof createDiagnoseClient> | null = null;

function getDiagnoseClient() {
  if (!_diagnoseClient) {
    _diagnoseClient = createDiagnoseClient();
  }
  return _diagnoseClient;
}

// ═══════════════════════════════════════════════════════════════════
//  Type definitions matching the API contracts
// ═══════════════════════════════════════════════════════════════════

export interface SensorPoint {
  timestamp: string; // ISO-8601
  s1: number;
  s2: number;
  s3: number;
  s4: number;
  s5: number;
  s6: number;
  s7: number;
  s8: number;
  s9: number;
  s10: number;
  s11: number;
  s12: number;
  s13: number;
  s14: number;
  s15: number;
  s16: number;
  s17: number;
  s18: number;
  s19: number;
  s20: number;
  s21: number;
}

export interface MonitorResult {
  event_id: string;
  device_id: string;
  device_model: string;
  timestamp: string;
  model_version: string;
  rul_predicted: number;
  rul_series: number[];
  anomaly_score: number | null;
  anomaly_type: string | null;
  pseudo_attribution: { feature: string; direction: string; contribution: number }[] | null;
  feature_attribution: null;
  raw_data_ref: string | null;
}

export interface DiagnoseResult {
  event_id: string;
  device_id: string;
  diagnosis: {
    root_cause: string;
    l1: string | null;
    l2: string | null;
    l3: string | null;
    confidence: number;
    need_human_review: boolean;
    logic_path: string[];
    mechanism: string;
    evidence: string;
    evidence_level: string;
  };
  solution: {
    urgency: string;
    action_plan: string[];
    matched_tickets: string[];
  };
  report_markdown: string;
  rag_hit_count: number;
}

export interface DiagnoseJobResponse {
  job_id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  progress: number; // 0 | 50 | 100
  result?: DiagnoseResult;
  error?: string;
}

export interface MonitorAnalyzePayload {
  device_id: string;
  device_model: string;
  sensor_data: SensorPoint[];
  operating_settings: { op1: number; op2: number; op3: number };
  dataset: 'FD001' | 'FD002' | 'FD003' | 'FD004' | 'PHM08';
}

export interface DiagnoseJobPayload {
  event_id: string;
  device_id: string;
  timestamp: string;
  model_version: string;
  anomaly_type: string;
  rul_hours: number;
  rul_series: number[];
  risk_level: string;
  feature_attribution: null | { feature: string; direction: string; contribution: number }[];
  pseudo_attribution: { feature: string; direction: string; contribution: number; deviation_strength?: number }[] | null;
}

// ═══════════════════════════════════════════════════════════════════
//  API methods
// ═══════════════════════════════════════════════════════════════════

export const monitorApi = {
  analyze: (payload: MonitorAnalyzePayload): Promise<MonitorResult> =>
    monitorClient.post('/analyze', payload).then((r) => r.data.data as MonitorResult),
};

// ── Retry helper: retry on 502/503/504 or network error ──────────
async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries = 3,
  delayMs = 2000,
): Promise<T> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number }; code?: string };
      const status = axiosErr?.response?.status;
      const isRetryable =
        !status || // network error (no response)
        status === 502 ||
        status === 503 ||
        status === 504;
      if (attempt === maxRetries || !isRetryable) throw err;
      await new Promise((r) => setTimeout(r, delayMs));
    }
  }
  throw new Error('unreachable');
}

export const diagnoseApi = {
  submitJob: (payload: DiagnoseJobPayload): Promise<DiagnoseJobResponse> =>
    withRetry(() =>
      getDiagnoseClient().post('/jobs', payload).then((r) => r.data.data as DiagnoseJobResponse),
    ),
  pollJob: (jobId: string): Promise<DiagnoseJobResponse> =>
    getDiagnoseClient().get(`/jobs/${jobId}`).then((r) => r.data.data as DiagnoseJobResponse),
};

export const historyApi = {
  list: (): Promise<DiagnosisRecord[]> =>
    apiClient.get('/v1/history').then((r) => r.data.data),
  get: (id: string): Promise<DiagnosisRecord> =>
    apiClient.get(`/v1/history/${id}`).then((r) => r.data.data),
  create: (record: DiagnosisRecord): Promise<void> =>
    apiClient.post('/v1/history', record),
  delete: (id: string): Promise<void> =>
    apiClient.delete(`/v1/history/${id}`),
};

