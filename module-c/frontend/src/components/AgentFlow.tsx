import React from 'react';

/**
 * AgentFlow — Agent workflow visualization component (暗夜工控风格).
 *
 * Accepts optional progress (0-100) and status to highlight active step:
 *   - progress=0  → ACQUIRE active
 *   - progress=1-49 → DETECT active
 *   - progress=50 → DIAGNOSE active
 *   - progress=51-99 → RETRIEVE active
 *   - progress=100 → GENERATE active (green glow)
 * If no progress prop, all steps show dimmed (default).
 */
interface AgentFlowProps {
  progress?: number;
  status?: string;
  erroredStep?: number; // highlight this step in red
}

const AgentFlow: React.FC<AgentFlowProps> = ({ progress, status, erroredStep }) => {
  const steps = [
    { icon: '◈', label: 'ACQUIRE' },
    { icon: '◇', label: 'DETECT' },
    { icon: '◆', label: 'DIAGNOSE' },
    { icon: '◉', label: 'RETRIEVE' },
    { icon: '◎', label: 'GENERATE' },
  ];

  // Determine active step from progress
  const getActiveStep = (): number => {
    if (progress === undefined) return -1; // all dimmed
    if (progress === 0) return 0; // ACQUIRE
    if (progress < 50) return 1; // DETECT
    if (progress === 50) return 2; // DIAGNOSE
    if (progress < 100) return 3; // RETRIEVE
    return 4; // GENERATE
  };

  const activeStep = getActiveStep();
  const isComplete = progress === 100;

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-panel)',
        borderRadius: 2,
        padding: 16,
        border: '1px solid var(--border-panel)',
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          marginBottom: 16,
          color: 'var(--text-secondary)',
          fontFamily: 'var(--font-mono)',
          textTransform: 'uppercase',
          letterSpacing: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span>■ AGENT WORKFLOW</span>
        {status && (
          <span style={{ color: 'var(--accent-primary)', fontSize: 10 }}>
            {status.toUpperCase()}
          </span>
        )}
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 4,
        }}
      >
        {steps.map((step, idx) => {
          const isActive = idx === activeStep;
          const isDone = activeStep > idx;
          const isErrored = erroredStep !== undefined && idx === erroredStep;

          // Errored step takes priority over all other styling
          const bgColor = isErrored
            ? 'rgba(239,68,68,0.15)'
            : isComplete && idx === 4
              ? 'var(--status-normal)'
              : isActive
                ? 'var(--accent-glow)'
                : isDone
                  ? 'rgba(0,255,0,0.08)'
                  : 'var(--bg-elevated)';

          const borderColor = isErrored
            ? 'var(--status-danger)'
            : isComplete && idx === 4
              ? 'var(--status-normal)'
              : isActive
                ? 'var(--accent-primary)'
                : isDone
                  ? 'var(--status-normal)'
                  : 'var(--border-panel)';

          const textColor = isErrored
            ? 'var(--status-danger)'
            : isComplete && idx === 4
              ? 'var(--status-normal)'
              : isActive
                ? 'var(--accent-primary)'
                : isDone
                  ? 'var(--status-normal)'
                  : 'var(--text-dim)';

          return (
            <React.Fragment key={step.label}>
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 8,
                  fontSize: 11,
                  fontFamily: 'var(--font-mono)',
                  color: textColor,
                }}
              >
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: '50%',
                    backgroundColor: bgColor,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 14,
                    color: textColor,
                    border: `1px solid ${borderColor}`,
                    boxShadow: isErrored
                      ? `0 0 8px var(--status-danger)`
                      : isActive || (isComplete && idx === 4)
                      ? `0 0 8px ${borderColor}`
                      : 'none',
                    transition: 'all 0.3s ease',
                  }}
                >
                  {step.icon}
                </div>
                <span>{isErrored ? `${step.label} ERROR` : step.label}</span>
              </div>
              {idx < steps.length - 1 && (
                <div
                  style={{
                    flex: 1,
                    height: 1,
                    backgroundColor: isDone
                      ? 'var(--status-normal)'
                      : isActive
                        ? 'var(--accent-primary)'
                        : 'var(--border-panel)',
                    marginTop: -20,
                    transition: 'background-color 0.3s ease',
                  }}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};

export default AgentFlow;
