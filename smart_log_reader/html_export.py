"""HTML export — self-contained dashboard + secure localhost-only HTTP server."""
from __future__ import annotations
import html
import json
import stat
from datetime import datetime
from pathlib import Path
from .models import AnalysisResult


def get_report_dir() -> Path:
    """
    Return ~/.smart-log-reader/reports/, creating it with mode 700 if needed.

    Storing reports here instead of next to the log file avoids:
      - PermissionError on /var/log/* and other root-owned directories
      - Accidentally leaving sensitive HTML in world-readable locations
      - Polluting system log directories with analysis artefacts

    The directory is:
      - Hidden  (dot-prefixed → not shown by plain `ls`)
      - Private (chmod 700  → only the owning user can read/write/enter)
    """
    report_dir = Path.home() / ".smart-log-reader" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_dir.chmod(stat.S_IRWXU)
    return report_dir


def safe_report_path(log_file: Path, suffix: str = ".html") -> Path:
    """
    Build a collision-safe, timestamped path inside the private report dir.

    Example:
        log_file = /var/log/postgresql/postgresql-16-main.log
        suffix   = .html
        →  ~/.smart-log-reader/reports/postgresql-16-main_20240115_102345.html
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{log_file.stem}_{ts}{suffix}"
    return get_report_dir() / name


def prune_old_reports(keep: int = 20) -> None:
    """Keep only the N most-recent reports. Silently ignores errors."""
    try:
        report_dir = get_report_dir()
        reports = sorted(
            report_dir.iterdir(),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in reports[keep:]:
            old.unlink(missing_ok=True)
    except Exception:
        pass



def _esc(s: str) -> str:
    return html.escape(str(s or ""), quote=True)


def _ts(dt) -> str:
    return str(dt) if dt else "—"



def export_html(result: AnalysisResult, output_path: Path) -> Path:
    """Render result to a fully self-contained HTML file (chmod 600)."""

    js_entries = json.dumps([
        {
            "ts": str(e.timestamp) if e.timestamp else "",
            "level": e.level,
            "src": e.source or "",
            "msg": e.message[:600],
            "cat": e.category or "",
            "cnt": e.occurrence_count,
            "line": e.line_number,
        }
        for e in result.entries
    ], separators=(",", ":"))

    js_groups = json.dumps([
        {
            "issue": g.core_issue[:200],
            "count": g.count,
            "first": _ts(g.first_seen),
            "last": _ts(g.last_seen),
            "sample": g.representative[:400],
        }
        for g in result.error_groups
    ], separators=(",", ":"))

    total = result.parsed_entries
    errors = result.error_count
    warns = result.warning_count
    infos = result.info_count
    debugs = result.debug_count
    unique = result.unique_errors
    fmt = _esc(result.detected_format)
    ts_from = _esc(_ts(result.time_span_start))
    ts_to = _esc(_ts(result.time_span_end))
    err_rate = round(errors / total * 100, 1) if total else 0

    group_rows = ""
    for i, g in enumerate(result.error_groups[:50], 1):
        pct = round(g.count / errors * 100, 1) if errors else 0
        group_rows += f"""
        <tr class="group-row" onclick="copyGroup(this)" title="Click to copy for AI">
          <td class="rank">#{i}</td>
          <td class="freq"><span class="badge-freq">{g.count}</span><span class="pct">{pct}%</span></td>
          <td class="issue-cell">
            <div class="issue-text">{_esc(g.core_issue[:160])}</div>
            <div class="sample-msg">{_esc(g.representative[:300])}</div>
          </td>
          <td class="ts-cell">{_esc(_ts(g.first_seen))}</td>
          <td class="ts-cell">{_esc(_ts(g.last_seen))}</td>
        </tr>"""

    if not group_rows:
        group_rows = '<tr><td colspan="5" class="empty-row">No error groups detected</td></tr>'

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Log Analysis Report — {fmt}</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#0d0f14;--surface:#13161e;--surface2:#1a1e29;
  --border:#252a38;--border2:#2e3447;
  --text:#c8cfe0;--text-dim:#5a6278;--text-bright:#e8ecf6;
  --accent:#3b82f6;--accent2:#1d4ed8;
  --red:#f43f5e;--red-dim:#3b0a16;
  --amber:#f59e0b;--amber-dim:#2d1f04;
  --green:#22c55e;--green-dim:#052e16;
  --cyan:#06b6d4;--purple:#a855f7;
  --font-mono:'JetBrains Mono','Fira Code','Cascadia Code',monospace;
  --font-ui:'DM Sans','IBM Plex Sans',sans-serif;
  --radius:6px;--gutter:20px;
}}
html{{scroll-behavior:smooth}}
body{{background:var(--bg);color:var(--text);font-family:var(--font-ui);font-size:14px;line-height:1.6;min-height:100vh;}}
body::before{{content:'';position:fixed;inset:0;pointer-events:none;z-index:999;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.06) 2px,rgba(0,0,0,.06) 4px);}}
::-webkit-scrollbar{{width:6px;height:6px}}::-webkit-scrollbar-track{{background:var(--bg)}}::-webkit-scrollbar-thumb{{background:var(--border2);border-radius:3px}}
.page{{max-width:1400px;margin:0 auto;padding:var(--gutter)}}
header{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;padding:18px 24px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:20px;position:relative;overflow:hidden;}}
header::after{{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--accent),var(--purple),var(--cyan));}}
.brand{{display:flex;align-items:center;gap:10px}}
.brand-icon{{width:36px;height:36px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px;}}
.brand-name{{font-size:17px;font-weight:700;color:var(--text-bright);letter-spacing:-.3px}}
.brand-sub{{font-size:11px;color:var(--text-dim);font-family:var(--font-mono)}}
.header-meta{{display:flex;gap:16px;align-items:center;flex-wrap:wrap}}
.meta-pill{{font-family:var(--font-mono);font-size:11px;padding:3px 10px;border-radius:20px;background:var(--surface2);border:1px solid var(--border2);color:var(--text-dim);}}
.meta-pill span{{color:var(--text-bright)}}
.stats-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:20px;}}
.stat-card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px 18px;position:relative;overflow:hidden;transition:border-color .2s,transform .15s;cursor:default;}}
.stat-card:hover{{border-color:var(--border2);transform:translateY(-1px)}}
.stat-card::before{{content:'';position:absolute;top:0;left:0;width:3px;height:100%;border-radius:3px 0 0 3px;}}
.stat-card.card-total::before{{background:var(--accent)}}.stat-card.card-error::before{{background:var(--red)}}.stat-card.card-warn::before{{background:var(--amber)}}.stat-card.card-info::before{{background:var(--green)}}.stat-card.card-debug::before{{background:var(--text-dim)}}.stat-card.card-unique::before{{background:var(--purple)}}
.stat-label{{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px}}
.stat-value{{font-size:28px;font-weight:700;font-family:var(--font-mono);color:var(--text-bright);line-height:1}}
.stat-card.card-error .stat-value{{color:var(--red)}}.stat-card.card-warn .stat-value{{color:var(--amber)}}.stat-card.card-info .stat-value{{color:var(--green)}}.stat-card.card-unique .stat-value{{color:var(--purple)}}
.stat-rate{{font-size:11px;color:var(--text-dim);margin-top:4px;font-family:var(--font-mono)}}
.panel{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:20px;overflow:hidden;}}
.panel-header{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;padding:12px 18px;border-bottom:1px solid var(--border);background:var(--surface2);}}
.panel-title{{font-size:13px;font-weight:600;color:var(--text-bright);display:flex;align-items:center;gap:8px;letter-spacing:.2px;}}
.panel-badge{{font-size:10px;font-family:var(--font-mono);padding:2px 8px;border-radius:20px;background:var(--border);color:var(--text-dim);}}
.erate-bar{{height:4px;background:var(--surface2);margin-bottom:20px;border-radius:2px;overflow:hidden;}}
.erate-fill{{height:100%;background:linear-gradient(90deg,var(--accent),var(--red));border-radius:2px;}}
.groups-table{{width:100%;border-collapse:collapse}}
.groups-table thead tr{{background:var(--surface2)}}
.groups-table th{{padding:9px 12px;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.9px;color:var(--text-dim);font-weight:600;border-bottom:1px solid var(--border);white-space:nowrap;}}
.group-row{{border-bottom:1px solid var(--border);cursor:pointer;transition:background .15s;}}
.group-row:hover{{background:rgba(59,130,246,.05)}}.group-row:hover .issue-text{{color:var(--accent)}}
.group-row td{{padding:10px 12px;vertical-align:top}}
.rank{{font-family:var(--font-mono);font-size:11px;color:var(--text-dim);white-space:nowrap}}
.freq{{white-space:nowrap;text-align:center}}
.badge-freq{{display:inline-block;background:var(--red-dim);color:var(--red);font-family:var(--font-mono);font-size:12px;font-weight:700;padding:2px 8px;border-radius:4px;border:1px solid rgba(244,63,94,.2);}}
.pct{{display:block;font-size:10px;color:var(--text-dim);margin-top:2px;font-family:var(--font-mono)}}
.issue-text{{font-family:var(--font-mono);font-size:12px;color:var(--text-bright);margin-bottom:4px;word-break:break-all}}
.sample-msg{{font-size:11px;color:var(--text-dim);word-break:break-all;max-height:40px;overflow:hidden}}
.ts-cell{{font-family:var(--font-mono);font-size:10px;color:var(--text-dim);white-space:nowrap}}
.empty-row{{text-align:center;padding:40px;color:var(--text-dim);font-style:italic}}
.toolbar{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 18px;border-bottom:1px solid var(--border);background:var(--surface2);}}
.search-box{{flex:1;min-width:200px;background:var(--bg);border:1px solid var(--border2);border-radius:var(--radius);color:var(--text-bright);padding:6px 12px;font-family:var(--font-mono);font-size:12px;outline:none;transition:border-color .2s;}}
.search-box:focus{{border-color:var(--accent)}}.search-box::placeholder{{color:var(--text-dim)}}
.level-btns{{display:flex;gap:4px;flex-wrap:wrap}}
.lvl-btn{{padding:4px 10px;border-radius:4px;border:1px solid var(--border2);font-size:11px;font-family:var(--font-mono);font-weight:600;background:transparent;cursor:pointer;color:var(--text-dim);transition:all .15s;letter-spacing:.3px;}}
.lvl-btn.active-ALL{{background:var(--surface);color:var(--text-bright);border-color:var(--border)}}
.lvl-btn.active-ERROR{{background:var(--red-dim);color:var(--red);border-color:rgba(244,63,94,.3)}}
.lvl-btn.active-WARNING{{background:var(--amber-dim);color:var(--amber);border-color:rgba(245,158,11,.3)}}
.lvl-btn.active-INFO{{background:var(--green-dim);color:var(--green);border-color:rgba(34,197,94,.3)}}
.lvl-btn.active-DEBUG{{background:var(--surface2);color:var(--text-dim);border-color:var(--border)}}
.toolbar-right{{margin-left:auto;display:flex;gap:6px}}
.btn-copy-all{{padding:5px 14px;border-radius:var(--radius);background:var(--accent2);border:1px solid var(--accent);color:#fff;font-size:11px;font-weight:600;cursor:pointer;transition:background .15s;white-space:nowrap;}}
.btn-copy-all:hover{{background:var(--accent)}}
.count-badge{{font-family:var(--font-mono);font-size:11px;color:var(--text-dim);padding:4px 10px;background:var(--bg);border-radius:4px;border:1px solid var(--border);white-space:nowrap;}}
.log-scroll{{max-height:620px;overflow-y:auto;}}
.log-table{{width:100%;border-collapse:collapse;font-family:var(--font-mono)}}
.log-table th{{padding:8px 12px;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.8px;color:var(--text-dim);border-bottom:1px solid var(--border);background:var(--surface2);font-weight:600;position:sticky;top:0;z-index:2;}}
.log-row{{border-bottom:1px solid rgba(37,42,56,.5);transition:background .1s}}
.log-row:hover{{background:var(--surface2)}}
.log-row td{{padding:6px 12px;vertical-align:top;font-size:11.5px}}
.log-row.row-error{{background:rgba(244,63,94,.04)}}.log-row.row-error:hover{{background:rgba(244,63,94,.08)}}
.log-row.row-warn{{background:rgba(245,158,11,.03)}}
.log-row.row-hidden{{display:none}}
.td-ts{{color:var(--cyan);white-space:nowrap;font-size:11px}}
.lvl-error{{color:var(--red);font-weight:700}}.lvl-warn{{color:var(--amber);font-weight:600}}.lvl-info{{color:var(--green)}}.lvl-debug{{color:var(--text-dim)}}.lvl-unknown{{color:var(--text-dim)}}
.td-src{{color:var(--purple);max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.td-msg{{word-break:break-word;color:var(--text)}}
.td-line{{color:var(--text-dim);text-align:right;font-size:10px}}
.td-cnt span{{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;background:var(--surface2);color:var(--text-dim);border:1px solid var(--border);}}
.td-cnt span.cnt-high{{background:var(--red-dim);color:var(--red);border-color:rgba(244,63,94,.2)}}
.copy-row-btn{{visibility:hidden;cursor:pointer;color:var(--text-dim);background:none;border:none;font-size:12px;padding:0 4px;transition:color .15s;}}
.log-row:hover .copy-row-btn{{visibility:visible}}.copy-row-btn:hover{{color:var(--accent)}}
#toast{{position:fixed;bottom:24px;right:24px;z-index:1000;background:var(--accent);color:#fff;padding:8px 18px;border-radius:6px;font-size:13px;font-weight:600;opacity:0;transform:translateY(8px);transition:opacity .2s,transform .2s;pointer-events:none;}}
#toast.show{{opacity:1;transform:translateY(0)}}
footer{{text-align:center;padding:24px;font-size:11px;color:var(--text-dim);font-family:var(--font-mono);}}
footer a{{color:var(--accent);text-decoration:none}}
@media(max-width:768px){{.stats-grid{{grid-template-columns:repeat(2,1fr)}}.ts-cell,.td-ts,.td-src,.td-line{{display:none}}}}
</style>
</head>
<body>
<div class="page">
<header>
  <div class="brand">
    <div class="brand-icon"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 96 96" id="Python--Streamline-Svg-Logos" height="24" width="24"> <desc> Python Streamline Icon: https://streamlinehq.com </desc> <path fill="url(#a)" d="M47.6611 1.24463c-23.863 0-22.3728 10.34847-22.3728 10.34847l.0266 10.7209h22.7719v3.2189H16.27S1 23.8011 1 47.8792c-.000002 24.078 13.328 23.2241 13.328 23.2241h7.9542V59.9302s-.4288-13.328 13.1151-13.328H57.983s12.6895.2052 12.6895-12.2638V13.7213S72.5991 1.24463 47.6611 1.24463ZM35.1047 8.45396c2.2656 0 4.0968 1.83114 4.0968 4.09684 0 2.2656-1.8312 4.0968-4.0968 4.0968-2.2657 0-4.0968-1.8312-4.0968-4.0968 0-2.2657 1.8311-4.09684 4.0968-4.09684Z"></path> <path fill="url(#b)" d="M48.3393 94.7555c23.8631 0 22.3729-10.3484 22.3729-10.3484l-.0266-10.7209H47.9137v-3.2189h31.8168s15.27 1.7317 15.27-22.3463-13.328-23.2242-13.328-23.2242h-7.9542v11.1731s.4288 13.328-13.1151 13.328H38.0175S25.328 49.1928 25.328 61.6618v20.6171s-1.9267 12.4766 23.0113 12.4766Zm12.5565-7.2093c-2.2657 0-4.0968-1.8312-4.0968-4.0968 0-2.2657 1.8311-4.0968 4.0968-4.0968 2.2656 0 4.0968 1.8311 4.0968 4.0968 0 2.2656-1.8312 4.0968-4.0968 4.0968Z"></path> <defs> <linearGradient id="a" x1="904.358" x2="5562.66" y1="842.346" y2="5454.17" gradientUnits="userSpaceOnUse"> <stop stop-color="#387eb8"></stop> <stop offset="1" stop-color="#366994"></stop> </linearGradient> <linearGradient id="b" x1="1358.62" x2="6361.13" y1="1462.61" y2="6191.63" gradientUnits="userSpaceOnUse"> <stop stop-color="#ffe052"></stop> <stop offset="1" stop-color="#ffc331"></stop> </linearGradient> </defs> </svg>
</div>
    <div>
      <div class="brand-name">smart-log-reader</div>
      <div class="brand-sub">Log Analysis Report</div>
    </div>
  </div>
  <div class="header-meta">
    <div class="meta-pill">Format: <span>{fmt}</span></div>
    <div class="meta-pill">From: <span>{ts_from}</span></div>
    <div class="meta-pill">To: <span>{ts_to}</span></div>
    <div class="meta-pill">Generated: <span id="gen-ts"></span></div>
  </div>
</header>
<div class="stats-grid">
  <div class="stat-card card-total"><div class="stat-label">Total Entries</div><div class="stat-value">{total:,}</div></div>
  <div class="stat-card card-error"><div class="stat-label">Errors</div><div class="stat-value">{errors:,}</div><div class="stat-rate">{err_rate}% of total</div></div>
  <div class="stat-card card-warn"><div class="stat-label">Warnings</div><div class="stat-value">{warns:,}</div></div>
  <div class="stat-card card-info"><div class="stat-label">Info</div><div class="stat-value">{infos:,}</div></div>
  <div class="stat-card card-debug"><div class="stat-label">Debug</div><div class="stat-value">{debugs:,}</div></div>
  <div class="stat-card card-unique"><div class="stat-label">Unique Errors</div><div class="stat-value">{unique:,}</div><div class="stat-rate">grouped by similarity</div></div>
</div>
<div class="erate-bar"><div class="erate-fill" style="width:{min(err_rate, 100)}%"></div></div>
<div class="panel">
  <div class="panel-header">
    <div class="panel-title">🔴 Error Groups <span class="panel-badge">{unique} unique · sorted by frequency</span></div>
    <button class="btn-copy-all" onclick="copyAllGroups()">📋 Copy All for AI</button>
  </div>
  <table class="groups-table">
    <thead><tr><th>#</th><th>Frequency</th><th>Error / Core Issue</th><th>First Seen</th><th>Last Seen</th></tr></thead>
    <tbody id="group-tbody">{group_rows}</tbody>
  </table>
</div>
<div class="panel">
  <div class="panel-header"><div class="panel-title">📄 Log Entries</div></div>
  <div class="toolbar">
    <input class="search-box" id="search" type="text" placeholder="Search message, source, category…" oninput="filterTable()"/>
    <div class="level-btns">
      <button class="lvl-btn active-ALL" data-lvl="ALL" onclick="setLevel('ALL')">ALL</button>
      <button class="lvl-btn" data-lvl="ERROR" onclick="setLevel('ERROR')">ERR</button>
      <button class="lvl-btn" data-lvl="WARNING" onclick="setLevel('WARNING')">WARN</button>
      <button class="lvl-btn" data-lvl="INFO" onclick="setLevel('INFO')">INFO</button>
      <button class="lvl-btn" data-lvl="DEBUG" onclick="setLevel('DEBUG')">DEBUG</button>
    </div>
    <div class="toolbar-right">
      <span class="count-badge" id="row-count">Loading…</span>
      <button class="btn-copy-all" onclick="copyVisible()">📋 Copy Visible for AI</button>
    </div>
  </div>
  <div class="log-scroll">
    <table class="log-table">
      <thead><tr><th>Timestamp</th><th>Level</th><th>Source</th><th>Message</th><th>#</th><th>Line</th><th></th></tr></thead>
      <tbody id="log-tbody"></tbody>
    </table>
  </div>
</div>
<footer>Generated by <a href="https://github.com/ABHINAVSSABHIGIT/smart_log_reader" target="_blank">smart-log-reader</a> &nbsp;·&nbsp; {total:,} entries &nbsp;·&nbsp; format: {fmt}</footer>
</div>
<div id="toast">✓ Copied to clipboard</div>
<script>
const ENTRIES={js_entries};
const GROUPS={js_groups};
const tbody=document.getElementById('log-tbody');
const rowEls=[];
const LC={{ERROR:'lvl-error',WARNING:'lvl-warn',INFO:'lvl-info',DEBUG:'lvl-debug',UNKNOWN:'lvl-unknown'}};
const RC={{ERROR:'row-error',WARNING:'row-warn',INFO:'',DEBUG:'',UNKNOWN:''}};
function esc(s){{return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}}
ENTRIES.forEach((e,i)=>{{
  const tr=document.createElement('tr');
  tr.className='log-row '+(RC[e.level]||'');
  tr.dataset.level=e.level;
  tr.dataset.search=(e.ts+' '+e.src+' '+e.msg+' '+e.cat).toLowerCase();
  const cnt=e.cnt>1?`<span class="cnt-high">${{e.cnt}}×</span>`:`<span>${{e.cnt}}</span>`;
  tr.innerHTML=`<td class="td-ts">${{e.ts||'—'}}</td><td class="${{LC[e.level]||'lvl-unknown'}}">${{e.level}}</td><td class="td-src" title="${{esc(e.src)}}">${{esc(e.src)}}</td><td class="td-msg">${{esc(e.msg)}}</td><td class="td-cnt">${{cnt}}</td><td class="td-line">${{e.line||''}}</td><td><button class="copy-row-btn" onclick="copyRow(${{i}})" title="Copy for AI">📋</button></td>`;
  tbody.appendChild(tr);rowEls.push(tr);
}});
let currentLevel='ALL',currentSearch='';
function setLevel(lvl){{
  currentLevel=lvl;
  document.querySelectorAll('.lvl-btn').forEach(b=>{{b.className='lvl-btn'+(b.dataset.lvl===lvl?' active-'+lvl:'');}});
  filterTable();
}}
function filterTable(){{
  currentSearch=document.getElementById('search').value.toLowerCase();
  let vis=0;
  rowEls.forEach(tr=>{{
    const ok=(currentLevel==='ALL'||tr.dataset.level===currentLevel)&&(!currentSearch||tr.dataset.search.includes(currentSearch));
    tr.classList.toggle('row-hidden',!ok);if(ok)vis++;
  }});
  document.getElementById('row-count').textContent=vis===rowEls.length?`${{rowEls.length}} entries`:`${{vis}} / ${{rowEls.length}} entries`;
}}
filterTable();
function toast(){{const t=document.getElementById('toast');t.classList.add('show');setTimeout(()=>t.classList.remove('show'),1800);}}
function copyText(txt){{navigator.clipboard.writeText(txt).then(toast).catch(()=>{{const ta=document.createElement('textarea');ta.value=txt;document.body.appendChild(ta);ta.select();document.execCommand('copy');document.body.removeChild(ta);toast();}});}}
function copyRow(i){{const e=ENTRIES[i];copyText(`[${{e.ts}}] [${{e.level}}] ${{e.src?e.src+': ':''}}${{e.msg}}`);}}
function copyVisible(){{
  const lines=['=== Log Analysis Export ===','Format: {fmt}  |  Errors: {errors}  |  Warnings: {warns}  |  Info: {infos}',''];
  rowEls.forEach((tr,i)=>{{if(!tr.classList.contains('row-hidden')){{const e=ENTRIES[i];lines.push(`[${{e.ts||'—'}}] [${{e.level}}] ${{e.src?e.src+': ':''}}${{e.msg}}`);}}}}); 
  copyText(lines.join('\\n'));
}}
function copyGroup(tr){{
  const i=tr.rowIndex-1;if(i<0||i>=GROUPS.length)return;
  const g=GROUPS[i];
  copyText(`ERROR GROUP: ${{g.issue}}\\nOccurrences: ${{g.count}}\\nFirst: ${{g.first}}  Last: ${{g.last}}\\nSample: ${{g.sample}}`);
}}
function copyAllGroups(){{
  const lines=['=== Error Groups Summary ===',''];
  GROUPS.forEach((g,i)=>{{lines.push(`#${{i+1}} [${{g.count}}×] ${{g.issue}}`);lines.push(`  First: ${{g.first}}  Last: ${{g.last}}`);lines.push(`  Sample: ${{g.sample}}`);lines.push('');}});
  copyText(lines.join('\\n'));
}}
document.getElementById('gen-ts').textContent=new Date().toLocaleString();
</script>
</body>
</html>"""

    output_path.touch(mode=stat.S_IRUSR | stat.S_IWUSR, exist_ok=True)
    output_path.write_text(doc, encoding="utf-8")
    output_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    return output_path



def serve_html(html_path: Path, port: int = 0, public: bool = False) -> None:
    """
    Serve html_path via a minimal HTTP server.

    Security model
    ──────────────
    Default (public=False):
      • Binds to 127.0.0.1 ONLY — unreachable from any other machine.
      • Access requires an SSH tunnel from the analyst's laptop:
            ssh -L <port>:127.0.0.1:<port> user@server
        then open http://localhost:<port>/<filename> locally.
      • No credentials needed because SSH itself is the auth layer.

    Explicit public mode (public=True, requires --serve-public flag):
      • Binds to 0.0.0.0 — reachable over the network.
      • A single-use random token is embedded in the URL.
      • Token is checked on every request; wrong/missing token → 403.
      • Still HTTP (not HTTPS) — only use inside a trusted LAN or VPN.
      • For anything truly production-facing, put nginx/caddy in front with TLS.
    """
    import http.server
    import secrets
    import socket

    directory = html_path.parent
    filename = html_path.name
    token = secrets.token_urlsafe(24) if public else None

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def do_GET(self):
            if public and token:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(self.path)
                supplied = parse_qs(parsed.query).get("token", [""])[0]
                if supplied != token:
                    self.send_error(403, "Forbidden — missing or invalid token")
                    return
                self.path = parsed.path  # strip token before serving
            super().do_GET()

        def log_message(self, *_):
            pass

    bind_addr = "0.0.0.0" if public else "127.0.0.1"

    with http.server.HTTPServer((bind_addr, port), Handler) as httpd:
        actual_port = httpd.server_address[1]

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "127.0.0.1"

        print()
        if not public:
            pad = " " * max(0, 27 - len(local_ip))
            print("  ✅  Report server started  (localhost-only · SSH tunnel required)")
            print()
            print("  ┌─ Run this on your LOCAL machine ──────────────────────────────────┐")
            print(f"  │                                                                    │")
            print(f"  │   ssh -L {actual_port}:127.0.0.1:{actual_port} <user>@{local_ip}{pad}│")
            print(f"  │                                                                    │")
            print(f"  │   Then open in your browser:                                       │")
            print(f"  │   http://localhost:{actual_port}/{filename:<42}│")
            print(f"  └────────────────────────────────────────────────────────────────────┘")
            print()
            print(f"  📁  File : {html_path}")
            print(f"  🔒  Bind : 127.0.0.1:{actual_port}  (not reachable without the tunnel)")
        else:
            # ── EXPLICIT public mode ──────────────────────────────────────
            url = f"http://{local_ip}:{actual_port}/{filename}?token={token}"
            print("  ⚠️   PUBLIC mode — token-protected · HTTP only · LAN/VPN use only")
            print()
            print(f"  🌐  URL →  {url}")
            print()
            print("  This URL contains a secret token. Share only over secure channels.")
            print("  For internet-facing access, put Nginx/Caddy with TLS in front instead.")

        print()
        print("  Ctrl+C to stop.\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Server stopped.")
