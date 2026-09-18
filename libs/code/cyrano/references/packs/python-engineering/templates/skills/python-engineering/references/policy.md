# Policy interpretation

PEP 8 default code lines are 79 characters and prose comments/docstrings are
72. This repository may explicitly use the team-agreed 88/72 profile.
Do not claim Black's default is the original PEP 8 line limit.

Read the active pyproject. Black controls format, Ruff selected rules control
lint, the selected mypy/Pyright controls types, and pytest checks behavior.
Neither Black nor lint proves all design requirements or correctness.

W505 also needs max-doc-length. New noqa, type-ignore, fmt-skip, test skip,
and exclusions require a narrow approved rationale. Fix root causes first.
