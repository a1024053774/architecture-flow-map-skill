#!/bin/bash
# Acceptance run for build_map.py against a throwaway fixture repository.
# Run: bash tests/build_map_e2e.sh
#
# Ways the builder can fail, each covered below by a map that must be rejected (exit 1, named error):
#   refs:      path missing, path escapes --root, line past end of file, symbol absent,
#              symbol moved away from its line (stale reference after a refactor), symbol only
#              near the cited line rather than on it
#   evidence:  confirmed without refs or runs, inferred without a basis note, unknown without
#              `needs`, a run without its observed result (a run alone may confirm a claim)
#   graph:     edge to an undefined node, unknown edge kind, undeclared lane,
#              the same id used for a node and a child
#   scenarios: step names an undefined edge, step highlights nothing, scenario with one step,
#              data op that is not create/read/update/delete
#   objects:   transition between states the object does not declare
#   output:    a failed build leaves the previous HTML untouched;
#              `</script>` inside map text cannot close the data block early
#   budget:    an overview over 14 nodes warns but still builds; so does a long edge label
BUILD="python3 $(cd "$(dirname "$0")/.." && pwd)/architecture-flow-map/scripts/build_map.py"
R=$(mktemp -d "${TMPDIR:-/tmp}/flowmap.XXXX"); cd "$R" || exit 1
pass=0; fail=0
ok() { pass=$((pass+1)); echo "PASS $1"; }
no() { fail=$((fail+1)); echo "FAIL $1"; [ -n "$2" ] && echo "$2" | sed 's/^/    /'; }

mkdir -p repo/app
cat > repo/app/server.py <<'EOF'
import queue

jobs = queue.Queue()


def create_order(payload):
    order = {"id": 1, "status": "pending", **payload}
    jobs.put(order)
    return order


def worker():
    order = jobs.get()
    order["status"] = "paid"
EOF
echo "# Shop" > repo/README.md

cat > good.json <<'EOF'
{
  "schema": 1, "title": "Shop", "summary": "One HTTP handler queues orders for a worker.",
  "lanes": [{"id": "entry", "label": "Entry"}, {"id": "core", "label": "Core"}],
  "nodes": [
    {"id": "api", "label": "API", "lane": "entry", "kind": "entry", "role": "Creates orders.",
     "evidence": {"level": "confirmed", "refs": [{"path": "app/server.py", "line": 6, "symbol": "def create_order"}]},
     "children": [{"id": "api.create", "label": "create_order()", "role": "Builds and queues an order.",
       "evidence": {"level": "confirmed", "refs": [{"path": "app/server.py", "line": 6, "symbol": "def create_order"}]}}]},
    {"id": "worker", "label": "Worker", "lane": "core", "kind": "job", "role": "Marks orders paid.",
     "evidence": {"level": "inferred", "note": "Nothing in the repo starts it.", "refs": [{"path": "app/server.py", "line": 12, "symbol": "def worker"}]}},
    {"id": "pay", "label": "Payment provider", "lane": "core", "kind": "external", "role": "Unknown.",
     "evidence": {"level": "unknown", "needs": "Deployment config naming the provider."}}
  ],
  "edges": [
    {"id": "e1", "from": "api.create", "to": "worker", "kind": "async", "label": "jobs.put(order)",
     "evidence": {"level": "confirmed", "refs": [{"path": "app/server.py", "line": 8, "symbol": "jobs.put"}]}}
  ],
  "objects": [
    {"id": "order", "label": "Order", "description": "A purchase.", "createdBy": ["api.create"], "writtenBy": ["worker"],
     "states": ["pending", "paid"], "transitions": [{"from": "pending", "to": "paid", "by": "worker"}],
     "evidence": {"level": "confirmed", "refs": [{"path": "app/server.py", "line": 14, "symbol": "\"paid\""}]}}
  ],
  "scenarios": [
    {"id": "buy", "title": "Place an order", "trigger": "POST", "result": "Order paid",
     "steps": [
       {"title": "Create", "text": "Handler builds the order.", "nodes": ["api.create"], "data": [{"object": "order", "op": "create"}],
        "evidence": {"level": "confirmed", "refs": [{"path": "app/server.py", "line": 7, "symbol": "\"pending\""}]}},
       {"title": "Queue", "text": "Order goes to the worker.", "edges": ["e1"],
        "branches": [{"when": "queue full", "then": "unknown", "evidence": {"level": "unknown", "needs": "Queue size config."}}],
        "evidence": {"level": "confirmed", "refs": [{"path": "app/server.py", "line": 8, "symbol": "jobs.put"}]}}
     ]}
  ],
  "docDrift": [
    {"doc": {"path": "README.md", "line": 1}, "claim": "A shop", "actual": "Only a queue",
     "evidence": {"level": "confirmed", "runs": [{"command": "python -c 'import app.server'", "observed": "imports with no web framework"}]}}
  ],
  "openQuestions": [{"question": "Who starts the worker?", "needs": "Process manager config.", "related": ["worker"]}]
}
EOF

out=$($BUILD --root repo --data good.json --out out/map.html 2>&1); code=$?
if [ $code = 0 ] && grep -q '"title": "Shop"' out/map.html && ! grep -q '__FLOW_MAP_DATA__' out/map.html; then ok "good map builds and embeds its data"
else no "good map builds and embeds its data (exit $code)" "$out"; fi
cp out/map.html before.html

# reject <label> <expected-error-substring> <python statement mutating `m`>
reject() {
  python3 - "$3" <<'EOF' > bad.json
import json, sys
m = json.load(open("good.json"))
exec(sys.argv[1])
print(json.dumps(m))
EOF
  out=$($BUILD --root repo --data bad.json --out out/map.html 2>&1); code=$?
  if [ $code = 1 ] && grep -qF -- "$2" <<<"$out"; then ok "rejects: $1"; else no "rejects: $1 (exit $code)" "$out"; fi
}
N='m["nodes"][0]'; REF="$N[\"evidence\"][\"refs\"][0]"
reject "missing path"            "does not exist"            "$REF['path'] = 'app/gone.py'"
reject "path outside root"       "is outside --root"         "$REF['path'] = '../good.json'; $REF.pop('line'); $REF.pop('symbol')"
reject "line past end of file"   "is outside 1.."            "$REF['line'] = 400"
reject "symbol absent"           "not found in"              "$REF['symbol'] = 'def refund'"
reject "symbol moved from line"  "is not on line 2"          "$REF['line'] = 2"
reject "symbol only near line"   "is not on line 7"          "$REF['line'] = 7"
reject "confirmed without refs"  "needs at least one ref or run" "$N['evidence']['refs'] = []"
reject "run without observed"    "needs \`command\` and \`observed\`" "m['docDrift'][0]['evidence']['runs'][0]['observed'] = ''"
reject "inferred without note"   "needs a \`note\`"          "del m['nodes'][1]['evidence']['note']"
reject "unknown without needs"   "needs \`needs\`"           "del m['nodes'][2]['evidence']['needs']"
reject "edge to undefined node"  "is not a node"             "m['edges'][0]['to'] = 'billing'"
reject "unknown edge kind"       "\`kind\` must be one of"   "m['edges'][0]['kind'] = 'calls'"
reject "undeclared lane"         "is not declared"           "m['nodes'][1]['lane'] = 'storage'"
reject "node and child share id" "duplicate id \`api\`"      "$N['children'][0]['id'] = 'api'"
reject "step names unknown edge" "unknown edge \`e9\`"       "m['scenarios'][0]['steps'][1]['edges'] = ['e9']"
reject "step highlights nothing" "highlights nothing"        "m['scenarios'][0]['steps'][0]['nodes'] = []"
reject "one-step scenario"       "at least two steps"        "m['scenarios'][0]['steps'] = m['scenarios'][0]['steps'][:1]"
reject "bad data op"             "data \`op\` must be"       "m['scenarios'][0]['steps'][0]['data'][0]['op'] = 'write'"
reject "undeclared state"        "is not in \`states\`"      "m['objects'][0]['transitions'][0]['to'] = 'refunded'"

if cmp -s before.html out/map.html; then ok "failed builds left the previous HTML untouched"; else no "failed builds left the previous HTML untouched"; fi

python3 - <<'EOF' > inject.json
import json
m = json.load(open("good.json"))
m["summary"] = "</script><script>alert(1)</script><!--"
print(json.dumps(m))
EOF
$BUILD --root repo --data inject.json --out inject.html >/dev/null 2>&1
python3 - <<'EOF' && ok "map text cannot close the data block" || no "map text cannot close the data block"
import json, re, sys
html = open("inject.html").read()
block = re.search(r'<script id="flow-map-data" type="application/json">(.*?)</script>', html, re.S).group(1)
sys.exit(0 if json.loads(block)["summary"] == "</script><script>alert(1)</script><!--" else 1)
EOF

python3 - <<'EOF' > big.json
import json, copy
m = json.load(open("good.json"))
for i in range(13):
    n = copy.deepcopy(m["nodes"][1]); n["id"] = f"w{i}"; m["nodes"].append(n)
print(json.dumps(m))
EOF
out=$($BUILD --root repo --data big.json --check 2>&1); code=$?
if [ $code = 0 ] && grep -q "WARN  map: 16 overview nodes" <<<"$out"; then ok "over-budget overview warns but builds"; else no "over-budget overview warns but builds (exit $code)" "$out"; fi

python3 - <<'EOF' > long.json
import json
m = json.load(open("good.json"))
m["edges"][0]["label"] = "把新建的订单放进内存队列等待后台工作线程处理"
print(json.dumps(m, ensure_ascii=False))
EOF
out=$($BUILD --root repo --data long.json --check 2>&1); code=$?
if [ $code = 0 ] && grep -q "WARN  edge e1: label is wider" <<<"$out"; then ok "long edge label warns but builds"; else no "long edge label warns but builds (exit $code)" "$out"; fi

echo "$pass passed, $fail failed  (fixture: $R)"
[ $fail = 0 ]
