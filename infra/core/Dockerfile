# Agent-Core with the glazed addons (Phase 3, G7). Build context: this directory (infra/core), which
# carries the glazed deployment's own policy rule. The Agent-Core checkout is the additional build
# context `agent_core` (its repository ROOT, branch feat/glazed-addons): the image needs both Core/
# and addons/. See infra/docker-compose.yml and docs/agent-core-addons-runbook.md.
FROM python:3.12-slim
WORKDIR /app/Core

# Layer 1 (cached): third-party dependencies only, read from pyproject.toml.
COPY --from=agent_core Core/pyproject.toml ./
RUN python - <<'PY' > /tmp/requirements.txt
import tomllib
print("\n".join(tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]))
PY
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Layer 2: the code. Editable so the package finds profiles/, policy/ and skills/ next to src/ and
# the addons at /app/addons (the repository layout: Core/ and addons/ side by side).
COPY --from=agent_core Core/src ./src
COPY --from=agent_core Core/profiles ./profiles
COPY --from=agent_core Core/policy ./policy
COPY --from=agent_core Core/skills ./skills
COPY --from=agent_core addons /app/addons
RUN pip install --no-cache-dir --no-deps -e .

# The one glazed rule an addon cannot carry (it allows Core's `ask_peer`): it joins Core's own rules
# in the policy directory, and glazed_tools' 33 rules come from the addon.
COPY policy/glazed_deployment.yaml ./policy/glazed_deployment.yaml

ENV AGENT_CORE_HTTP_HOST=0.0.0.0 AGENT_CORE_HTTP_PORT=8000 \
    AGENT_CORE_POLICY_DIR=/app/Core/policy \
    AGENT_CORE_ADDONS_DIR=/app/addons \
    AGENT_CORE_ADDONS=http_tool_bridge,glazed_tools,plain_language,glazed_vertical \
    AGENT_CORE_ADDONS_CONFIG=/app/addons/glazed_vertical/addons_config.yaml
EXPOSE 8000
CMD ["python", "-m", "agent_core", "serve"]
