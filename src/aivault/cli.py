"""AIVault CLI (ARCHITECTURE §13). Thin layer over `service` + exporters."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .adapters.base import syncable_sources
from .config import VaultConfig, resolve_vault_path
from .exporters.llmwiki import export_llmwiki
from .service import Vault, init_vault, normalize_status

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="AIVault — local-first AI session collector, search, triage, and LLM Wiki export.",
)
export_app = typer.Typer(no_args_is_help=True, help="Export curated sessions.")
config_app = typer.Typer(no_args_is_help=True, help="View and edit vault config.")
app.add_typer(export_app, name="export")
app.add_typer(config_app, name="config")

# global state populated by the root callback
_state: dict[str, Optional[Path]] = {"vault": None}


@app.callback()
def _root(
    vault: Optional[Path] = typer.Option(
        None, "--vault", help="Vault path (default: $AIVAULT_HOME or ~/ai-vault)."
    ),
):
    _state["vault"] = vault


def _vault_path() -> Path:
    return resolve_vault_path(_state["vault"])


def _open() -> Vault:
    cfg = VaultConfig.load(_vault_path())
    return Vault(cfg)


def _short(sid: str) -> str:
    return sid[:8]


# ---------------------------------------------------------------------------
# Vault lifecycle
# ---------------------------------------------------------------------------

@app.command()
def init(path: Optional[Path] = typer.Argument(None, help="Vault directory to create.")):
    """Create a local vault (dirs + SQLite + config)."""
    root = resolve_vault_path(path or _state["vault"])
    if (root / "config.yaml").exists():
        typer.echo(f"Vault already exists at {root}")
        raise typer.Exit(0)
    init_vault(root)
    typer.secho(f"Initialized AIVault v{__version__} at {root}", fg=typer.colors.GREEN)


@app.command()
def status():
    """Show vault location and counts."""
    root = _vault_path()
    if not (root / "config.yaml").exists():
        typer.secho(f"No vault at {root}. Run `aivault init {root}`.", fg=typer.colors.RED)
        raise typer.Exit(1)
    v = _open()
    c = v.counts()
    typer.echo(f"Vault:    {root}")
    typer.echo(f"Sessions: {c['sessions']}  (wiki_ready: {c['wiki_ready']})")
    typer.echo(f"Messages: {c['messages']}")
    typer.echo(f"Raw artifacts: {c['raw_artifacts']}   Projects: {c['projects']}")
    typer.echo(f"Redaction findings: {c['findings']}")
    v.close()


@app.command()
def discover(
    os_scope: str = typer.Option(
        "native", "--os-scope", help="Where to look: native | windows | wsl | all."
    ),
):
    """List supported local sources found on this machine (optionally cross-OS)."""
    v = _open()
    candidates = v.discover(os_scope)
    if not candidates:
        typer.echo(f"No known local sources discovered (scope: {os_scope}).")
    for c in candidates:
        typer.echo(
            f"{c.source_tool:<12} {c.os_context:<8} ~{c.estimated_sessions} sessions  {c.path}"
        )
    v.close()


# ---------------------------------------------------------------------------
# Import / sync
# ---------------------------------------------------------------------------

@app.command("import-file")
def import_file(
    path: Path = typer.Argument(..., exists=True, readable=True),
    source: str = typer.Option(..., "--source", "-s", help="Source tool label."),
):
    """Import a single file."""
    v = _open()
    res = v.import_file(path, source)
    for sid in res.imported:
        typer.echo(f"imported {_short(sid)}")
    typer.secho(
        f"Done: {len(res.imported)} imported, {res.skipped} skipped, "
        f"{res.findings} redaction findings.",
        fg=typer.colors.GREEN,
    )
    v.close()


@app.command("import-folder")
def import_folder(
    path: Path = typer.Argument(..., exists=True, file_okay=False),
    source: str = typer.Option("folder", "--source", "-s"),
    pattern: str = typer.Option("**/*", "--pattern", help="Glob of files to import."),
):
    """Import a folder of exports (md/txt/json/html)."""
    v = _open()
    imported = skipped = findings = 0
    for f in sorted(path.glob(pattern)):
        if not f.is_file():
            continue
        if f.suffix.lower() not in (".md", ".txt", ".json", ".jsonl", ".html", ".htm", ".zip"):
            continue
        res = v.import_file(f, source)
        imported += len(res.imported)
        skipped += res.skipped
        findings += res.findings
    typer.secho(
        f"Done: {imported} imported, {skipped} skipped, {findings} findings.",
        fg=typer.colors.GREEN,
    )
    v.close()


_OS_SCOPE_OPT = typer.Option(None, "--os-scope", help="native | windows | wsl | all.")


@app.command()
def detect(
    os_scope: str = typer.Option("native", "--os-scope", help="native | windows | wsl | all."),
    save: bool = typer.Option(
        False, "--save", help="Save detected agents to config as the sync set."
    ),
):
    """Detect which agents are sync-able on this machine (and optionally save them)."""
    v = _open()
    found = v.detect(os_scope)
    v.close()
    if not found:
        typer.echo(f"No sync-able agents detected (scope: {os_scope}).")
    for tool, info in sorted(found.items()):
        typer.echo(
            f"{tool:<12} ~{info['sessions']} sessions  "
            f"[{', '.join(info['os_contexts'])}]  {info['paths'][0]}"
        )
    if save:
        cfg = VaultConfig.load(_vault_path())
        cfg.sync_sources = sorted(found.keys())
        cfg.sync_os_scope = os_scope
        cfg.save()
        typer.secho(
            f"Saved sync sources: {', '.join(cfg.sync_sources) or '(none)'}",
            fg=typer.colors.GREEN,
        )


@app.command()
def sync(
    tool: Optional[str] = typer.Argument(
        None, help="Agent to sync (e.g. claude-code). Omit to sync configured agents."
    ),
    os_scope: Optional[str] = _OS_SCOPE_OPT,
    all_: bool = typer.Option(False, "--all", help="Sync every sync-able agent."),
):
    """Discover and import native logs. With no argument, syncs the agents in config."""
    cfg = VaultConfig.load(_vault_path())
    scope = os_scope or cfg.sync_os_scope

    if tool:
        targets = [tool]
    elif all_:
        targets = syncable_sources()
    else:
        targets = cfg.sync_sources
        if not targets:
            typer.secho(
                "No sync sources configured. Run `aivault detect --save` (or "
                "`aivault config set-sources <agent...>`), or pass an agent / --all.",
                fg=typer.colors.YELLOW,
            )
            raise typer.Exit(1)

    v = Vault(cfg)
    total_i = total_s = total_f = 0
    for t in targets:
        res = v.sync(t, scope)
        total_i += len(res.imported)
        total_s += res.skipped
        total_f += res.findings
        typer.echo(
            f"  {t:<12} {len(res.imported)} imported, {res.skipped} skipped, "
            f"{res.findings} findings"
        )
    v.close()
    typer.secho(
        f"Sync ({', '.join(targets)} @ {scope}): {total_i} imported, "
        f"{total_s} skipped, {total_f} findings.",
        fg=typer.colors.GREEN,
    )


# ---------------------------------------------------------------------------
# Query / view
# ---------------------------------------------------------------------------

@app.command("list")
def list_sessions(
    source: Optional[str] = typer.Option(None, "--source"),
    project: Optional[str] = typer.Option(None, "--project"),
    status_: Optional[str] = typer.Option(None, "--status"),
    limit: int = typer.Option(100, "--limit"),
):
    """List sessions."""
    v = _open()
    rows = v.list_sessions(source=source, project=project, status=status_, limit=limit)
    if not rows:
        typer.echo("No sessions.")
    for r in rows:
        date = (r["started_at"] or r["imported_at"] or "")[:10]
        typer.echo(
            f"{_short(r['id'])}  {r['status']:<10} {r['source_tool']:<12} "
            f"{(r['project_name'] or '-'):<14} {date}  {r['title'] or ''}"
        )
    v.close()


@app.command()
def search(
    query: str = typer.Argument(...),
    limit: int = typer.Option(50, "--limit"),
):
    """Full-text search across all imported sessions."""
    v = _open()
    rows = v.search(query, limit=limit)
    if not rows:
        typer.echo("No matches.")
    for r in rows:
        date = (r["started_at"] or r["imported_at"] or "")[:10]
        typer.echo(
            f"{_short(r['id'])}  {r['source_tool']:<12} "
            f"{(r['project_name'] or '-'):<14} {date}  {r['title'] or ''}"
        )
    v.close()


@app.command()
def show(session_id: str = typer.Argument(...)):
    """Show session detail."""
    v = _open()
    s = v.get_session(session_id)
    if not s:
        typer.secho(f"No session matching '{session_id}'.", fg=typer.colors.RED)
        v.close()
        raise typer.Exit(1)
    tags = v.get_tags(s["id"])
    findings = v.get_findings(s["id"])
    typer.secho(s["title"] or "(untitled)", bold=True)
    typer.echo(f"id:          {s['id']}")
    typer.echo(f"source:      {s['source_tool']} / {s['source_kind']}")
    typer.echo(f"project:     {s['project_name'] or '-'}")
    typer.echo(f"status:      {s['status']}   sensitivity: {s['sensitivity']}")
    typer.echo(f"started_at:  {s['started_at'] or '-'}")
    typer.echo(f"messages:    {s['message_count']}   tags: {', '.join(tags) or '-'}")
    typer.echo(f"raw artifact id: {s['raw_artifact_id']}")
    if findings:
        typer.secho(f"⚠ {len(findings)} redaction finding(s):", fg=typer.colors.YELLOW)
        for f in findings:
            typer.echo(f"   [{f['confidence']}] {f['kind']}: {f['excerpt']}")
    cmds = [r["value"] for r in v.get_snippets(s["id"], "command")]
    files = [r["value"] for r in v.get_snippets(s["id"], "file_path")]
    if files:
        typer.echo("files: " + ", ".join(files))
    if cmds:
        typer.echo("commands: " + "; ".join(cmds))
    typer.echo("---")
    for m in v.get_messages(s["id"]):
        content = (m["content"] or "").strip()
        if content:
            typer.echo(f"[{m['role']}] {content[:500]}")
    v.close()


# ---------------------------------------------------------------------------
# Triage
# ---------------------------------------------------------------------------

@app.command()
def mark(
    session_id: str = typer.Argument(...),
    status_: str = typer.Argument(..., metavar="STATUS"),
):
    """Set triage status (new|reviewed|keep|ignore|wiki-ready|exported)."""
    v = _open()
    s = v.get_session(session_id)
    if not s:
        typer.secho(f"No session matching '{session_id}'.", fg=typer.colors.RED)
        v.close()
        raise typer.Exit(1)
    try:
        v.mark(s["id"], status_)
    except ValueError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        v.close()
        raise typer.Exit(1)
    typer.secho(f"{_short(s['id'])} -> {normalize_status(status_)}", fg=typer.colors.GREEN)
    v.close()


@app.command()
def tag(
    session_id: str = typer.Argument(...),
    tags: list[str] = typer.Argument(...),
):
    """Add one or more tags to a session."""
    v = _open()
    s = v.get_session(session_id)
    if not s:
        typer.secho(f"No session matching '{session_id}'.", fg=typer.colors.RED)
        v.close()
        raise typer.Exit(1)
    v.add_tags(s["id"], tags)
    typer.secho(f"tagged {_short(s['id'])}: {', '.join(tags)}", fg=typer.colors.GREEN)
    v.close()


@app.command()
def note(
    session_id: str = typer.Argument(...),
    text: str = typer.Argument(...),
):
    """Set the note for a session (searchable)."""
    v = _open()
    s = v.get_session(session_id)
    if not s:
        typer.secho(f"No session matching '{session_id}'.", fg=typer.colors.RED)
        v.close()
        raise typer.Exit(1)
    v.set_notes(s["id"], text)
    typer.secho(f"note set on {_short(s['id'])}", fg=typer.colors.GREEN)
    v.close()


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@export_app.command("llmwiki")
def export_llmwiki_cmd(
    out: Path = typer.Option(..., "--out", help="Output directory."),
    status_: str = typer.Option("wiki-ready", "--status"),
    mark_exported: bool = typer.Option(
        False, "--mark-exported", help="Set status to 'exported' after writing."
    ),
):
    """Export sessions to LLM Wiki-compatible Markdown + manifest."""
    v = _open()
    summary = export_llmwiki(v, out, status=status_, mark_exported=mark_exported)
    typer.secho(
        f"Exported {len(summary.exported)}, skipped {summary.skipped} (unchanged) "
        f"-> {summary.out_path}",
        fg=typer.colors.GREEN,
    )
    v.close()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address (local-only by default)."),
    port: int = typer.Option(8765, "--port"),
):
    """Start the local web frontend to browse and search the vault."""
    from .web import run as run_web

    root = _vault_path()
    if not (root / "config.yaml").exists():
        typer.secho(f"No vault at {root}. Run `aivault init {root}`.", fg=typer.colors.RED)
        raise typer.Exit(1)
    run_web(root, host=host, port=port)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@config_app.command("show")
def config_show():
    """Print the current vault configuration."""
    cfg = VaultConfig.load(_vault_path())
    typer.echo(f"root:                {cfg.root}")
    typer.echo(f"version:             {cfg.version}")
    typer.echo(f"default_sensitivity: {cfg.default_sensitivity}")
    typer.echo(f"redaction_policy:    {cfg.redaction_policy}")
    typer.echo(f"sync_os_scope:       {cfg.sync_os_scope}")
    typer.echo(f"sync_sources:        {', '.join(cfg.sync_sources) or '(none)'}")


@config_app.command("set-sources")
def config_set_sources(
    sources: list[str] = typer.Argument(..., help="Agents that `sync` will sync."),
    os_scope: Optional[str] = typer.Option(None, "--os-scope", help="Also set the sync scope."),
):
    """Set which agents `aivault sync` (no argument) syncs."""
    cfg = VaultConfig.load(_vault_path())
    syncable = set(syncable_sources())
    unknown = [s for s in sources if s not in syncable]
    if unknown:
        typer.secho(
            f"Warning: not auto-discoverable, will be no-ops on sync: {', '.join(unknown)}. "
            f"Sync-able agents: {', '.join(sorted(syncable))}.",
            fg=typer.colors.YELLOW,
        )
    cfg.sync_sources = list(dict.fromkeys(sources))  # de-dupe, keep order
    if os_scope:
        cfg.sync_os_scope = os_scope
    cfg.save()
    typer.secho(f"sync_sources = {', '.join(cfg.sync_sources)}", fg=typer.colors.GREEN)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
