import React, { useState, useMemo } from 'react';
import { useDeviceStore } from '../stores/useDeviceStore';
import { useNavigate } from 'react-router-dom';
import { FARMS } from '../constants/devices';

export interface DeviceTreeProps {
  onDeviceSelect?: (deviceId: string) => void;
}

/**
 * DeviceTree — Device list tree component grouped by farm (暗夜工控风格).
 */
const DeviceTree: React.FC<DeviceTreeProps> = ({ onDeviceSelect }) => {
  const devices = useDeviceStore((s) => s.devices);
  const selectedDeviceId = useDeviceStore((s) => s.selectedDeviceId);
  const selectDevice = useDeviceStore((s) => s.selectDevice);
  const navigate = useNavigate();

  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggleFarm = (farm: string) => {
    setCollapsed((prev) => {
      const next = !prev[farm];
      if (next) setExpanded((e) => ({ ...e, [farm]: false })); // collapse → reset expanded
      return { ...prev, [farm]: next };
    });
  };

  // Group devices by farm
  const farmGroups = useMemo(() => {
    return FARMS.map((farm) => {
      const farmDevices = devices.filter((d) => d.farm === farm);
      const alerts = farmDevices.filter((d) => d.status === 'alert').length;
      const visible = expanded[farm] ? farmDevices : farmDevices.slice(0, 15);
      return {
        farm,
        devices: visible,
        total: farmDevices.length,
        alerts,
        hasMore: farmDevices.length > 15 && !expanded[farm],
      };
    }).filter((g) => g.total > 0);
  }, [devices, expanded]);

  const handleDeviceClick = (deviceId: string) => {
    if (selectedDeviceId === deviceId) {
      // Second click on same device → navigate to detail
      if (onDeviceSelect) {
        onDeviceSelect(deviceId);
      } else {
        navigate(`/device/${deviceId}`);
      }
    } else {
      // First click → select device (shows RealTimeChart on Dashboard)
      selectDevice(deviceId);
    }
  };

  const statusDot = (status: string) => {
    const colors: Record<string, string> = {
      running: 'var(--status-normal)',
      alert: 'var(--status-danger)',
      stopped: 'var(--status-offline)',
    };
    return (
      <span
        style={{
          display: 'inline-block',
          width: 7,
          height: 7,
          borderRadius: '50%',
          backgroundColor: colors[status] || 'var(--status-offline)',
          marginRight: 8,
          boxShadow: status === 'alert' ? '0 0 6px var(--status-danger)' : 'none',
        }}
      />
    );
  };

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-panel)',
        borderRadius: 2,
        padding: 16,
        border: '1px solid var(--border-panel)',
        height: '100%',
        minHeight: 0,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          marginBottom: 12,
          color: 'var(--text-secondary)',
          fontFamily: 'var(--font-mono)',
          textTransform: 'uppercase',
          letterSpacing: 1,
          flexShrink: 0,
        }}
      >
        ■ DEVICE LIST
      </div>

      {devices.length === 0 ? (
        <p style={{ color: 'var(--text-dim)', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
          NO DEVICES
        </p>
      ) : (
        <div style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
          {farmGroups.map((group) => (
            <div key={group.farm} style={{ marginBottom: 6 }}>
              {/* Farm header — click to toggle */}
              <div
                onClick={() => toggleFarm(group.farm)}
                style={{
                  padding: '6px 8px',
                  cursor: 'pointer',
                  borderRadius: 2,
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--accent-primary)',
                  backgroundColor: 'rgba(0,230,118,0.04)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  userSelect: 'none',
                  marginBottom: collapsed[group.farm] ? 0 : 4,
                }}
              >
                <span>
                  {collapsed[group.farm] ? '▸' : '▾'} {group.farm}
                </span>
                <span style={{ fontSize: 10, color: 'var(--text-dim)', fontWeight: 400 }}>
                  {group.total} dev / <span style={{ color: 'var(--status-danger)' }}>{group.alerts} alt</span>
                </span>
              </div>

              {/* Device list */}
              {!collapsed[group.farm] && (
                <div style={{ paddingLeft: 4 }}>
                  {group.devices.map((device) => (
                    <div
                      key={device.id}
                      onClick={() => handleDeviceClick(device.id)}
                      style={{
                        padding: '7px 10px',
                        cursor: 'pointer',
                        borderRadius: 2,
                        marginBottom: 2,
                        backgroundColor:
                          selectedDeviceId === device.id
                            ? 'var(--accent-glow)'
                            : 'transparent',
                        color:
                          selectedDeviceId === device.id
                            ? 'var(--accent-primary)'
                            : 'var(--text-primary)',
                        fontSize: 12,
                        fontFamily: 'var(--font-mono)',
                        display: 'flex',
                        alignItems: 'center',
                        transition: 'background-color 0.15s',
                        borderLeft:
                          selectedDeviceId === device.id
                            ? '2px solid var(--accent-primary)'
                            : '2px solid transparent',
                      }}
                      onMouseEnter={(e) => {
                        if (selectedDeviceId !== device.id) {
                          e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.03)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (selectedDeviceId !== device.id) {
                          e.currentTarget.style.backgroundColor = 'transparent';
                        }
                      }}
                    >
                      {statusDot(device.status)}
                      <span style={{ flex: 1 }}>{device.name}</span>
                      <span style={{ fontSize: 10, color: 'var(--text-dim)', marginRight: 8 }}>
                        {device.model}
                      </span>
                      <span style={{
                        fontSize: 10,
                        fontFamily: 'var(--font-mono)',
                        color: device.status === 'alert' ? 'var(--status-danger)' : 'var(--accent-primary)',
                        minWidth: 60,
                        textAlign: 'right',
                      }}>
                        {device.rulHours !== undefined ? `${device.rulHours} cyc` : '—'}
                      </span>
                    </div>
                  ))}
                  {group.hasMore && (
                    <div
                      onClick={(e) => {
                        e.stopPropagation();
                        setExpanded((prev) => ({ ...prev, [group.farm]: true }));
                      }}
                      style={{
                        fontSize: 10,
                        color: 'var(--accent-primary)',
                        fontFamily: 'var(--font-mono)',
                        textAlign: 'center',
                        padding: '4px 0',
                        cursor: 'pointer',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.color = '#00e676'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--accent-primary)'; }}
                    >
                      +{group.total - 15} more...
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DeviceTree;
