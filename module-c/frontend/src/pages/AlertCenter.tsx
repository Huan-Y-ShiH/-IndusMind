import React, { useMemo, useState, useCallback } from 'react';
import { Card, Table, Tag, Button, Space, Row, Col, Select, Input, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { SearchOutlined } from '@ant-design/icons';
import { useDeviceStore } from '../stores/useDeviceStore';
import type { AlertItem } from '../types/device';
import { buildExtendedAlertData } from '../services/alertDetailBuilder';
import AlertModal from '../components/AlertModal';

// ── Risk level config ──────────────────────────────────────────────

const RISK_LEVELS = ['critical', 'high', 'medium', 'low'] as const;

interface RiskConfig {
  label: string;
  color: string;
  cardColor: string;
}

const RISK_CONFIG: Record<string, RiskConfig> = {
  critical: { label: 'CRITICAL', color: '#ff1744', cardColor: '#ff1744' },
  high:     { label: 'HIGH',     color: '#ff9800', cardColor: '#ff9800' },
  medium:   { label: 'MEDIUM',   color: '#ff9800', cardColor: 'var(--status-warning)' },
  low:      { label: 'LOW',      color: '#2196f3', cardColor: 'var(--accent-primary)' },
};

// ── Stat Card ──────────────────────────────────────────────────────

const statCardBase: React.CSSProperties = {
  backgroundColor: 'var(--bg-panel)',
  border: '1px solid var(--border-panel)',
  borderRadius: 2,
  padding: 12,
  textAlign: 'center',
};

const statLabelStyle: React.CSSProperties = {
  fontSize: 10,
  color: 'var(--text-dim)',
  fontFamily: 'var(--font-mono)',
  textTransform: 'uppercase',
  letterSpacing: 1,
};

const statValueStyle: React.CSSProperties = {
  fontSize: 28,
  fontFamily: 'var(--font-mono)',
  fontWeight: 600,
  lineHeight: '32px',
  marginBottom: 4,
};

const statSubStyle: React.CSSProperties = {
  fontSize: 10,
  color: 'var(--text-dim)',
  fontFamily: 'var(--font-mono)',
  textTransform: 'uppercase',
};

interface StatCardProps {
  level: string;
  count: number;
  totalActive: number;
}

const StatCard: React.FC<StatCardProps> = ({ level, count, totalActive }) => {
  const cfg = RISK_CONFIG[level];
  const color = level === 'medium' ? 'var(--status-warning)' : level === 'low' ? 'var(--accent-primary)' : cfg.cardColor;
  return (
    <div style={statCardBase}>
      <div style={statLabelStyle}>{cfg.label}</div>
      <div style={{ ...statValueStyle, color }}>{count}</div>
      <div style={statSubStyle}>{totalActive} ACTIVE</div>
    </div>
  );
};

// ── Filter types ───────────────────────────────────────────────────

interface AlertFilters {
  riskLevel: string;
  deviceName: string;
  acknowledged: string; // '' = all, 'active' = unacked, 'ackd' = acked
}

// ── riskColorMap for Tag ────────────────────────────────────────────

const riskTagColorMap: Record<string, string> = {
  low: 'green',
  medium: 'orange',
  high: 'volcano',
  critical: 'red',
};

// ── Main Component ─────────────────────────────────────────────────

const AlertCenter: React.FC = () => {
  // ── Store ────────────────────────────────────────────────────────
  const alerts = useDeviceStore((s) => s.alerts);
  const devices = useDeviceStore((s) => s.devices);
  const acknowledgeAlert = useDeviceStore((s) => s.acknowledgeAlert);

  // ── Local state ──────────────────────────────────────────────────
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [filters, setFilters] = useState<AlertFilters>({
    riskLevel: '',
    deviceName: '',
    acknowledged: '',
  });

  // ── Filtered data ────────────────────────────────────────────────
  const filteredAlerts = useMemo(() => {
    const order: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
    return alerts
      .filter((a) => {
        if (filters.riskLevel && a.riskLevel !== filters.riskLevel) return false;
        if (filters.deviceName && !a.deviceName.toLowerCase().includes(filters.deviceName.toLowerCase())) return false;
        if (filters.acknowledged === 'active' && a.acknowledged) return false;
        if (filters.acknowledged === 'ackd' && !a.acknowledged) return false;
        return true;
      })
      .sort((a, b) => (order[a.riskLevel] ?? 99) - (order[b.riskLevel] ?? 99));
  }, [alerts, filters]);

  // ── Stat card counts (count unacknowledged per risk level) ───────
  const statCounts = useMemo(() => {
    const unacked = alerts.filter((a) => !a.acknowledged);
    const totalActive = unacked.length;
    return {
      critical: unacked.filter((a) => a.riskLevel === 'critical').length,
      high:     unacked.filter((a) => a.riskLevel === 'high').length,
      medium:   unacked.filter((a) => a.riskLevel === 'medium').length,
      low:      unacked.filter((a) => a.riskLevel === 'low').length,
      totalActive,
    };
  }, [alerts]);

  // ── Batch ACK ────────────────────────────────────────────────────
  const handleBatchAck = useCallback(() => {
    if (selectedRowKeys.length === 0) return;
    const keys = new Set(selectedRowKeys.map(String));
    let count = 0;
    alerts.forEach((a) => {
      if (keys.has(a.id) && !a.acknowledged) {
        acknowledgeAlert(a.id);
        count++;
      }
    });
    message.success(`ACK'd ${count} alert${count !== 1 ? 's' : ''}`);
    setSelectedRowKeys([]);
  }, [selectedRowKeys, alerts, acknowledgeAlert]);

  // ── ACK ALL ──────────────────────────────────────────────────────
  const handleAckAll = useCallback(() => {
    const unacked = alerts.filter((a) => !a.acknowledged);
    if (unacked.length === 0) {
      message.info('No active alerts to acknowledge');
      return;
    }
    unacked.forEach((a) => acknowledgeAlert(a.id));
    message.success(`ACK'd ${unacked.length} alert${unacked.length !== 1 ? 's' : ''}`);
    setSelectedRowKeys([]);
  }, [alerts, acknowledgeAlert]);

  // ── Table columns ────────────────────────────────────────────────
  const columns: ColumnsType<AlertItem> = [
    {
      title: 'TIME',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 100,
      render: (ts: string) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
          {new Date(ts).toISOString().slice(11, 19)}
        </span>
      ),
    },
    {
      title: 'DEVICE',
      dataIndex: 'deviceName',
      key: 'deviceName',
      width: 160,
    },
    {
      title: 'RISK',
      dataIndex: 'riskLevel',
      key: 'riskLevel',
      width: 100,
      render: (level: string) => (
        <Tag color={riskTagColorMap[level] || 'default'}>{level.toUpperCase()}</Tag>
      ),
    },
    {
      title: 'MESSAGE',
      dataIndex: 'message',
      key: 'message',
      ellipsis: true,
    },
    {
      title: 'STATUS',
      dataIndex: 'acknowledged',
      key: 'acknowledged',
      width: 90,
      render: (ack: boolean) => (
        <Tag color={ack ? 'default' : 'processing'}>
          {ack ? "ACK'D" : 'ACTIVE'}
        </Tag>
      ),
    },
    {
      title: 'ACTION',
      key: 'actions',
      width: 170,
      render: (_: unknown, record: AlertItem) => (
        <Space size="small">
          <Button
            size="small"
            type="link"
            onClick={() => {
              const deviceRul = devices.find((d) => d.id === record.deviceId)?.rulHours;
              const extended = buildExtendedAlertData(record, deviceRul);
              setSelectedAlert(extended as unknown as AlertItem);
              setModalOpen(true);
            }}
          >
            DETAILS
          </Button>
          {!record.acknowledged && (
            <Button
              size="small"
              type="link"
              onClick={() => {
                acknowledgeAlert(record.id);
                message.success('Alert acknowledged');
              }}
            >
              ACK
            </Button>
          )}
        </Space>
      ),
    },
  ];

  // ── Row selection config ─────────────────────────────────────────
  const rowSelection = {
    selectedRowKeys,
    onChange: (keys: React.Key[]) => setSelectedRowKeys(keys),
    getCheckboxProps: (record: AlertItem) => ({
      disabled: record.acknowledged,
    }),
  };

  // ── Render ───────────────────────────────────────────────────────
  return (
    <div>
      {/* ── Stat cards ─────────────────────────────────────────────── */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        {RISK_LEVELS.map((level) => (
          <Col xs={12} sm={6} key={level}>
            <StatCard
              level={level}
              count={statCounts[level]}
              totalActive={statCounts.totalActive}
            />
          </Col>
        ))}
      </Row>

      {/* ── Filter bar ─────────────────────────────────────────────── */}
      <div
        style={{
          backgroundColor: 'var(--bg-panel)',
          border: '1px solid var(--border-panel)',
          borderRadius: 2,
          padding: '8px 12px',
          marginBottom: 12,
        }}
      >
        <Space wrap size="small">
          <Select
            placeholder="RISK LEVEL"
            allowClear
            style={{ width: 130 }}
            value={filters.riskLevel || undefined}
            onChange={(val) =>
              setFilters((prev) => ({ ...prev, riskLevel: val || '' }))
            }
            options={[
              { value: 'critical', label: 'CRITICAL' },
              { value: 'high', label: 'HIGH' },
              { value: 'medium', label: 'MEDIUM' },
              { value: 'low', label: 'LOW' },
            ]}
          />
          <Input
            placeholder="DEVICE NAME"
            allowClear
            style={{ width: 180 }}
            prefix={<SearchOutlined />}
            value={filters.deviceName}
            onChange={(e) =>
              setFilters((prev) => ({ ...prev, deviceName: e.target.value }))
            }
          />
          <Select
            placeholder="STATUS"
            allowClear
            style={{ width: 120 }}
            value={filters.acknowledged || undefined}
            onChange={(val) =>
              setFilters((prev) => ({ ...prev, acknowledged: val || '' }))
            }
            options={[
              { value: 'active', label: 'ACTIVE' },
              { value: 'ackd', label: "ACK'D" },
            ]}
          />
          {selectedRowKeys.length > 0 && (
            <Button size="small" type="primary" danger onClick={handleBatchAck}>
              ACK SELECTED ({selectedRowKeys.length})
            </Button>
          )}
        </Space>
      </div>

      {/* ── Main table card ────────────────────────────────────────── */}
      <Card
        title={
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
            ■ ALERT CENTER
            <span
              style={{
                fontSize: 11,
                color: 'var(--text-dim)',
                marginLeft: 8,
                fontFamily: 'var(--font-mono)',
              }}
            >
              ({filteredAlerts.length} / {alerts.length} TOTAL)
            </span>
          </span>
        }
        extra={
          <Button size="small" onClick={handleAckAll}>
            ACK ALL
          </Button>
        }
      >
        <Table
          rowSelection={rowSelection}
          columns={columns}
          dataSource={filteredAlerts}
          rowKey="id"
          size="small"
          pagination={{ pageSize: 15, showSizeChanger: false }}
          locale={{ emptyText: 'NO ALERTS' }}
          rowClassName={(record) =>
            selectedRowKeys.includes(record.id) ? 'alert-row-selected' : ''
          }
          onRow={(record) => {
            if (!selectedRowKeys.includes(record.id)) return {};
            return {
              onMouseEnter: (e) => {
                const cells = (e.currentTarget as HTMLElement).querySelectorAll<HTMLElement>('.ant-table-cell');
                cells.forEach((c) => { c.style.setProperty('background-color', '#f5f5f5', 'important'); });
              },
              onMouseLeave: (e) => {
                const cells = (e.currentTarget as HTMLElement).querySelectorAll<HTMLElement>('.ant-table-cell');
                cells.forEach((c) => { c.style.removeProperty('background-color'); });
              },
            };
          }}
        />
      </Card>

      {/* ── Alert detail modal ─────────────────────────────────────── */}
      <AlertModal
        open={modalOpen}
        alertData={
          selectedAlert
            ? {
                deviceId: selectedAlert.deviceId,
                riskLevel: selectedAlert.riskLevel,
                message: selectedAlert.message,
                anomalyScore: (selectedAlert as unknown as Record<string, unknown>).anomalyScore as number | undefined,
                abnormalSensors: (selectedAlert as unknown as Record<string, unknown>).abnormalSensors as string[] | undefined,
                diagnosis: (selectedAlert as unknown as Record<string, unknown>).diagnosis as string | undefined,
                solution: (selectedAlert as unknown as Record<string, unknown>).solution as string[] | undefined,
                rulHours: (selectedAlert as unknown as Record<string, unknown>).rulHours as number | undefined,
              }
            : null
        }
        onClose={() => {
          setModalOpen(false);
          setSelectedAlert(null);
        }}
      />
    </div>
  );
};

export default AlertCenter;
