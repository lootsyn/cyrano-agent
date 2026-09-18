"""Build standalone design docs from canonical sources; never edit."""

import argparse
import hashlib
import html
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _rewrite_links(text: str, source: Path, output: Path) -> str:
    """Relocate local Markdown targets; fenced code is not prose."""
    fenced = False
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~~")):
            fenced = not fenced
        if not fenced:

            def replace(match: re.Match[str]) -> str:
                label, target = match.group(1), match.group(2)
                if "://" in target or target.startswith(
                    ("#", "mailto:", "data:")
                ):
                    return match.group(0)
                filename, marker, anchor = target.partition("#")
                resolved = (source.parent / filename).resolve()
                relocated = os.path.relpath(resolved, output.parent).replace(
                    os.sep, "/"
                )
                return f"[{label}]({relocated}{marker}{anchor})"

            line = re.sub(r"\[([^\]]+)\]\(([^\s)]+)\)", replace, line)
        lines.append(line)
    return "\n".join(lines)


def compile_markdown() -> tuple[str, dict[str, object]]:
    """Return deterministic Markdown and the source manifest."""
    manifest = json.loads(
        (ROOT / "docs/build-manifest.json").read_text(encoding="utf-8")
    )
    output = ROOT / manifest["output_markdown"]
    records = []
    parts = [
        "# Cyrano Agent · dcode 기반 전체 상세 설계\n",
        "**2026-09-17 · 현재 통합 기준 · dcode source-native 개발 "
        "준비 · 사용자15항목 · 경로 A/B 전체 포함**\n",
        "이 문서는 canonical 설계·개발·실행계획과 schema·설정·역할·"
        "skill·수용 명세를 합친 독립 읽기용 산출물이다. 제품 기능 "
        "구현 완료나 실제 성능 검증 완료를 뜻하지 않는다. 원본은 각 "
        "절에 표시한 source 파일이며 통합본을 직접 편집하지 않는다.\n",
        "현재 존재하는 foundation 코드와 앞으로 구현할 제품 기능의 "
        "상태를 구분한다. 전체 문서를 매 model 요청의 system "
        "prompt로 넣지 말고, 할당 WP·역할·필요 skill만 로딩한다.\n",
    ]
    counter = 0
    for relative in manifest["primary_markdown_sources"]:
        path = ROOT / relative
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        records.append(
            {"path": relative, "sha256": hashlib.sha256(raw).hexdigest()}
        )
        counter += 1
        parts += [f"\n---\n\n## {counter:03d} · {relative}\n"]
        # Skill metadata is shown explicitly, not interpreted as
        # document frontmatter.
        if text.startswith("---\n"):
            _, front, rest = text.split("---", 2)
            text = "```yaml\n" + front.strip() + "\n```\n" + rest
        text = _rewrite_links(text, path, output)
        shifted = []
        inside = False
        for line in text.splitlines():
            if line.lstrip().startswith("```"):
                inside = not inside
            if not inside:
                line = re.sub(
                    r"^(#{1,5}) ",
                    lambda m: "#" * min(6, len(m.group(1)) + 2) + " ",
                    line,
                )
            shifted.append(line)
        parts.append("\n".join(shifted) + "\n")
    for relative in manifest["fenced_appendices"]:
        path = ROOT / relative
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        records.append(
            {"path": relative, "sha256": hashlib.sha256(raw).hexdigest()}
        )
        counter += 1
        language = {
            ".json": "json",
            ".sql": "sql",
            ".yaml": "yaml",
            ".toml": "toml",
        }.get(path.suffix, "text")
        longest = max(
            [len(m.group(0)) for m in re.finditer(r"`+", text)] or [0]
        )
        fence = "`" * max(4, longest + 1)
        parts += [
            f"\n---\n\n## {counter:03d} · 부록 원문 {relative}\n",
            f"{fence}{language}\n{text.rstrip()}\n{fence}\n",
        ]
    data = "\n".join(parts).rstrip() + "\n"
    return data, {
        "schema_version": "1.0",
        "source_count": len(records),
        "sources": records,
        "markdown_sha256": hashlib.sha256(data.encode("utf-8")).hexdigest(),
    }


def render_html(markdown: str, fingerprint: str) -> str:
    """Render a self-contained Korean view; no external assets."""
    try:
        import mistune
    except ImportError as error:
        raise RuntimeError(
            "HTML_RENDER_BLOCKED: install mistune or use --markdown-only"
        ) from error
    headings = []

    class Renderer(mistune.HTMLRenderer):
        def heading(self, text: str, level: int, **attrs: object) -> str:
            anchor = f"section-{len(headings) + 1:04d}"
            plain = html.unescape(re.sub(r"<[^>]+>", "", text))
            headings.append((level, anchor, plain))
            return f'<h{level} id="{anchor}">{text}</h{level}>\n'

    renderer = Renderer(escape=True)
    body = mistune.create_markdown(
        renderer=renderer, plugins=["table", "strikethrough"]
    )(markdown)
    toc = "".join(
        f'<a href="#{anchor}">{html.escape(title)}</a>'
        for level, anchor, title in headings
        if level <= 2
    )
    css = """
        :root{--ink:#142a3d;--muted:#526675;--line:#dbe4e9;--paper:#ffffff;
    --nav:#102b3f;--accent:#157a8a}
        *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;
    background:#f2f5f7;color:var(--ink);font:16px/1.85 system-ui,
    -apple-system,'Malgun Gothic','Apple SD Gothic Neo',sans-serif}
        nav{position:fixed;inset:0 auto 0 0;width:310px;
    background:var(--nav);color:white;padding:26px 20px;overflow:auto}
    nav strong{display:block;font-size:21px;line-height:1.4;
    margin-bottom:18px}nav p{font-size:12px;color:#c1d4e1}
    nav a{display:block;color:#dde9ef;text-decoration:none;font-size:12px;
    line-height:1.5;padding:8px 0;border-bottom:1px solid #2a455a;
    overflow-wrap:anywhere}nav a:hover{color:white}
        main{margin-left:310px;max-width:1300px;padding:48px 58px;
    background:var(--paper);min-height:100vh}h1{font-size:34px;
    line-height:1.35;margin-top:0}h2{font-size:24px;
    border-top:4px solid var(--accent);padding-top:20px;margin-top:50px;
    overflow-wrap:anywhere}h3{font-size:22px}h4{font-size:19px;
    margin-top:30px}h5,h6{font-size:17px}p{margin:0 0 18px}a{color:#126a83}
    pre{background:#f2f5f8;border:1px solid var(--line);border-radius:5px;
    padding:20px;overflow:auto;font-size:12px;line-height:1.65}
    code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}p code,
    li code{background:#edf3f6;padding:2px 4px;overflow-wrap:anywhere}
    table{border-collapse:collapse;width:100%;font-size:13px;margin:20px 0;
    display:block;overflow:auto}th{background:#e7f0f4;text-align:left}th,
    td{border:1px solid var(--line);padding:10px 13px;vertical-align:top}
    td code{font-size:12px}hr{border:0;border-top:1px solid var(--line);
    margin:50px 0}blockquote{border-left:4px solid var(--accent);
    padding-left:20px;color:var(--muted)}ul,ol{padding-left:25px}
    footer{font-size:12px;color:var(--muted);margin-top:50px}
        @media(max-width:1050px){nav{position:static;width:auto;
    max-height:280px}main{margin:0;padding:24px}h1{font-size:28px}}
    @media print{nav{display:none}main{margin:0;padding:0;max-width:none}
    pre{white-space:pre-wrap}h2,h3,h4{break-after:avoid}}
    """
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="cyrano-markdown-sha256" content="{fingerprint}"><title>
    Cyrano Agent · dcode 기반 개발 설계</title><style>{css}</style>
    </head><body>
    <nav><strong>Cyrano Agent<br>dcode 기반 개발</strong><p>
    경로 A/B · 인터뷰 · 캐시 · Memory<br>
    설계 · 개발계획 · 실행계획<br>개발 준비 / 운영 검증 아님</p>
    {toc}</nav><main>{body}<footer>
    Generated from canonical project sources. SHA256: {fingerprint}</footer>
    </main></body></html>"""


def compile_guide() -> str:
    """Build the guide from the manifest, not a previous delivery."""
    manifest = json.loads((ROOT / "docs/build-manifest.json").read_text())
    output = ROOT / "docs/generated/DEVELOPER_GUIDE.ko.md"
    parts = [
        "# Cyrano Agent · 개발 수행 가이드\n",
        "현재 실행 가능한 준비 도구와 구현할 제품 기능을 구분한다. "
        "전체 기능 계약은 FULL_DESIGN과 각 원본 문서에 있다.\n",
    ]
    for i, relative in enumerate(manifest["developer_guide_sources"], 1):
        source = ROOT / relative
        text = _rewrite_links(source.read_text(), source, output)
        parts.append(f"\n---\n\n## {i:02d} · {relative}\n")
        inside = False
        for line in text.splitlines():
            if line.lstrip().startswith("```"):
                inside = not inside
            if not inside:
                line = re.sub(
                    r"^(#{1,5}) ",
                    lambda m: "#" * min(6, len(m[1]) + 2) + " ",
                    line,
                )
            parts.append(line)
    return "\n".join(parts).rstrip() + "\n"


def main() -> int:
    """Check freshness or publish Markdown and optional HTML."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--markdown-only", action="store_true")
    args = parser.parse_args()
    if not args.check:
        from build_catalog import generate

        generate(ROOT)
    text, evidence = compile_markdown()
    guide = compile_guide()
    guide_path = ROOT / "docs/generated/DEVELOPER_GUIDE.ko.md"
    guide_html = guide_path.with_suffix(".html")
    guide_hash = hashlib.sha256(guide.encode()).hexdigest()
    md = ROOT / "docs/generated/FULL_DESIGN.ko.md"
    html_path = ROOT / "docs/generated/FULL_DESIGN.ko.html"
    if args.check:
        if not md.exists() or md.read_text(encoding="utf-8") != text:
            print(
                "GENERATED_DOCS_STALE: run python cyrano/scripts/dev.py docs"
            )
            return 1
        if (
            html_path.exists()
            and f'content="{evidence["markdown_sha256"]}"'
            not in html_path.read_text(encoding="utf-8")
        ):
            print("GENERATED_HTML_STALE")
            return 1
        if not guide_path.exists() or guide_path.read_text() != guide:
            print("GENERATED_GUIDE_STALE")
            return 1
        if guide_html.exists() and guide_hash not in guide_html.read_text():
            print("GENERATED_GUIDE_HTML_STALE")
            return 1
        print("Generated design freshness: PASS")
        return 0
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(text, encoding="utf-8")
    guide_path.write_text(guide, encoding="utf-8")
    if not args.markdown_only:
        guide_html.write_text(render_html(guide, guide_hash), encoding="utf-8")
        html_path.write_text(
            render_html(text, str(evidence["markdown_sha256"])),
            encoding="utf-8",
        )
    (ROOT / "docs/generated/source-manifest.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    from build_catalog import generate

    generate(ROOT)
    print(
        json.dumps(
            {
                "sources": evidence["source_count"],
                "markdown_bytes": md.stat().st_size,
                "html_generated": not args.markdown_only,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
