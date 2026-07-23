import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { RUL_GAUGE_MAX } from '../constants/devices';

/**
 * RULGauge — Remaining Useful Life gauge component (暗夜工控风格).
 *
 * 使用 ECharts gauge 仪表盘展示剩余寿命百分比。
 * 根据风险等级 (low/medium/high/critical) 切换轴线段颜色和中心值颜色。
 * 暗夜工控风格：深色透明背景、霓虹绿指针、风险分级色带。
 */
interface RULGaugeProps {
  rulHours?: number;
  confidence?: number;
  riskLevel?: 'low' | 'medium' | 'high' | 'critical';
  maxRul?: number;
}

const RISK_LABELS: Record<string, string> = {
  low: 'LOW',
  medium: 'MED',
  high: 'HIGH',
  critical: 'CRIT',
};

/** Derive axis color segments from actual gauge percentage (self-consistent). */
function getAxisColors(value: number): Array<[number, string]> {
  if (value >= 0.6) return [[0.8, '#00e676'], [1, '#00c853']];
  if (value >= 0.4) return [[0.6, '#00e676'], [0.8, '#ff9800'], [1, '#e65100']];
  if (value >= 0.2) return [[0.4, '#00e676'], [0.6, '#ff9800'], [0.8, '#ff5722'], [1, '#ff1744']];
  return [[0.3, '#ff9800'], [0.6, '#ff5722'], [1, '#ff1744']];
}

function getDetailColor(value: number): string {
  if (value >= 0.6) return '#00e676';
  if (value >= 0.4) return '#ff9800';
  if (value >= 0.2) return '#ff5722';
  return '#ff1744';
}

const RULGauge: React.FC<RULGaugeProps> = ({
  rulHours = 4320,
  confidence = 0.92,
  riskLevel = 'medium',
  maxRul,
}) => {
  const gaugeValue = useMemo(() => Math.min(rulHours / (maxRul ?? RUL_GAUGE_MAX), 1), [rulHours, maxRul]);

  const option = useMemo(
    () => ({
      backgroundColor: 'transparent',
      series: [
        {
          type: 'gauge',
          startAngle: 210,
          endAngle: -30,
          min: 0,
          max: 1,
          center: ['50%', '55%'],
          radius: '90%',
          axisLine: {
            lineStyle: {
              width: 8,
              color: getAxisColors(gaugeValue),
            },
          },
          progress: {
            show: true,
            width: 6,
            itemStyle: {
              color: '#00e676',
              opacity: 0.35,
            },
          },
          pointer: {
            length: '70%',
            width: 6,
            itemStyle: {
              color: '#00e676',
            },
          },
          axisTick: {
            distance: -8,
            length: 5,
            lineStyle: {
              width: 1,
              color: '#546e7a',
            },
          },
          splitLine: {
            distance: -12,
            length: 10,
            lineStyle: {
              width: 2,
              color: '#546e7a',
            },
          },
          axisLabel: {
            distance: 20,
            color: '#90a4ae',
            fontSize: 10,
            fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace',
            formatter: (val: number) => (val * 100).toFixed(0),
          },
          anchor: {
            show: true,
            size: 10,
            itemStyle: {
              color: '#00e676',
              borderColor: '#111620',
              borderWidth: 2,
            },
          },
          detail: {
            valueAnimation: true,
            formatter: (val: number) => (val * 100).toFixed(0) + '%',
            fontSize: 28,
            fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace',
            color: getDetailColor(gaugeValue),
            offsetCenter: [0, '50%'],
          },
          data: [{ value: gaugeValue }],
        },
      ],
    }),
    [gaugeValue],
  );

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-panel)',
        borderRadius: 2,
        padding: '8px 16px 12px',
        height: 260,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        border: '1px solid var(--border-panel)',
      }}
    >
      {/* Header: Title */}
      <div
        style={{
          fontSize: 11,
          color: 'var(--text-secondary)',
          fontFamily: 'var(--font-mono)',
          textTransform: 'uppercase',
          letterSpacing: 1,
          width: '100%',
          textAlign: 'center',
          flexShrink: 0,
        }}
      >
        RUL (Remaining Useful Life)
      </div>

      {/* ECharts Gauge */}
      <div style={{ width: '100%', flex: 1, minHeight: 0 }}>
        <ReactECharts
          option={option}
          style={{ width: '100%', height: '100%' }}
          opts={{ renderer: 'canvas' }}
        />
      </div>

      {/* Footer: Confidence & Risk Level */}
      <div
        style={{
          fontSize: 11,
          color: 'var(--text-dim)',
          fontFamily: 'var(--font-mono)',
          width: '100%',
          textAlign: 'center',
          flexShrink: 0,
        }}
      >
        CONF {(confidence * 100).toFixed(0)}% · RISK:{' '}
        {RISK_LABELS[riskLevel]}
      </div>
    </div>
  );
};

export default RULGauge;
