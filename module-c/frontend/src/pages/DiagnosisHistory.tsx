import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Table, Tag, Button, Space, Select, Empty, Modal, Spin, Alert } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useDeviceStore } from '../stores/useDeviceStore';
import { useDiagnosisHistoryStore } from '../stores/useDiagnosisHistoryStore';
import type { DiagnosisRecord } from '../types/device';

const RISK_LEVELS = ['all', 'critical', 'high', 'medium', 'low'] as const;

const RISK_TAG_COLOR: Record<DiagnosisRecord['riskLevel'], string> = {
  critical: 'red',
  high: 'orange',
  medium: 'gold',
  low: 'blue',
};

const DiagnosisHistory: React.FC = () => {
  const navigate = useNavigate();
  const devices = useDeviceStore((s) => s.devices);
  const records = useDiagnosisHistoryStore((s) => s.records);
  const loading = useDiagnosisHistoryStore((s) => s.loading);
  const error = useDiagnosisHistoryStore((s) => s.error);
  const fetchRecords = useDiagnosisHistoryStore((s) => s.fetchRecords);
  const removeRecord = useDiagnosisHistoryStore((s) => s.removeRecord);

  useEffect(() => {
    if (records.length === 0) {
      void fetchRecords();
    }
  }, [fetchRecords, records.length]);

  const [deviceFilter, setDeviceFilter] = useState<string>('all');
  const [riskFilter, setRiskFilter] = useState<(typeof RISK_LEVELS)[number]>('all');

  const deviceOptions = useMemo(() => {
    const fromStore = devices.map((d) => ({ value: d.id, label: `${d.id} — ${d.name}` }));
    const fromRecords = records
      .filter((r) => !fromStore.some((o) => o.value === r.deviceId))
      .map((r) => ({ value: r.deviceId, label: `${r.deviceId} — ${r.deviceName}` }));

    const seen = new Set<string>();
    const merged = [...fromStore, ...fromRecords].filter((o) => {
      if (seen.has(o.value)) return false;
      seen.add(o.value);
      return true;
    });

    return [{ value: 'all', label: 'All devices' }, ...merged];
  }, [devices, records]);

  const filteredRecords = useMemo(() => {
    let result = [...records];

    if (deviceFilter !== 'all') {
      result = result.filter((r) => r.deviceId === deviceFilter);
    }
    if (riskFilter !== 'all') {
      result = result.filter((r) => r.riskLevel === riskFilter);
    }

    result.sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    );

    return result;
  }, [records, deviceFilter, riskFilter]);

  const formatTimestamp = (ts: string) => {
    try {
      return new Date(ts).toLocaleString();
    } catch {
      return ts;
    }
  };

  const handleDelete = (record: DiagnosisRecord) => {
    Modal.confirm({
      title: 'Delete diagnosis record?',
      content: `Remove diagnosis from ${record.deviceName} at ${formatTimestamp(record.timestamp)}?`,
      okText: 'DELETE',
      okType: 'danger',
      cancelText: 'CANCEL',
      onOk: () => removeRecord(record.id),
    });
  };

  const columns: ColumnsType<DiagnosisRecord> = [
    {
      title: 'TIMESTAMP',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (ts: string) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)' }}>
          {formatTimestamp(ts)}
        </span>
      ),
    },
    {
      title: 'DEVICE',
      key: 'device',
      width: 160,
      render: (_, record) => (
        <div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-primary)' }}>
            {record.deviceName}
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)' }}>
            {record.deviceId}
          </div>
        </div>
      ),
    },
    {
      title: 'FARM',
      dataIndex: 'farm',
      key: 'farm',
      width: 100,
      render: (farm: string) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)' }}>
          {farm}
        </span>
      ),
    },
    {
      title: 'RISK',
      dataIndex: 'riskLevel',
      key: 'riskLevel',
      width: 90,
      render: (level: DiagnosisRecord['riskLevel']) => (
        <Tag color={RISK_TAG_COLOR[level]} style={{ fontFamily: 'var(--font-mono)', fontSize: 10, margin: 0 }}>
          {level.toUpperCase()}
        </Tag>
      ),
    },
    {
      title: 'ROOT CAUSE',
      dataIndex: 'rootCause',
      key: 'rootCause',
      ellipsis: true,
      render: (cause: string) => (
        <span
          style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)' }}
          title={cause}
        >
          {cause.length > 80 ? `${cause.slice(0, 80)}...` : cause}
        </span>
      ),
    },
    {
      title: 'URGENCY',
      dataIndex: 'urgency',
      key: 'urgency',
      width: 110,
      render: (urgency: string) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)' }}>
          {urgency.toUpperCase()}
        </span>
      ),
    },
    {
      title: 'ACTIONS',
      key: 'actions',
      width: 140,
      render: (_, record) => (
        <Space size={4}>
          <Button
            size="small"
            type="link"
            onClick={() => navigate(`/diagnosis/${record.id}`, { state: { from: 'history' } })}
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11, padding: 0 }}
          >
            VIEW
          </Button>
          <Button
            size="small"
            type="link"
            danger
            onClick={() => handleDelete(record)}
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11, padding: 0 }}
          >
            DELETE
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div
        style={{
          marginBottom: 16,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <h2
          style={{
            margin: 0,
            fontFamily: 'var(--font-mono)',
            fontSize: 14,
            color: 'var(--text-primary)',
            letterSpacing: 1,
            textTransform: 'uppercase',
          }}
        >
          ■ Diagnosis History
        </h2>
        <Space wrap>
          <Select
            value={deviceFilter}
            onChange={setDeviceFilter}
            options={deviceOptions}
            style={{ width: 220 }}
            placeholder="Filter by device"
          />
          <Select
            value={riskFilter}
            onChange={setRiskFilter}
            style={{ width: 140 }}
            options={RISK_LEVELS.map((level) => ({
              value: level,
              label: level === 'all' ? 'All risk levels' : level.toUpperCase(),
            }))}
          />
        </Space>
      </div>

      <Card size="small" style={{ backgroundColor: 'var(--bg-panel)', borderColor: 'var(--border-panel)' }}>
        {error && (
          <Alert
            type="error"
            message={error}
            action={
              <Button size="small" onClick={() => void fetchRecords()}>
                Retry
              </Button>
            }
            style={{ marginBottom: 16 }}
          />
        )}
        {loading && records.length === 0 ? (
          <div style={{ padding: 48, textAlign: 'center' }}>
            <Spin tip="Loading diagnosis history..." />
          </div>
        ) : records.length === 0 ? (
          <Empty
            description={
              <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                No diagnosis history yet. Go to Device Detail to run a diagnosis.
              </span>
            }
          />
        ) : (
          <Table
            columns={columns}
            dataSource={filteredRecords}
            rowKey="id"
            size="small"
            pagination={{ pageSize: 15, showSizeChanger: false }}
            locale={{
              emptyText: (
                <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                  No records match the current filters.
                </span>
              ),
            }}
          />
        )}
      </Card>
    </div>
  );
};

export default DiagnosisHistory;
