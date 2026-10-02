# Tracing the code

Steps 1-4 of the workflow in [../SKILL.md](../SKILL.md). Read each step when you reach it; write `map.json` as you go ([map-schema.md](map-schema.md)).

## 1. Survey, bounded

Read in this order and stop widening once each item below has an answer or is marked unknown:

1. README, architecture docs, `AGENTS.md`/`CLAUDE.md`: what the project claims to be. Treat these as claims to verify.
2. Manifests and run config: `package.json` scripts and `bin`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `Dockerfile`, compose files, `Procfile`, serverless config, CI workflows. They name the real entry points and processes.
3. Entry points: `main`, CLI parsers, HTTP routers, message consumers, scheduled jobs (cron, CI `schedule`, task queues), webhooks and callbacks.
4. Storage: schemas, migrations, ORM models, files the code reads or writes, caches.
5. External services: HTTP/SDK clients and the env vars or config that point at them.

Search before you read whole files, for example `rg -n "def main|if __name__|createServer|app\.(get|post)|router\.|@app\.|cron|schedule|queue|subscribe|publish|emit\(|webhook"` adjusted to the stack.

## 2. Choose the overview

- Overview nodes are actors, entry points, top-level modules, data stores, background jobs, and external services: 6-14 of them. Group files by responsibility; one file is not one node.
- `lanes` order the layers (for example actor, entry, domain, storage, external). The viewer lays them out as rows or columns, whichever fits the screen.
- Add `children` to a module only for the functions or classes that a scenario step or a business object needs, at most 12. The viewer shows them when the module is expanded.
- Business objects are the nouns the system creates and changes (order, ticket, session, job). For each: where it is stored, who creates, reads, and writes it, its states, and the transitions between them with what causes each.

## 3. Pick 3-5 scenarios

Start with the user's. Then prefer the operations that run most often, cross the most modules, write data, or involve asynchronous work or external services. Include at least one failure path when the code has real error handling.

## 4. Trace each scenario through the code

Read along the actual call path. Each step is one hop the reader can follow on the map, and its `text` answers, as far as the hop does:

- what triggered it, and which module receives it;
- which modules or external services it calls, and whether synchronously or not;
- which objects it creates, reads, updates, or deletes (`data`);
- whether an event, queue, job, or callback carries the work on;
- how the result returns or is shown;
- the failure handling, retries, and branches the code actually has (`branches`, each with evidence).

Edge kinds carry direction and meaning:

- `sync`: a call that waits for its result. Arrow from caller to callee.
- `async`: an event, queue message, scheduled job, or callback; the sender does not wait. Arrow from producer to consumer.
- `data`: data moving between code and a store or file. Arrow in the direction data moves: store to reader for a read, writer to store for a write.

Give every edge a short label saying what passes or why (`POST /orders`, `jobs.put(order)`, `读取 MAP.md`), not just "calls". Keep it to about ten Chinese characters or twenty Latin ones and put the full sentence in `detail`, which the viewer shows when the edge is clicked; long labels collide on the canvas.
