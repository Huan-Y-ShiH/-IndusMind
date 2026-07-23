import React, { useMemo } from 'react';
import type { DeviceInfo } from '../../types/device';

interface DonutSegment {
  color: string;
  offset: number;
  length: number;
  count: number;
}

export interface DeviceStatusDonutProps {
  devices: DeviceInfo[];
}

const DONUT_RADIUS = 42;
const DONUT_STROKE = 10;
const DONUT_CENTER = 60;
const DONUT_CIRCUMFERENCE = 2 * Math.PI * DONUT_RADIUS;

const DeviceStatusDonut: React.FC<DeviceStatusDonutProps> = ({ devices }) => {
  const running = devices.filter((d) => d.status === 'running').length;
  const alert = devices.filter((d) => d.status === 'alert').length;
  const stopped = devices.filter((d) => d.status === 'stopped').length;
  const total = devices.length || 1;

  const segments: DonutSegment[] = useMemo(() => {
    const rLen = (running / total) * DONUT_CIRCUMFERENCE;
    const aLen = (alert / total) * DONUT_CIRCUMFERENCE;
    const sLen = (stopped / total) * DONUT_CIRCUMFERENCE;
    return [
      { color: 'var(--status-normal)', offset: 0, length: rLen, count: running },
      { color: 'var(--status-danger)', offset: rLen, length: aLen, count: alert },
      { color: 'var(--status-offline)', offset: rLen + aLen, length: sLen, count: stopped },
    ].filter((s) => s.count > 0);
  }, [running, alert, stopped, total]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: 120 }}>
      <svg width={DONUT_CENTER * 2} height={DONUT_CENTER * 2} viewBox={`0 0 ${DONUT_CENTER * 2} ${DONUT_CENTER * 2}`}>
        <circle
          cx={DONUT_CENTER}
          cy={DONUT_CENTER}
          r={DONUT_RADIUS}
          fill="none"
          stroke="var(--border-panel)"
          strokeWidth={DONUT_STROKE}
        />
        <g transform={`rotate(-90 ${DONUT_CENTER} ${DONUT_CENTER})`}>
          {segments.map((seg, i) => (
            <circle
              key={i}
              cx={DONUT_CENTER}
              cy={DONUT_CENTER}
              r={DONUT_RADIUS}
              fill="none"
              stroke={seg.color}
              strokeWidth={DONUT_STROKE}
              strokeLinecap="butt"
              strokeDasharray={`${seg.length} ${DONUT_CIRCUMFERENCE - seg.length}`}
              strokeDashoffset={-seg.offset}
            />
          ))}
        </g>
        <text
          x={DONUT_CENTER}
          y={DONUT_CENTER - 4}
          textAnchor="middle"
          fill="var(--text-primary)"
          fontFamily="var(--font-mono)"
          fontSize={20}
          fontWeight={600}
        >
          {total}
        </text>
        <text
          x={DONUT_CENTER}
          y={DONUT_CENTER + 14}
          textAnchor="middle"
          fill={alert > 0 ? 'var(--status-danger)' : 'var(--text-dim)'}
          fontFamily="var(--font-mono)"
          fontSize={10}
        >
          {alert > 0 ? `${alert} ALERT` : 'OK'}
        </text>
      </svg>
      <div style={{ display: 'flex', gap: 12, marginTop: 8, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-secondary)' }}>
        <span><span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: 'var(--status-normal)', marginRight: 4, verticalAlign: 'middle' }} />RUN {running}</span>
        <span><span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: 'var(--status-danger)', marginRight: 4, verticalAlign: 'middle' }} />ALT {alert}</span>
        <span><span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: 'var(--status-offline)', marginRight: 4, verticalAlign: 'middle' }} />STP {stopped}</span>
      </div>
    </div>
  );
};

export default DeviceStatusDonut;
