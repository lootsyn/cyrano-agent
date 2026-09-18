"""Check design-template syntax and policy consistency, not tool behavior."""

from __future__ import annotations

import ast
import json
import tomllib
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


class TemplateTests(unittest.TestCase):
    def test_toml_files_parse(self) -> None:
        for path in ROOT.rglob("*.toml"):
            with self.subTest(path=str(path.relative_to(ROOT))):
                tomllib.loads(path.read_text(encoding="utf-8"))

    def test_policy_alignment(self) -> None:
        path = ROOT / "templates/project/python-quality.fragment.toml"
        tool = tomllib.loads(path.read_text(encoding="utf-8"))["tool"]
        self.assertEqual(tool["black"]["line-length"], 88)
        self.assertEqual(tool["ruff"]["line-length"], 88)
        self.assertEqual(tool["mypy"]["python_version"], "3.12")
        lint = tool["ruff"]["lint"]
        self.assertEqual(lint["pycodestyle"]["max-doc-length"], 72)
        self.assertIn("W", lint["select"])
        self.assertIn("N", lint["select"])
        self.assertNotIn("E501", lint["ignore"])

    def test_all_python_syntax(self) -> None:
        for path in ROOT.rglob("*.py"):
            with self.subTest(path=str(path.relative_to(ROOT))):
                ast.parse(path.read_text(encoding="utf-8"))

    def test_all_schemas_valid(self) -> None:
        for path in (ROOT / "contracts/v1").glob("*.json"):
            with self.subTest(path.name):
                Draft202012Validator.check_schema(
                    json.loads(path.read_text(encoding="utf-8"))
                )

    def test_positive_schema_instances(self) -> None:
        manifest = json.loads((ROOT / "fixtures/manifest.json").read_text())
        for entry in manifest["positive"]:
            with self.subTest(entry["path"]):
                schema_path = ROOT / "contracts/v1" / entry["schema"]
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                value = json.loads(
                    (ROOT / "fixtures" / entry["path"]).read_text(encoding="utf-8")
                )
                Draft202012Validator(schema).validate(value)

    def test_skill_frontmatter(self) -> None:
        path = ROOT / "templates/skills/python-engineering/SKILL.md"
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("name: python-engineering", text)
        self.assertIn("description:", text)
        self.assertLess(len(text.splitlines()), 500)

    def test_ci_contract_not_claimed_as_workflow(self) -> None:
        path = ROOT / "templates/ci/python-quality.contract.yaml"
        self.assertIn("NOT a runnable", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
