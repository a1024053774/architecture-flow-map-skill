#!/usr/bin/env python3
"""Validate an architecture flow map against the repository it describes, then render it.

    python3 build_map.py --root <repo> --data <map.json> --out <flow-map.html>
    python3 build_map.py --root <repo> --data <map.json> --check

Every code reference must resolve: the path exists under --root, the line is inside the file, and
a given symbol appears on exactly that line (or anywhere in the file when no line is given). Every
node, edge, object, step, and drift entry carries an evidence level; scenario steps may only
highlight nodes and edges the map defines. On any error nothing is written and the exit code is 1,
so a previous good HTML is never replaced by a broken one. Warnings (readability budgets, long
labels) do not fail the build.

The format is documented in ../references/map-schema.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LEVELS = ("confirmed", "inferred", "unknown")
EDGE_KINDS = ("sync", "async", "data")
NODE_KINDS = ("actor", "entry", "module", "store", "external", "job", "config", "doc")
DATA_OPS = ("create", "read", "update", "delete")
OVERVIEW_BUDGET = 14
CHILD_BUDGET = 12
LABEL_BUDGET = 12  # edge label width in CJK characters (Latin counts ~0.55); longer text goes in `detail`
TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "viewer.html"
PLACEHOLDER = "__FLOW_MAP_DATA__"


class Checker:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self._lines: dict[Path, list[str]] = {}
        self.levels: dict[str, int] = {}

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def file_lines(self, path: Path) -> list[str]:
        if path not in self._lines:
            self._lines[path] = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return self._lines[path]

    def ref(self, where: str, ref: object) -> None:
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not ref["path"]:
            self.err(where, "a ref needs a non-empty `path`")
            return
        target = (self.root / ref["path"]).resolve()
        if self.root != target and self.root not in target.parents:
            self.err(where, f"`{ref['path']}` is outside --root")
            return
        if not target.exists():
            self.err(where, f"`{ref['path']}` does not exist")
            return
        line, symbol = ref.get("line"), ref.get("symbol")
        if target.is_dir():
            if line is not None or symbol is not None:
                self.err(where, f"`{ref['path']}` is a directory; drop `line`/`symbol`")
            return
        lines = self.file_lines(target)
        if line is not None and (not isinstance(line, int) or not 1 <= line <= len(lines)):
            self.err(where, f"`{ref['path']}` line {line} is outside 1..{len(lines)}")
            return
        if symbol is None:
            return
        if line is not None and symbol in lines[line - 1]:
            return
        hits = [i + 1 for i, text in enumerate(lines) if symbol in text]
        if not hits:
            self.err(where, f"symbol `{symbol}` not found in `{ref['path']}`")
        elif line is not None:
            self.err(where, f"symbol `{symbol}` is not on line {line} of `{ref['path']}`; found on {hits[:5]}")

    def evidence(self, where: str, ev: object) -> None:
        if not isinstance(ev, dict) or ev.get("level") not in LEVELS:
            self.err(where, f"`evidence.level` must be one of {', '.join(LEVELS)}")
            return
        refs, runs = ev.get("refs") or [], ev.get("runs") or []
        if not isinstance(refs, list) or not isinstance(runs, list):
            self.err(where, "`evidence.refs` and `evidence.runs` must be lists")
            return
        level = ev["level"]
        self.levels[level] = self.levels.get(level, 0) + 1
        if level in ("confirmed", "inferred") and not refs and not runs:
            self.err(where, f"{level} evidence needs at least one ref or run")
        for i, run in enumerate(runs):
            if not isinstance(run, dict) or not run.get("command") or not run.get("observed"):
                self.err(f"{where} run[{i}]", "a run needs `command` and `observed`")
        if level == "inferred" and not ev.get("note"):
            self.err(where, "inferred evidence needs a `note` stating the basis of the inference")
        if level == "unknown" and not ev.get("needs"):
            self.err(where, "unknown evidence needs `needs`: what evidence would settle it")
        for i, ref in enumerate(refs):
            self.ref(f"{where} ref[{i}]", ref)


def width(text: str) -> float:
    return sum(0.55 if ord(ch) < 0x100 else 1 for ch in text)


def need(c: Checker, obj: dict, where: str, *fields: str) -> bool:
    missing = [f for f in fields if not obj.get(f)]
    for f in missing:
        c.err(where, f"missing `{f}`")
    return not missing


def unique(c: Checker, items: list[dict], where: str, seen: set[str]) -> None:
    for item in items:
        ident = item.get("id")
        if not isinstance(ident, str) or not ident:
            c.err(where, "every entry needs a string `id`")
        elif ident in seen:
            c.err(where, f"duplicate id `{ident}`")
        else:
            seen.add(ident)


def check(data: dict, c: Checker) -> None:
    if data.get("schema") != 1:
        c.err("map", "`schema` must be 1")
    if not need(c, data, "map", "title", "summary", "lanes", "nodes", "edges", "scenarios"):
        return

    lanes = {lane.get("id") for lane in data["lanes"] if isinstance(lane, dict)}
    nodes: dict[str, dict] = {}
    seen: set[str] = set()
    unique(c, data["nodes"], "nodes", seen)
    for node in data["nodes"]:
        where = f"node {node.get('id')}"
        need(c, node, where, "label", "role")
        if node.get("lane") not in lanes:
            c.err(where, f"lane `{node.get('lane')}` is not declared in `lanes`")
        if node.get("kind") not in NODE_KINDS:
            c.err(where, f"`kind` must be one of {', '.join(NODE_KINDS)}")
        c.evidence(where, node.get("evidence"))
        nodes[node.get("id")] = node
        children = node.get("children") or []
        unique(c, children, f"{where} children", seen)
        if len(children) > CHILD_BUDGET:
            c.warnings.append(f"{where}: {len(children)} children (budget {CHILD_BUDGET}); keep only what a scenario or object needs")
        for child in children:
            cwhere = f"node {child.get('id')} (in {node.get('id')})"
            need(c, child, cwhere, "label", "role")
            c.evidence(cwhere, child.get("evidence"))
            nodes[child.get("id")] = child
    if len(data["nodes"]) > OVERVIEW_BUDGET:
        c.warnings.append(f"map: {len(data['nodes'])} overview nodes (budget {OVERVIEW_BUDGET}); move detail into children")

    edges: set[str] = set()
    unique(c, data["edges"], "edges", edges)
    for edge in data["edges"]:
        where = f"edge {edge.get('id')}"
        need(c, edge, where, "label")
        for end in ("from", "to"):
            if edge.get(end) not in nodes:
                c.err(where, f"`{end}` `{edge.get(end)}` is not a node")
        if edge.get("kind") not in EDGE_KINDS:
            c.err(where, f"`kind` must be one of {', '.join(EDGE_KINDS)}")
        c.evidence(where, edge.get("evidence"))
        if width(edge.get("label") or "") > LABEL_BUDGET:
            c.warnings.append(f"{where}: label is wider than {LABEL_BUDGET} CJK characters and will crowd the canvas; "
                              "keep a few words and move the rest to `detail`")

    objects: dict[str, dict] = {}
    obj_ids: set[str] = set()
    unique(c, data.get("objects") or [], "objects", obj_ids)
    for obj in data.get("objects") or []:
        where = f"object {obj.get('id')}"
        need(c, obj, where, "label", "description")
        objects[obj.get("id")] = obj
        for field in ("createdBy", "readBy", "writtenBy"):
            for ref in obj.get(field) or []:
                if ref not in nodes:
                    c.err(where, f"`{field}` names unknown node `{ref}`")
        states = obj.get("states") or []
        for t in obj.get("transitions") or []:
            for end in ("from", "to"):
                if t.get(end) not in states:
                    c.err(where, f"transition {end} `{t.get(end)}` is not in `states`")
        c.evidence(where, obj.get("evidence"))
    for node_id, node in nodes.items():
        for ref in node.get("objects") or []:
            if ref not in objects:
                c.err(f"node {node_id}", f"`objects` names unknown object `{ref}`")

    unique(c, data["scenarios"], "scenarios", set())
    for sc in data["scenarios"]:
        swhere = f"scenario {sc.get('id')}"
        need(c, sc, swhere, "title", "trigger", "result")
        steps = sc.get("steps") or []
        if len(steps) < 2:
            c.err(swhere, "needs at least two steps, from trigger to result")
        for i, step in enumerate(steps, 1):
            where = f"{swhere} step {i}"
            need(c, step, where, "title", "text")
            if not step.get("nodes") and not step.get("edges"):
                c.err(where, "highlights nothing; name its `nodes` or `edges`")
            for ref in step.get("nodes") or []:
                if ref not in nodes:
                    c.err(where, f"unknown node `{ref}`")
            for ref in step.get("edges") or []:
                if ref not in edges:
                    c.err(where, f"unknown edge `{ref}`")
            for op in step.get("data") or []:
                if op.get("object") not in objects:
                    c.err(where, f"data op on unknown object `{op.get('object')}`")
                if op.get("op") not in DATA_OPS:
                    c.err(where, f"data `op` must be one of {', '.join(DATA_OPS)}")
            for j, branch in enumerate(step.get("branches") or [], 1):
                bwhere = f"{where} branch {j}"
                need(c, branch, bwhere, "when", "then")
                c.evidence(bwhere, branch.get("evidence"))
            c.evidence(where, step.get("evidence"))

    for i, drift in enumerate(data.get("docDrift") or [], 1):
        where = f"docDrift {i}"
        need(c, drift, where, "doc", "claim", "actual")
        c.ref(f"{where} doc", drift.get("doc"))
        c.evidence(where, drift.get("evidence"))
    for i, q in enumerate(data.get("openQuestions") or [], 1):
        need(c, q, f"openQuestion {i}", "question", "needs")
        for ref in q.get("related") or []:
            if ref not in nodes and ref not in edges and ref not in objects:
                c.err(f"openQuestion {i}", f"`related` names unknown id `{ref}`")


def render(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, indent=1)
    # Keep the payload inert inside <script type="application/json">: `\/` is a valid JSON escape.
    payload = payload.replace("</", "<\\/").replace("<!--", "<\\u0021--")
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(PLACEHOLDER) != 1:
        raise SystemExit(f"{TEMPLATE}: expected exactly one {PLACEHOLDER}")
    return template.replace(PLACEHOLDER, payload)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, type=Path, help="repository the map describes")
    ap.add_argument("--data", required=True, type=Path, help="map.json")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--out", type=Path, help="HTML file to write")
    group.add_argument("--check", action="store_true", help="validate only")
    args = ap.parse_args()

    try:
        data = json.loads(args.data.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR {args.data}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print(f"ERROR {args.data}: top level must be an object", file=sys.stderr)
        return 1

    c = Checker(args.root)
    check(data, c)
    for w in c.warnings:
        print(f"WARN  {w}", file=sys.stderr)
    for e in c.errors:
        print(f"ERROR {e}", file=sys.stderr)
    if c.errors:
        print(f"{len(c.errors)} error(s); nothing written", file=sys.stderr)
        return 1

    counts = (f"{len(data['nodes'])} overview nodes, {len(data['edges'])} edges, "
              f"{len(data.get('objects') or [])} objects, {len(data['scenarios'])} scenarios; evidence "
              + " / ".join(f"{c.levels.get(level, 0)} {level}" for level in LEVELS))
    if args.check:
        print(f"OK {counts}")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_name(args.out.name + ".tmp")
    tmp.write_text(render(data), encoding="utf-8")
    tmp.replace(args.out)
    print(f"OK {counts} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
