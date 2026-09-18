# sentinel fixture repo

Frozen agent-visible input for the WP23 live-effectiveness study 4.
Agents receive a byte-identical copy of this directory as their
workspace; `../oracle/` is never copied into the agent workspace.

Capability modules live in `sentinel/` and are registered in
`sentinel/registry.py`; packaging metadata lives under `caps/` and
is validated by an external packaging check.
