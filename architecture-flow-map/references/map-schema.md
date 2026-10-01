# map.json format

One JSON object. `build_map.py` validates it and embeds it in `assets/viewer.html`. A complete worked example is `examples/project-map/map.json` in the Skill's repository; a minimal one is the fixture in `tests/build_map_e2e.sh`.

## Top level

| Field | Required | Meaning |
| --- | --- | --- |
| `schema` | yes | Always `1`. |
| `title` | yes | Page title, for example `<project> 运行地图`. |
| `summary` | yes | How the project runs as a whole, in a few sentences. Shown on the home panel. |
| `locale` | no | `zh-CN` (default) or `en`. Sets the viewer's UI language; map text is shown as written. |
| `generatedAt`, `commit` | no | When and at which commit the map was traced. Shown in the header. |
| `lanes` | yes | Ordered layers: `[{id, label}]`. Every node names one. |
| `nodes` | yes | Overview nodes (below). |
| `edges` | yes | Relationships (below). |
| `objects` | no | Business objects (below). |
| `scenarios` | yes | Step-by-step flows (below). |
| `docDrift` | no | Places where docs and code disagree (below). |
| `openQuestions` | no | `[{question, needs, related?}]`; `related` lists node, edge, or object ids. |

## Evidence

Every node, child, edge, object, step, branch, and drift entry has `evidence`:

```json
{ "level": "confirmed", "refs": [ { "path": "src/orders/api.py", "line": 42, "symbol": "def create_order" } ] }
{ "level": "inferred",  "refs": [ ... ], "note": "why this follows from the refs" }
{ "level": "unknown",   "needs": "the evidence that would settle it" }
```

A ref's `path` is relative to `--root` and must exist. `line` is optional and must be inside the file. `symbol` is optional; when given it must occur in the file, and when `line` is also given it must occur within three lines of it. A directory ref takes neither `line` nor `symbol`.

## Nodes

```json
{
  "id": "orders", "label": "订单服务", "lane": "domain", "kind": "module",
  "role": "what it is responsible for, one or two sentences",
  "objects": ["order"],
  "evidence": { ... },
  "children": [ { "id": "orders.create", "label": "create_order()", "role": "...", "evidence": { ... } } ]
}
```

- `kind`: `actor`, `entry`, `module`, `store`, `external`, `job`, `config`, or `doc`.
- `children` take `id`, `label`, `role`, `evidence` (and optionally `objects`). Ids are unique across nodes and children.
- Shown only when the module is expanded. In the overview, any edge touching a child is drawn to its parent, and edges with the same parents and kind merge into one line labelled "… 等 N 条".

## Edges

```json
{ "id": "e-create-queue", "from": "orders.create", "to": "worker", "kind": "async", "label": "jobs.put(order)", "detail": "optional longer note", "evidence": { ... } }
```

- `from` and `to` may be nodes or children.
- `kind`: `sync` (caller waits; arrow caller to callee), `async` (event, queue, scheduled job, callback; arrow producer to consumer), `data` (arrow in the direction data moves: store to reader, writer to store).
- Edges whose level is not `confirmed` get a `？` prefix on the canvas and appear in the viewer's "unconfirmed and inferred" list.

## Objects

```json
{
  "id": "order", "label": "订单", "description": "...", "storedIn": "orders table",
  "createdBy": ["orders.create"], "readBy": ["worker"], "writtenBy": ["worker"],
  "states": ["pending", "paid", "failed"],
  "transitions": [ { "from": "pending", "to": "paid", "by": "worker", "note": "after the charge succeeds" } ],
  "relations": [ { "to": "customer", "label": "belongs to" } ],
  "evidence": { ... }
}
```

`createdBy`, `readBy`, and `writtenBy` name nodes or children. Transition endpoints must be listed in `states`. A state computed on every run rather than stored is still a state; say so in `description`.

## Scenarios

```json
{
  "id": "checkout", "title": "用户下单", "why": "why this flow matters, one line",
  "trigger": "what starts it", "result": "what the user or system ends up with",
  "steps": [
    {
      "title": "short name", "text": "what happens in this hop, in the reader's language",
      "nodes": ["orders.create"], "edges": ["e-create-queue"],
      "data": [ { "object": "order", "op": "create" } ],
      "branches": [ { "when": "payment declined", "then": "order marked failed, no retry", "evidence": { ... } } ],
      "evidence": { ... }
    }
  ]
}
```

- At least two steps, from trigger to result.
- A step highlights its `nodes`, its `edges`, and both ends of each edge. Name a child when the step happens inside a module; the overview then highlights the parent and offers to expand it.
- `data[].op`: `create`, `read`, `update`, or `delete`.

## Doc drift

```json
{ "doc": { "path": "README.md", "line": 30, "symbol": "retries" }, "claim": "what the doc says", "actual": "what the code does", "evidence": { ... } }
```

`doc` is a ref to the documentation; `evidence` points at the implementation.
