import "./MetaHarness.css";

interface Props {
  step: number;
}

export default function MetaHarness({ step }: Props) {
  return (
    <div className="mh scene">
      {/* step 0: intro — "harness 谁来查？" */}
      {step === 0 && (
        <div className="mh-intro">
          <div className="mh-intro-grid" />
          <div className="mh-intro-center">
            <span className="mh-intro-kicker mono">chapter 03</span>
            <h1 className="mh-intro-title serif-cn">
              harness 谁来查？
            </h1>
            <div className="mh-intro-def">
              <div className="mh-intro-def-card">
                <div className="mh-intro-def-name mono">Meta Harness</div>
                <div className="mh-intro-def-desc">只看不动手</div>
                <div className="mh-intro-def-detail mono">
                  observes artifacts<br />
                  diagnoses gaps<br />
                  proposes improvements
                </div>
              </div>
            </div>
            <div className="mh-intro-boundary mono">
              may propose, may not promote
            </div>
          </div>
        </div>
      )}

      {/* step 1: seven-step pipeline */}
      {step === 1 && (
        <div className="mh-pipeline">
          <div className="mh-pipeline-header">
            <span className="mh-pipeline-tag mono">七步 pipeline</span>
          </div>
          <div className="mh-pipeline-flow">
            <div className="mh-pipe-step mh-pipe-find">
              <div className="mh-pipe-num mono">01</div>
              <div className="mh-pipe-name mono">collect-signals</div>
              <div className="mh-pipe-desc">采集产出物</div>
            </div>
            <div className="mh-pipe-arrow">
              <svg width="32" height="16" viewBox="0 0 32 16" fill="none">
                <line x1="0" y1="8" x2="24" y2="8" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="4 3"/>
                <polygon points="24,3 32,8 24,13" fill="var(--accent)"/>
              </svg>
            </div>
            <div className="mh-pipe-step mh-pipe-find">
              <div className="mh-pipe-num mono">02</div>
              <div className="mh-pipe-name mono">analyze-gaps</div>
              <div className="mh-pipe-desc">分析质量缺口</div>
            </div>
            <div className="mh-pipe-arrow">
              <svg width="32" height="16" viewBox="0 0 32 16" fill="none">
                <line x1="0" y1="8" x2="24" y2="8" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="4 3"/>
                <polygon points="24,3 32,8 24,13" fill="var(--accent)"/>
              </svg>
            </div>
            <div className="mh-pipe-step mh-pipe-find">
              <div className="mh-pipe-num mono">03</div>
              <div className="mh-pipe-name mono">build-evidence</div>
              <div className="mh-pipe-desc">打包证据</div>
            </div>
            <div className="mh-pipe-arrow">
              <svg width="32" height="16" viewBox="0 0 32 16" fill="none">
                <line x1="0" y1="8" x2="24" y2="8" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="4 3"/>
                <polygon points="24,3 32,8 24,13" fill="var(--accent)"/>
              </svg>
            </div>
            <div className="mh-pipe-step mh-pipe-find">
              <div className="mh-pipe-num mono">04</div>
              <div className="mh-pipe-name mono">semantic-triage</div>
              <div className="mh-pipe-desc">语义分诊</div>
            </div>
          </div>
          <div className="mh-pipeline-divider">
            <div className="mh-pipeline-divider-line" />
            <div className="mh-pipeline-divider-text mono">前四步找问题 → 后三步出方案</div>
            <div className="mh-pipeline-divider-line" />
          </div>
          <div className="mh-pipeline-flow">
            <div className="mh-pipe-step mh-pipe-fix">
              <div className="mh-pipe-num mono">05</div>
              <div className="mh-pipe-name mono">propose-repairs</div>
              <div className="mh-pipe-desc">提修复方案</div>
            </div>
            <div className="mh-pipe-arrow">
              <svg width="32" height="16" viewBox="0 0 32 16" fill="none">
                <line x1="0" y1="8" x2="24" y2="8" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="4 3"/>
                <polygon points="24,3 32,8 24,13" fill="var(--accent)"/>
              </svg>
            </div>
            <div className="mh-pipe-step mh-pipe-fix">
              <div className="mh-pipe-num mono">06</div>
              <div className="mh-pipe-name mono">replay-contracts</div>
              <div className="mh-pipe-desc">回放验证</div>
            </div>
            <div className="mh-pipe-arrow">
              <svg width="32" height="16" viewBox="0 0 32 16" fill="none">
                <line x1="0" y1="8" x2="24" y2="8" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="4 3"/>
                <polygon points="24,3 32,8 24,13" fill="var(--accent)"/>
              </svg>
            </div>
            <div className="mh-pipe-step mh-pipe-fix">
              <div className="mh-pipe-num mono">07</div>
              <div className="mh-pipe-name mono">render-report</div>
              <div className="mh-pipe-desc">出报告</div>
            </div>
          </div>
        </div>
      )}

      {/* step 2: four gap types */}
      {step === 2 && (
        <div className="mh-gaps">
          <div className="mh-gaps-header">
            <span className="mh-gaps-tag mono">四类缺口</span>
            <span className="mh-gaps-sub">找什么？</span>
          </div>
          <div className="mh-gaps-grid">
            <div className="mh-gap-card">
              <div className="mh-gap-type mono">token_waste</div>
              <div className="mh-gap-example">
                同样的模板写了一遍又一遍没复用，每次从头生成
              </div>
              <div className="mh-gap-severity mono">waste</div>
            </div>
            <div className="mh-gap-card">
              <div className="mh-gap-type mono">ai_guidance_gap</div>
              <div className="mh-gap-example">
                scope 写得含糊，验收条件也含糊，AI 不知道边界在哪
              </div>
              <div className="mh-gap-severity mono">guidance</div>
            </div>
            <div className="mh-gap-card">
              <div className="mh-gap-type mono">delivery_quality_risk</div>
              <div className="mh-gap-example">
                review 不带 diff 就交了，BLOCKED 任务没人管
              </div>
              <div className="mh-gap-severity mono">risk</div>
            </div>
            <div className="mh-gap-card">
              <div className="mh-gap-type mono">missing_evaluator_coverage</div>
              <div className="mh-gap-example">
                某类变更没有对应的检查脚本，漏网之鱼
              </div>
              <div className="mh-gap-severity mono">coverage</div>
            </div>
          </div>
        </div>
      )}

      {/* step 3: prediction contract */}
      {step === 3 && (
        <div className="mh-contract">
          <div className="mh-contract-header">
            <span className="mh-contract-tag mono">prediction contract</span>
            <span className="mh-contract-sub">关键机制</span>
          </div>
          <div className="mh-contract-body">
            <div className="mh-contract-vs">
              <div className="mh-contract-side mh-contract-bad">
                <div className="mh-contract-side-label mono">不是</div>
                <div className="mh-contract-side-text">"建议改进"</div>
                <div className="mh-contract-side-detail mono">
                  模糊的、不可量化的<br />
                  "最好能优化一下"
                </div>
              </div>
              <div className="mh-contract-vs-divider">
                <div className="mh-contract-vs-line" />
                <div className="mh-contract-vs-text mono">vs</div>
                <div className="mh-contract-vs-line" />
              </div>
              <div className="mh-contract-side mh-contract-good">
                <div className="mh-contract-side-label mono">而是</div>
                <div className="mh-contract-side-text">可量化预测</div>
                <div className="mh-contract-side-detail mono">
                  "改这条规则后<br />
                  token 浪费率降到 5%"
                </div>
              </div>
            </div>
            <div className="mh-contract-card">
              <div className="mh-contract-card-header mono">提案结构</div>
              <div className="mh-contract-card-fields">
                <div className="mh-contract-field">
                  <div className="mh-contract-field-name mono">expected behavior</div>
                  <div className="mh-contract-field-val">预期未来行为</div>
                </div>
                <div className="mh-contract-field">
                  <div className="mh-contract-field-name mono">measurable signal</div>
                  <div className="mh-contract-field-val">可测量信号</div>
                </div>
                <div className="mh-contract-field">
                  <div className="mh-contract-field-name mono">replay method</div>
                  <div className="mh-contract-field-val">回放验证方法</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* step 4: replay verification */}
      {step === 4 && (
        <div className="mh-replay">
          <div className="mh-replay-header">
            <span className="mh-replay-tag mono">replay verification</span>
          </div>
          <div className="mh-replay-body">
            <div className="mh-replay-compare">
              <div className="mh-replay-col">
                <div className="mh-replay-col-title mono">baseline</div>
                <div className="mh-replay-bar">
                  <div className="mh-replay-bar-fill mh-replay-bar-baseline" style={{ width: "68%" }} />
                  <span className="mh-replay-bar-val mono">68%</span>
                </div>
                <div className="mh-replay-bar">
                  <div className="mh-replay-bar-fill mh-replay-bar-baseline" style={{ width: "42%" }} />
                  <span className="mh-replay-bar-val mono">42%</span>
                </div>
                <div className="mh-replay-bar">
                  <div className="mh-replay-bar-fill mh-replay-bar-baseline" style={{ width: "85%" }} />
                  <span className="mh-replay-bar-val mono">85%</span>
                </div>
                <div className="mh-replay-metrics mono">
                  <span>token 浪费率</span>
                  <span>scope 违规率</span>
                  <span>review 缺陷率</span>
                </div>
              </div>
              <div className="mh-replay-vs mono">vs</div>
              <div className="mh-replay-col">
                <div className="mh-replay-col-title mono">current</div>
                <div className="mh-replay-bar">
                  <div className="mh-replay-bar-fill mh-replay-bar-current" style={{ width: "12%" }} />
                  <span className="mh-replay-bar-val mono">12%</span>
                </div>
                <div className="mh-replay-bar">
                  <div className="mh-replay-bar-fill mh-replay-bar-current" style={{ width: "8%" }} />
                  <span className="mh-replay-bar-val mono">8%</span>
                </div>
                <div className="mh-replay-bar">
                  <div className="mh-replay-bar-fill mh-replay-bar-current" style={{ width: "22%" }} />
                  <span className="mh-replay-bar-val mono">22%</span>
                </div>
                <div className="mh-replay-metrics mono">
                  <span>token 浪费率</span>
                  <span>scope 违规率</span>
                  <span>review 缺陷率</span>
                </div>
              </div>
            </div>
            <div className="mh-replay-promotion">
              <div className="mh-replay-promo-title mono">三级晋升</div>
              <div className="mh-replay-steps">
                <div className="mh-replay-step">
                  <div className="mh-replay-step-dot" />
                  <div className="mh-replay-step-name mono">candidate</div>
                  <div className="mh-replay-step-desc">提出方案</div>
                </div>
                <div className="mh-replay-step-arrow">
                  <svg width="40" height="16" viewBox="0 0 40 16" fill="none">
                    <line x1="0" y1="8" x2="30" y2="8" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="4 3"/>
                    <polygon points="30,3 40,8 30,13" fill="var(--accent)"/>
                  </svg>
                </div>
                <div className="mh-replay-step">
                  <div className="mh-replay-step-dot" />
                  <div className="mh-replay-step-name mono">validated</div>
                  <div className="mh-replay-step-desc">回放验证通过</div>
                </div>
                <div className="mh-replay-step-arrow">
                  <svg width="40" height="16" viewBox="0 0 40 16" fill="none">
                    <line x1="0" y1="8" x2="30" y2="8" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="4 3"/>
                    <polygon points="30,3 40,8 30,13" fill="var(--accent)"/>
                  </svg>
                </div>
                <div className="mh-replay-step">
                  <div className="mh-replay-step-dot mh-replay-step-dot-active" />
                  <div className="mh-replay-step-name mono">active</div>
                  <div className="mh-replay-step-desc">写入 harness</div>
                </div>
              </div>
              <div className="mh-replay-quarantine mono">
                没变好 → 隔离
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
