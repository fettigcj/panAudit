"""
Pan Audit CLI

Run audits non-interactively by reusing the core application components.

Usage examples (PowerShell):
  python pan_audit_cli.py run --config config\panAudit.json --audits config\audits.json \
    --panorama panorama.example.com --jobs 4 --delete-intermediate

Notes:
- Reads audits from the audits.json file and app settings from panAudit.json.
- Executes audits using the same TaskQueue as the GUI and then consolidates the
  resulting per-audit .xls files into a single XLSX via analyze_output().
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Dict, Tuple, List

# Ensure src is importable when running from repo root
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(CURRENT_DIR, 'src')) and os.path.join(CURRENT_DIR) not in sys.path:
    sys.path.append(CURRENT_DIR)

from src.core.application import PanAuditApplication  # type: ignore

LOGGER = logging.getLogger('PanAuditCLI')


def setup_logging(level: str) -> None:
    lvl = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=lvl, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    LOGGER.setLevel(lvl)


def load_configs(config_path: str, audits_path: str) -> Dict:
    """Load panAudit.json and audits.json, merging audits into config like the GUI does.
    """
    # Defaults aligned with PanAuditApplication._load_config
    config = {
        "Panoramas": {},
        "globalConfig": {
            "currentPanorama": "",
            "maxThreads": 5,
            "maxActiveProcesses": 5
        },
        "extraArguments": {
            "shadow-ignoreInvalidAddressobjects": "enabled",
            "shadow-json": "enabled"
        }
    }

    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            try:
                base = json.load(f)
                if isinstance(base, dict):
                    # shallow-merge base into defaults
                    config.update(base)
                else:
                    LOGGER.warning("panAudit.json is not a JSON object; using defaults")
            except Exception as e:
                LOGGER.error(f"Failed to parse {config_path}: {e}")
    else:
        LOGGER.info(f"Config file not found, using defaults: {config_path}")

    if os.path.exists(audits_path):
        with open(audits_path, 'r', encoding='utf-8') as f:
            try:
                audits_cfg = json.load(f)
                if isinstance(audits_cfg, dict):
                    if "AuditSections" in audits_cfg:
                        config["AuditSections"] = audits_cfg["AuditSections"]
                    if "SPG_Audits" in audits_cfg:
                        config["SPG_Audits"] = audits_cfg["SPG_Audits"]
                else:
                    LOGGER.warning("audits.json is not a JSON object; no audits loaded")
            except Exception as e:
                LOGGER.error(f"Failed to parse {audits_path}: {e}")
    else:
        LOGGER.warning(f"Audits file not found, no audits loaded: {audits_path}")

    return config


def select_panoramas(config: Dict, cli_panoramas: List[str] | None) -> List[str]:
    """Return list of panorama keys to run.
    Rules:
    - If --panorama provided, each token may be a name or a 1-based index. Tokens can be comma- or space-separated.
    - If not provided, use globalConfig.currentPanorama if valid; otherwise default to index 1 (first defined Panorama).
    """
    # Preserve JSON order by using dict keys order (Python 3.7+ preserves insertion order)
    available = list(config.get('Panoramas', {}).keys())
    if not available:
        LOGGER.error("No Panoramas configured in panAudit.json")
        return []

    def resolve_token(tok: str) -> str | None:
        t = tok.strip()
        if not t:
            return None
        if t.isdigit():
            idx = int(t)
            if 1 <= idx <= len(available):
                name = available[idx - 1]
                LOGGER.debug(f"--panorama index {idx} -> '{name}'")
                return name
            else:
                LOGGER.error(f"Panorama index out of range: {idx}. Valid range is 1..{len(available)}")
                return None
        # name path
        if t in available:
            return t
        LOGGER.error(f"Unknown Panorama: '{t}'. Available: {', '.join(available)}")
        return None

    if cli_panoramas:
        # Flatten comma-separated values inside tokens
        flat_tokens: List[str] = []
        for token in cli_panoramas:
            if token is None:
                continue
            parts = [p for p in (token.split(',') if ',' in token else [token])]
            flat_tokens.extend(parts)
        resolved: List[str] = []
        seen = set()
        for tok in flat_tokens:
            name = resolve_token(tok)
            if name is None:
                return []  # abort on any bad token
            if name not in seen:
                seen.add(name)
                resolved.append(name)
        return resolved

    current = config.get('globalConfig', {}).get('currentPanorama')
    if current and current in available:
        return [current]

    # Default to first panorama (index 1) when not specified and no valid currentPanorama
    return [available[0]]


def wait_for_tasks(app: PanAuditApplication, poll_interval: float = 0.5) -> None:
    """Poll the task list until all are completed/terminal states and queue is empty."""
    terminal = {"Completed", "Error", "Warning"}
    tq = app.task_queue
    last_report = 0
    while True:
        tasks = tq.get_all_tasks()
        # Consider no tasks a terminal condition as well
        if tasks and all(t.get('status') in terminal for t in tasks):
            # Ensure queue drained
            if tq.task_queue.empty():  # type: ignore[attr-defined]
                break
        elif not tasks and tq.task_queue.empty():  # type: ignore[attr-defined]
            break
        # periodic progress
        now = time.time()
        if now - last_report > 5:
            done = sum(1 for t in tasks if t.get('status') in terminal)
            total = len(tasks)
            LOGGER.info(f"Progress: {done}/{total} tasks finished")
            last_report = now
        time.sleep(poll_interval)


def consolidate(app: PanAuditApplication) -> Tuple[bool, str | None]:
    """Run analyze_output and return success and path to XLSX if any."""
    success, message, output_file = app.audit_manager.analyze_output()
    if success:
        LOGGER.info(f"Consolidation OK: {output_file}")
        return True, output_file
    LOGGER.error(f"Consolidation failed: {message}")
    return False, None


def delete_intermediate(output_dir: str) -> int:
    cnt = 0
    if os.path.isdir(output_dir):
        for fn in os.listdir(output_dir):
            if fn.lower().endswith('.xls'):
                try:
                    os.remove(os.path.join(output_dir, fn))
                    cnt += 1
                except Exception as e:
                    LOGGER.warning(f"Failed to delete {fn}: {e}")
    return cnt


def run_cmd(args: argparse.Namespace) -> int:
    setup_logging(args.log_level)

    # Resolve paths
    config_path = os.path.abspath(args.config)
    audits_path = os.path.abspath(args.audits)

    config = load_configs(config_path, audits_path)

    # Override output dir if provided
    if args.output_dir:
        outdir = os.path.abspath(args.output_dir)
        if not os.path.exists(outdir):
            os.makedirs(outdir, exist_ok=True)
        # Ensure application uses this
        # Note: PanAuditApplication uses cwd/output internally; we update cwd by chdir into repo root
        # so we also modify app directories post-init.
    else:
        outdir = os.path.join(os.getcwd(), 'output')
        os.makedirs(outdir, exist_ok=True)

    # Concurrency
    if 'globalConfig' not in config:
        config['globalConfig'] = {}
    config['globalConfig']['maxActiveProcesses'] = max(1, int(args.jobs))

    selected = select_panoramas(config, args.panorama)
    if not selected:
        return 1

    # Initialize core app with prepared config
    app = PanAuditApplication(config=config)

    # If output-dir override, update paths inside app components
    if outdir and os.path.abspath(app.output_dir) != outdir:
        app.output_dir = outdir
        app.audit_manager.output_dir = outdir
        # TaskQueue constructed its output_dir at init; override it too
        app.task_queue.output_dir = outdir
        # Ensure directories exist
        os.makedirs(outdir, exist_ok=True)

    exit_code = 0

    for pano in selected:
        LOGGER.info(f"Running audits for Panorama: {pano}")
        # Switch current panorama in config for this run
        app.config['globalConfig']['currentPanorama'] = pano

        # Generate tasks
        tasks = app.audit_manager.generate_audits()
        if not tasks:
            LOGGER.warning("No audits generated; skipping")
            continue

        if args.dry_run:
            LOGGER.info(f"Dry-run: would execute {len(tasks)} audits for {pano}")
            continue

        # Enqueue and execute
        submitted = app.audit_manager.execute_audits(tasks)
        LOGGER.info(f"Submitted {submitted} audit tasks for {pano}")

        # Wait for completion
        wait_for_tasks(app)

        # Consolidate outputs
        ok, xlsx = consolidate(app)
        if not ok:
            exit_code = 2
        else:
            # Optionally rename consolidated to include panorama and timestamped/overwrite policy
            if args.timestamped:
                # Already timestamped by analyze_output; optionally prepend panorama
                try:
                    if xlsx and pano not in os.path.basename(xlsx):
                        base = os.path.basename(xlsx)
                        new_name = f"panAudit_{pano}_{base.split('consolidated_output_')[-1]}"
                        new_path = os.path.join(os.path.dirname(xlsx), new_name)
                        os.replace(xlsx, new_path)
                        xlsx = new_path
                except Exception as e:
                    LOGGER.debug(f"Rename skipped: {e}")
            else:
                # Overwrite stable name per panorama
                stable = os.path.join(outdir, f"panAudit_{pano}.xlsx")
                try:
                    if xlsx:
                        os.replace(xlsx, stable)
                        xlsx = stable
                except Exception as e:
                    LOGGER.warning(f"Failed to move consolidated to stable name: {e}")

            LOGGER.info(f"Final report for {pano}: {xlsx}")

        # Optionally delete intermediate .xls
        if args.delete_intermediate:
            removed = delete_intermediate(outdir)
            LOGGER.info(f"Deleted {removed} intermediate .xls files for {pano}")

    return exit_code


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Pan Audit CLI')

    sub = p.add_subparsers(dest='command', required=False)
    runp = sub.add_parser('run', help='Run audits and consolidate outputs (default)')

    # Common options
    for rp in (runp,):
        rp.add_argument('--config', default=os.path.join('config', 'panAudit.json'), help='Path to panAudit.json')
        rp.add_argument('--audits', default=os.path.join('config', 'audits.json'), help='Path to audits.json')
        rp.add_argument('--panorama', nargs='*', help='Panorama selector(s): name(s) or 1-based index(es). Comma or space separated. If omitted, uses currentPanorama; else defaults to index 1.')
        rp.add_argument('--output-dir', default=os.path.join('output'), help='Directory for outputs and final report')
        rp.add_argument('--jobs', type=int, default=2, help='Max concurrent pan-os-php processes')
        rp.add_argument('--delete-intermediate', action='store_true', help='Delete per-audit .xls files after consolidation')
        rp.add_argument('--keep-intermediate', action='store_true', help='Keep per-audit .xls files (overrides --delete-intermediate)')
        rp.add_argument('--timestamped', action='store_true', help='Keep timestamp in consolidated filename (adds panorama prefix)')
        rp.add_argument('--log-level', default='info', help='Log level (debug, info, warning, error)')
        rp.add_argument('--dry-run', action='store_true', help='Print what would run without executing audits')

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    # Parse known args; if no subcommand provided, reparse with 'run' as default
    raw_argv = argv if argv is not None else sys.argv[1:]
    args = parser.parse_args(raw_argv)
    if getattr(args, 'command', None) is None:
        # Re-parse with 'run' prepended so subparser options (e.g., --log-level) are included
        args = parser.parse_args(['run', *raw_argv])

    # Normalize mutually exclusive flags
    if getattr(args, 'keep_intermediate', False):
        args.delete_intermediate = False

    if args.command == 'run':
        return run_cmd(args)

    LOGGER.error(f"Unknown command: {args.command}")
    return 1


if __name__ == '__main__':
    sys.exit(main())
