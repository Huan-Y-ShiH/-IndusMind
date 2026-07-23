import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Bell, Settings, Activity, AlertTriangle, Monitor, Menu, X } from 'lucide-react';
import { useDeviceStore } from '../stores/useDeviceStore';
import { alertWS, type WsAlertMessage } from '../services/websocket';
import type { AlertItem } from '../types/device';
import { generateAlertsFromDevices } from '../services/mock';

// ── 暗夜工控（NASA 控制中心风格）布局 ──────────────────────────────
// Layout spec:
//   - Top bar: 52px, #0d1117 (bg-header), bottom 1px neon-green border
//   - Sidebar: 210px, #0c1016 (bg-sidebar), right edge 1px dark line
//   - Content: fills rest, scrollable, #0a0e14 (bg-base)
//   - Active menu: 2px left green stripe + green text + subtle green bg

const MENU_ITEMS = [
  { path: '/', label: '监控大屏', icon: Monitor },
  { path: '/alerts', label: '告警中心', icon: AlertTriangle },
  { path: '/settings', label: '系统设置', icon: Settings },
];

interface LayoutProps {
  children?: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [utcTime, setUtcTime] = useState('');

  const addAlert = useDeviceStore((s) => s.addAlert);
  const devices = useDeviceStore((s) => s.devices);

  const alertCount = useDeviceStore((s) => s.alerts.filter((a) => !a.acknowledged).length);

  // ── UTC Clock ──────────────────────────────────────────────────
  useEffect(() => {
    const tick = () => {
      const now = new Date();
      const hh = String(now.getUTCHours()).padStart(2, '0');
      const mm = String(now.getUTCMinutes()).padStart(2, '0');
      const ss = String(now.getUTCSeconds()).padStart(2, '0');
      setUtcTime(`${hh}:${mm}:${ss}`);
    };
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, []);

  // ── Alert seeding (runs when devices first load) ──────────────
  useEffect(() => {
    const alerts = useDeviceStore.getState().alerts;
    if (alerts.length === 0 && devices.length > 0) {
      const deviceAlerts = generateAlertsFromDevices(devices);
      deviceAlerts.forEach((a) => addAlert(a));
    }
  }, [devices.length, addAlert]);

  // ── WebSocket connection (once on mount) ──────────────────────
  useEffect(() => {
    const currentDevices = useDeviceStore.getState().devices;

    // Connect WebSocket
    alertWS.connect();

    // Build device name lookup map
    const deviceNameMap = new Map<string, string>();
    currentDevices.forEach((d) => deviceNameMap.set(d.id, d.name));

    const unsub = alertWS.onMessage((raw: unknown) => {
      const msg = raw as WsAlertMessage;
      if (msg.type !== 'alert') return;

      const riskLevel = (msg.data.risk_level || 'medium') as AlertItem['riskLevel'];
      const deviceName = deviceNameMap.get(msg.device_id) || msg.device_id;

      addAlert({
        id: msg.event_id || `ALT-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        deviceId: msg.device_id,
        deviceName,
        type: 'alert',
        riskLevel,
        message: msg.data.message,
        timestamp: msg.timestamp,
        acknowledged: false,
      });
    });

    return () => {
      unsub();
      alertWS.disconnect();
    };
  }, []);

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* ── Header (52px) ───────────────────────────────────── */}
      <header
        style={{
          height: 52,
          backgroundColor: 'var(--bg-header)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 20px',
          flexShrink: 0,
          borderBottom: '1px solid var(--accent-primary)',
        }}
      >
        {/* Left: Logo + hamburger */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              padding: 4,
              display: 'flex',
              transition: 'color 0.2s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--accent-primary)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-secondary)'; }}
          >
            {sidebarCollapsed ? <Menu size={18} /> : <X size={18} />}
          </button>

          <Activity size={22} color="var(--accent-primary)" />
          <span
            style={{
              color: '#fff',
              fontSize: 15,
              fontWeight: 700,
              letterSpacing: 3,
              fontFamily: 'var(--font-mono)',
            }}
          >
            INDUSMIND
          </span>
        </div>

        {/* Right: Alert light + Clock + Settings */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
          {/* Alert indicator with pulse animation */}
          <button
            onClick={() => navigate('/alerts')}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: 0,
            }}
          >
            {/* Red pulse dot — visible only when alertCount > 0 */}
            {alertCount > 0 ? (
              <>
                <span
                  className="alert-pulse"
                  style={{
                    display: 'inline-block',
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    backgroundColor: 'var(--status-danger)',
                    boxShadow: '0 0 6px var(--status-danger)',
                  }}
                />
                <span
                  style={{
                    color: 'var(--status-danger)',
                    fontSize: 13,
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 600,
                  }}
                >
                  {alertCount}
                </span>
              </>
            ) : (
              <Bell size={17} color="var(--text-dim)" />
            )}
          </button>

          {/* UTC Clock — monospace 24h */}
          <span
            style={{
              color: 'var(--accent-primary)',
              fontSize: 13,
              fontFamily: 'var(--font-mono)',
              letterSpacing: 2,
              minWidth: 80,
              textAlign: 'right',
            }}
          >
            {utcTime} UTC
          </span>

          {/* Settings gear */}
          <button
            onClick={() => navigate('/settings')}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-dim)',
              cursor: 'pointer',
              display: 'flex',
              padding: 0,
              transition: 'color 0.2s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--accent-primary)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-dim)'; }}
          >
            <Settings size={17} />
          </button>
        </div>
      </header>

      {/* ── Body ────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Sidebar (210px) */}
        {!sidebarCollapsed && (
          <aside
            style={{
              width: 210,
              backgroundColor: 'var(--bg-sidebar)',
              flexShrink: 0,
              overflowY: 'auto',
              paddingTop: 8,
              borderRight: '1px solid var(--border-subtle)',
            }}
          >
            <nav>
              {MENU_ITEMS.map((item) => {
                const active = isActive(item.path);
                const Icon = item.icon;
                return (
                  <div
                    key={item.path}
                    onClick={() => navigate(item.path)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: '10px 18px',
                      cursor: 'pointer',
                      color: active ? 'var(--accent-primary)' : 'var(--text-dim)',
                      backgroundColor: active ? 'var(--accent-glow)' : 'transparent',
                      borderLeft: active ? '2px solid var(--accent-primary)' : '2px solid transparent',
                      transition: 'all 0.2s',
                      fontSize: 12,
                      fontFamily: 'var(--font-mono)',
                      letterSpacing: 0.5,
                    }}
                    onMouseEnter={(e) => {
                      if (!active) {
                        e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.04)';
                        e.currentTarget.style.color = '#e0e0e0';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!active) {
                        e.currentTarget.style.backgroundColor = 'transparent';
                        e.currentTarget.style.color = 'var(--text-dim)';
                      }
                    }}
                  >
                    <Icon size={15} />
                    <span>{item.label}</span>
                  </div>
                );
              })}
            </nav>
          </aside>
        )}

        {/* Content area */}
        <main
          style={{
            flex: 1,
            backgroundColor: 'var(--bg-base)',
            overflowY: 'auto',
            padding: 20,
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;
