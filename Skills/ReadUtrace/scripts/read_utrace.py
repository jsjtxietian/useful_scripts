from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_UNREAL_INSIGHTS_EXE = r"D:\unrealengine5\Engine\Binaries\Win64\UnrealInsights.exe"
DEFAULT_TRACE_ANALYZER_EXE = r"D:\unrealengine5\Engine\Binaries\Win64\TraceAnalyzer.exe"


NEW_TRACE_RE = re.compile(
    r"EVENT(?: \[\d+\])?\s+\$Trace\.NewTrace\s+:.*?\bStartCycle=(0x[0-9A-Fa-f]+|\d+)\b.*?\bCycleFrequency=(0x[0-9A-Fa-f]+|\d+)\b"
)
BEGIN_FRAME_RE = re.compile(
    r"EVENT(?: \[\d+\])?\s+Misc\.BeginFrame\s+:.*?\bCycle=(\d+)\b.*?\bFrameType=(\d+)\b"
)
END_FRAME_RE = re.compile(
    r"EVENT(?: \[\d+\])?\s+Misc\.EndFrame\s+:.*?\bCycle=(\d+)\b.*?\bFrameType=(\d+)\b"
)


@dataclass
class FrameRecord:
    index: int
    start_cycle: int
    end_cycle: int
    start_time: float
    end_time: float


class SkillError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export an aggregated Unreal Insights timer callees tree for a specific frame."
    )
    parser.add_argument("--utrace", required=True, help="Path to the input .utrace file.")
    parser.add_argument(
        "--frame",
        type=int,
        help="Trace-local zero-based frame index. This is not the large absolute frame number shown in some Insights views.",
    )
    parser.add_argument("--timer", help="Timer name pattern passed to Unreal Insights.")
    parser.add_argument(
        "--threads",
        default="GameThread",
        help='Comma-separated thread filter passed to Unreal Insights. Use "*" for all threads.',
    )
    parser.add_argument(
        "--frame-type",
        choices=("game", "rendering"),
        default="game",
        help="Frame type used when resolving the frame window.",
    )
    parser.add_argument("--insights-exe", help="Explicit path to UnrealInsights.exe.")
    parser.add_argument("--trace-analyzer-exe", help="Explicit path to TraceAnalyzer.exe.")
    parser.add_argument(
        "--start-time-ms",
        type=float,
        help="Start time in milliseconds. When provided, frame resolution is skipped.",
    )
    parser.add_argument(
        "--end-time-ms",
        type=float,
        help="End time in milliseconds. Defaults to start_time_ms + duration_ms when omitted.",
    )
    parser.add_argument(
        "--duration-ms",
        type=float,
        default=30.0,
        help="Default window duration in milliseconds when end_time_ms is omitted.",
    )
    parser.add_argument(
        "--output-json",
        help="Optional output JSON path. Defaults to stdout when omitted.",
    )
    parser.add_argument(
        "--list-frames",
        action="store_true",
        help="List resolved trace-local frame indexes instead of exporting timer callees.",
    )
    parser.add_argument(
        "--list-frames-start",
        type=int,
        default=0,
        help="Start index for --list-frames output.",
    )
    parser.add_argument(
        "--list-frames-count",
        type=int,
        default=20,
        help="Number of frames to print for --list-frames.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep intermediate exported files.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print executed commands and temp paths to stderr.",
    )
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def find_executable(explicit_path: str | None, relative_candidates: Iterable[str], display_name: str) -> Path:
    if explicit_path:
        path = Path(explicit_path).expanduser().resolve()
        if not path.is_file():
            raise SkillError(f"{display_name} not found: {path}")
        return path

    root = repo_root()
    for candidate in relative_candidates:
        path = root / candidate
        if path.is_file():
            return path.resolve()

    found = shutil.which(display_name)
    if found:
        return Path(found).resolve()

    raise SkillError(
        f"Unable to locate {display_name}. Pass an explicit path with the corresponding command line option."
    )


def insights_quote(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def run_process(command: list[str], verbose: bool) -> subprocess.CompletedProcess[str]:
    if verbose:
        print("RUN:", subprocess.list2cmdline(command), file=sys.stderr)
    popen_kwargs: dict[str, object] = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if os.name == "nt":
        startup_info = subprocess.STARTUPINFO()
        startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        popen_kwargs["startupinfo"] = startup_info
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    result = subprocess.run(command, **popen_kwargs)
    if result.returncode != 0:
        raise SkillError(
            "Command failed.\n"
            f"Exit code: {result.returncode}\n"
            f"Command: {subprocess.list2cmdline(command)}\n"
            f"Stdout:\n{result.stdout}\n"
            f"Stderr:\n{result.stderr}"
        )
    return result


def parse_frame_records_from_text(text_path: Path, frame_type: str) -> list[FrameRecord]:
    frame_type_value = 0 if frame_type == "game" else 1

    start_cycle: int | None = None
    cycle_frequency: int | None = None
    open_cycles: list[int] = []
    frames: list[FrameRecord] = []

    with text_path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue

            if start_cycle is None or cycle_frequency is None:
                match = NEW_TRACE_RE.search(line)
                if match:
                    start_cycle = int(match.group(1), 0)
                    cycle_frequency = int(match.group(2), 0)
                    continue

            match = BEGIN_FRAME_RE.search(line)
            if match and int(match.group(2)) == frame_type_value:
                open_cycles.append(int(match.group(1)))
                continue

            match = END_FRAME_RE.search(line)
            if match and int(match.group(2)) == frame_type_value:
                if not open_cycles:
                    continue
                if start_cycle is None or cycle_frequency is None or cycle_frequency <= 0:
                    raise SkillError("Failed to resolve trace timing metadata before frame events were encountered.")

                begin_cycle = open_cycles.pop()
                end_cycle = int(match.group(1))
                if end_cycle < begin_cycle:
                    continue

                frame_index = len(frames)
                frames.append(
                    FrameRecord(
                        index=frame_index,
                        start_cycle=begin_cycle,
                        end_cycle=end_cycle,
                        start_time=(begin_cycle - start_cycle) / cycle_frequency,
                        end_time=(end_cycle - start_cycle) / cycle_frequency,
                    )
                )

    if start_cycle is None or cycle_frequency is None:
        raise SkillError("Could not find $Trace.NewTrace metadata in TraceAnalyzer output.")

    return frames


def load_frames(trace_analyzer_exe: Path, utrace_path: Path, frame_type: str, verbose: bool) -> list[FrameRecord]:
    with tempfile.TemporaryDirectory(prefix="insights_frame_scan_") as scan_dir:
        trace_text_path = Path(scan_dir) / "traceanalyzer.txt"
        command = [
            str(trace_analyzer_exe),
            str(utrace_path),
            f"-o={trace_text_path}",
            "-no_new_event_log",
            "-no_analysis_stats",
            "-no_event_stats",
        ]
        run_process(command, verbose)
        if not trace_text_path.is_file():
            raise SkillError(f"TraceAnalyzer did not create output file: {trace_text_path}")
        return parse_frame_records_from_text(trace_text_path, frame_type)


def resolve_frame(frames: list[FrameRecord], frame_index: int, frame_type: str) -> FrameRecord:
    if frame_index < 0:
        raise SkillError("Frame index must be non-negative.")
    if not frames:
        raise SkillError(f"No {frame_type} frames were resolved from the trace.")
    if frame_index >= len(frames):
        raise SkillError(
            "Frame index is out of range for this trace.\n"
            f"Requested frame index: {frame_index}\n"
            f"Resolved {frame_type} frames: {len(frames)}\n"
            f"Valid frame index range: 0..{len(frames) - 1}\n"
            "Note: --frame expects the trace-local zero-based frame index, not the large absolute frame number shown in some Insights views.\n"
            "Tip: run with --list-frames to inspect the available frame indexes for this trace."
        )
    return frames[frame_index]


def build_time_window_record(start_time_ms: float, end_time_ms: float) -> FrameRecord:
    if start_time_ms < 0:
        raise SkillError("--start-time-ms must be non-negative.")
    if end_time_ms <= start_time_ms:
        raise SkillError("--end-time-ms must be greater than --start-time-ms.")

    return FrameRecord(
        index=-1,
        start_cycle=0,
        end_cycle=0,
        start_time=start_time_ms / 1000.0,
        end_time=end_time_ms / 1000.0,
    )


def build_frame_listing(
    utrace_path: Path,
    frame_type: str,
    frames: list[FrameRecord],
    start: int,
    count: int,
) -> dict[str, object]:
    if start < 0:
        raise SkillError("--list-frames-start must be non-negative.")
    if count <= 0:
        raise SkillError("--list-frames-count must be positive.")

    end = min(start + count, len(frames))
    listed_frames = [
        {
            "frame": frame.index,
            "start_time": frame.start_time,
            "end_time": frame.end_time,
            "duration": frame.end_time - frame.start_time,
        }
        for frame in frames[start:end]
    ]
    return {
        "mode": "list_frames",
        "utrace_path": str(utrace_path),
        "frame_type": frame_type,
        "total_frames": len(frames),
        "list_start": start,
        "list_count": len(listed_frames),
        "frames": listed_frames,
    }


def read_text_tail(path: Path, max_lines: int = 80) -> str:
    if not path.is_file():
        return ""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()
    return "".join(lines[-max_lines:]).strip()


def export_timer_callees(
    insights_exe: Path,
    utrace_path: Path,
    export_csv_path: Path,
    insights_log_path: Path,
    response_file_path: Path,
    timer: str,
    threads: str,
    frame: FrameRecord,
    verbose: bool,
) -> None:
    export_csv_text = export_csv_path.as_posix()
    command_text = (
        f"TimingInsights.ExportTimerCallees {insights_quote(export_csv_text)} "
        f"-threads={insights_quote(threads)} "
        f"-timers={insights_quote(timer)} "
        f"-startTime={frame.start_time:.9f} "
        f"-endTime={frame.end_time:.9f}"
    )
    response_file_path.write_text(command_text + os.linesep, encoding="utf-8")
    command = [
        str(insights_exe),
        f'-OpenTraceFile={utrace_path}',
        f'-ABSLOG={insights_log_path}',
        "-AutoQuit",
        "-NoUI",
        f'-ExecOnAnalysisCompleteCmd=@={response_file_path}',
        "-log",
    ]
    run_process(command, verbose)
    if not export_csv_path.is_file():
        log_tail = read_text_tail(insights_log_path)
        details = f"Expected export file was not created: {export_csv_path}"
        if log_tail:
            details += f"\nUnrealInsights log tail:\n{log_tail}"
        raise SkillError(details)


def parse_exported_callees(csv_path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"TimerId", "ParentId", "TimerName", "Count", "Inc.Time", "Exc.Time", "NumFrames"}
        if not reader.fieldnames or not required_columns.issubset(set(reader.fieldnames)):
            raise SkillError(f"Unexpected exported CSV schema in {csv_path}")

        for row in reader:
            if not row:
                continue
            parent_id_raw = row["ParentId"]
            parent_id = None if parent_id_raw in ("", str(2**32 - 1)) else int(parent_id_raw)
            rows.append(
                {
                    "timer_id": int(row["TimerId"]),
                    "parent_id": parent_id,
                    "timer_name": row["TimerName"],
                    "count": int(row["Count"]),
                    "inclusive_time": float(row["Inc.Time"]) if row["Inc.Time"] else 0.0,
                    "exclusive_time": float(row["Exc.Time"]) if row["Exc.Time"] else 0.0,
                    "num_frames": int(row["NumFrames"]) if row["NumFrames"] else 0,
                }
            )
    return rows


def enrich_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    enriched_rows: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        enriched_row = dict(row)
        enriched_row["row_index"] = index
        enriched_row["self_time"] = enriched_row["exclusive_time"]
        enriched_rows.append(enriched_row)
    return enriched_rows


def make_row_summary(row: dict[str, object]) -> dict[str, object]:
    return {
        "row_index": row["row_index"],
        "timer_id": row["timer_id"],
        "parent_id": row["parent_id"],
        "timer_name": row["timer_name"],
        "count": row["count"],
        "inclusive_time": row["inclusive_time"],
        "exclusive_time": row["exclusive_time"],
        "self_time": row["self_time"],
        "num_frames": row["num_frames"],
    }


def make_minimal_tree_node(row: dict[str, object]) -> dict[str, object]:
    total_time_ms = round(float(row["inclusive_time"]) * 1000.0, 6)
    self_time_ms = round(float(row["self_time"]) * 1000.0, 6)
    return {
        "name": row["timer_name"],
        "total_time_ms": total_time_ms,
        "self_time_ms": self_time_ms,
        "count": row["count"],
        "children": [],
    }


def sort_row_summaries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        rows,
        key=lambda row: (
            -float(row["inclusive_time"]),
            -float(row["exclusive_time"]),
            -int(row["count"]),
            str(row["timer_name"]),
            int(row["row_index"]),
        ),
    )


def build_children_by_parent_timer(rows: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    children_by_parent: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        parent_id = row["parent_id"]
        if parent_id is None:
            continue
        key = str(parent_id)
        children_by_parent.setdefault(key, []).append(make_row_summary(row))

    for key, children in children_by_parent.items():
        children_by_parent[key] = sort_row_summaries(children)

    return children_by_parent


def build_best_effort_tree(rows: list[dict[str, object]]) -> tuple[dict[str, object] | None, list[dict[str, object]]]:
    root: dict[str, object] | None = None
    stack: list[dict[str, object]] = []
    orphans: list[dict[str, object]] = []

    for row in rows:
        node = make_row_summary(row)
        node["children"] = []

        while stack and stack[-1]["timer_id"] != row["parent_id"]:
            stack.pop()

        if row["parent_id"] is None:
            if root is None:
                root = node
            else:
                orphans.append(node)
            stack = [node]
            continue

        if stack and stack[-1]["timer_id"] == row["parent_id"]:
            stack[-1]["children"].append(node)
            stack.append(node)
        else:
            orphans.append(node)
            stack = [node]

    return root, orphans


def build_minimal_tree(rows: list[dict[str, object]]) -> dict[str, object] | None:
    root: dict[str, object] | None = None
    stack: list[tuple[int, dict[str, object]]] = []

    for row in rows:
        node = make_minimal_tree_node(row)

        while stack and stack[-1][0] != row["parent_id"]:
            stack.pop()

        if row["parent_id"] is None:
            if root is None:
                root = node
            stack = [(int(row["timer_id"]), node)]
            continue

        if stack and stack[-1][0] == row["parent_id"]:
            stack[-1][1]["children"].append(node)
            stack.append((int(row["timer_id"]), node))
        elif root is None:
            root = node
            stack = [(int(row["timer_id"]), node)]

    return root


def build_aggregated_view(rows: list[dict[str, object]]) -> dict[str, object]:
    if not rows:
        return {
            "root_row_index": None,
            "root_timer_id": None,
            "root_timer_name": None,
            "direct_children": [],
            "children_by_parent_timer": {},
            "hotspots": [],
            "best_effort_tree": None,
            "reconstruction_notes": [
                "No rows were exported for the requested timer and time window.",
            ],
        }

    root_row = rows[0]
    children_by_parent_timer = build_children_by_parent_timer(rows)
    direct_children = children_by_parent_timer.get(str(root_row["timer_id"]), [])
    non_root_rows = [row for row in rows if row["parent_id"] is not None]
    hotspots = sort_row_summaries([make_row_summary(row) for row in non_root_rows])[:16]
    best_effort_tree, orphan_nodes = build_best_effort_tree(rows)

    notes = [
        "This is an aggregated callees view exported by Unreal Insights, not a unique invocation tree.",
        "timer_id identifies a timer type, not a unique node instance.",
        "best_effort_tree is reconstructed from export order and parent timer ids; repeated or recursive timer names can still be ambiguous.",
    ]
    if orphan_nodes:
        notes.append(
            f"Tree reconstruction left {len(orphan_nodes)} orphan node(s); inspect raw_rows when exact structure matters."
        )

    return {
        "root_row_index": root_row["row_index"],
        "root_timer_id": root_row["timer_id"],
        "root_timer_name": root_row["timer_name"],
        "direct_children": direct_children,
        "children_by_parent_timer": children_by_parent_timer,
        "hotspots": hotspots,
        "best_effort_tree": best_effort_tree,
        "orphan_nodes": orphan_nodes,
        "reconstruction_notes": notes,
    }


def build_result(
    utrace_path: Path,
    frame: FrameRecord,
    timer: str,
    threads: str,
    frame_type: str,
    rows: list[dict[str, object]],
    insights_exe: Path,
    trace_analyzer_exe: Path,
) -> dict[str, object]:
    enriched_rows = enrich_rows(rows)
    return {
        "frame": frame.index if frame.index >= 0 else None,
        "timer": timer,
        "tree": build_minimal_tree(enriched_rows),
    }


def write_output(result: dict[str, object], output_json: str | None) -> None:
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if output_json:
        path = Path(output_json).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + os.linesep, encoding="utf-8")
    else:
        print(text)


def main() -> int:
    args = parse_args()
    temp_dir_path: Path | None = None

    try:
        utrace_path = Path(args.utrace).expanduser().resolve()
        if not utrace_path.is_file():
            raise SkillError(f".utrace file not found: {utrace_path}")

        configured_insights_exe = args.insights_exe or DEFAULT_UNREAL_INSIGHTS_EXE or None
        configured_trace_analyzer_exe = args.trace_analyzer_exe or DEFAULT_TRACE_ANALYZER_EXE or None
        use_time_window = args.start_time_ms is not None

        insights_exe = find_executable(
            configured_insights_exe,
            (
                r"Engine\Binaries\Win64\UnrealInsights.exe",
                r"Engine\Binaries\Linux\UnrealInsights",
                r"Engine\Binaries\Mac\UnrealInsights.app\Contents\MacOS\UnrealInsights",
            ),
            "UnrealInsights.exe",
        )
        trace_analyzer_exe: Path | None = None
        frames: list[FrameRecord] = []

        if args.list_frames or not use_time_window:
            trace_analyzer_exe = find_executable(
                configured_trace_analyzer_exe,
                (
                    r"Engine\Binaries\Win64\TraceAnalyzer.exe",
                    r"Engine\Binaries\Linux\TraceAnalyzer",
                    r"Engine\Binaries\Mac\TraceAnalyzer.app\Contents\MacOS\TraceAnalyzer",
                ),
                "TraceAnalyzer.exe",
            )
            frames = load_frames(
                trace_analyzer_exe=trace_analyzer_exe,
                utrace_path=utrace_path,
                frame_type=args.frame_type,
                verbose=args.verbose,
            )

        if args.list_frames:
            result = build_frame_listing(
                utrace_path=utrace_path,
                frame_type=args.frame_type,
                frames=frames,
                start=args.list_frames_start,
                count=args.list_frames_count,
            )
            write_output(result, args.output_json)
            return 0

        if not args.timer:
            raise SkillError("--timer is required unless --list-frames is specified.")
        if use_time_window:
            end_time_ms = args.end_time_ms if args.end_time_ms is not None else args.start_time_ms + args.duration_ms
            frame = build_time_window_record(args.start_time_ms, end_time_ms)
        else:
            if args.frame is None:
                raise SkillError("--frame is required unless --start-time-ms or --list-frames is specified.")
            frame = resolve_frame(
                frames=frames,
                frame_index=args.frame,
                frame_type=args.frame_type,
            )

        temp_dir_path = Path(tempfile.mkdtemp(prefix="insights_skill_"))
        if args.verbose:
            print(f"TEMP: {temp_dir_path}", file=sys.stderr)
        export_csv_path = temp_dir_path / "timer_callees.csv"
        insights_log_path = temp_dir_path / "insights.log"
        response_file_path = temp_dir_path / "export.rsp"

        export_timer_callees(
            insights_exe=insights_exe,
            utrace_path=utrace_path,
            export_csv_path=export_csv_path,
            insights_log_path=insights_log_path,
            response_file_path=response_file_path,
            timer=args.timer,
            threads=args.threads,
            frame=frame,
            verbose=args.verbose,
        )
        rows = parse_exported_callees(export_csv_path)
        result = build_result(
            utrace_path=utrace_path,
            frame=frame,
            timer=args.timer,
            threads=args.threads,
            frame_type=args.frame_type,
            rows=rows,
            insights_exe=insights_exe,
            trace_analyzer_exe=trace_analyzer_exe or Path(),
        )
        write_output(result, args.output_json)

        return 0
    except SkillError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    finally:
        if temp_dir_path is not None:
            if args.keep_temp:
                if args.verbose:
                    print(f"KEPT: {temp_dir_path}", file=sys.stderr)
            else:
                shutil.rmtree(temp_dir_path, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
