/* global React, PaperCard, Button, Chip, Stamp, ProgressBar, Icons */
// Palimpsest — Archive register (real API)

const { useState: jUseState, useMemo: jUseMemo, useEffect: jUseEffect } = React;

const FILTERS = ['all','done','active','queued','error'];

// Map server status → ledger chip
function chipForRow(state) {
  if (state === 'processing') return <Chip variant="info" dot pulse>active</Chip>;
  if (state === 'queued')     return <Chip variant="mute" dot>queued</Chip>;
  if (state === 'done')       return <Chip variant="ok" dot>done</Chip>;
  if (state === 'error')      return <Chip variant="warn" dot>error</Chip>;
  return null;
}

function matchesFilter(job, filter) {
  if (filter === 'all') return true;
  if (filter === 'active') return job.state === 'processing';
  if (filter === 'done')   return job.state === 'done';
  if (filter === 'queued') return job.state === 'queued';
  if (filter === 'error')  return job.state === 'error';
  return true;
}

// Normalize server job records to the ledger shape
function normalize(raw) {
  const ts = raw.timestamp ? new Date(raw.timestamp) : null;
  const date = ts ? ts.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) : '';
  const time = ts ? ts.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false }) : '';
  const total = raw.total || 0;
  const page  = raw.progress || 0;
  const pct = total ? Math.round((page / total) * 100) : 0;
  return {
    id:       raw.job_id,
    raw,
    date,
    time,
    file:     raw.filename || raw.job_id,
    state:    raw.status,
    model:    (raw.model || '').replace(/-\d{8}$/, ''),
    ocr:      raw.engine || 'vision',
    pages:    total,
    page,
    progress: pct,
    hasPdf:   raw.has_pdf !== false,
    error:    raw.error,
  };
}

function JobsPage() {
  const [filter, setFilter] = jUseState('all');
  const [q, setQ] = jUseState('');
  const [jobs, setJobs]   = jUseState([]);
  const [loading, setLoading] = jUseState(true);
  const [err, setErr] = jUseState(null);

  const load = async () => {
    try {
      const res = await fetch('/api/jobs/list?limit=500');
      if (!res.ok) throw new Error('http ' + res.status);
      const j = await res.json();
      const list = (j.jobs || []).map(normalize);
      setJobs(list);
      setErr(null);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  };

  jUseEffect(() => {
    load();
    const id = setInterval(load, 4000); // poll every 4s for live updates
    return () => clearInterval(id);
  }, []);

  const filtered = jUseMemo(() => jobs.filter(j =>
    matchesFilter(j, filter) && (!q || j.file.toLowerCase().includes(q.toLowerCase()))
  ), [jobs, filter, q]);

  const stats = jUseMemo(() => ({
    total:  jobs.length,
    done:   jobs.filter(j => j.state === 'done').length,
    active: jobs.filter(j => j.state === 'processing').length,
    error:  jobs.filter(j => j.state === 'error').length,
  }), [jobs]);

  const today = new Date();
  const opened = `${String(today.getDate()).padStart(2,'0')}·${['i','ii','iii','iv','v','vi','vii','viii','ix','x','xi','xii'][today.getMonth()]}·${String(today.getFullYear()).slice(2)}`;

  return (
    <div className="jobs-page" data-screen-label="02 Archive register">
      <CommandBand />
      <Masthead opened={opened} />
      <StatsStrip stats={stats} filter={filter} setFilter={setFilter} q={q} setQ={setQ} />
      <Ledger jobs={filtered} loading={loading} err={err} totalCount={jobs.length} />
      <Footer count={filtered.length} />
    </div>
  );
}

function CommandBand() {
  return (
    <div className="jobs-cmd">
      <span className="wordmark"><span className="wm-slash">//</span> Palimpsest</span>
      <span className="crumb">~/archive</span>
      <span className="caret" />
      <div className="right">
        <span className="ws">
          <span className="ws-dot" /> ws · live
        </span>
        <a href="/" className="btn btn-term btn-sm on-term">
          <Icons.Plus size={14} /> new job
        </a>
      </div>
    </div>
  );
}

function Masthead({ opened }) {
  return (
    <div className="jobs-masthead">
      <a href="/" className="jobs-back">‹ back to workshop</a>
      <div className="jobs-title-row">
        <h1 className="jobs-title">Archive register</h1>
        <p className="jobs-sub">all your processed documents · vol. iii</p>
        <div className="jobs-mast-right"><Stamp>opened {opened}</Stamp></div>
      </div>
      <div className="jobs-mast-stamp-mobile"><Stamp>opened {opened}</Stamp></div>
    </div>
  );
}

function StatsStrip({ stats, filter, setFilter, q, setQ }) {
  return (
    <div className="jobs-stats-wrap">
      <div className="jobs-stats-grid">
        <PaperCard rotate={-0.4} className="stat-card">
          <div className="stat-label">TOTAL</div>
          <div className="stat-value">{stats.total}</div>
          <div className="stat-foot">documents · all time</div>
        </PaperCard>
        <PaperCard rotate={0.3} className="stat-card">
          <div className="stat-label">DONE</div>
          <div className="stat-value green">{stats.done}</div>
          <div className="stat-foot">compiled · ready</div>
        </PaperCard>
        <PaperCard rotate={-0.3} className="stat-card">
          <div className="stat-label">ACTIVE</div>
          <div className="stat-value ai">{stats.active}</div>
          <div className="stat-foot">in pipeline now</div>
        </PaperCard>
        <PaperCard rotate={0.5} className="stat-card">
          <div className="stat-label">ERRATA</div>
          <div className="stat-value rule">{stats.error}</div>
          <div className="stat-foot">need attention</div>
        </PaperCard>
        <div className="jobs-tools">
          <div className="filter-pills">
            {FILTERS.map(f => (
              <button key={f} className={`filter-pill ${filter === f ? 'is-on' : ''}`}
                      onClick={() => setFilter(f)}>{f}</button>
            ))}
          </div>
          <label className="search-box">
            <Icons.Search size={14} />
            <input value={q} onChange={e => setQ(e.target.value)} placeholder="search filename…" />
          </label>
          <div className="m-filter-dropdown">
            <select value={filter} onChange={e => setFilter(e.target.value)}>
              {FILTERS.map(f => <option key={f} value={f}>{f}</option>)}
            </select>
            <label className="search-box" style={{ flex: 1 }}>
              <Icons.Search size={14} />
              <input value={q} onChange={e => setQ(e.target.value)} placeholder="search…" />
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}

function Ledger({ jobs, loading, err, totalCount }) {
  return (
    <div className="jobs-ledger">
      {loading && jobs.length === 0 && (
        <div style={{ padding: '40px 0', fontFamily: 'var(--mono)', color: 'var(--ink-faint)', fontSize: 13 }}>
          ↳ loading register…
        </div>
      )}
      {err && (
        <div style={{ padding: '40px 0', fontFamily: 'var(--mono)', color: 'var(--rule)', fontSize: 13 }}>
          ! cannot load registry: {err}
        </div>
      )}
      {!loading && !err && jobs.length === 0 && totalCount === 0 && (
        <div style={{ padding: '40px 0', fontFamily: 'var(--mono)', color: 'var(--ink-faint)', fontSize: 13 }}>
          ↳ no entries yet. <a href="/" style={{ borderBottom: '1px dotted', color: 'var(--ink-soft)' }}>start a job</a> to begin.
        </div>
      )}
      {!loading && !err && jobs.length === 0 && totalCount > 0 && (
        <div style={{ padding: '40px 0', fontFamily: 'var(--mono)', color: 'var(--ink-faint)', fontSize: 13 }}>
          ↳ no entries match. clear filter or try another query.
        </div>
      )}
      {jobs.map(j => <LedgerRow key={j.id} job={j} />)}
    </div>
  );
}

function LedgerRow({ job }) {
  const isActive = job.state === 'processing';
  return (
    <div className={`ledger-row ${isActive ? 'is-active' : ''}`}>
      <div className="ledger-date">
        <span className="d-day">{job.date}</span>
        <span className="d-time">{job.time}</span>
        <span className="d-id">#{job.id}</span>
      </div>
      <div className="ledger-entry">
        <div className="ledger-entry-head">
          <span className="ledger-entry-file">{job.file}</span>
          {chipForRow(job.state)}
        </div>
        <div className="ledger-meta">
          {job.model || '—'}<span className="sep">·</span>{job.ocr}<span className="sep">·</span>{job.pages || '—'} p
          {isActive && job.pages > 0 && (<><span className="sep">·</span>{job.progress}% · page {job.page}/{job.pages}</>)}
        </div>
        {job.state === 'error' && job.error && (
          <div className="ledger-error">! {job.error}</div>
        )}
        {isActive && job.pages > 0 && (
          <div className="ledger-active-bar">
            <ProgressBar value={job.progress} tone="ai" />
          </div>
        )}
      </div>
      <div className="ledger-actions">
        {isActive && (
          <a className="btn btn-ai btn-sm ledger-primary-action" href={`/?job=${job.id}`}>
            view live <Icons.ChevR size={12} />
          </a>
        )}
        {job.state === 'done' && (
          <>
            <span className="ledger-secondary-actions" style={{ display: 'inline-flex', gap: 6 }}>
              {job.hasPdf && (
                <a className="btn btn-paper btn-sm" href={`/api/jobs/${job.id}/download?fmt=pdf`}>
                  <Icons.Download size={12} /> <span className="btn-text">pdf</span>
                </a>
              )}
              <a className="btn btn-ghost btn-sm" href={`/api/jobs/${job.id}/download?fmt=tex`}>
                <Icons.Download size={12} /> <span className="btn-text">tex</span>
              </a>
            </span>
            <a className="btn btn-ghost btn-sm ledger-primary-action"
               href={`/api/jobs/${job.id}/download?fmt=${job.hasPdf ? 'pdf' : 'tex'}`}>
              <Icons.Download size={12} /> {job.hasPdf ? 'pdf' : 'tex'}
            </a>
          </>
        )}
        {job.state === 'error' && (
          <>
            <span className="ledger-secondary-actions" style={{ display: 'inline-flex', gap: 6 }}>
              <a className="btn btn-ghost btn-sm" href={`/api/jobs/${job.id}/download?fmt=tex`}>
                <Icons.Download size={12} /> <span className="btn-text">.tex</span>
              </a>
            </span>
            <a className="btn btn-ghost-warn btn-sm ledger-primary-action" href="/">
              <Icons.Reload size={12} /> retry
            </a>
          </>
        )}
        {job.state === 'queued' && (
          <span className="mono" style={{ fontSize: 11, color: 'var(--ink-faint)' }}>queued</span>
        )}
      </div>
    </div>
  );
}

function Footer({ count }) {
  return (
    <div className="jobs-footer">
      <span>made with ♥ by @cmrabdu</span>
      <span style={{ padding: '0 10px' }}>·</span>
      <a href="https://github.com/cmrabdu/Palimpsest" target="_blank" rel="noreferrer" className="footer-link">github ↗</a>
      <span style={{ padding: '0 10px' }}>·</span>
      <a href="https://cmrabdu.com" target="_blank" rel="noreferrer" className="footer-link">cmrabdu.com</a>
      <span className="jobs-footer-right">vol. iii · {count} entries</span>
    </div>
  );
}

Object.assign(window, { JobsPage });
