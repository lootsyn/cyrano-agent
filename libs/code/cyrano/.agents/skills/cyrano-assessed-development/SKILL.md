---
name: cyrano-assessed-development
description: CYRANO 기능을 실제 dcode source에서 개발하거나 사용자 15항목 평가 테스트를 추가할 때 사용한다.
---

# 평가 근거를 남기는 개발

`docs/design/DCODE_INTEGRATION.ko.md`와 할당 WP를 읽고 현재 source digest를 확인한다. 요구·범위·완료 oracle·수정 파일·작업 순서·tests를 계획한다. 독립 AI reviewer의 finding을 반영한 현재 계획에 승인/permit이 없으면 code mutation을 시작하지 않는다.

필요한 `references/packs/dcode-analysis/analysis/NN-*.md`와 `references/packs/python-engineering/docs/design/NN*.md`만 선택해서 읽는다. 원문 AGENTS의 historical 분석-only 지시는 현재 프로젝트 전체 지시가 아니다. source를 직접 확인하고 추정과 검증을 구분한다.

새 Python에는 단일 formatter·naming/import·주요 docstring과 필요한 주석 검사를 적용한다. 코드 작성 후 동일 snapshot에 대해 test와 독립 code review를 수행한다. `tests/assessment/cases.json`의 case와 실제 node/receipt를 연결한다. 문서·fixture·schema PASS를 제품40점 증거로 사용하지 않는다.

memory query/injection/application을 구분하고 prompt/skill/memory/code 변경은 B 실제 paired evaluation으로 검증한다. 승인 전 active release를 수정하지 않는다. 도구·비용·오류·trace gap을 숨기지 않는다. 품질/실행 도구가 없으면 blocked로 보고한다.
