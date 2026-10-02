# Build, check, and report

Steps 6-8 of the workflow in [../SKILL.md](../SKILL.md), and updating an existing map.

## 6. Build until it passes

Run the build command from step 6 in [../SKILL.md](../SKILL.md#workflow).

Every `ERROR` names the entry and the problem; for a symbol that is not on its line it also lists the lines where the symbol does occur. Fix it by re-reading the code and correcting the ref or the claim; never edit the generated HTML. A failed build writes nothing, so an earlier good HTML survives. `WARN` lines flag readability budgets (more than 14 overview nodes, more than 12 children, edge labels that are too long); fix them rather than ignoring them. Use `--check` to validate without writing. The `OK` line counts evidence levels; check that the split is honest.

## 7. Check the result in a browser

Serve the output folder over local HTTP (`python3 -m http.server --directory <out>`); some embedded browsers render `file://` pages as static snapshots that ignore clicks. Open it at 1280x800 and run this in the page, with whatever browser tool you have (Playwright `page.evaluate`, a browser pane's JavaScript tool, DevTools):

```js
await flowMapSelfCheck()
```

It drives the real controls and compares what the page shows against `map.json`: every step of every scenario (stepper, title, highlighted nodes and edges), every node's details, every module's expansion and breadcrumb, zoom and Reset view. It returns `{ok, failures, metrics}`; `metrics` gives the overview's scale, the rendered text size, the number of edge labels that overlap a label or node, and the evidence counts. Fix every failure. For overlaps, shorten the labels involved or drop edges that add nothing at overview level; if the overview text is under 11px, move nodes into `children`.

Then take one screenshot of the overview and one of a scenario step and look at them: the self-check proves the page matches the data, not that the picture explains the system.

Without a browser tool, say that the interaction checks were not run.

## 8. Report

In the user's language, briefly:

1. Any finding with an `impact`, first.
2. How the project runs as a whole, in a few sentences.
3. The 3-5 relationships most worth understanding, each pointing at a node, edge, or scenario.
4. What remains unconfirmed and the evidence each item needs, and any doc drift.
5. How to open the map and how to rebuild it after code changes.
6. Status: `PASS` only when the build passed and `flowMapSelfCheck()` returned `ok: true`; otherwise `INCOMPLETE` with what was skipped or still failing.

## Updating an existing map

Rerun the build after the code changes. References that moved or vanished fail with the entry and the line where the symbol now appears; fix them, re-trace any scenario whose code path changed, and update `commit` and `generatedAt`. `map.json` is the source of truth; the HTML is always regenerated.
