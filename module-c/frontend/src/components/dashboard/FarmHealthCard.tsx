import React from 'react';
import { Progress } from 'antd';

export interface FarmHealthCardProps {
  farm: string;
  running: number;
  alert: number;
  stopped: number;
}

const FarmHealthCard: React.FC<FarmHealthCardProps> = ({ farm, running, alert, stopped }) => {
  const total = running + alert + stopped || 1;
  const pct = Math.round((running / total) * 100);
  const hasAlert = alert > 0;

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-panel)',
        border: '1px solid var(--border-panel)',
        borderLeft: hasAlert ? '3px solid var(--status-danger)' : '3px solid var(--border-panel)',
        borderRadius: 2,
        padding: '10px 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        ...(hasAlert ? { animation: 'farm-alert-flash 1.5s ease-in-out infinite' } : {}),
      }}
    >
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        fontWeight: 600,
        color: 'var(--text-primary)',
      }}>
        {farm}
      </div>
      <div style={{
        display: 'flex',
        gap: 8,
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
      }}>
        <span style={{ color: 'var(--status-normal)' }}>RUN {running}</span>
        <span style={{ color: hasAlert ? 'var(--status-danger)' : 'var(--text-dim)' }}>ALT {alert}</span>
        <span style={{ color: 'var(--status-offline)' }}>STP {stopped}</span>
      </div>
      <Progress
        percent={pct}
        size="small"
        strokeColor={hasAlert ? 'var(--status-warning)' : 'var(--status-normal)'}
        trailColor="var(--border-panel)"
        showInfo={false}
        style={{ marginBottom: 0 }}
      />
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 9,
        color: 'var(--text-dim)',
        textAlign: 'right',
      }}>
        {running}/{total} ({pct}%)
      </div>
    </div>
  );
};

export default FarmHealthCard;
