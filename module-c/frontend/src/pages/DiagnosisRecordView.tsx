import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { Button, Tag, Collapse, Empty, Spin } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { historyApi } from '../services/api';
import { useDiagnosisHistoryStore } from '../stores/useDiagnosisHistoryStore';
import type { DiagnosisRecord } from '../types/device';

const RISK_TAG_COLOR: Record<DiagnosisRecord['riskLevel'], string> = {
  critical: 'red',
  high: 'orange',
  medium: 'gold',
  low: 'blue',
};

const getUrgencyColor = (urgency: string) => {
  const u = urgency.toLowerCase();
  if (u.includes('critical') || u.includes('emergency')) return 'red';
  if (u.includes('high')) return 'orange';
  if (u.includes('medium')) return 'gold';
  return 'blue';
};

const getAttributionColor = (direction: string) => {
  if (direction === 'high' || direction === 'positive') return '#ef4444';
  if (direction === 'low' || direction === 'negative') return '#3b82f6';
  return '#f59e0b';
};

const formatTimestamp = (ts: string) => {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
};

const DiagnosisRecordView: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { recordId } = useParams<{ recordId: string }>();
  const records = useDiagnosisHistoryStore((s) => s.records);

  const [fetchedRecord, setFetchedRecord] = useState<DiagnosisRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);

  const localRecord = useMemo(
    () => records.find((r) => r.id === recordId),
    [records, recordId],
  );

  const record = localRecord ?? fetchedRecord;

  useEffect(() => {
    if (!recordId || localRecord) return;

    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    setFetchedRecord(null);

    historyApi
      .get(recordId)
      .then((data) => {
        if (!cancelled) setFetchedRecord(data);
      })
      .catch(() => {
        if (!cancelled) setNotFound(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [recordId, localRecord]);

  const handleBack = () => {
    const from = (location.state as { from?: string } | null)?.from;
    if (from === 'history') {
      navigate('/history');
    } else if (record) {
      navigate(`/device/${record.deviceId}`);
    } else {
      navigate('/history');
    }
  };

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <Spin tip="Loading diagnosis record..." />
      </div>
    );
  }

  if (!record && notFound) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <Empty
          description={
            <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
              Record not found
            </span>
          }
        />
        <Button
          type="link"
          onClick={() => navigate('/history')}
          style={{ fontFamily: 'var(--font-mono)', marginTop: 16 }}
        >
          ← Back to History
        </Button>
      </div>
    );
  }

  if (!record) {
    return null;
  }

  const { monitorResult, diagnoseResult } = record;
  const topAttribution = monitorResult.pseudo_attribution
    ?.slice()
    .sort((a, b) => b.contribution - a.contribution)
    .slice(0, 3) ?? [];

  const confidencePct = (record.confidence * 100).toFixed(0);
  const confidenceColor =
    record.confidence >= 0.8 ? 'green' : record.confidence >= 0.5 ? 'orange' : 'red';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minHeight: 'calc(100vh - 120px)' }}>
      {/* ── Top bar ─────────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          flexWrap: 'wrap',
          paddingBottom: 12,
          borderBottom: '1px solid var(--border-panel)',
        }}
      >
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={handleBack}
          type="text"
          style={{ color: 'var(--text-secondary)' }}
        />
        <div style={{ flex: 1, minWidth: 200 }}>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 14,
              color: 'var(--text-primary)',
              fontWeight: 600,
            }}
          >
            {record.deviceName}
          </div>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: 'var(--text-dim)',
              marginTop: 2,
            }}
          >
            {record.deviceId} · {formatTimestamp(record.timestamp)}
          </div>
        </div>
        <Tag
          color={RISK_TAG_COLOR[record.riskLevel]}
          style={{ fontFamily: 'var(--font-mono)', fontSize: 11, padding: '2px 10px' }}
        >
          {record.riskLevel.toUpperCase()}
        </Tag>
        <Tag
          color={getUrgencyColor(record.urgency)}
          style={{ fontFamily: 'var(--font-mono)', fontSize: 11, padding: '2px 10px', fontWeight: 700 }}
        >
          {record.urgency.toUpperCase()}
        </Tag>
      </div>

      {/* ── Body: sidebar + main ────────────────────────────── */}
      <div style={{ display: 'flex', gap: 16, flex: 1, alignItems: 'flex-start' }}>
        {/* ── Left sidebar (30%) ─────────────────────────────── */}
        <div style={{ width: '30%', minWidth: 240, flexShrink: 0 }}>
          <Collapse
            ghost
            defaultActiveKey={['moduleA', 'moduleB']}
            items={[
              {
                key: 'moduleA',
                label: (
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)' }}>
                    ■ MODULE A — RUL PREDICTION
                  </span>
                ),
                children: (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                      <span
                        style={{
                          fontSize: 28,
                          fontWeight: 700,
                          color: 'var(--accent-primary)',
                          fontFamily: 'var(--font-mono)',
                        }}
                      >
                        {record.rulPredicted.toFixed(0)}
                      </span>
                      <span style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                        cyc
                      </span>
                      <Tag
                        color={RISK_TAG_COLOR[record.riskLevel]}
                        style={{ fontFamily: 'var(--font-mono)', fontSize: 9, margin: 0 }}
                      >
                        {record.riskLevel.toUpperCase()}
                      </Tag>
                    </div>

                    {topAttribution.length > 0 && (
                      <div>
                        <div
                          style={{
                            fontSize: 9,
                            color: 'var(--text-dim)',
                            fontFamily: 'var(--font-mono)',
                            marginBottom: 6,
                            textTransform: 'uppercase',
                          }}
                        >
                          Top Sensors
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                          {topAttribution.map((attr, i) => (
                            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <span
                                style={{
                                  fontSize: 9,
                                  fontFamily: 'var(--font-mono)',
                                  color: 'var(--text-secondary)',
                                  width: 52,
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                }}
                              >
                                {attr.feature}
                              </span>
                              <div
                                style={{
                                  flex: 1,
                                  height: 6,
                                  backgroundColor: 'var(--bg-elevated)',
                                  borderRadius: 1,
                                  overflow: 'hidden',
                                }}
                              >
                                <div
                                  style={{
                                    height: '100%',
                                    width: `${Math.min(Math.abs(attr.contribution) * 100, 100)}%`,
                                    backgroundColor: getAttributionColor(attr.direction),
                                    borderRadius: 1,
                                  }}
                                />
                              </div>
                              <span
                                style={{
                                  fontSize: 8,
                                  fontFamily: 'var(--font-mono)',
                                  color: getAttributionColor(attr.direction),
                                  width: 32,
                                  textAlign: 'right',
                                }}
                              >
                                {(attr.contribution * 100).toFixed(0)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ),
              },
              {
                key: 'moduleB',
                label: (
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)' }}>
                    ■ MODULE B — DIAGNOSIS
                  </span>
                ),
                children: (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div
                      style={{
                        fontSize: 11,
                        color: 'var(--text-primary)',
                        fontFamily: 'var(--font-mono)',
                        lineHeight: 1.5,
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                      }}
                    >
                      {record.rootCause}
                    </div>
                    <Tag
                      color={confidenceColor}
                      style={{ fontFamily: 'var(--font-mono)', fontSize: 9, alignSelf: 'flex-start' }}
                    >
                      CONF: {confidencePct}%
                    </Tag>
                    {record.logicPath.length > 0 && (
                      <Collapse
                        ghost
                        size="small"
                        items={[
                          {
                            key: 'logic',
                            label: (
                              <span
                                style={{
                                  fontFamily: 'var(--font-mono)',
                                  fontSize: 9,
                                  color: 'var(--text-dim)',
                                }}
                              >
                                ■ LOGIC PATH
                              </span>
                            ),
                            children: (
                              <ol
                                style={{
                                  margin: 0,
                                  paddingLeft: 16,
                                  fontSize: 9,
                                  fontFamily: 'var(--font-mono)',
                                  color: 'var(--text-dim)',
                                }}
                              >
                                {record.logicPath.map((step, i) => (
                                  <li key={i} style={{ marginBottom: 3 }}>
                                    {step}
                                  </li>
                                ))}
                              </ol>
                            ),
                          },
                        ]}
                      />
                    )}
                  </div>
                ),
              },
            ]}
          />
        </div>

        {/* ── Main area (70%) — SOLUTION hero ─────────────────── */}
        <div
          style={{
            flex: 1,
            backgroundColor: 'var(--bg-panel)',
            border: '1px solid var(--border-panel)',
            borderRadius: 2,
            padding: 24,
            display: 'flex',
            flexDirection: 'column',
            gap: 24,
          }}
        >
          {/* URGENCY */}
          <div>
            <div
              style={{
                fontSize: 10,
                color: 'var(--text-dim)',
                fontFamily: 'var(--font-mono)',
                marginBottom: 8,
                textTransform: 'uppercase',
                letterSpacing: 1,
              }}
            >
              ■ URGENCY
            </div>
            <Tag
              color={getUrgencyColor(record.urgency)}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 16,
                fontWeight: 700,
                padding: '6px 16px',
                letterSpacing: 1,
              }}
            >
              {record.urgency.toUpperCase()}
            </Tag>
          </div>

          {/* ACTION PLAN */}
          <div>
            <div
              style={{
                fontSize: 10,
                color: 'var(--text-dim)',
                fontFamily: 'var(--font-mono)',
                marginBottom: 12,
                textTransform: 'uppercase',
                letterSpacing: 1,
              }}
            >
              ■ ACTION PLAN
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {record.actionPlan.map((step, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    gap: 12,
                    alignItems: 'flex-start',
                    padding: '12px 16px',
                    backgroundColor: 'var(--bg-elevated)',
                    borderLeft: '3px solid var(--accent-primary)',
                    borderRadius: 2,
                  }}
                >
                  <span
                    style={{
                      color: 'var(--accent-primary)',
                      fontFamily: 'var(--font-mono)',
                      fontSize: 15,
                      fontWeight: 700,
                      flexShrink: 0,
                    }}
                  >
                    [{i + 1}]
                  </span>
                  <span
                    style={{
                      fontSize: 15,
                      fontFamily: 'var(--font-mono)',
                      color: 'var(--text-primary)',
                      lineHeight: 1.6,
                    }}
                  >
                    {step}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* REPORT */}
          {diagnoseResult.report_markdown && (
            <div>
              <div
                style={{
                  fontSize: 10,
                  color: 'var(--text-dim)',
                  fontFamily: 'var(--font-mono)',
                  marginBottom: 8,
                  textTransform: 'uppercase',
                  letterSpacing: 1,
                }}
              >
                ■ REPORT
              </div>
              <pre
                style={{
                  margin: 0,
                  padding: 16,
                  backgroundColor: '#0a0e14',
                  borderRadius: 2,
                  fontSize: 11,
                  fontFamily: 'var(--font-mono)',
                  color: '#00e676',
                  maxHeight: 400,
                  overflowY: 'auto',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  lineHeight: 1.6,
                  border: '1px solid var(--border-panel)',
                }}
              >
                {diagnoseResult.report_markdown}
              </pre>
            </div>
          )}

          {/* MATCHED TICKETS */}
          {diagnoseResult.solution?.matched_tickets &&
            diagnoseResult.solution.matched_tickets.length > 0 && (
              <div>
                <div
                  style={{
                    fontSize: 10,
                    color: 'var(--text-dim)',
                    fontFamily: 'var(--font-mono)',
                    marginBottom: 8,
                    textTransform: 'uppercase',
                    letterSpacing: 1,
                  }}
                >
                  ■ MATCHED TICKETS
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {diagnoseResult.solution.matched_tickets.map((ticket, i) => (
                    <Tag key={i} style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                      {ticket}
                    </Tag>
                  ))}
                </div>
              </div>
            )}
        </div>
      </div>
    </div>
  );
};

export default DiagnosisRecordView;
