# Runbook: run glazed's Agent-Core on addons (Phase 3, G7)

Status: PREPARED, NOT DEPLOYED. Every step below needs the owner's approval before it runs on the
live host.

## What changes

| | Before | After |
|---|---|---|
| Agent-Core source | `../Agent-Core` checked out on `vertical/glazed` (glazed patched into Core) | an Agent-Core checkout of `feat/glazed-addons` (`AGENT_CORE_SRC`, default `../Agent-Core`) |
| Build context | `Agent-Core/Core` | `infra/core` + additional context `agent_core` = the Agent-Core ROOT (`Core/` and `addons/`) |
| Glazed tools, profiles, policy, channel | code and files patched into Core | addons `http_tool_bridge`, `glazed_tools`, `plain_language`, `glazed_vertical` |
| Backend URL for the tools | `GLAZED_BACKEND_URL` | `AGENT_CORE_ADDON__GLAZED_TOOLS__BASE_URL=http://backend:8080` |
| `ask_peer` allow for the orchestrator | in Core's `policy/rules.yaml` | `infra/core/policy/glazed_deployment.yaml`, copied into Core's policy directory |
| Startup order | core after db | core and peer worker after db AND a healthy backend (Core reads `/openapi.json` once at startup) |

Files: `infra/core/Dockerfile`, `infra/core/policy/glazed_deployment.yaml`, `infra/docker-compose.yml`
(`x-core`, backend healthcheck, `depends_on`), `.env.example` (`AGENT_CORE_SRC`).

The image sets, and compose repeats:

```
AGENT_CORE_ADDONS=http_tool_bridge,glazed_tools,plain_language,glazed_vertical
AGENT_CORE_ADDONS_DIR=/app/addons
AGENT_CORE_ADDONS_CONFIG=/app/addons/glazed_vertical/addons_config.yaml
AGENT_CORE_POLICY_DIR=/app/Core/policy
AGENT_CORE_ADDON__GLAZED_TOOLS__BASE_URL=http://backend:8080
```

The effective policy is the same set of rules: the 42 rule ids of `vertical/glazed` (Core's 8, the
glazed deployment's 1, `glazed_tools`' 33), same ids and text.

## What was checked before deploy (no live service touched)

- `docker compose -f infra/docker-compose.yml config`: valid; core and peer worker resolve the build
  above, the env above, and `depends_on` backend `service_healthy`.
- A local build of the image under a throwaway tag (removed after): `build_container()` ran inside it
  with no network, the OpenAPI read from the committed snapshot: the 4 addons loaded, the 9 glazed
  profiles, the 8 toolsets, 33 addon rules plus 9 file rules (the deployment rule among them).
- Agent-Core suites on `feat/glazed-addons`, glazed backend suite on this branch.

Not checked: a start against the live database and backend (needs this deploy).

## Risks to know before approving

1. Database migrations. The new Core runs 18 schema migrations that `vertical/glazed` does not have
   (peer, task graph, tool journal, turn events, addons...). They run forward at the first start. The
   old image is NOT guaranteed to run on the migrated schema, so rollback restores the dump (step 3).
2. In-flight turns. A durable turn started by the old Core and resumed by the new one crosses code
   versions. Deploy in a quiet window with no turn running.
3. The backend must serve the marked operations. The backend image from this branch carries the
   `x-agent-*` marks; with an older backend the tools fail the startup contract check and Core stops
   (loud, nothing half-works).
4. A wrong `AGENT_CORE_SRC` (a checkout on `vertical/glazed`) fails the build at `COPY addons` (it
   has no `addons/`), so the old code cannot be shipped by mistake under the new compose file.

## Deploy (on the live host, from the glazed-copilot deploy checkout)

1. Put the deploy checkout on the branch that holds this change (`feat/agent-tool-marks` or its merge),
   and prepare the Agent-Core source WITHOUT moving the existing `vertical/glazed` checkout:

   ```
   git -C ../Agent-Core fetch origin
   git -C ../Agent-Core worktree add ../Agent-Core-deploy origin/feat/glazed-addons --detach
   ```

   In `.env` (never commit it): `AGENT_CORE_SRC=<absolute path>/Agent-Core-deploy`.
2. Keep the current images for rollback:

   ```
   for s in core core-peer-worker backend; do
     docker tag glazed-copilot-$s:latest glazed-copilot-$s:pre-g7
   done
   ```
3. Dump the Agent-Core databases (`agent_core` and the DBOS database; list them with
   `docker exec glazed-db psql -U postgres -Atc "select datname from pg_database"`):

   ```
   docker exec glazed-db pg_dump -U postgres -Fc agent_core > agent_core-pre-g7.dump
   docker exec glazed-db pg_dump -U postgres -Fc <dbos database> > dbos-pre-g7.dump
   ```
4. Check the configuration: `docker compose -f infra/docker-compose.yml --env-file .env config -q`.
5. In a quiet window, build and start the three services:

   ```
   make up SERVICES="backend core core-peer-worker"
   ```
6. Verify:

   ```
   docker compose -f infra/docker-compose.yml --env-file .env ps        # all healthy
   curl -s localhost:8100/openapi.json | grep -c '"x-agent-tool"'        # the marked operations
   docker exec glazed-core python -m agent_core addons list             # the 4 addons, installed
   docker logs glazed-core 2>&1 | tail -50                              # no startup error
   ```

   Then one manager turn in the copilot that asks a specialist (the orchestrator's `ask_peer` must be
   allowed by `glazed-orchestrator-asks-specialists`) and one that proposes an action (a pending
   proposal appears in the backend).

## Rollback

1. Stop the new Core: `docker compose -f infra/docker-compose.yml --env-file .env stop core core-peer-worker`.
2. Restore the dumps of deploy step 3 into recreated databases. The schema was migrated forward,
   and `pg_restore --clean` only drops objects the dump contains, so tables and columns added by
   the new migrations would survive it. Drop and recreate each database instead (nothing else may
   be connected; the core services are stopped in step 1):

   ```
   for db in agent_core "<dbos database>"; do
     docker exec glazed-db dropdb -U postgres --if-exists --force "$db"
     docker exec glazed-db createdb -U postgres "$db"
   done
   docker exec -i glazed-db pg_restore -U postgres -d agent_core < agent_core-pre-g7.dump
   docker exec -i glazed-db pg_restore -U postgres -d <dbos database> < dbos-pre-g7.dump
   ```

   Check the restore: `docker exec glazed-db psql -U postgres -d agent_core -c '\dt'` lists no
   table the pre-G7 schema did not have (for example `addons`, `addon_migrations`).
3. Put the deploy checkout back on the revision before this change (its compose file builds Core from
   `../Agent-Core/Core` with `GLAZED_BACKEND_URL`), restore the old images and start them unbuilt:

   ```
   for s in core core-peer-worker backend; do
     docker tag glazed-copilot-$s:pre-g7 glazed-copilot-$s:latest
   done
   docker compose -f infra/docker-compose.yml --env-file .env up -d --no-build backend core core-peer-worker
   ```
4. Remove `AGENT_CORE_SRC` from `.env` and, when no longer needed, the `../Agent-Core-deploy` worktree.

## Phase 5: switch Agent-Core-deploy to `feat/fast-comms` (P5)

What changes: the Core image is built from Agent-Core `feat/fast-comms` instead of `feat/glazed-addons` (deployed
today: `7a33df4`). It adds the System One turn router (Jev through the Typesafe API, addon `system_one_router`), the
ten layer-B intent plans and the orchestrator's routing opt-in, plus Core's SSE feed which the backend now follows
for first-text latency (`GLAZED_CORE_STREAM`, on by default; `false` = polling only, the old behaviour).

- **Migrations** `0045` (`audit_turn_routes`), `0046` (route reason and token usage) and `0047`
  (`audit_turn_intents`) are additive and idempotent; they run at the first start and the old build ignores them.
- **Drain: YES.** The pinned DBOS application version changes from `agent-core-turns.11` (`7a33df4`) to
  `agent-core-turns.12` (the route step runs for every person turn). A turn or peer callee still suspended under
  `.11` (an open approval, an unanswered peer ask) is never recovered by `.12`. Before the deploy, stop new turns
  and run against the OLD core until it reports 0:

  ```
  docker exec glazed-core python -m agent_core stranded-turns
  ```

  If something cannot be drained, cancel it after the deploy (Agent-Core `docs/OPERATIONS.md`, "Cancel what is
  left") and tell the manager to ask again.
- **Routing is ON** after this deploy: `AGENT_CORE_TURN_ROUTING` defaults to `true` in the compose file. A confident
  System One answer sends the manager's turn to one specialist (layer A) or runs one of the ten read-only intent
  plans (layer B); anything else (below the 0.5 threshold, a timeout, no `JEV_API_KEY`) runs the orchestrator as
  before. `JEV_API_KEY` is passed from `.env` into the core containers (never printed, never in the compose file).
- **Who a routed turn runs as** (Agent-Core D98): the specialist's PEER identity (`peer-agent`, channel `peer`,
  role `peer`), on behalf of the manager, exactly as when the orchestrator asks that specialist with `ask_peer`.
  So the glazed policy is unchanged: the specialists' reads stay allowed only to `peer` and `glazed-service`, the
  manager identity still reads nothing directly, and a route lands only where the orchestrator's own `ask_peer`
  could go (its peers allowlist plus `glazed-orchestrator-asks-specialists` in `infra/core/policy/`). The reply is
  still delivered to the manager. Migration `0048` (additive) records both identities: `audit_tool_calls.caller` is
  `peer-agent` and `on_behalf_of` the manager; `audit_turn_routes` and `audit_turn_intents` carry `actor` and
  `on_behalf_of`. A refused delegation runs the orchestrator, with the reason in `audit_turn_routes.fallback_reason`
  (`peer_refused:<reason>`, `ask_peer_not_allowed:<effect>`).
- **Turn routing off**: `AGENT_CORE_TURN_ROUTING=false` in `.env`, then recreate `core` and `core-peer-worker`
  (`make up SERVICES="core core-peer-worker"`). No drain is needed to switch it either way: the route step stays in
  every turn and simply passes. The DRAIN above is still required for this deploy itself (`.11` -> `.12`).
- **Streams are capped**: the backend keeps at most `GLAZED_CORE_MAX_STREAMS` (default 16) SSE streams open; a turn
  past the cap is polled as before, so streams never take the connections sending and polling need. A partial reply
  is shown only when the final reply's quality guard would keep it.
- **Reply streaming (P11)**: `AGENT_CORE_STREAM_REPLIES` defaults to `true` in the compose file, so the Core puts each
  manager turn's reply on the SSE feed as it is written (routed turns and intent plans included; peer turns never).
  Without it the feed carries only progress and `first_text` stays empty. When an intent plan's compose is cut and
  the turn falls back, the Core takes the draft back (one empty chunk) and the manager's partial reply is cleared.
  Off: `AGENT_CORE_STREAM_REPLIES=false` in `.env`, recreate `core` and `core-peer-worker`; no drain either way.

What the router did, and as whom (Agent-Core `docs/OPERATIONS.md` has more):

```
docker exec glazed-db psql -U postgres -d agent_core -c "SELECT turn_id, profile_id, decision, label, confidence, fallback_reason, actor, on_behalf_of FROM audit_turn_routes ORDER BY id DESC LIMIT 20;"
```

Deploy, with the backups and checks of the sections above (tag images `:pre-p5`, dump both Agent-Core databases):

```
git -C ../Agent-Core fetch origin
git -C ../Agent-Core-deploy checkout --detach origin/feat/fast-comms
docker compose -f infra/docker-compose.yml --env-file .env config -q
make up SERVICES="backend core core-peer-worker"
docker exec glazed-core python -m agent_core addons list    # 5 addons, system_one_router among them
docker exec glazed-core python -m agent_core stranded-turns # exit 0
```

Rollback: `git -C ../Agent-Core-deploy checkout --detach 7a33df4`, restore the `:pre-p5` images and the dumps as
in "Rollback" above (the `.11` build cannot recover turns started under `.12`: drain again or cancel them).

## Phase 5: the fast path (P12, Agent-Core S10)

"System One decides, code executes, the model only writes", behind one switch, `AGENT_CORE_FAST_PATH`:

| `.env` value | What the manager gets |
|---|---|
| `shadow` (compose default) | exactly today's behaviour; each turn's `audit_turn_routes` row records what the fast path WOULD have done |
| `on` | a question about two or three frequent topics ("¿Cómo voy hoy y qué tengo que pedir?") runs the plans of every topic in parallel and one short reply written by the orchestrator; a request to do something, a follow-up that depends on the conversation or a complex question runs the orchestrator as today |
| `off` | Jev is asked only the route question, as before P12 |

Switching: set the value in `.env`, `make up SERVICES="core core-peer-worker"`. No drain either way (the pinned
workflow version stays `.12`). Needs Agent-Core `feat/fast-comms` at the P12 commits or later and this backend
(it sends the case date as `X-Data-Version`). Migration `0049` is additive.

Compare shadow before turning it on:

```
docker exec glazed-db psql -U postgres -d agent_core -c "SELECT fast_path, count(*) FROM audit_turn_routes WHERE fast_path_mode = 'shadow' GROUP BY 1 ORDER BY 2 DESC;"
docker exec glazed-db psql -U postgres -d agent_core -c "SELECT turn_id, fast_path, fast_path_intents, assessment FROM audit_turn_routes WHERE fast_path_mode IS NOT NULL ORDER BY id DESC LIMIT 20;"
```

With `on`, each composite member is an `audit_turn_intents` row (`reply_mode = 'composite'`, or `'cache'` from the
reply cache) and its reads are `audit_tool_calls` rows of `peer-agent` on behalf of the manager; a composite that
fails (`planned` = `fallback:<reason>`) runs the orchestrator. Knobs: `AGENT_CORE_FAST_PATH_INTENT_THRESHOLD` (0.7
here), `AGENT_CORE_FAST_PATH_ROUTE_THRESHOLD` (0.7 default: a Jev route choice of an intent at or above it counts
that intent as detected), `AGENT_CORE_FAST_PATH_CACHE_SECONDS` (0 = off; a remembered reply is keyed by case, case
date, the caller and the exact question). The stress battery's `garbled` flag counts glued words, stray English and
markdown debris per turn: run it in shadow and in on with `--repeat` and compare per path (docs/stress-battery.md).

P13 (after the P12 shadow/on battery): Jev now also counts how many separate things a message asks for, and a
message asking for more than the topics it detected runs the orchestrator (`fast_path = 'pass:uncovered'`) instead of
a composite that would call the missing part "no disponible". day_summary got its own question and criteria (it was
never detected at 0.7). On the routing benchmark (109 questions): intent sets exact 77% -> 94%, day_summary recall
100%, combined questions answered by an exact composite 7/17 -> 19/21, coverage questions never a composite. The
shipped default stays `shadow` until a repeated battery confirms it.

