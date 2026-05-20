/* global React, PaperCard, Button, Chip, WaxSeal, StageChip, ProgressBar, LogLine, Icons */
// Palimpsest — Workshop (real API integration)

const { useState, useEffect, useRef, useMemo, useCallback } = React;

// --------------------------------------------------------------------------
// COST TABLE — per page, mirrors backend's accepted models
// --------------------------------------------------------------------------
const COSTS = {
  'o4-mini':                    { withImg: 0.027, noImg: 0.023, label: 'o4-mini' },
  'gpt-4.1':                    { withImg: 0.041, noImg: 0.033, label: 'gpt-4.1' },
  'gpt-4o':                     { withImg: 0.049, noImg: 0.039, label: 'gpt-4o' },
  'gpt-4.1-mini':               { withImg: 0.016, noImg: 0.015, label: 'gpt-4.1-mini' },
  'gpt-4.1-nano':               { withImg: 0.012, noImg: 0.011, label: 'gpt-4.1-nano' },
  'claude-opus-4-20250514':     { withImg: 0.098, noImg: 0.078, label: 'claude-opus-4' },
  'claude-sonnet-4-20250514':   { withImg: 0.063, noImg: 0.051, label: 'claude-sonnet-4' },
  'o1':                         { withImg: 0.243, noImg: 0.183, label: 'o1' },
};
const MATHPIX_SURCHARGE = 0.005;

function estimateCost(cfg, pages) {
  const info = COSTS[cfg.model];
  if (!info || !pages) return null;
  const per = (cfg.src === 'preserve images' ? info.withImg : info.noImg) +
              (cfg.ocr === 'mathpix' ? MATHPIX_SURCHARGE : 0);
  return pages * per;
}

// --------------------------------------------------------------------------
// STATE → STAGE MAPPING
// stages: [preprocess, ocr, rewrite, compile]
// --------------------------------------------------------------------------
function deriveStages(state, currentStage) {
  if (state === 'idle')    return ['pending', 'pending', 'pending', 'pending'];
  if (state === 'done')    return ['done', 'done', 'done', 'done'];
  if (state === 'error') {
    // mark the failing stage
    const s = currentStage || '';
    if (s.startsWith('rewrite'))      return ['done', 'done', 'failed', 'pending'];
    if (s.startsWith('ocr'))          return ['done', 'failed', 'pending', 'pending'];
    if (s.startsWith('compile'))      return ['done', 'done', 'done', 'failed'];
    if (s.startsWith('pre'))          return ['failed', 'pending', 'pending', 'pending'];
    return ['done', 'failed', 'pending', 'pending'];
  }
  // processing
  const s = currentStage || 'preprocessing';
  if (s.startsWith('pre'))     return ['active', 'pending', 'pending', 'pending'];
  if (s.startsWith('ocr'))     return ['done', 'active', 'pending', 'pending'];
  if (s.startsWith('rewrite')) return ['done', 'done', 'active', 'pending'];
  if (s.startsWith('compile')) return ['done', 'done', 'done', 'active'];
  return ['active', 'pending', 'pending', 'pending'];
}

function stageStatuses(state, currentStage, page, total) {
  const stages = deriveStages(state, currentStage);
  const pages = (i) => {
    const st = stages[i];
    if (st === 'done')    return 'complete';
    if (st === 'failed')  return 'failed';
    if (st === 'pending') return 'pending';
    if (st === 'active')  return total ? `page ${String(page).padStart(2, '0')}` : '…';
    return '';
  };
  return [pages(0), pages(1), pages(2), pages(3)];
}

// overall progress (0-100) weighted across the four stages
function overallProgress(state, currentStage, page, total) {
  if (state === 'idle')  return { value: 0,   tone: 'ai',    label: '0%',   sub: 'awaiting input' };
  if (state === 'done')  return { value: 100, tone: 'green', label: '100%', sub: 'complete' };
  if (state === 'error') return { value: 0,   tone: 'warn',  label: '!',    sub: 'halted' };

  const t = total || 1;
  const frac = Math.min(1, (page || 0) / t);
  const s = currentStage || 'preprocessing';
  let value = 0;
  if (s.startsWith('pre'))          value = frac * 25;
  else if (s.startsWith('ocr'))     value = 25 + frac * 30;
  else if (s.startsWith('rewrite')) value = 55 + frac * 40;
  else if (s.startsWith('compile')) value = 95 + frac * 5;
  value = Math.round(value);

  let sub = '';
  if (total) sub = `${page}/${total} · ${s}`;
  else       sub = s;
  return { value, tone: 'ai', label: `${value}%`, sub };
}

function chipFor(state, page, total) {
  if (state === 'idle')       return <Chip variant="mute" dot>queued</Chip>;
  if (state === 'processing') return <Chip variant="term" dot pulse>live{total ? ` · ${String(page).padStart(2, '0')}/${total}` : ''}</Chip>;
  if (state === 'done')       return <Chip variant="term-ok" dot>done{total ? ` · ${total}/${total} ✓` : ' ✓'}</Chip>;
  if (state === 'error')      return <Chip variant="term-warn" dot>error</Chip>;
}

// --------------------------------------------------------------------------
// HEADER
// --------------------------------------------------------------------------
function PaperHeader() {
  return (
    <div className="paper-header">
      <div className="paper-header-row">
        <div className="wordmark" id="logo">
          <span className="wm-slash">//</span> Palimpsest
        </div>
        <div className="tagline mono">scan <span className="ar">→</span> ocr <span className="ar">→</span> llm <span className="ar">→</span> LaTeX</div>
        <div className="ref-no mono">MS · 2026 / vol. iii</div>
      </div>
      <p className="promise">
        Drop your old scan, get a clean scientific document back.
      </p>
    </div>
  );
}

// --------------------------------------------------------------------------
// DROPZONE
// --------------------------------------------------------------------------
function DropzoneBlock({ file, pageCount, onPick, onClear, flash }) {
  const [hot, setHot] = useState(false);
  const inputRef = useRef(null);
  const sizeMB = file ? (file.size / 1048576).toFixed(1) : null;
  return (
    <PaperCard rotate={-0.5} ribbon="INPUT · BAY 01" ribbonTone="ink" className="dz-card">
      <div
        className={`dropzone ${hot ? 'dropzone-hot' : 'dropzone-empty'} ${flash ? 'dropzone-flash' : ''}`}
        onClick={() => !file && inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); if (!file) setHot(true); }}
        onDragLeave={() => setHot(false)}
        onDrop={e => {
          e.preventDefault(); setHot(false);
          if (file) return;
          const f = e.dataTransfer.files[0];
          if (f && f.name.toLowerCase().endsWith('.pdf')) onPick(f);
        }}
        style={{ cursor: file ? 'default' : 'pointer' }}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          style={{ display: 'none' }}
          onChange={e => e.target.files[0] && onPick(e.target.files[0])}
        />
        <div className="dz-arch mono caps">{file ? 'staged · ready' : 'drop a scanned PDF'}</div>
        <div className="dz-sub mono">{file ? 'click start to launch the pipeline' : 'or click to browse · max 60 MB'}</div>
        <div className="dz-pages">
          <div className="scan-placeholder" data-label="page" style={{ width: 38, height: 50, transform: 'rotate(-4deg)' }} />
          <div className="scan-placeholder" data-label="page" style={{ width: 38, height: 50, marginTop: -4 }} />
          <div className="scan-placeholder" data-label="page" style={{ width: 38, height: 50, transform: 'rotate(3deg)' }} />
        </div>
      </div>
      {file && (
        <div className="staged-row">
          <WaxSeal size="sm">✓</WaxSeal>
          <div className="staged-meta">
            <div className="staged-name mono">{file.name}</div>
            <div className="staged-sub mono">
              {pageCount ? `${pageCount} pages · ` : ''}{sizeMB} MB{pageCount ? ' · scanned' : ''}
            </div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClear} title="remove">
            <Icons.X size={12} />
          </button>
          <Chip variant="ok" dot>staged</Chip>
        </div>
      )}
    </PaperCard>
  );
}

// --------------------------------------------------------------------------
// SPECIMEN CONFIG
// --------------------------------------------------------------------------
function SpecimenCard({ cfg, setCfg, cost }) {
  return (
    <PaperCard rotate={0.4} tab="SPECIMEN" className="spec-card">
      <div className="spec-grid">
        <SpecField label="MODEL">
          <select className="spec-select mono" value={cfg.model}
                  onChange={e => setCfg({ ...cfg, model: e.target.value })}>
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
        </SpecField>
        <SpecField label="OCR">
          <Toggle options={['vision','mathpix']} value={cfg.ocr}
                  onChange={v => setCfg({ ...cfg, ocr: v })} />
        </SpecField>
        <SpecField label="SOURCE">
          <Toggle options={['preserve images','text only']} value={cfg.src}
                  onChange={v => setCfg({ ...cfg, src: v })} compact />
        </SpecField>
        <SpecField label="COST">
          <div className="cost mono">
            <span className="cost-prefix serif"><i>≈</i></span> {cost != null ? `$${cost.toFixed(2)}` : '—'}
            <span className="cost-foot mono">per run</span>
          </div>
        </SpecField>
      </div>
    </PaperCard>
  );
}
function SpecField({ label, children }) {
  return (
    <div className="spec-field">
      <div className="spec-label mono caps">{label}</div>
      <div className="spec-control">{children}</div>
    </div>
  );
}
function Toggle({ options, value, onChange, compact }) {
  return (
    <div className={`toggle ${compact ? 'toggle-compact' : ''}`}>
      {options.map(o => (
        <button key={o}
                className={`toggle-opt mono ${value === o ? 'is-on' : ''}`}
                onClick={() => onChange(o)}>
          {o}
        </button>
      ))}
    </div>
  );
}

// --------------------------------------------------------------------------
// TERMINAL HEADER
// --------------------------------------------------------------------------
function TermHeader({ state, page, total, file, jobNo, wsConnected }) {
  return (
    <div className="term-header">
      <div className="term-header-row">
        <span className="term-dot" />
        <span className="term-path mono">palimpsest@workshop&nbsp;<span className="ts">~/jobs/{jobNo || '—'}</span></span>
        <span className="term-spacer" />
        <span className="term-ws mono">
          <span className="ws-dot" style={{ background: wsConnected ? 'var(--green)' : 'var(--warn)' }} />
          ws · {wsConnected ? 'connected' : 'idle'}
        </span>
      </div>
      <div className="term-job-row">
        <span className="job-file mono">{file || '— no job —'}</span>
        {jobNo && <span className="job-no mono">#{jobNo}</span>}
        <span className="term-spacer" />
        {chipFor(state, page, total)}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------
// STAGE ROW
// --------------------------------------------------------------------------
function StageRow({ state, currentStage, page, total }) {
  const states  = deriveStages(state, currentStage);
  const statuses = stageStatuses(state, currentStage, page, total);
  const names = ['preprocess','ocr','rewrite','compile'];
  return (
    <div className="stage-row">
      {names.map((n,i) => (
        <StageChip key={n} name={n} state={states[i]} status={statuses[i]} />
      ))}
    </div>
  );
}

// --------------------------------------------------------------------------
// PROGRESS BLOCK
// --------------------------------------------------------------------------
function ProgressBlock({ state, currentStage, page, total }) {
  const p = overallProgress(state, currentStage, page, total);
  return (
    <div className="progress-block">
      <div className="progress-labels">
        <span className="mono term-dim caps">// progress</span>
        <span className="mono progress-readout">{p.label} <span className="term-dim">· {p.sub}</span></span>
      </div>
      <ProgressBar value={p.value} tone={p.tone} />
    </div>
  );
}

// --------------------------------------------------------------------------
// LOG STREAM
// --------------------------------------------------------------------------
function LogStream({ state, log, mobile }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [log]);
  return (
    <div className={`log-stream bg-term-recessed ${mobile ? 'm-log-stream' : ''}`}>
      <div className="log-stream-header">
        <span className="log-title mono"># pipeline.log</span>
        <span className="log-cmd mono term-dim">tail -f</span>
        <span style={{ flex: 1 }} />
        <Chip
          variant={state === 'processing' ? 'term' : state === 'done' ? 'term-ok' : state === 'error' ? 'term-warn' : 'mute'}
          dot
          pulse={state === 'processing'}
        >
          {state === 'processing' ? 'live' : state === 'done' ? 'complete' : state === 'error' ? 'halted' : 'idle'}
        </Chip>
      </div>
      <div className="log-stream-body" ref={ref}>
        {log.map((l, i) => <LogLine key={i} {...l} />)}
        {state !== 'error' && (
          <div className="log-prompt mono">
            <span className={state === 'processing' ? 'text-ai' : 'text-green'}>$</span>
            <span className={`caret ${state === 'processing' ? 'caret-ai' : ''}`} />
          </div>
        )}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------
// OUTPUTS ROW
// --------------------------------------------------------------------------
function OutputsRow({ state, jobId, hasPdf, errorMsg }) {
  if (state === 'idle') {
    return (
      <div className="outputs-row outputs-idle mono">
        <span className="term-dim">↳ drop a PDF and start the pipeline to unlock outputs</span>
      </div>
    );
  }
  if (state === 'processing') {
    return (
      <div className="outputs-row outputs-idle mono">
        <span className="term-dim">↳ outputs unlock at compile</span>
      </div>
    );
  }
  if (state === 'done') {
    return (
      <div className="outputs-row outputs-unlock">
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
      </div>
    );
  }
  if (state === 'error') {
    return (
      <div className="outputs-row">
        {jobId && (
          <a className="btn btn-term on-term" href={`/api/jobs/${jobId}/download?fmt=tex`}>
            <Icons.Download /> .tex if any
          </a>
        )}
        <span className="outputs-note mono term-dim">↳ {errorMsg || 'pipeline halted'}</span>
      </div>
    );
  }
}

// --------------------------------------------------------------------------
// WORKSHOP (page body — desktop)
// --------------------------------------------------------------------------
function Workshop(props) {
  const {
    state, page, total, currentStage, log, jobId, file, pageCount,
    cfg, setCfg, cost, wsConnected, hasPdf, errorMsg,
    onPick, onClear, onStart, flash, canStart, uploading,
  } = props;

  return (
    <div className="workshop" data-screen-label="01 Workshop">
      {/* PAPER half */}
      <section className="workshop-paper bg-paper">
        <PaperHeader />
        <div className="paper-body">
          <DropzoneBlock file={file} pageCount={pageCount} onPick={onPick} onClear={onClear} flash={flash} />
          <SpecimenCard cfg={cfg} setCfg={setCfg} cost={cost} />
        </div>
        <div className="paper-footer">
          <span className="mono">made with ♥ by @cmrabdu · open source</span>
          <Button
            variant="ai"
            size="lg"
            disabled={!canStart}
            onClick={onStart}
            icon={<span style={{ fontSize: 14 }}>▷</span>}
          >
            {uploading ? 'uploading…' : 'start pipeline'}
          </Button>
        </div>
      </section>

      {/* SCANNER SEAM */}
      <div className="seam" aria-hidden="true">
        <div className="seam-line" />
        <div className="seam-rivets">
          {Array.from({length: 8}).map((_,i) => <span key={i} className="rivet" />)}
        </div>
      </div>

      {/* TERMINAL half */}
      <section className="workshop-term bg-term">
        <TermHeader
          state={state}
          page={page}
          total={total}
          file={file?.name || (jobId ? '(resumed job)' : null)}
          jobNo={jobId}
          wsConnected={wsConnected}
        />
        <div className="term-body">
          <StageRow state={state} currentStage={currentStage} page={page} total={total} />
          <ProgressBlock state={state} currentStage={currentStage} page={page} total={total} />
          <LogStream state={state} log={log} />
          <OutputsRow state={state} jobId={jobId} hasPdf={hasPdf} errorMsg={errorMsg} />
        </div>
        <div className="term-footer mono term-dim">
          <span>palimpsest 0.6.2</span>
          {jobId && <span>· run-id {jobId}</span>}
          <span style={{ flex: 1 }} />
          <a href="/brand.html" className="footer-link">↳ brand kit</a>
          <a href="/jobs.html" className="footer-link">↳ archive register</a>
        </div>
      </section>
    </div>
  );
}

Object.assign(window, { Workshop, COSTS, estimateCost });
