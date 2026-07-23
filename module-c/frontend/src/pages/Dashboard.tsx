import React, { useEffect, useMemo } from 'react';
import { Card, Statistic, Row, Col } from 'antd';
import {
  ThunderboltOutlined,
  AlertOutlined,
  ToolOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import DeviceTree from '../components/DeviceTree';
import RealTimeChart from '../components/RealTimeChart';
import DeviceStatusDonut from '../components/dashboard/DeviceStatusDonut';
import FarmHealthCard from '../components/dashboard/FarmHealthCard';
import AlertTimeline from '../components/dashboard/AlertTimeline';
import { useDeviceStore } from '../stores/useDeviceStore';
import { mockDevices } from '../services/mock';
import { FARMS } from '../constants/devices';

const statCardStyle: React.CSSProperties = {
  backgroundColor: 'var(--bg-panel)',
  border: '1px solid var(--border-panel)',
  borderRadius: 2,
};

const panelTitleStyle: React.CSSProperties = {
  fontSize: 11,
  fontFamily: 'var(--font-mono)',
  textTransform: 'uppercase' as const,
  color: 'var(--text-secondary)',
  letterSpacing: 1,
  marginBottom: 12,
};

const Dashboard: React.FC = () => {
  const setDevices = useDeviceStore((s) => s.setDevices);
  const devices = useDeviceStore((s) => s.devices);
  const alerts = useDeviceStore((s) => s.alerts);
  const selectedDeviceId = useDeviceStore((s) => s.selectedDeviceId);
  const selectedRul = useMemo(
    () => devices.find((d) => d.id === selectedDeviceId)?.rulHours,
    [devices, selectedDeviceId],
  );

  useEffect(() => {
    if (devices.length === 0) {
      setDevices(mockDevices);
    }
  }, [devices.length, setDevices]);

  const timelineAlerts = useMemo(() => {
    const order = { critical: 0, high: 1, medium: 2, low: 3 };
    return alerts
      .filter((a) => !a.acknowledged)
      .sort((a, b) => (order[a.riskLevel] ?? 99) - (order[b.riskLevel] ?? 99))
      .slice(0, 50);
  }, [alerts]);

  const runningCount = devices.filter((d) => d.status === 'running').length;
  const alertCount = devices.filter((d) => d.status === 'alert').length;
  const stoppedCount = devices.filter((d) => d.status === 'stopped').length;

  const farmStats = useMemo(() => {
    return FARMS.map((farm) => {
      const farmDevices = devices.filter((d) => d.farm === farm);
      return {
        farm,
        running: farmDevices.filter((d) => d.status === 'running').length,
        alert: farmDevices.filter((d) => d.status === 'alert').length,
        stopped: farmDevices.filter((d) => d.status === 'stopped').length,
      };
    });
  }, [devices]);

  return (
    <div style={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card style={{ ...statCardStyle, height: 94 }} styles={{ body: { padding: '18px 20px' } }}>
            <Statistic
              title="DEVICES"
              value={devices.length}
              prefix={<ThunderboltOutlined style={{ color: 'var(--accent-primary)' }} />}
              valueStyle={{
                color: 'var(--accent-primary)',
                fontFamily: 'var(--font-mono)',
                fontSize: 28,
              }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={{ ...statCardStyle, height: 94 }} styles={{ body: { padding: '18px 20px' } }}>
            <Statistic
              title="RUNNING"
              value={runningCount}
              prefix={<CheckCircleOutlined style={{ color: 'var(--status-normal)' }} />}
              valueStyle={{
                color: 'var(--status-normal)',
                fontFamily: 'var(--font-mono)',
                fontSize: 28,
              }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={{ ...statCardStyle, height: 94 }} styles={{ body: { padding: '18px 20px' } }}>
            <Statistic
              title="ALERTS"
              value={alertCount}
              prefix={<AlertOutlined style={{ color: alertCount > 0 ? 'var(--status-danger)' : 'var(--text-dim)' }} />}
              valueStyle={{
                color: alertCount > 0 ? 'var(--status-danger)' : 'var(--text-dim)',
                fontFamily: 'var(--font-mono)',
                fontSize: 28,
              }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={{ ...statCardStyle, height: 94 }} styles={{ body: { padding: '18px 20px' } }}>
            <Statistic
              title="STOPPED"
              value={stoppedCount}
              prefix={<ToolOutlined style={{ color: 'var(--status-offline)' }} />}
              valueStyle={{
                color: 'var(--status-offline)',
                fontFamily: 'var(--font-mono)',
                fontSize: 28,
              }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ flex: 1, minHeight: 0 }}>
        <Col xs={24} lg={6} style={{ height: '100%', minHeight: 0 }}>
          <DeviceTree />
        </Col>
        <Col xs={24} lg={12} style={{ height: '100%', minHeight: 0 }}>
          <RealTimeChart deviceId={selectedDeviceId || undefined} rulHours={selectedRul} />
        </Col>
        <Col xs={24} lg={6} style={{ height: '100%', minHeight: 0 }}>
          <Card
            title={<span style={panelTitleStyle}>■ DEVICE STATUS</span>}
            style={statCardStyle}
            styles={{ body: { padding: '12px 16px', display: 'flex', justifyContent: 'center' } }}
          >
            <DeviceStatusDonut devices={devices} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        {farmStats.map((fs) => (
          <Col xs={24} sm={12} lg={6} key={fs.farm}>
            <FarmHealthCard {...fs} />
          </Col>
        ))}
      </Row>

      <Card
        title={<span style={panelTitleStyle}>■ ALERT TIMELINE</span>}
        style={statCardStyle}
        styles={{ body: { padding: '8px 14px' } }}
      >
        <AlertTimeline alerts={timelineAlerts} />
      </Card>
    </div>
  );
};

export default Dashboard;
