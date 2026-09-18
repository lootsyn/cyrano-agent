# widgetbox fixture repo

Frozen agent-visible input for the WP23 live-effectiveness study.
Agents receive a byte-identical copy of this directory as their
workspace; `../oracle/` is never copied into the agent workspace.

Widgets are registered in `widgetbox/registry.py` and carry packaging
metadata under `meta/` that is validated by an external packaging check.
