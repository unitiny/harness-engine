import "./SelfEvolve.css";

interface Props {
  step: number;
}

export default function SelfEvolve({ step }: Props) {
  return (
    <div className="se scene">
      {/* step 0: dual loop diagram */}
      {step === 0 && (
        <div className="se-dual">
          <div className="se-dual-label mono">自进化闭环</div>
          <div className="se-dual-diagram">
            {/* outer ring — dev harness */}
            <div className="se-ring se-ring-outer">
              <svg viewBox="0 0 600 600" className="se-ring-svg">
                <circle cx="300" cy="300" r="270" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="8 6" fill="none" opacity="0.3"/>
                {/* flow arrows on outer ring */}
                <g opacity="0.6">
                  <path d="M300 30 A270 270 0 0 1 570 300" stroke="var(--accent)" strokeWidth="2" fill="none" strokeDasharray="12 6"/>
                  <polygon points="570,294 578,300 570,306" fill="var(--accent)"/>
                  <path d="M570 300 A270 270 0 0 1 300 570" stroke="var(--accent)" strokeWidth="2" fill="none" strokeDasharray="12 6"/>
                  <polygon points="306,570 300,578 294,570" fill="var(--accent)"/>
                  <path d="M300 570 A270 270 0 0 1 30 300" stroke="var(--accent)" strokeWidth="2" fill="none" strokeDasharray="12 6"/>
                  <polygon points="30,306 22,300 30,294" fill="var(--accent)"/>
                  <path d="M30 300 A270 270 0 0 1 300 30" stroke="var(--accent)" strokeWidth="2" fill="none" strokeDasharray="12 6"/>
                  <polygon points="294,30 300,22 306,30" fill="var(--accent)"/>
                </g>
                {/* outer labels */}
                <text x="440" y="100" fill="var(--accent)" fontFamily="var(--font-mono)" fontSize="14" letterSpacing="0.08em">execute</text>
                <text x="480" y="480" fill="var(--accent)" fontFamily="var(--font-mono)" fontSize="14" letterSpacing="0.08em">gate</text>
                <text x="100" y="510" fill="var(--accent)" fontFamily="var(--font-mono)" fontSize="14" letterSpacing="0.08em">review</text>
                <text x="80" y="140" fill="var(--accent)" fontFamily="var(--font-mono)" fontSize="14" letterSpacing="0.08em">commit</text>
              </svg>
              <div className="se-ring-label se-ring-outer-label mono">dev harness</div>
              <div className="se-ring-desc se-ring-outer-desc">干活留痕迹</div>
            </div>
            {/* inner ring — meta harness */}
            <div className="se-ring se-ring-inner">
              <svg viewBox="0 0 600 600" className="se-ring-svg">
                <circle cx="300" cy="300" r="160" stroke="#34d399" strokeWidth="1.5" strokeDasharray="6 4" fill="none" opacity="0.3"/>
                <g opacity="0.5">
                  <path d="M300 140 A160 160 0 0 1 460 300" stroke="#34d399" strokeWidth="2" fill="none" strokeDasharray="10 5"/>
                  <polygon points="460,294 468,300 460,306" fill="#34d399"/>
                  <path d="M460 300 A160 160 0 0 1 300 460" stroke="#34d399" strokeWidth="2" fill="none" strokeDasharray="10 5"/>
                  <polygon points="306,460 300,468 294,460" fill="#34d399"/>
                  <path d="M300 460 A160 160 0 0 1 140 300" stroke="#34d399" strokeWidth="2" fill="none" strokeDasharray="10 5"/>
                  <polygon points="140,306 132,300 140,294" fill="#34d399"/>
                  <path d="M140 300 A160 160 0 0 1 300 140" stroke="#34d399" strokeWidth="2" fill="none" strokeDasharray="10 5"/>
                  <polygon points="294,140 300,132 306,140" fill="#34d399"/>
                </g>
                {/* inner labels */}
                <text x="350" y="210" fill="#34d399" fontFamily="var(--font-mono)" fontSize="12" letterSpacing="0.06em">analyze</text>
                <text x="370" y="400" fill="#34d399" fontFamily="var(--font-mono)" fontSize="12" letterSpacing="0.06em">propose</text>
                <text x="180" y="400" fill="#34d399" fontFamily="var(--font-mono)" fontSize="12" letterSpacing="0.06em">replay</text>
                <text x="180" y="220" fill="#34d399" fontFamily="var(--font-mono)" fontSize="12" letterSpacing="0.06em">report</text>
              </svg>
              <div className="se-ring-label se-ring-inner-label mono">meta harness</div>
              <div className="se-ring-desc se-ring-inner-desc">读痕迹，找缺口，提修复</div>
            </div>
            {/* center connection */}
            <div className="se-dual-center">
              <svg width="80" height="200" viewBox="0 0 80 200" fill="none">
                <line x1="40" y1="0" x2="40" y2="80" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="4 4"/>
                <polygon points="34,78 40,90 46,78" fill="var(--accent)"/>
                <line x1="40" y1="200" x2="40" y2="120" stroke="#34d399" strokeWidth="1.5" strokeDasharray="4 4"/>
                <polygon points="34,122 40,110 46,122" fill="#34d399"/>
              </svg>
            </div>
          </div>
          <div className="se-dual-footer mono">验证过了再写回 dev harness</div>
        </div>
      )}

      {/* step 1: gap analysis — "harness 哪没拦住？" */}
      {step === 1 && (
        <div className="se-gap">
          <div className="se-gap-question serif-cn">
            harness 哪没拦住？
          </div>
          <div className="se-gap-body">
            <div className="se-gap-list">
              <div className="se-gap-item">
                <div className="se-gap-type mono">missing_rule</div>
                <div className="se-gap-desc">该加规则——某种行为没被约束</div>
              </div>
              <div className="se-gap-item">
                <div className="se-gap-type mono">weak_rule</div>
                <div className="se-gap-desc">规则太弱——存在但拦不住</div>
              </div>
              <div className="se-gap-item">
                <div className="se-gap-type mono">missing_checker</div>
                <div className="se-gap-desc">该加 checker——某种变更没有检查</div>
              </div>
              <div className="se-gap-item">
                <div className="se-gap-type mono">missing_memory</div>
                <div className="se-gap-desc">该加 memory——可复用经验没沉淀</div>
              </div>
              <div className="se-gap-item">
                <div className="se-gap-type mono">missing_eval</div>
                <div className="se-gap-desc">该加 eval——缺少评估维度</div>
              </div>
            </div>
            <div className="se-gap-rationale">
              <div className="se-gap-rat-title mono">rule rationale</div>
              <div className="se-gap-rat-fields">
                <div className="se-gap-rat-field">
                  <span className="se-gap-rat-q mono">why it exists</span>
                  <span className="se-gap-rat-a">为什么存在</span>
                </div>
                <div className="se-gap-rat-field">
                  <span className="se-gap-rat-q mono">risk it prevents</span>
                  <span className="se-gap-rat-a">防止什么风险</span>
                </div>
                <div className="se-gap-rat-field">
                  <span className="se-gap-rat-q mono">when not to apply</span>
                  <span className="se-gap-rat-a">什么时候不该用</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* step 2: three-tier promotion + CTA */}
      {step === 2 && (
        <div className="se-finale">
          <div className="se-finale-label mono">三级晋升</div>
          <div className="se-finale-steps">
            <div className="se-finale-tier">
              <div className="se-finale-tier-ring" />
              <div className="se-finale-tier-content">
                <div className="se-finale-tier-name mono">candidate</div>
                <div className="se-finale-tier-desc">提出方案</div>
                <div className="se-finale-tier-req mono">prediction contract</div>
              </div>
            </div>
            <div className="se-finale-tier-arrow">
              <svg width="60" height="20" viewBox="0 0 60 20" fill="none">
                <line x1="0" y1="10" x2="48" y2="10" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="6 4"/>
                <polygon points="48,4 60,10 48,16" fill="var(--accent)"/>
              </svg>
            </div>
            <div className="se-finale-tier">
              <div className="se-finale-tier-ring" />
              <div className="se-finale-tier-content">
                <div className="se-finale-tier-name mono">validated</div>
                <div className="se-finale-tier-desc">回放验证通过</div>
                <div className="se-finale-tier-req mono">evidence + replay</div>
              </div>
            </div>
            <div className="se-finale-tier-arrow">
              <svg width="60" height="20" viewBox="0 0 60 20" fill="none">
                <line x1="0" y1="10" x2="48" y2="10" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="6 4"/>
                <polygon points="48,4 60,10 48,16" fill="var(--accent)"/>
              </svg>
            </div>
            <div className="se-finale-tier se-finale-tier-active">
              <div className="se-finale-tier-ring se-finale-tier-ring-active" />
              <div className="se-finale-tier-content">
                <div className="se-finale-tier-name mono">active</div>
                <div className="se-finale-tier-desc">写入 harness</div>
                <div className="se-finale-tier-req mono">production rule</div>
              </div>
            </div>
          </div>
          <div className="se-finale-divider" />
          <div className="se-finale-cta">
            <div className="se-finale-cta-text serif-cn">harness 改进 harness 自己</div>
            <div className="se-finale-cta-link mono">
              <span className="se-finale-cta-gt">&gt;</span>
              github.com/ConardLi/garden-skills
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
