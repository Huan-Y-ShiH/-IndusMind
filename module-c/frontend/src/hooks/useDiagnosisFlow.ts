import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { Tag } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { monitorApi, diagnoseApi } from '../services/api';
import { generateCmapssSensorData } from '../services/sensorSimulator';
import { rulToRiskLevel } from '../utils/riskLevel';
import { useDeviceStore } from '../stores/useDeviceStore';
import type {
  MonitorResult,
  DiagnoseResult,
  DiagnoseJobResponse,
} from '../services/api';

type FlowStage =
  | 'idle'
  | 'analyzing'
  | 'monitor_done'
  | 'submitting_diagnose'
  | 'polling'
  | 'complete'
  | 'error';

export function useDiagnosisFlow(deviceId: string | undefined) {
  const devices = useDeviceStore((s) => s.devices);

  const selectedDevice = useMemo(
    () => devices.find((d) => d.id === deviceId),
    [devices, deviceId],
  );

  const [stage, setStage] = useState<FlowStage>('idle');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [erroredStep, setErroredStep] = useState<number | undefined>(undefined);
  const [lastProgress, setLastProgress] = useState<number | undefined>(undefined);

  const [monitorResult, setMonitorResult] = useState<MonitorResult | null>(null);
  const [diagnoseResult, setDiagnoseResult] = useState<DiagnoseResult | null>(null);
  const [diagnoseStatus, setDiagnoseStatus] = useState<string>('');
  const [diagnoseProgress, setDiagnoseProgress] = useState<number>(0);
  const [jobId, setJobId] = useState<string | null>(null);

  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const abortRef = useRef(false);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, []);

  const resetFlow = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    abortRef.current = false;
    setStage('idle');
    setErrorMsg(null);
    setErroredStep(undefined);
    setLastProgress(undefined);
    setMonitorResult(null);
    setDiagnoseResult(null);
    setDiagnoseStatus('');
    setDiagnoseProgress(0);
    setJobId(null);
  }, []);

  const startDiagnosis = useCallback(async () => {
    if (!deviceId || !selectedDevice) return;

    resetFlow();
    abortRef.current = false;
    setStage('analyzing');

    let phase: 'monitor' | 'diagnose_submit' | 'poll' = 'monitor';

    try {
      const sensorData = generateCmapssSensorData(30, deviceId, selectedDevice.rulHours);

      const payload = {
        device_id: deviceId,
        device_model: selectedDevice.model,
        sensor_data: sensorData,
        operating_settings: { op1: 25, op2: 50, op3: 100 },
        dataset: 'FD001' as const,
      };

      const aResult = await monitorApi.analyze(payload);

      if (abortRef.current) return;

      setMonitorResult(aResult);
      phase = 'diagnose_submit';
      setStage('submitting_diagnose');

      const riskLevel = rulToRiskLevel(aResult.rul_predicted);

      const bPayload = {
        event_id: aResult.event_id,
        device_id: aResult.device_id,
        timestamp: aResult.timestamp,
        model_version: aResult.model_version,
        anomaly_type: aResult.anomaly_type || 'rul_anomaly',
        rul_hours: aResult.rul_predicted,
        rul_series: aResult.rul_series,
        risk_level: riskLevel,
        feature_attribution: [],
        pseudo_attribution: (aResult.pseudo_attribution || []).map((attr) => ({
          ...attr,
          deviation_strength:
            attr.direction === 'high' ? attr.contribution : -attr.contribution,
        })),
      };

      const bResponse = await diagnoseApi.submitJob(bPayload);

      if (abortRef.current) return;

      const newJobId = bResponse.job_id;
      setJobId(newJobId);
      setDiagnoseStatus(bResponse.status);
      setDiagnoseProgress(bResponse.progress);

      if (bResponse.status === 'succeeded' && bResponse.result) {
        setDiagnoseResult(bResponse.result);
        setDiagnoseProgress(100);
        setStage('complete');
        return;
      }
      if (bResponse.status === 'failed') {
        setErroredStep(2);
        setLastProgress(25);
        setErrorMsg(bResponse.error || 'Diagnose job failed');
        setStage('error');
        return;
      }

      phase = 'poll';
      setStage('polling');
      pollTimerRef.current = setInterval(async () => {
        try {
          const pollResp: DiagnoseJobResponse = await diagnoseApi.pollJob(newJobId);

          setDiagnoseStatus(pollResp.status);
          setDiagnoseProgress(pollResp.progress);

          if (pollResp.status === 'succeeded' && pollResp.result) {
            setDiagnoseResult(pollResp.result);
            setDiagnoseProgress(100);
            setStage('complete');
            if (pollTimerRef.current) {
              clearInterval(pollTimerRef.current);
              pollTimerRef.current = null;
            }
          } else if (pollResp.status === 'failed') {
            setErroredStep(3);
            setLastProgress(50);
            setErrorMsg(pollResp.error || 'Diagnose job failed');
            setStage('error');
            if (pollTimerRef.current) {
              clearInterval(pollTimerRef.current);
              pollTimerRef.current = null;
            }
          }
        } catch {
          // Poll error — keep trying unless aborted
        }
      }, 3000);

      setTimeout(() => {
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current);
          pollTimerRef.current = null;
          if (stage !== 'complete') {
            setErroredStep(3);
            setLastProgress(50);
            setErrorMsg('Diagnose job timed out after 120 seconds');
            setStage('error');
          }
        }
      }, 120000);
    } catch (err: unknown) {
      if (abortRef.current) return;
      const error = err as { response?: { data?: { msg?: string; detail?: string } }; message?: string };
      const msg =
        error?.response?.data?.msg ||
        error?.response?.data?.detail ||
        error?.message ||
        'Unknown error';
      setErrorMsg(msg);

      if (phase === 'monitor') {
        setErroredStep(1);
        setLastProgress(0);
      } else if (phase === 'diagnose_submit') {
        setErroredStep(2);
        setLastProgress(25);
      }
      setStage('error');
    }
  }, [deviceId, selectedDevice, resetFlow, stage]);

  const formatTimestamp = (ts: string) => {
    try {
      return new Date(ts).toLocaleString();
    } catch {
      return ts;
    }
  };

  const getAttributionColor = (direction: string) => {
    if (direction === 'high' || direction === 'positive') return '#ef4444';
    if (direction === 'low' || direction === 'negative') return '#3b82f6';
    return '#f59e0b';
  };

  const getStageBadge = (): React.ReactNode => {
    switch (stage) {
      case 'analyzing':
        return React.createElement(Tag, { color: 'processing', icon: React.createElement(LoadingOutlined, { spin: true }) }, 'ANALYZING');
      case 'submitting_diagnose':
      case 'polling':
        return React.createElement(Tag, { color: 'processing', icon: React.createElement(ClockCircleOutlined) }, 'DIAGNOSING');
      case 'complete':
        return React.createElement(Tag, { color: 'success', icon: React.createElement(CheckCircleOutlined) }, 'COMPLETE');
      case 'error':
        return React.createElement(Tag, { color: 'error', icon: React.createElement(CloseCircleOutlined) }, 'ERROR');
      default:
        return null;
    }
  };

  const getUrgencyColor = (urgency: string) => {
    const u = urgency.toLowerCase();
    if (u.includes('critical') || u.includes('emergency')) return 'red';
    if (u.includes('high')) return 'orange';
    if (u.includes('medium')) return 'gold';
    return 'blue';
  };

  const isRunning = ['analyzing', 'submitting_diagnose', 'polling'].includes(stage);
  const hasMonitorResult = stage !== 'idle' && stage !== 'analyzing';
  const hasDiagnoseActivity = ['submitting_diagnose', 'polling', 'complete', 'error'].includes(stage);

  return {
    stage,
    errorMsg,
    erroredStep,
    lastProgress,
    monitorResult,
    diagnoseResult,
    diagnoseStatus,
    diagnoseProgress,
    jobId,
    startDiagnosis,
    resetFlow,
    isRunning,
    hasMonitorResult,
    hasDiagnoseActivity,
    formatTimestamp,
    getAttributionColor,
    getStageBadge,
    getUrgencyColor,
  };
}
