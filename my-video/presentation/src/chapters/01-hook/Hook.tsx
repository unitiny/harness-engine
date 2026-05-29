import "./Hook.css";

interface Props {
  step: number;
}

export default function Hook({ step }: Props) {
  return (
    <div className="hk scene">
      {/* step 0: cold open hook */}
      {step === 0 && (
        <div className="hk-cold-open">
          <div className="hk-stage-grid" />
          <div className="hk-hook-center">
            <span className="hk-hook-label mono">harness-engine</span>
            <h1 className="hk-hook-title serif-cn">
              你让 AI 写代码
              <br />
              <span className="hk-hook-then">然后呢？</span>
            </h1>
            <div className="hk-hook-sub">
              <span className="hk-hook-fail mono">没人管，它就翻车。</span>
            </div>
          </div>
          <div className="hk-corner-frame" />
        </div>
      )}

      {/* step 1: scope diffusion — file tree with red marks */}
      {step === 1 && (
        <div className="hk-scope-diff">
          <div className="hk-sd-header">
            <span className="hk-sd-tag mono">scope 扩散</span>
          </div>
          <div className="hk-sd-body">
            <div className="hk-file-tree">
              <div className="hk-ft-row hk-ft-ok">
                <span className="hk-ft-icon mono">─</span>
                <span className="hk-ft-name mono">src/engine.rs</span>
                <span className="hk-ft-badge mono">task scope</span>
              </div>
              <div className="hk-ft-row hk-ft-ok">
                <span className="hk-ft-icon mono">─</span>
                <span className="hk-ft-name mono">src/scoring.rs</span>
                <span className="hk-ft-badge mono">task scope</span>
              </div>
              <div className="hk-ft-sep" />
              <div className="hk-ft-row hk-ft-bad">
                <span className="hk-ft-icon mono">✕</span>
                <span className="hk-ft-name mono">src/lib.rs</span>
                <span className="hk-ft-badge hk-ft-badge-bad mono">out of scope</span>
              </div>
              <div className="hk-ft-row hk-ft-bad">
                <span className="hk-ft-icon mono">✕</span>
                <span className="hk-ft-name mono">Cargo.toml</span>
                <span className="hk-ft-badge hk-ft-badge-bad mono">out of scope</span>
              </div>
              <div className="hk-ft-row hk-ft-bad">
                <span className="hk-ft-icon mono">✕</span>
                <span className="hk-ft-name mono">docs/api.md</span>
                <span className="hk-ft-badge hk-ft-badge-bad mono">out of scope</span>
              </div>
            </div>
            <div className="hk-sd-quote">
              <span className="hk-sd-quote-text serif-cn">动了不该动的东西</span>
            </div>
          </div>
        </div>
      )}

      {/* step 2: "跑通了" — fake pass with gate failures */}
      {step === 2 && (
        <div className="hk-fake-pass">
          <div className="hk-fp-big-quote serif-cn">
            <span className="hk-fp-q">"</span>跑通了。<span className="hk-fp-q">"</span>
          </div>
          <div className="hk-fp-gates">
            <div className="hk-fp-gate hk-fp-fail">
              <span className="hk-fp-gate-icon mono">✕</span>
              <span className="hk-fp-gate-name mono">scope_diff_gate</span>
              <span className="hk-fp-gate-status mono">NOT RUN</span>
            </div>
            <div className="hk-fp-gate hk-fp-fail">
              <span className="hk-fp-gate-icon mono">✕</span>
              <span className="hk-fp-gate-name mono">dev_gate</span>
              <span className="hk-fp-gate-status mono">NOT RUN</span>
            </div>
            <div className="hk-fp-gate hk-fp-fail">
              <span className="hk-fp-gate-icon mono">✕</span>
              <span className="hk-fp-gate-name mono">review</span>
              <span className="hk-fp-gate-status mono">NONE</span>
            </div>
          </div>
          <div className="hk-fp-verdict mono">
            <span className="hk-fp-accent">它自己觉得行就行。</span>
          </div>
        </div>
      )}

      {/* step 3: harness definition — three pillars */}
      {step === 3 && (
        <div className="hk-definition">
          <div className="hk-def-label mono">harness = AI 的工程纪律</div>
          <div className="hk-def-pillars">
            <div className="hk-def-pillar">
              <div className="hk-def-pillar-icon">
                <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                  <rect x="4" y="4" width="40" height="40" rx="2" stroke="var(--accent)" strokeWidth="2" strokeDasharray="4 3"/>
                  <line x1="4" y1="16" x2="44" y2="16" stroke="var(--accent)" strokeWidth="1.5"/>
                  <line x1="4" y1="28" x2="44" y2="28" stroke="var(--accent)" strokeWidth="1.5"/>
                  <line x1="20" y1="4" x2="20" y2="44" stroke="var(--accent)" strokeWidth="1.5"/>
                </svg>
              </div>
              <div className="hk-def-pillar-title mono">task brief</div>
              <div className="hk-def-pillar-desc">scope 锁死</div>
              <div className="hk-def-pillar-detail mono">
                allowed files<br />
                acceptance criteria<br />
                stop conditions
              </div>
            </div>
            <div className="hk-def-connector">
              <svg width="60" height="24" viewBox="0 0 60 24" fill="none">
                <line x1="0" y1="12" x2="50" y2="12" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="6 4"/>
                <polygon points="50,6 60,12 50,18" fill="var(--accent)"/>
              </svg>
            </div>
            <div className="hk-def-pillar">
              <div className="hk-def-pillar-icon">
                <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                  <rect x="4" y="4" width="40" height="40" rx="2" stroke="var(--accent)" strokeWidth="2" strokeDasharray="4 3"/>
                  <circle cx="24" cy="24" r="12" stroke="var(--accent)" strokeWidth="2"/>
                  <line x1="24" y1="12" x2="24" y2="36" stroke="var(--accent)" strokeWidth="1.5"/>
                  <line x1="12" y1="24" x2="36" y2="24" stroke="var(--accent)" strokeWidth="1.5"/>
                </svg>
              </div>
              <div className="hk-def-pillar-title mono">gate</div>
              <div className="hk-def-pillar-desc">质量卡住</div>
              <div className="hk-def-pillar-detail mono">
                10+ check scripts<br />
                scope / quality / memory<br />
                receipt / alignment
              </div>
            </div>
            <div className="hk-def-connector">
              <svg width="60" height="24" viewBox="0 0 60 24" fill="none">
                <line x1="0" y1="12" x2="50" y2="12" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="6 4"/>
                <polygon points="50,6 60,12 50,18" fill="var(--accent)"/>
              </svg>
            </div>
            <div className="hk-def-pillar">
              <div className="hk-def-pillar-icon">
                <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                  <rect x="4" y="4" width="40" height="40" rx="2" stroke="var(--accent)" strokeWidth="2" strokeDasharray="4 3"/>
                  <path d="M14 28 L22 16 L30 28 L38 12" stroke="var(--accent)" strokeWidth="2" fill="none"/>
                  <circle cx="14" cy="28" r="3" fill="var(--accent)"/>
                  <circle cx="22" cy="16" r="3" fill="var(--accent)"/>
                  <circle cx="30" cy="28" r="3" fill="var(--accent)"/>
                  <circle cx="38" cy="12" r="3" fill="var(--accent)"/>
                </svg>
              </div>
              <div className="hk-def-pillar-title mono">review</div>
              <div className="hk-def-pillar-desc">结果把关</div>
              <div className="hk-def-pillar-detail mono">
                scope verification<br />
                scientific verdict<br />
                memory promotion
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
