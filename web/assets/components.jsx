/* global React */
// Palimpsest — shared UI components (paper × terminal)

const { useState, useEffect, useRef, useMemo } = React;

// ----- ICONS (monoline, 16px, 1.5px stroke) ---------------------------------
const Icon = ({ d, size = 16, stroke = 1.5, ...rest }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
       stroke="currentColor" strokeWidth={stroke}
       strokeLinecap="round" strokeLinejoin="round" {...rest}>
    {typeof d === 'string' ? <path d={d}/> : d}
  </svg>
);

const Icons = {
  Download: (p) => <Icon {...p} d="M12 4v12m0 0l-4-4m4 4l4-4M5 20h14"/>,
  Upload:   (p) => <Icon {...p} d="M12 20V8m0 0L8 12m4-4l4 4M5 4h14"/>,
  Play:     (p) => <Icon {...p} d="M6 4l14 8L6 20V4z"/>,
  Check:    (p) => <Icon {...p} d="M4 12l5 5L20 6"/>,
  X:        (p) => <Icon {...p} d="M6 6l12 12M18 6L6 18"/>,
  Plus:     (p) => <Icon {...p} d="M12 5v14m-7-7h14"/>,
  ArrowR:   (p) => <Icon {...p} d="M5 12h14m-6-6l6 6-6 6"/>,
  ArrowL:   (p) => <Icon {...p} d="M19 12H5m6-6l-6 6 6 6"/>,
  Ext:      (p) => <Icon {...p} d="M14 4h6v6M10 14L20 4M19 13v7H5V5h7"/>,
  Search:   (p) => <Icon {...p} d="M11 19a8 8 0 100-16 8 8 0 000 16zM21 21l-5-5"/>,
  ChevD:    (p) => <Icon {...p} d="M6 9l6 6 6-6"/>,
  ChevR:    (p) => <Icon {...p} d="M9 6l6 6-6 6"/>,
  More:     (p) => <Icon {...p} d="M5 12h.01M12 12h.01M19 12h.01" strokeWidth="2.4"/>,
  Reload:   (p) => <Icon {...p} d="M3 12a9 9 0 1015-6.7L21 8M21 3v5h-5"/>,
  History:  (p) => <Icon {...p} d="M3 12a9 9 0 109-9c-2.5 0-4.8 1-6.5 2.7L3 8M3 3v5h5M12 7v5l3 2"/>,
  File:     (p) => <Icon {...p} d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9l-6-6zM14 3v6h6"/>,
  Settings: (p) => <Icon {...p} d="M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.6 1.6 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.6 1.6 0 00-1.8-.3 1.6 1.6 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.6 1.6 0 00-1-1.5 1.6 1.6 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.6 1.6 0 00.3-1.8 1.6 1.6 0 00-1.5-1H3a2 2 0 110-4h.1a1.6 1.6 0 001.5-1 1.6 1.6 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.6 1.6 0 001.8.3H9a1.6 1.6 0 001-1.5V3a2 2 0 114 0v.1a1.6 1.6 0 001 1.5 1.6 1.6 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.6 1.6 0 00-.3 1.8V9a1.6 1.6 0 001.5 1H21a2 2 0 110 4h-.1a1.6 1.6 0 00-1.5 1z"/>,
};

// ----- BUTTON ---------------------------------------------------------------
function Button({ variant = "paper", size = "md", children, icon, iconRight, onTerm, ...rest }) {
  const cls = [
    "btn",
    `btn-${variant}`,
    size === "lg" && "btn-lg",
    size === "sm" && "btn-sm",
    onTerm && "on-term",
  ].filter(Boolean).join(" ");
  return (
    <button className={cls} {...rest}>
      {icon}
      {children}
      {iconRight}
    </button>
  );
}

// ----- CHIP -----------------------------------------------------------------
function Chip({ variant = "mute", dot, pulse, children, ...rest }) {
  return (
    <span className={`chip chip-${variant}`} {...rest}>
      {dot && <span className={`dot ${pulse ? 'dot-pulse' : ''}`} />}
      {children}
    </span>
  );
}

// ----- STAMP / WAX SEAL / RIBBON --------------------------------------------
function Stamp({ children, style }) {
  return <span className="stamp" style={style}>{children}</span>;
}
function WaxSeal({ children = '✎', size = 'md', style }) {
  const cls = size === 'sm' ? 'wax-seal wax-seal-sm' : size === 'lg' ? 'wax-seal wax-seal-lg' : 'wax-seal';
  return <span className={cls} style={style}>{children}</span>;
}
function Ribbon({ tone = 'ink', children }) {
  const cls = "ribbon" + (tone === 'ochre' ? ' ribbon-ochre' : tone === 'rule' ? ' ribbon-rule' : '');
  return <div className={cls}>{children}</div>;
}
function FolderTab({ children }) {
  return <div className="folder-tab">{children}</div>;
}

// ----- PAPER CARD -----------------------------------------------------------
function PaperCard({ rotate = 0, ribbon, ribbonTone, tab, foldCorner, children, className = '', style = {}, ...rest }) {
  return (
    <div
      className={`paper-card ${className}`}
      style={{ transform: rotate ? `rotate(${rotate}deg)` : undefined, ...style }}
      {...rest}
    >
      {ribbon && <Ribbon tone={ribbonTone}>{ribbon}</Ribbon>}
      {tab && <FolderTab>{tab}</FolderTab>}
      {foldCorner && <div className="fold-corner" />}
      {children}
    </div>
  );
}

// ----- TERMINAL PANEL -------------------------------------------------------
function TerminalPanel({ active, children, className = '', style = {}, ...rest }) {
  return (
    <div className={`term-panel ${active ? 'term-panel-active' : ''} ${className}`} style={style} {...rest}>
      {children}
    </div>
  );
}

// ----- PROGRESS BAR ---------------------------------------------------------
function ProgressBar({ value = 0, tone = "ai", size = "md" }) {
  const fill = tone === 'green' ? 'progress-fill-green'
             : tone === 'warn'  ? 'progress-fill-warn'
             : 'progress-fill-ai';
  return (
    <div className={`progress ${size === 'lg' ? 'progress-lg' : ''}`}>
      <div className={`progress-fill ${fill}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
    </div>
  );
}

// ----- STAGE CHIP -----------------------------------------------------------
function StageChip({ name, state = "pending", status }) {
  const cls = `stage-chip stage-chip-${state}`;
  const glyph = state === 'done' ? '✓' : state === 'failed' ? '!' : state === 'active' ? '◐' : '○';
  return (
    <div className={cls}>
      <div className="stage-name">{name}</div>
      <div className="stage-status">{glyph} {status}</div>
    </div>
  );
}

// ----- LOG STREAM -----------------------------------------------------------
function LogLine({ time, glyph = ' ', stage, msg, tone = "" }) {
  return (
    <div className={`log-line log-${tone}`}>
      <span className="log-time">[{time}]</span>
      <span className="log-glyph">{glyph}</span>
      <span className="log-stage">{stage}</span>
      <span className="log-msg">{msg}</span>
    </div>
  );
}

// Export all to window
Object.assign(window, {
  Icon, Icons, Button, Chip, Stamp, WaxSeal, Ribbon, FolderTab,
  PaperCard, TerminalPanel, ProgressBar, StageChip, LogLine,
});
