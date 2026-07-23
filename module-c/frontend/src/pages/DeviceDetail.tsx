import React, { useState, useMemo, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Card, Button, Select, Tag, Progress, Spin, Collapse, Space, Empty, Timeline } from 'antd';
import {
  ArrowLeftOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import RULGauge from '../components/RULGauge';
import AgentFlow from '../components/AgentFlow';
import { rulToRiskLevel } from '../utils/riskLevel';
import { RUL_GAUGE_MAX } from '../constants/devices';
import { useDeviceStore } from '../stores/useDeviceStore';
import { useDiagnosisHistoryStore } from '../stores/useDiagnosisHistoryStore';
import { useDiagnosisFlow } from '../hooks/useDiagnosisFlow';
import type { DiagnosisRecord } from '../types/device';

const RISK_TAG_COLOR: Record<DiagnosisRecord['riskLevel'], string> = {
  critical: 'red',
  high: 'orange',
  medium: 'gold',
  low: 'blue',
};

const DeviceDetail: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();

  const devices = useDeviceStore((s) => s.devices);
  const allHistoryRecords = useDiagnosisHistoryStore((s) => s.records);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | undefined>(id);

  const diagnosis = useDiagnosisFlow(selectedDeviceId);

  const deviceHistoryRecords = useMemo(
    () =>
      selectedDeviceId
        ? allHistoryRecords.filter((r) => r.deviceId === selectedDeviceId)
        : [],
    [allHistoryRecords, selectedDeviceId],
  );

  const selectedDevice = useMemo(
    () => devices.find((d) => d.id === selectedDeviceId),
    [devices, selectedDeviceId],
  );
  const deviceOptions = devices.map((d) => ({
    value: d.id,
    label: `${d.id} — ${d.name} (${d.farm})`,
  }));

  const {
    stage,
    errorMsg,
    erroredStep,
    lastProgress,
    monitorResult,
    diagnoseResult,
    diagnoseStatus,
    diagnoseProgress,
    jobId,
    startDiagnosis,
    resetFlow,
    isRunning,
    hasMonitorResult,
    hasDiagnoseActivity,
    formatTimestamp,
    getAttributionColor,
    getStageBadge,
    getUrgencyColor,
  } = diagnosis;

  const handleReset = useCallback(() => {
    resetFlow();
  }, [resetFlow]);

  return (
    <div>
      {/* ── Header bar ─────────────────────────────────────── */}
      <div
        style={{
          marginBottom: 16,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/')}
            type="text"
            style={{ color: 'var(--text-secondary)' }}
          />
          <Select
            showSearch
            value={selectedDeviceId}
            onChange={(val) => {
              handleReset();
              setSelectedDeviceId(val);
            }}
            placeholder="Select device..."
            options={deviceOptions}
            style={{ width: 300 }}
            filterOption={(input, option) =>
              (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
            }
            disabled={isRunning}
          />
          {getStageBadge()}
          {errorMsg && (
            <Tag color="error" style={{ maxWidth: 300 }} title={errorMsg}>
              {errorMsg.length > 40 ? errorMsg.slice(0, 40) + '...' : errorMsg}
            </Tag>
          )}
        </div>

        <Space>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={startDiagnosis}
            disabled={!selectedDeviceId || isRunning}
            loading={isRunning}
            style={{
              fontFamily: 'var(--font-mono)',
              letterSpacing: 1,
              textTransform: 'uppercase',
            }}
          >
            START DIAGNOSIS
          </Button>
          {(stage === 'complete' || stage === 'error') && (
            <Button onClick={handleReset} style={{ fontFamily: 'var(--font-mono)' }}>
              RESET
            </Button>
          )}
        </Space>
      </div>

      {/* ── Error-only state (no monitor result) ───────────── */}
      {stage === 'error' && !monitorResult && (
        <Card
          style={{
            borderColor: 'var(--status-danger)',
            backgroundColor: 'rgba(239,68,68,0.05)',
          }}
        >
          <p style={{ color: 'var(--status-danger)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
            ■ ERROR: {errorMsg}
          </p>
          <Button onClick={handleReset} size="small" style={{ marginTop: 8 }}>
            RETRY
          </Button>
        </Card>
      )}

      {/* ── Agent Flow progress — always visible ────────────── */}
      <div style={{ marginBottom: 16 }}>
        <AgentFlow
          progress={
            stage === 'idle' ? undefined
            : stage === 'analyzing' ? 0
            : stage === 'submitting_diagnose' ? 25
            : stage === 'polling'
              ? diagnoseProgress === 100
                ? 100
                : 50
            : stage === 'complete' ? 100
            : lastProgress
          }
          status={
            stage === 'idle' ? undefined
            : stage === 'analyzing' ? 'acquiring data'
            : stage === 'submitting_diagnose' ? 'submitting job'
            : stage === 'polling' ? 'diagnosing...'
            : stage === 'complete' ? 'complete'
            : stage === 'error' ? 'error'
            : undefined
          }
          erroredStep={stage === 'error' ? erroredStep : undefined}
        />
      </div>

      {/* ── Three-column layout (after analysis starts) ────── */}
      {(hasMonitorResult || hasDiagnoseActivity) && (
        <>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1fr',
              gap: 16,
            }}
          >
            {/* ── Left: Module A — RUL Prediction ─────────── */}
            <Card
              title={
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  ■ MODULE A — RUL PREDICTION
                </span>
              }
              size="small"
              extra={
                monitorResult ? (
                  <Tag color="green" style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                    DONE
                  </Tag>
                ) : (
                  <Spin size="small" />
                )
              }
              style={{ minHeight: 400 }}
            >
              {monitorResult ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <RULGauge
                    rulHours={selectedDevice?.rulHours}
                    confidence={0.88}
                    maxRul={RUL_GAUGE_MAX}
                    riskLevel={
                      !selectedDevice?.rulHours ? 'low' :
                      rulToRiskLevel(selectedDevice.rulHours)
                    }
                  />

                  <div style={{ textAlign: 'center' }}>
                    <span style={{ fontSize: 27, fontWeight: 700, color: 'var(--accent-primary)', fontFamily: 'var(--font-mono)' }}>
                      {selectedDevice?.rulHours ?? '—'}
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginLeft: 4 }}>
                      cyc
                    </span>
                  </div>

                  <div
                    style={{
                      fontSize: 10,
                      color: 'var(--text-dim)',
                      fontFamily: 'var(--font-mono)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 4,
                    }}
                  >
                    <div>
                      EVENT: <span style={{ color: 'var(--accent-primary)' }}>{monitorResult.event_id}</span>
                    </div>
                    <div>
                      MODEL: <span style={{ color: 'var(--text-secondary)' }}>{monitorResult.model_version}</span>
                      {' · '}
                      TIME: {formatTimestamp(monitorResult.timestamp)}
                    </div>
                  </div>

                  {monitorResult.pseudo_attribution && monitorResult.pseudo_attribution.length > 0 && (
                    <div>
                      <div
                        style={{
                          fontSize: 10,
                          color: 'var(--text-secondary)',
                          fontFamily: 'var(--font-mono)',
                          marginBottom: 6,
                          textTransform: 'uppercase',
                        }}
                      >
                        ■ SENSOR ATTRIBUTION
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {monitorResult.pseudo_attribution
                          .slice(0, 10)
                          .sort((a, b) => b.contribution - a.contribution)
                          .map((attr, i) => (
                            <div
                              key={i}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                              }}
                            >
                              <span
                                style={{
                                  fontSize: 10,
                                  fontFamily: 'var(--font-mono)',
                                  color: 'var(--text-secondary)',
                                  width: 60,
                                }}
                              >
                                {attr.feature}
                              </span>
                              <div
                                style={{
                                  flex: 1,
                                  height: 8,
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
                                  fontSize: 9,
                                  fontFamily: 'var(--font-mono)',
                                  color: getAttributionColor(attr.direction),
                                  width: 36,
                                  textAlign: 'right',
                                }}
                              >
                                {(attr.contribution * 100).toFixed(1)}%
                              </span>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
                  <Spin tip="Analyzing sensor data..." />
                </div>
              )}
            </Card>

            {/* ── Center: Module B — Diagnosis ────────────── */}
            <Card
              title={
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  ■ MODULE B — DIAGNOSIS
                </span>
              }
              size="small"
              extra={
                diagnoseResult ? (
                  <Tag color="green" style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                    DONE
                  </Tag>
                ) : stage === 'error' ? (
                  <Tag color="red" style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                    FAILED
                  </Tag>
                ) : hasDiagnoseActivity ? (
                  <Spin size="small" />
                ) : null
              }
              style={{ minHeight: 400 }}
            >
              {hasDiagnoseActivity && (
                <>
                  <div style={{ marginBottom: 16 }}>
                    <div
                      style={{
                        fontSize: 10,
                        color: 'var(--text-dim)',
                        fontFamily: 'var(--font-mono)',
                        marginBottom: 6,
                        textTransform: 'uppercase',
                      }}
                    >
                      JOB STATUS: {diagnoseStatus.toUpperCase()}
                      {jobId && (
                        <span style={{ marginLeft: 8, color: 'var(--accent-primary)' }}>
                          #{jobId.slice(0, 8)}...
                        </span>
                      )}
                    </div>
                    <Progress
                      percent={diagnoseProgress}
                      status={
                        stage === 'error'
                          ? 'exception'
                          : diagnoseProgress === 100
                            ? 'success'
                            : 'active'
                      }
                      strokeColor={{
                        '0%': 'var(--accent-primary)',
                        '100%': 'var(--status-normal)',
                      }}
                      trailColor="var(--bg-elevated)"
                      format={(p) => `${p}%`}
                    />
                  </div>

                  {stage === 'error' && errorMsg && (
                    <div
                      style={{
                        padding: 12,
                        backgroundColor: 'rgba(239,68,68,0.08)',
                        borderRadius: 2,
                        marginBottom: 12,
                      }}
                    >
                      <p
                        style={{
                          color: 'var(--status-danger)',
                          fontFamily: 'var(--font-mono)',
                          fontSize: 11,
                          margin: 0,
                        }}
                      >
                        {errorMsg}
                      </p>
                    </div>
                  )}

                  {diagnoseResult && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      <div>
                        <div
                          style={{
                            fontSize: 10,
                            color: 'var(--text-secondary)',
                            fontFamily: 'var(--font-mono)',
                            marginBottom: 4,
                            textTransform: 'uppercase',
                          }}
                        >
                          ■ ROOT CAUSE
                        </div>
                        <div
                          style={{
                            fontSize: 12,
                            color: 'var(--text-primary)',
                            fontFamily: 'var(--font-mono)',
                            lineHeight: 1.6,
                            padding: 8,
                            backgroundColor: 'var(--bg-elevated)',
                            borderRadius: 2,
                            borderLeft: '2px solid var(--accent-primary)',
                          }}
                        >
                          {diagnoseResult.diagnosis.root_cause}
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                        <Tag
                          color={
                            diagnoseResult.diagnosis.confidence >= 0.8
                              ? 'green'
                              : diagnoseResult.diagnosis.confidence >= 0.5
                                ? 'orange'
                                : 'red'
                          }
                          style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}
                        >
                          CONF: {(diagnoseResult.diagnosis.confidence * 100).toFixed(0)}%
                        </Tag>
                        {diagnoseResult.diagnosis.need_human_review && (
                          <Tag color="orange" style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                            HUMAN REVIEW
                          </Tag>
                        )}
                        {diagnoseResult.diagnosis.l1 && (
                          <Tag style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                            {diagnoseResult.diagnosis.l1}
                          </Tag>
                        )}
                      </div>

                      <div>
                        <div
                          style={{
                            fontSize: 10,
                            color: 'var(--text-dim)',
                            fontFamily: 'var(--font-mono)',
                            marginBottom: 4,
                          }}
                        >
                          L1 → L2 → L3
                        </div>
                        <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                          {[diagnoseResult.diagnosis.l1, diagnoseResult.diagnosis.l2, diagnoseResult.diagnosis.l3]
                            .filter(Boolean)
                            .join(' → ') || 'N/A'}
                        </div>
                      </div>

                      {diagnoseResult.diagnosis.logic_path?.length > 0 && (
                        <Collapse
                          ghost
                          size="small"
                          items={[
                            {
                              key: 'logic',
                              label: (
                                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-secondary)' }}>
                                  ■ LOGIC PATH
                                </span>
                              ),
                              children: (
                                <ol
                                  style={{
                                    margin: 0,
                                    paddingLeft: 16,
                                    fontSize: 10,
                                    fontFamily: 'var(--font-mono)',
                                    color: 'var(--text-dim)',
                                  }}
                                >
                                  {diagnoseResult.diagnosis.logic_path.map((step, i) => (
                                    <li key={i} style={{ marginBottom: 4 }}>{step}</li>
                                  ))}
                                </ol>
                              ),
                            },
                          ]}
                        />
                      )}

                      {diagnoseResult.diagnosis.evidence && (
                        <Collapse
                          ghost
                          size="small"
                          items={[
                            {
                              key: 'evidence',
                              label: (
                                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-secondary)' }}>
                                  ■ EVIDENCE
                                  {diagnoseResult.diagnosis.evidence_level && (
                                    <Tag style={{ marginLeft: 8, fontFamily: 'var(--font-mono)', fontSize: 9 }}>
                                      {diagnoseResult.diagnosis.evidence_level}
                                    </Tag>
                                  )}
                                </span>
                              ),
                              children: (
                                <pre
                                  style={{
                                    margin: 0,
                                    fontSize: 10,
                                    fontFamily: 'var(--font-mono)',
                                    color: 'var(--text-dim)',
                                    whiteSpace: 'pre-wrap',
                                    wordBreak: 'break-word',
                                  }}
                                >
                                  {diagnoseResult.diagnosis.evidence}
                                </pre>
                              ),
                            },
                          ]}
                        />
                      )}

                      {diagnoseResult.diagnosis.mechanism && (
                        <Collapse
                          ghost
                          size="small"
                          items={[
                            {
                              key: 'mechanism',
                              label: (
                                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-secondary)' }}>
                                  ■ MECHANISM
                                </span>
                              ),
                              children: (
                                <div
                                  style={{
                                    fontSize: 10,
                                    fontFamily: 'var(--font-mono)',
                                    color: 'var(--text-dim)',
                                    lineHeight: 1.5,
                                  }}
                                >
                                  {diagnoseResult.diagnosis.mechanism}
                                </div>
                              ),
                            },
                          ]}
                        />
                      )}

                      <div
                        style={{
                          fontSize: 9,
                          color: 'var(--text-dim)',
                          fontFamily: 'var(--font-mono)',
                        }}
                      >
                        RAG HITS: {diagnoseResult.rag_hit_count}
                      </div>
                    </div>
                  )}

                  {!diagnoseResult && stage !== 'error' && (
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'center',
                        padding: 20,
                        color: 'var(--text-dim)',
                        fontFamily: 'var(--font-mono)',
                        fontSize: 11,
                      }}
                    >
                      {stage === 'submitting_diagnose' ? 'Submitting diagnose job...' : 'Waiting for diagnosis result...'}
                    </div>
                  )}
                </>
              )}

              {!hasDiagnoseActivity && hasMonitorResult && (
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'center',
                    padding: 40,
                    color: 'var(--text-dim)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 11,
                  }}
                >
                  Waiting for Module A to complete...
                </div>
              )}
            </Card>

            {/* ── Right: Solution ──────────────────────────── */}
            <Card
              title={
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  ■ SOLUTION
                </span>
              }
              size="small"
              extra={
                diagnoseResult?.solution ? (
                  <Tag
                    color={getUrgencyColor(diagnoseResult.solution.urgency)}
                    style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}
                  >
                    {diagnoseResult.solution.urgency.toUpperCase()}
                  </Tag>
                ) : null
              }
              style={{ minHeight: 400 }}
            >
              {diagnoseResult?.solution ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div>
                    <div
                      style={{
                        fontSize: 10,
                        color: 'var(--text-dim)',
                        fontFamily: 'var(--font-mono)',
                        marginBottom: 4,
                        textTransform: 'uppercase',
                      }}
                    >
                      ■ URGENCY
                    </div>
                    <Tag
                      color={getUrgencyColor(diagnoseResult.solution.urgency)}
                      style={{ fontFamily: 'var(--font-mono)', fontSize: 12, padding: '2px 10px' }}
                    >
                      {diagnoseResult.solution.urgency.toUpperCase()}
                    </Tag>
                  </div>

                  <div>
                    <div
                      style={{
                        fontSize: 10,
                        color: 'var(--text-dim)',
                        fontFamily: 'var(--font-mono)',
                        marginBottom: 6,
                        textTransform: 'uppercase',
                      }}
                    >
                      ■ ACTION PLAN
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {diagnoseResult.solution.action_plan.map((step, i) => (
                        <div
                          key={i}
                          style={{
                            display: 'flex',
                            gap: 8,
                            alignItems: 'flex-start',
                            fontSize: 11,
                            fontFamily: 'var(--font-mono)',
                            color: 'var(--text-secondary)',
                          }}
                        >
                          <span style={{ color: 'var(--accent-primary)', flexShrink: 0 }}>
                            [{i + 1}]
                          </span>
                          <span>{step}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {diagnoseResult.solution.matched_tickets?.length > 0 && (
                    <div>
                      <div
                        style={{
                          fontSize: 10,
                          color: 'var(--text-dim)',
                          fontFamily: 'var(--font-mono)',
                          marginBottom: 6,
                          textTransform: 'uppercase',
                        }}
                      >
                        ■ MATCHED TICKETS
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {diagnoseResult.solution.matched_tickets.map((ticket, i) => (
                          <Tag
                            key={i}
                            style={{ fontFamily: 'var(--font-mono)', fontSize: 9 }}
                          >
                            {ticket}
                          </Tag>
                        ))}
                      </div>
                    </div>
                  )}

                  {diagnoseResult.report_markdown && (
                    <div>
                      <div
                        style={{
                          fontSize: 10,
                          color: 'var(--text-dim)',
                          fontFamily: 'var(--font-mono)',
                          marginBottom: 6,
                          textTransform: 'uppercase',
                        }}
                      >
                        ■ REPORT
                      </div>
                      <pre
                        style={{
                          margin: 0,
                          padding: 8,
                          backgroundColor: 'var(--bg-elevated)',
                          borderRadius: 2,
                          fontSize: 9,
                          fontFamily: 'var(--font-mono)',
                          color: 'var(--text-dim)',
                          maxHeight: 300,
                          overflowY: 'auto',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          lineHeight: 1.5,
                          border: '1px solid var(--border-panel)',
                        }}
                      >
                        {diagnoseResult.report_markdown}
                      </pre>
                    </div>
                  )}
                </div>
              ) : (
                <Empty
                  description={
                    <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                      Solution will appear after diagnosis completes
                    </span>
                  }
                />
              )}
            </Card>
          </div>
        </>
      )}

      {/* ── Diagnosis History ──────────────────────────────── */}
      {selectedDeviceId && (
        <Card
          style={{ marginTop: 16 }}
          title={
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
              ■ DIAGNOSIS HISTORY
            </span>
          }
          size="small"
        >
          {deviceHistoryRecords.length === 0 ? (
            <Empty
              description={
                <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                  No diagnosis history for this device yet.
                </span>
              }
            />
          ) : (
            <Timeline
              items={deviceHistoryRecords.map((record) => ({
                color:
                  record.riskLevel === 'critical' || record.riskLevel === 'high'
                    ? 'red'
                    : record.riskLevel === 'medium'
                      ? 'orange'
                      : 'green',
                children: (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      justifyContent: 'space-between',
                      gap: 12,
                      flexWrap: 'wrap',
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 200 }}>
                      <div
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: 11,
                          color: 'var(--text-secondary)',
                          marginBottom: 4,
                        }}
                      >
                        {formatTimestamp(record.timestamp)}
                      </div>
                      <Space size={8} wrap style={{ marginBottom: 6 }}>
                        <Tag
                          color={RISK_TAG_COLOR[record.riskLevel]}
                          style={{ fontFamily: 'var(--font-mono)', fontSize: 10, margin: 0 }}
                        >
                          {record.riskLevel.toUpperCase()}
                        </Tag>
                        <Tag style={{ fontFamily: 'var(--font-mono)', fontSize: 10, margin: 0 }}>
                          RUL: {record.rulPredicted.toFixed(0)} cyc
                        </Tag>
                      </Space>
                      <div
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: 11,
                          color: 'var(--text-dim)',
                          lineHeight: 1.5,
                        }}
                      >
                        {record.rootCause.length > 120
                          ? `${record.rootCause.slice(0, 120)}...`
                          : record.rootCause}
                      </div>
                    </div>
                    <Button
                      size="small"
                      onClick={() => navigate(`/diagnosis/${record.id}`, { state: { from: 'device' } })}
                      style={{ fontFamily: 'var(--font-mono)', flexShrink: 0 }}
                    >
                      VIEW
                    </Button>
                  </div>
                ),
              }))}
            />
          )}
        </Card>
      )}
    </div>
  );
};

export default DeviceDetail;
