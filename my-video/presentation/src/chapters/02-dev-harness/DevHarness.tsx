import "./DevHarness.css";

interface Props {
  step: number;
}

export default function DevHarness({ step }: Props) {
  return (
    <div className="dh scene">
      {/* step 0: loop overview — task brief → execute → gate → review → commit */}
      {step === 0 && (
        <div className="dh-loop">
          <div className="dh-loop-label mono">dev harness · execution loop</div>
          <div className="dh-loop-flow">
            <div className="dh-loop-node">
              <div className="dh-loop-icon">
                <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                  <rect x="4" y="4" width="32" height="32" rx="2" stroke="var(--accent)" strokeWidth="2" strokeDasharray="4 3"/>
                  <line x1="4" y1="14" x2="36" y2="14" stroke="var(--accent)" strokeWidth="1.5"/>
                  <line x1="4" y1="24" x2="36" y2="24" stroke="var(--accent)" strokeWidth="1.5"/>
                  <line x1="16" y1="4" x2="16" y2="36" stroke="var(--accent)" strokeWidth="1.5"/>
                </svg>
              </div>
              <div className="dh-loop-title mono">task brief</div>
              <div className="dh-loop-desc">写 scope</div>
            </div>
            <div className="dh-loop-arrow">
              <svg width="48" height="20" viewBox="0 0 48 20" fill="none">
                <line x1="0" y1="10" x2="38" y2="10" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="6 4"/>
                <polygon points="38,4 48,10 38,16" fill="var(--accent)"/>
              </svg>
            </div>
            <div className="dh-loop-node">
              <div className="dh-loop-icon">
                <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                  <rect x="4" y="4" width="32" height="32" rx="2" stroke="var(--accent)" strokeWidth="2" strokeDasharray="4 3"/>
                  <path d="M14 28 L20 12 L26 28" stroke="var(--accent)" strokeWidth="2" fill="none"/>
                  <circle cx="20" cy="10" r="3" fill="var(--accent)"/>
                </svg>
              </div>
              <div className="dh-loop-title mono">execute</div>
              <div className="dh-loop-desc">干活</div>
            </div>
            <div className="dh-loop-arrow">
              <svg width="48" height="20" viewBox="0 0 48 20" fill="none">
                <line x1="0" y1="10" x2="38" y2="10" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="6 4"/>
                <polygon points="38,4 48,10 38,16" fill="var(--accent)"/>
              </svg>
            </div>
            <div className="dh-loop-node dh-loop-node-gate">
              <div className="dh-loop-icon">
                <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                  <rect x="4" y="4" width="32" height="32" rx="2" stroke="var(--accent)" strokeWidth="2" strokeDasharray="4 3"/>
                  <circle cx="20" cy="20" r="10" stroke="var(--accent)" strokeWidth="2"/>
                  <line x1="20" y1="10" x2="20" y2="30" stroke="var(--accent)" strokeWidth="1.5"/>
                  <line x1="10" y1="20" x2="30" y2="20" stroke="var(--accent)" strokeWidth="1.5"/>
                </svg>
              </div>
              <div className="dh-loop-title mono">gate</div>
              <div className="dh-loop-desc">质量卡住</div>
            </div>
            <div className="dh-loop-arrow">
              <svg width="48" height="20" viewBox="0 0 48 20" fill="none">
                <line x1="0" y1="10" x2="38" y2="10" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="6 4"/>
                <polygon points="38,4 48,10 38,16" fill="var(--accent)"/>
              </svg>
            </div>
            <div className="dh-loop-node">
              <div className="dh-loop-icon">
                <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                  <rect x="4" y="4" width="32" height="32" rx="2" stroke="var(--accent)" strokeWidth="2" strokeDasharray="4 3"/>
                  <path d="M12 16 L28 16 L28 30 L12 30 Z" stroke="var(--accent)" strokeWidth="1.5" fill="none"/>
                  <path d="M12 16 L20 8 L28 16" stroke="var(--accent)" strokeWidth="1.5" fill="none"/>
                </svg>
              </div>
              <div className="dh-loop-title mono">review</div>
              <div className="dh-loop-desc">结果把关</div>
            </div>
            <div className="dh-loop-arrow">
              <svg width="48" height="20" viewBox="0 0 48 20" fill="none">
                <line x1="0" y1="10" x2="38" y2="10" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="6 4"/>
                <polygon points="38,4 48,10 38,16" fill="var(--accent)"/>
              </svg>
            </div>
            <div className="dh-loop-node dh-loop-node-commit">
              <div className="dh-loop-icon">
                <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                  <rect x="4" y="4" width="32" height="32" rx="2" stroke="var(--accent)" strokeWidth="2" strokeDasharray="4 3"/>
                  <circle cx="20" cy="18" r="8" stroke="var(--accent)" strokeWidth="2"/>
                  <path d="M16 18 L19 21 L24 15" stroke="var(--accent)" strokeWidth="2" fill="none"/>
                  <line x1="14" y1="32" x2="26" y2="32" stroke="var(--accent)" strokeWidth="1.5"/>
                </svg>
              </div>
              <div className="dh-loop-title mono">commit</div>
              <div className="dh-loop-desc">提交</div>
            </div>
          </div>
          <div className="dh-loop-footer mono">一圈都有脚本盯着</div>
          {/* loop-back arc */}
          <div className="dh-loop-arc">
            <svg width="900" height="80" viewBox="0 0 900 80" fill="none">
              <path d="M830 10 C860 60, 40 60, 70 10" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="6 4" fill="none" opacity="0.4"/>
              <polygon points="64,14 70,2 78,14" fill="var(--accent)" opacity="0.4"/>
            </svg>
          </div>
        </div>
      )}

      {/* step 1: dual model architecture */}
      {step === 1 && (
        <div className="dh-dual">
          <div className="dh-dual-label mono">双模型分工</div>
          <div className="dh-dual-body">
            <div className="dh-dual-model dh-dual-architect">
              <div className="dh-dual-model-badge mono">architect</div>
              <div className="dh-dual-model-tier mono">GPT-5.5 · 高配</div>
              <div className="dh-dual-model-icon">
                <svg width="56" height="56" viewBox="0 0 56 56" fill="none">
                  <rect x="4" y="4" width="48" height="48" rx="2" stroke="var(--accent)" strokeWidth="2" strokeDasharray="4 3"/>
                  <circle cx="28" cy="22" r="8" stroke="var(--accent)" strokeWidth="1.5"/>
                  <path d="M16 44 C16 34, 40 34, 40 44" stroke="var(--accent)" strokeWidth="1.5" fill="none"/>
                  <circle cx="44" cy="12" r="4" stroke="var(--accent)" strokeWidth="1" fill="var(--accent)" opacity="0.3"/>
                  <circle cx="12" cy="12" r="4" stroke="var(--accent)" strokeWidth="1" fill="var(--accent)" opacity="0.3"/>
                </svg>
              </div>
              <div className="dh-dual-model-tasks">
                <div className="dh-dual-task mono">
                  <span className="dh-dual-task-arrow">→</span> 写 task brief
                </div>
                <div className="dh-dual-task mono">
                  <span className="dh-dual-task-arrow">→</span> 审 review
                </div>
              </div>
              <div className="dh-dual-model-role">管方向</div>
            </div>
            <div className="dh-dual-center">
              <div className="dh-dual-brief-card">
                <div className="dh-dual-brief-title mono">task brief</div>
                <div className="dh-dual-brief-lines mono">
                  <span>scope</span>
                  <span>acceptance</span>
                  <span>verification</span>
                </div>
              </div>
              <div className="dh-dual-center-arrows">
                <svg width="160" height="80" viewBox="0 0 160 80" fill="none">
                  <line x1="10" y1="24" x2="70" y2="24" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="6 4"/>
                  <polygon points="70,18 80,24 70,30" fill="var(--accent)"/>
                  <line x1="150" y1="56" x2="90" y2="56" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="6 4"/>
                  <polygon points="90,50 80,56 90,62" fill="var(--accent)"/>
                  <text x="80" y="44" textAnchor="middle" fill="var(--text-mute)" fontFamily="var(--font-mono)" fontSize="11" letterSpacing="0.1em">RECEIPT</text>
                </svg>
              </div>
            </div>
            <div className="dh-dual-model dh-dual-implementer">
              <div className="dh-dual-model-badge mono">implementer</div>
              <div className="dh-dual-model-tier mono">GLM-5.1 · 低配</div>
              <div className="dh-dual-model-icon">
                <svg width="56" height="56" viewBox="0 0 56 56" fill="none">
                  <rect x="4" y="4" width="48" height="48" rx="2" stroke="var(--accent)" strokeWidth="2" strokeDasharray="4 3"/>
                  <path d="M18 40 L28 16 L38 40" stroke="var(--accent)" strokeWidth="2" fill="none"/>
                  <circle cx="28" cy="14" r="3" fill="var(--accent)"/>
                </svg>
              </div>
              <div className="dh-dual-model-tasks">
                <div className="dh-dual-task mono">
                  <span className="dh-dual-task-arrow">→</span> 领 task 干活
                </div>
                <div className="dh-dual-task mono">
                  <span className="dh-dual-task-arrow">→</span> 交 receipt
                </div>
              </div>
              <div className="dh-dual-model-role">管执行</div>
            </div>
          </div>
          <div className="dh-dual-bottom mono">
            token 省，质量不丢
          </div>
        </div>
      )}

      {/* step 2: gate system */}
      {step === 2 && (
        <div className="dh-gates">
          <div className="dh-gates-header">
            <span className="dh-gates-tag mono">gate 体系</span>
            <span className="dh-gates-count mono">10+ check scripts</span>
          </div>
          <div className="dh-gates-grid">
            <div className="dh-gate-card">
              <div className="dh-gate-name mono">scope_diff_gate</div>
              <div className="dh-gate-desc">改的文件跟 task 对不对得上</div>
              <div className="dh-gate-dot" />
            </div>
            <div className="dh-gate-card">
              <div className="dh-gate-name mono">dev_gate</div>
              <div className="dh-gate-desc">整体质量检查</div>
              <div className="dh-gate-dot" />
            </div>
            <div className="dh-gate-card">
              <div className="dh-gate-name mono">write_task_gate</div>
              <div className="dh-gate-desc">task 本身写得合不合格</div>
              <div className="dh-gate-dot" />
            </div>
            <div className="dh-gate-card">
              <div className="dh-gate-name mono">receipt_gate</div>
              <div className="dh-gate-desc">交付物结构化验证记录</div>
              <div className="dh-gate-dot" />
            </div>
            <div className="dh-gate-card">
              <div className="dh-gate-name mono">memory_gate</div>
              <div className="dh-gate-desc">经验沉淀检查</div>
              <div className="dh-gate-dot" />
            </div>
            <div className="dh-gate-card">
              <div className="dh-gate-name mono">epic_alignment_gate</div>
              <div className="dh-gate-desc">跟 epic 方向对齐</div>
              <div className="dh-gate-dot" />
            </div>
          </div>
          <div className="dh-gates-footer mono">各有各的检查域</div>
        </div>
      )}

      {/* step 3: five-layer acceptance */}
      {step === 3 && (
        <div className="dh-layers">
          <div className="dh-layers-label mono">五层验收模型</div>
          <div className="dh-layers-stack">
            <div className="dh-layer" style={{ "--layer-n": 1 } as React.CSSProperties}>
              <div className="dh-layer-num mono">L1</div>
              <div className="dh-layer-content">
                <div className="dh-layer-title">页面可达</div>
                <div className="dh-layer-detail mono">页面能不能打开</div>
              </div>
              <div className="dh-layer-check">✓</div>
            </div>
            <div className="dh-layer" style={{ "--layer-n": 2 } as React.CSSProperties}>
              <div className="dh-layer-num mono">L2</div>
              <div className="dh-layer-content">
                <div className="dh-layer-title">API 状态码</div>
                <div className="dh-layer-detail mono">状态对不对</div>
              </div>
              <div className="dh-layer-check">✓</div>
            </div>
            <div className="dh-layer" style={{ "--layer-n": 3 } as React.CSSProperties}>
              <div className="dh-layer-num mono">L3</div>
              <div className="dh-layer-content">
                <div className="dh-layer-title">控制台无错</div>
                <div className="dh-layer-detail mono">控制台有没有报错</div>
              </div>
              <div className="dh-layer-check">✓</div>
            </div>
            <div className="dh-layer" style={{ "--layer-n": 4 } as React.CSSProperties}>
              <div className="dh-layer-num mono">L4</div>
              <div className="dh-layer-content">
                <div className="dh-layer-title">DOM 可见可交互</div>
                <div className="dh-layer-detail mono">元素在不在、能不能点</div>
              </div>
              <div className="dh-layer-check">✓</div>
            </div>
            <div className="dh-layer" style={{ "--layer-n": 5 } as React.CSSProperties}>
              <div className="dh-layer-num mono">L5</div>
              <div className="dh-layer-content">
                <div className="dh-layer-title">数据持久化</div>
                <div className="dh-layer-detail mono">数据刷了还在不在</div>
              </div>
              <div className="dh-layer-check">✓</div>
            </div>
          </div>
          <div className="dh-layers-footer mono">层层过关</div>
        </div>
      )}

      {/* step 4: scope contract */}
      {step === 4 && (
        <div className="dh-scope">
          <div className="dh-scope-header">
            <span className="dh-scope-tag mono">scope contract</span>
            <span className="dh-scope-src mono">task brief 结构拆解</span>
          </div>
          <div className="dh-scope-body">
            <div className="dh-scope-brief">
              <div className="dh-scope-brief-header mono">
                <span className="dh-scope-brief-icon">□</span>
                task brief
              </div>
              <div className="dh-scope-fields">
                <div className="dh-scope-field">
                  <div className="dh-scope-field-name mono">allowed files</div>
                  <div className="dh-scope-field-val mono">
                    src/engine.rs<br />
                    src/scoring.rs<br />
                    tests/engine_test.rs
                  </div>
                  <div className="dh-scope-field-note">能改哪些文件</div>
                </div>
                <div className="dh-scope-field">
                  <div className="dh-scope-field-name mono">acceptance criteria</div>
                  <div className="dh-scope-field-val mono">
                    所有测试通过<br />
                    无新 warning<br />
                    性能不退化
                  </div>
                  <div className="dh-scope-field-note">验收标准</div>
                </div>
                <div className="dh-scope-field">
                  <div className="dh-scope-field-name mono">verification command</div>
                  <div className="dh-scope-field-val mono">
                    cargo test<br />
                    cargo clippy
                  </div>
                  <div className="dh-scope-field-note">验证命令</div>
                </div>
                <div className="dh-scope-field">
                  <div className="dh-scope-field-name mono">stop conditions</div>
                  <div className="dh-scope-field-val mono">
                    scope 扩散 → 停<br />
                    gate 不过 → 停<br />
                    超时 → 停
                  </div>
                  <div className="dh-scope-field-note">停的条件</div>
                </div>
              </div>
            </div>
            <div className="dh-scope-side">
              <div className="dh-scope-lock mono">
                <div className="dh-scope-lock-label">领 task 时</div>
                <div className="dh-scope-lock-action">scope 锁死</div>
                <div className="dh-scope-lock-line" />
                <div className="dh-scope-lock-label">干完</div>
                <div className="dh-scope-lock-action">交 receipt</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
