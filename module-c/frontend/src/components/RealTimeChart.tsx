import React, { useEffect, useMemo, useState, useRef } from 'react';
import ReactECharts from 'echarts-for-react';
import { generateSensorSnapshot } from '../services/mock';

interface RealTimeChartProps {
  deviceId?: string;
  rulHours?: number;
}

const WINDOW = 30;
const TICK_MS = 2000;

interface DataPoint {
  time: string;
  vibration_x: number;
  temperature: number;
  rpm: number;
}

function makePoint(deviceId: string, rulHours?: number): DataPoint {
  const t = new Date();
  const base = generateSensorSnapshot(deviceId, rulHours);
  return {
    time: t.toTimeString().slice(0, 8),
    vibration_x: +base.vibration_x.toFixed(4),
    temperature: +base.temperature.toFixed(1),
    rpm: +base.rpm.toFixed(0),
  };
}

function seedHistory(deviceId: string, count: number, rulHours?: number): DataPoint[] {
  const now = Date.now();
  return Array.from({ length: count }, (_, i) => {
    const t = new Date(now - (count - 1 - i) * TICK_MS);
    const base = generateSensorSnapshot(deviceId, rulHours);
    return {
      time: t.toTimeString().slice(0, 8),
      vibration_x: +base.vibration_x.toFixed(4),
      temperature: +base.temperature.toFixed(1),
      rpm: +base.rpm.toFixed(0),
    };
  });
}

// ── Baseline ranges per metric (from mock.ts formula) ──────────────
const RANGES = {
  vibration_x: { min: 0, max: 1.7 },
  temperature: { min: 55, max: 130 },
  rpm:         { min: 1050, max: 1700 },
} as const;

type MetricKey = keyof typeof RANGES;

function toPct(value: number, key: MetricKey): number {
  const { min, max } = RANGES[key];
  return +(((value - min) / (max - min)) * 100).toFixed(1);
}

const RealTimeChart: React.FC<RealTimeChartProps> = ({ deviceId, rulHours }) => {
  const [seriesData, setSeriesData] = useState<DataPoint[]>([]);
  const bufferRef = useRef<DataPoint[]>([]);

  useEffect(() => {
    if (!deviceId) {
      setSeriesData([]);
      bufferRef.current = [];
      return;
    }

    // Init with history
    const history = seedHistory(deviceId, WINDOW, rulHours);
    bufferRef.current = history;
    setSeriesData([...history]);

    const timer = setInterval(() => {
      const point = makePoint(deviceId, rulHours);
      bufferRef.current = [...bufferRef.current.slice(1), point];
      setSeriesData(bufferRef.current);
    }, TICK_MS);

    return () => clearInterval(timer);
  }, [deviceId]);

  const option = useMemo(() => {
    if (!deviceId || seriesData.length === 0) return null;

    const times = seriesData.map((d) => d.time);

    return {
      backgroundColor: '#111620',
      grid: { left: 52, right: 16, top: 36, bottom: 28 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(17,22,32,0.95)',
        borderColor: 'rgba(0,230,118,0.2)',
        textStyle: { color: '#b0bec5', fontFamily: 'monospace', fontSize: 11 },
        formatter: (params: { seriesName: string; value: number; color: string }[]) => {
          const t = (params[0] as unknown as { axisValue: string }).axisValue;
          let html = `<div style="font-weight:600;margin-bottom:4px">${t}</div>`;
          params.forEach((p) => {
            const raw = seriesData[params.indexOf(p)];
            const val =
              p.seriesName === 'VIB-X' ? raw.vibration_x.toFixed(4)
              : p.seriesName === 'TEMP' ? raw.temperature.toFixed(1) + '°C'
              : raw.rpm + ' RPM';
            html += `<div><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px"></span>${p.seriesName}: ${val} (${p.value}%)</div>`;
          });
          return html;
        },
      },
      legend: {
        data: ['VIB-X', 'TEMP', 'RPM'],
        top: 4,
        textStyle: { color: '#78909c', fontFamily: 'monospace', fontSize: 10 },
        itemWidth: 12,
        itemHeight: 8,
      },
      xAxis: {
        type: 'category',
        data: times,
        axisLine: { lineStyle: { color: 'rgba(0,230,118,0.15)' } },
        axisLabel: { color: '#546e7a', fontSize: 9, fontFamily: 'monospace' },
        splitLine: { show: false },
      },
      yAxis: {
        type: 'value',
        name: '%',
        min: 0,
        max: 100,
        nameTextStyle: { color: '#546e7a', fontSize: 9 },
        axisLabel: { color: '#546e7a', fontSize: 9, fontFamily: 'monospace' },
        splitLine: { lineStyle: { color: 'rgba(0,230,118,0.06)' } },
      },
      series: [
        {
          name: 'VIB-X',
          type: 'line',
          smooth: true,
          symbol: 'none',
          data: seriesData.map((d) => toPct(d.vibration_x, 'vibration_x')),
          lineStyle: { color: '#00e676', width: 1.5 },
          itemStyle: { color: '#00e676' },
        },
        {
          name: 'TEMP',
          type: 'line',
          smooth: true,
          symbol: 'none',
          data: seriesData.map((d) => toPct(d.temperature, 'temperature')),
          lineStyle: { color: '#ff9100', width: 1.5 },
          itemStyle: { color: '#ff9100' },
        },
        {
          name: 'RPM',
          type: 'line',
          smooth: true,
          symbol: 'none',
          data: seriesData.map((d) => toPct(d.rpm, 'rpm')),
          lineStyle: { color: '#69f0ae', width: 1.5, type: 'dashed' as const },
          itemStyle: { color: '#69f0ae' },
        },
      ],
    };
  }, [deviceId, seriesData]);

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-panel)',
        borderRadius: 2,
        padding: 16,
        height: '100%',
        minHeight: 260,
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid var(--border-panel)',
        fontFamily: 'var(--font-mono)',
      }}
    >
      <div style={{ color: 'var(--accent-primary)', marginBottom: 8, fontSize: 12, flexShrink: 0 }}>
        ■ REAL-TIME MONITOR
        <span style={{ color: 'var(--text-dim)', marginLeft: 12, fontSize: 10 }}>
          {deviceId || 'UNSELECTED'}
        </span>
      </div>

      {!deviceId || !option ? (
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-dim)',
            fontSize: 12,
          }}
        >
          SELECT A DEVICE TO VIEW SENSOR DATA
        </div>
      ) : (
        <ReactECharts
          option={option}
          style={{ flex: 1, minHeight: 200 }}
          opts={{ renderer: 'canvas' }}
        />
      )}
    </div>
  );
};

export default RealTimeChart;
