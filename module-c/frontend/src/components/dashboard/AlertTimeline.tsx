import React from 'react';
import { Tag } from 'antd';
import type { AlertItem } from '../../types/device';

const RISK_COLOR: Record<string, string> = {
  low: '#2196f3',
  medium: '#ff9800',
  high: '#ff1744',
  critical: '#ff1744',
};

const RISK_CLASS: Record<string, string> = {
  low: '',
  medium: '',
  high: '',
  critical: 'alert-pulse',
};

export interface AlertTimelineProps {
  alerts: AlertItem[];
}

const AlertTimeline: React.FC<AlertTimelineProps> = ({ alerts }) => {
  const formatTime = (ts: string) => {
    const d = new Date(ts);
    return d.toTimeString().slice(0, 8);
  };

  return (
    <div style={{ maxHeight: 250, overflowY: 'auto' }}>
      {alerts.map((a) => (
        <div
          key={a.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '6px 0',
            borderBottom: '1px solid var(--border-subtle)',
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
          }}
        >
          <span style={{ color: 'var(--text-dim)', flexShrink: 0, minWidth: 56 }}>
            {formatTime(a.timestamp)}
          </span>
          <span style={{ color: 'var(--text-secondary)', flexShrink: 0, minWidth: 90, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {a.deviceName}
          </span>
          <Tag
            color={RISK_COLOR[a.riskLevel]}
            className={RISK_CLASS[a.riskLevel]}
            style={{
              margin: 0,
              fontSize: 9,
              lineHeight: '16px',
              padding: '0 4px',
              flexShrink: 0,
            }}
          >
            {a.riskLevel.toUpperCase()}
          </Tag>
          <span style={{
            color: 'var(--text-secondary)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            flex: 1,
          }}>
            {a.message}
          </span>
        </div>
      ))}
    </div>
  );
};

export default AlertTimeline;
