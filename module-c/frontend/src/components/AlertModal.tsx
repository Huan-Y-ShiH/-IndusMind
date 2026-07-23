import React from 'react';
import { Modal, Tag, Descriptions } from 'antd';
import RULGauge from './RULGauge';

/**
 * AlertModal — Alert detail modal (暗夜工控风格).
 *
 * Shows alert details (device info, anomaly sensors, diagnosis), RUL gauge,
 * and recommended maintenance solution steps.
 */
interface AlertModalProps {
  open: boolean;
  alertData?: {
    deviceId: string;
    riskLevel: string;
    message: string;
    anomalyScore?: number;
    abnormalSensors?: string[];
    diagnosis?: string;
    solution?: string[];
    rulHours?: number;
  } | null;
  onClose: () => void;
}

const AlertModal: React.FC<AlertModalProps> = ({ open, alertData, onClose }) => {
  if (!alertData) return null;

  const riskColorMap: Record<string, string> = {
    low: 'green',
    medium: 'orange',
    high: 'volcano',
    critical: 'red',
  };

  return (
    <Modal
      title={
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          ■ ALERT DETAIL — {alertData.deviceId}
        </span>
      }
      open={open}
      onCancel={onClose}
      footer={null}
      width={640}
      styles={{
        body: { backgroundColor: 'var(--bg-panel)' },
      }}
    >
      <Descriptions column={1} size="small" bordered style={{ marginBottom: 16 }}>
        <Descriptions.Item label="RISK LEVEL">
          <Tag color={riskColorMap[alertData.riskLevel] || 'default'}>
            {alertData.riskLevel.toUpperCase()}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="MESSAGE">
          {alertData.message}
        </Descriptions.Item>
        {alertData.anomalyScore !== undefined && (
          <Descriptions.Item label="ANOMALY SCORE">
            {(alertData.anomalyScore * 100).toFixed(1)}%
          </Descriptions.Item>
        )}
        {alertData.abnormalSensors && (
          <Descriptions.Item label="SENSORS">
            {alertData.abnormalSensors.join(', ')}
          </Descriptions.Item>
        )}
      </Descriptions>

      {/* RUL Gauge */}
      {alertData.rulHours !== undefined && (
        <div style={{ marginBottom: 16 }}>
          <RULGauge
            rulHours={alertData.rulHours}
            riskLevel={alertData.riskLevel as 'low' | 'medium' | 'high' | 'critical'}
          />
        </div>
      )}

      {/* Diagnosis */}
      {alertData.diagnosis && (
        <div
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 2,
            padding: '12px 14px',
            marginBottom: 12,
          }}
        >
          <div
            style={{
              fontSize: 12,
              fontFamily: 'var(--font-mono)',
              color: 'var(--accent-primary)',
              marginBottom: 8,
              letterSpacing: 1,
            }}
          >
            ■ DIAGNOSIS
          </div>
          <div
            style={{
              fontSize: 13,
              color: 'var(--text-primary)',
              lineHeight: 1.6,
            }}
          >
            {alertData.diagnosis}
          </div>
        </div>
      )}

      {/* Solution Steps */}
      {alertData.solution && alertData.solution.length > 0 && (
        <div
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 2,
            padding: '12px 14px',
            marginBottom: 12,
          }}
        >
          <div
            style={{
              fontSize: 12,
              fontFamily: 'var(--font-mono)',
              color: 'var(--accent-primary)',
              marginBottom: 8,
              letterSpacing: 1,
            }}
          >
            ■ SOLUTION
          </div>
          {alertData.solution.map((step, idx) => (
            <div
              key={idx}
              style={{
                display: 'flex',
                gap: 10,
                marginBottom: idx < alertData.solution!.length - 1 ? 6 : 0,
                fontSize: 13,
                lineHeight: 1.6,
              }}
            >
              <span
                style={{
                  color: 'var(--accent-primary)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 12,
                  flexShrink: 0,
                }}
              >
                {String(idx + 1).padStart(2, '0')}
              </span>
              <span style={{ color: 'var(--text-secondary)' }}>{step}</span>
            </div>
          ))}
        </div>
      )}

      {/* Empty state when no extended data */}
      {!alertData.rulHours && !alertData.diagnosis && (!alertData.solution || alertData.solution.length === 0) && (
        <div
          style={{
            color: 'var(--text-dim)',
            fontSize: 12,
            fontFamily: 'var(--font-mono)',
            textAlign: 'center',
            padding: 16,
          }}
        >
          [DIAGNOSIS &amp; SOLUTION — NO DATA]
        </div>
      )}
    </Modal>
  );
};

export default AlertModal;
