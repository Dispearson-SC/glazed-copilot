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
2. Restore the dumps of deploy step 3 (the schema was migrated forward):

   ```
   docker exec -i glazed-db pg_restore -U postgres --clean --if-exists -d agent_core < agent_core-pre-g7.dump
   docker exec -i glazed-db pg_restore -U postgres --clean --if-exists -d <dbos database> < dbos-pre-g7.dump
   ```
3. Put the deploy checkout back on the revision before this change (its compose file builds Core from
   `../Agent-Core/Core` with `GLAZED_BACKEND_URL`), restore the old images and start them unbuilt:

   ```
   for s in core core-peer-worker backend; do
     docker tag glazed-copilot-$s:pre-g7 glazed-copilot-$s:latest
   done
   docker compose -f infra/docker-compose.yml --env-file .env up -d --no-build backend core core-peer-worker
   ```
4. Remove `AGENT_CORE_SRC` from `.env` and, when no longer needed, the `../Agent-Core-deploy` worktree.
