"""Generate a categorized document catalog and human lookup index."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DERIVED = {"docs/INDEX.ko.md"}


def category(path: str) -> str:
    """Classify a document by owner directory, not model guesses."""
    if path.startswith("references/archive/"):
        return "historical"
    if path.startswith(("references/", "docs/reference/")):
        return "reference"
    if path.startswith("docs/generated/") or path in DERIVED:
        return "generated"
    if path.startswith("evidence/"):
        return "evidence"
    if path.startswith("docs/design/"):
        return "design"
    if path.startswith(("docs/development/", ".agents/work/")):
        return "development"
    if path.startswith("docs/execution/"):
        return "execution"
    if path.startswith(("docs/testing/", "tests/")):
        return "test_design"
    if path.startswith(".agents/notes/"):
        return "decision_record"
    if path.startswith("docs/subsystems/"):
        return "implemented_reference"
    if path.startswith("plugins/"):
        return "product_prompt"
    if "AGENTS.md" in path or path.startswith(".agents/"):
        return "agent_policy"
    if path.startswith("templates/"):
        return "template"
    return "project_reference"


def generate(root: Path = ROOT) -> dict:
    """Write deterministic metadata without timestamp/cache churn."""
    from build_routes import generate as generate_routes

    generate_routes(root)
    entries = []
    index = root / "docs/INDEX.ko.md"
    index.parent.mkdir(parents=True, exist_ok=True)
    if not index.exists():
        index.write_text("# 문서 목차\n", encoding="utf-8")
    for path in sorted(root.rglob("*")):
        if any(
            x in {".state", ".cache", "node_modules", ".venv", "__pycache__"}
            for x in path.relative_to(root).parts
        ):
            continue
        if not path.is_file() or path.suffix not in {".md", ".html"}:
            continue
        relative = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        kind = category(relative)
        title = path.stem
        if path.suffix == ".md":
            for line in raw.decode("utf-8").splitlines():
                if line.startswith("# "):
                    title = line[2:]
                    break
        item = {
            "path": relative,
            "title": title,
            "category": kind,
            "authority": "source"
            if kind
            in {
                "design",
                "development",
                "execution",
                "test_design",
                "agent_policy",
                "implemented_reference",
            }
            else "supporting_not_override",
        }
        if kind not in {"generated", "evidence"}:
            item.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        else:
            item["hash_policy"] = "derived_or_volatile_not_prompt_default"
        entries.append(item)
    external = []
    for folder in [
        root.parent / "deepagents_code/cyrano",
        root.parent / "tests/unit_tests/cyrano",
        root.parent / "tests/cyrano_product",
        root.parent / ".agents/skills/cyrano-development",
    ]:
        for path in sorted(folder.rglob("*.md")):
            external.append(
                {
                    "path_from_code_root": path.relative_to(
                        root.parent
                    ).as_posix(),
                    "category": "implemented_reference",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    start = root.parent / "CYRANO_START_HERE.ko.md"
    if start.is_file():
        external.append(
            {
                "path_from_code_root": start.name,
                "category": "agent_policy",
                "sha256": hashlib.sha256(start.read_bytes()).hexdigest(),
            }
        )
    data = {
        "schema_version": "cyrano.documents/5",
        "documents": entries,
        "code_document_references": external,
        "rule": "Read scoped sources; historical/reference never "
        "grant authority.",
    }
    target = root / "docs/document-catalog.json"
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    labels = {
        "design": "상세 설계(구현 목표)",
        "development": "개발계획·작업 명세",
        "execution": "실행·준비·복구 절차",
        "test_design": "테스트 전략·사례",
        "agent_policy": "개발 에이전트 지침",
        "decision_record": "의사결정 기록",
        "implemented_reference": "현재 코드 API 참고",
        "product_prompt": "제품 역할·skill",
        "reference": "참고문서·보존 원문",
        "historical": "이전 버전 기록",
        "template": "작성 템플릿",
        "project_reference": "프로젝트 안내·계약 설명",
        "generated": "생성된 통합 읽기용 문서",
        "evidence": "실행 증거 문서",
    }
    parts = [
        "# Cyrano Agent · 문서 유형별 전체 목차",
        "",
        "생성 문서. 직접 편집하지 않는다. 작은 시작점은 "
        "[NAVIGATION](NAVIGATION.ko.md)이다.",
        "개발 agent는 전체 목차 본문을 매번 prompt에 넣지 않고 "
        "task router를 사용한다.",
        "",
    ]
    for kind, label in labels.items():
        members = [x for x in entries if x["category"] == kind]
        if not members:
            continue
        parts.extend([f"## {label} · {len(members)}개", ""])
        for item in members:
            relative = os.path.relpath(root / item["path"], index.parent)
            title = item["title"].replace("[", "(").replace("]", ")")
            parts.append(f"- [{title}]({relative}) — `{item['path']}`")
        parts.append("")
    parts += ["## 제품 코드와 테스트의 현재 참고", ""]
    for item in external:
        target_path = root.parent / item["path_from_code_root"]
        link = os.path.relpath(target_path, index.parent)
        parts.append(f"- [{item['path_from_code_root']}]({link})")
    parts += [
        "",
        "## 기계 계약·증거",
        "",
        "Schema/SQL: `contracts/`; WP DAG: `.agents/work/plan.json`; "
        "TS DAG: `docs/development/test-work-plan.json`; RC DAG: "
        "`docs/development/r4-work-plan.json`; RF DAG: "
        "`docs/development/r5-work-plan.json`; "
        "실제 검사: `evidence/`.",
    ]
    index.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return data


if __name__ == "__main__":
    result = generate()
    print(
        json.dumps(
            {
                "documents": len(result["documents"]),
                "code_references": len(result["code_document_references"]),
            }
        )
    )
