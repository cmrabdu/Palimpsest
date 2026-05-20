/* global React, PaperCard, Button, Chip, WaxSeal, StageChip, ProgressBar, LogLine, Icons,
   deriveStages, stageStatuses, overallProgress, chipFor */
// Palimpsest — Mobile workshop view (real API)

const { useState: useStateM } = React;

function MobileWorkshop(props) {
  const {
    state, page, total, currentStage, log, jobId, file, pageCount,
    cfg, setCfg, cost, wsConnected, hasPdf, errorMsg,
    onPick, onClear, onStart, flash, canStart, uploading,
  } = props;

  const [sheetOpen, setSheetOpen] = useStateM(false);
  const inputRef = React.useRef(null);
  const sizeMB = file ? (file.size / 1048576).toFixed(1) : null;

  return (
    <div className="mobile-shell bg-paper" data-screen-label="01M Workshop (mobile)">
      <div className="m-appbar">
        <div className="wordmark"><span className="wm-slash">//</span> Palimpsest</div>
        <a href="/jobs.html" className="m-iconbtn" title="archive">
          <Icons.History size={16} />
        </a>
      </div>

      <p className="m-promise">Drop your old scan, get a clean scientific document back.</p>

      <div className="m-paper-body">
        {/* Dropzone */}
        <PaperCard ribbon="INPUT · BAY 01" className="m-dz-card">
          <div
            className={`dropzone dropzone-empty ${flash ? 'dropzone-flash' : ''}`}
            onClick={() => !file && inputRef.current?.click()}
            style={{ cursor: file ? 'default' : 'pointer' }}
          >
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf"
              style={{ display: 'none' }}
              onChange={e => e.target.files[0] && onPick(e.target.files[0])}
            />
            <div className="dz-arch mono caps">{file ? 'staged · ready' : 'tap to browse a PDF'}</div>
            <div className="dz-sub mono">{file ? 'tap start below' : 'scanned · max 60 MB'}</div>
            <div className="dz-pages">
              <div className="scan-placeholder" data-label="" style={{ width: 32, height: 42, transform: 'rotate(-4deg)' }} />
              <div className="scan-placeholder" data-label="" style={{ width: 32, height: 42 }} />
              <div className="scan-placeholder" data-label="" style={{ width: 32, height: 42, transform: 'rotate(3deg)' }} />
            </div>
          </div>
          {file && (
            <div className="staged-row">
              <WaxSeal size="sm">✓</WaxSeal>
              <div className="staged-meta">
                <div className="staged-name mono">{file.name}</div>
                <div className="staged-sub mono">{pageCount ? `${pageCount} p · ` : ''}{sizeMB} MB</div>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={onClear} title="remove">
                <Icons.X size={12} />
              </button>
              <Chip variant="ok" dot>staged</Chip>
            </div>
          )}
        </PaperCard>

        {/* Config summary -> bottom sheet */}
        <PaperCard className="m-config-card">
          <div className="m-config-summary" onClick={() => setSheetOpen(true)}>
            <div className="m-config-summary-l">
              <span className="m-config-label">SPECIMEN</span>
              <div className="m-config-chips">
                <Chip variant="mute">{(window.COSTS[cfg.model]?.label || cfg.model)}</Chip>
                <Chip variant="mute">{cfg.ocr}</Chip>
                <Chip variant="mute">{cost != null ? `≈ $${cost.toFixed(2)}` : '— · pick a PDF'}</Chip>
              </div>
            </div>
            <div className="m-config-arrow mono">tap ›</div>
          </div>
        </PaperCard>

        {/* Inline terminal section */}
        {state !== 'idle' && (
          <div className="m-term-section" data-screen-label="01M-b Terminal (mobile)">
            <div className="term-header" style={{ paddingBottom: 12, marginBottom: 14 }}>
              <div className="term-header-row" style={{ fontSize: 11 }}>
                <span className="term-dot" />
                <span className="term-path mono">palimpsest@workshop<span className="ts"> ~/jobs/{jobId || '—'}</span></span>
                <span className="term-spacer" />
                <span className="ws-dot" style={{ background: wsConnected ? 'var(--green)' : 'var(--warn)' }} />
              </div>
              <div className="term-job-row">
                <span className="job-file mono">{file?.name || '(resumed)'}</span>
                {jobId && <span className="job-no mono">#{jobId}</span>}
                <div style={{ flexBasis: '100%', height: 0 }} />
                {chipFor(state, page, total)}
              </div>
            </div>

            <div className="m-stage-rail">
              {(() => {
                const s = deriveStages(state, currentStage);
                const t = stageStatuses(state, currentStage, page, total);
                return ['preprocess', 'ocr', 'rewrite', 'compile'].map((n, i) => (
                  <StageChip key={n} name={n} state={s[i]} status={t[i]} />
                ));
              })()}
            </div>

            <div className="m-progress-block progress-block" style={{ marginTop: 16 }}>
              {(() => {
                const p = overallProgress(state, currentStage, page, total);
                return (
                  <div className="progress-labels">
                    <span className="mono term-dim caps">// progress</span>
                    <ProgressBar value={p.value} tone={p.tone} size="lg" />
                    <span className="progress-readout mono">{p.label} <span className="term-dim">· {p.sub}</span></span>
                  </div>
                );
              })()}
            </div>

            <div className="m-log-stream log-stream bg-term-recessed" style={{ marginTop: 16 }}>
              <div className="log-stream-header">
                <span className="log-title mono"># pipeline.log</span>
                <span style={{ flex: 1 }} />
                <Chip
                  variant={state === 'processing' ? 'term' : state === 'done' ? 'term-ok' : 'term-warn'}
                  dot
                  pulse={state === 'processing'}
                >
                  {state === 'processing' ? 'live' : state === 'done' ? 'complete' : 'halted'}
                </Chip>
              </div>
              <div className="log-stream-body">
                {log.slice(-12).map((l, i) => <LogLine key={i} {...l} />)}
              </div>
            </div>

            <div className="m-outputs-row outputs-row" style={{ marginTop: 16 }}>
              {state === 'done' && <div className="m-done-trace" />}
              {state === 'processing' && (
                <span className="mono term-dim">↳ outputs unlock at compile</span>
              )}
              {state === 'done' && (
                <>
                  {hasPdf && (
                    <a className="btn btn-ai on-term" href={`/api/jobs/${jobId}/download?fmt=pdf`}>
                      <Icons.Download /> download pdf
                    </a>
                  )}
                  <a className="btn btn-term on-term" href={`/api/jobs/${jobId}/download?fmt=tex`}>
                    <Icons.Download /> .tex
                  </a>
                  <a className="btn btn-ghost-term on-term" href="https://www.overleaf.com/" target="_blank" rel="noreferrer">
                    Overleaf <Icons.Ext />
                  </a>
                </>
              )}
              {state === 'error' && (
                <>
                  {jobId && (
                    <a className="btn btn-term on-term" href={`/api/jobs/${jobId}/download?fmt=tex`}>
                      <Icons.Download /> .tex if any
                    </a>
                  )}
                  <span className="outputs-note mono term-dim">↳ {errorMsg || 'halted'}</span>
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Sticky bottom CTA — only when idle and no in-flight */}
      {!sheetOpen && state === 'idle' && (
        <div className="m-cta-bar">
          <Button
            variant="ai"
            size="lg"
            disabled={!canStart}
            onClick={onStart}
            icon={<span>▷</span>}
          >
            {uploading ? 'uploading…' : 'start pipeline'}
          </Button>
        </div>
      )}

      {/* Bottom sheet — specimen config */}
      {sheetOpen && (
        <>
          <div className="sheet-overlay" onClick={() => setSheetOpen(false)} />
          <div className="sheet">
            <div className="sheet-handle" />
            <h2>Specimen · pipeline settings</h2>
            <div className="spec-grid">
              <div className="spec-field">
                <div className="spec-label mono caps">MODEL</div>
                <select className="spec-select mono" value={cfg.model} onChange={e => setCfg({ ...cfg, model: e.target.value })}>
                  <optgroup label="OpenAI">
                    <option value="o4-mini">o4-mini</option>
                    <option value="gpt-4.1">gpt-4.1</option>
                    <option value="gpt-4o">gpt-4o</option>
                    <option value="gpt-4.1-mini">gpt-4.1-mini</option>
                    <option value="gpt-4.1-nano">gpt-4.1-nano</option>
                    <option value="o1">o1 · premium</option>
                  </optgroup>
                  <optgroup label="Anthropic">
                    <option value="claude-opus-4-20250514">claude-opus-4</option>
                    <option value="claude-sonnet-4-20250514">claude-sonnet-4</option>
                  </optgroup>
                </select>
              </div>
              <div className="spec-field">
                <div className="spec-label mono caps">OCR ENGINE</div>
                <div className="toggle">
                  {['vision','mathpix'].map(o => (
                    <button key={o} className={`toggle-opt mono ${cfg.ocr === o ? 'is-on' : ''}`}
                            onClick={() => setCfg({ ...cfg, ocr: o })}>{o}</button>
                  ))}
                </div>
              </div>
              <div className="spec-field">
                <div className="spec-label mono caps">SOURCE</div>
                <div className="toggle">
                  {['preserve images','text only'].map(o => (
                    <button key={o} className={`toggle-opt mono ${cfg.src === o ? 'is-on' : ''}`}
                            onClick={() => setCfg({ ...cfg, src: o })}>{o}</button>
                  ))}
                </div>
              </div>
              <div className="spec-field">
                <div className="spec-label mono caps">ESTIMATED COST</div>
                <div className="cost mono">
                  <span className="cost-prefix serif"><i>≈</i></span> {cost != null ? `$${cost.toFixed(2)}` : '—'}
                  <span className="cost-foot mono">per run</span>
                </div>
              </div>
            </div>
            <div className="sheet-cta">
              <Button
                variant="ai"
                size="lg"
                onClick={() => setSheetOpen(false)}
                icon={<Icons.Check />}
              >
                save settings
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

Object.assign(window, { MobileWorkshop });
