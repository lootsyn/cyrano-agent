# dcode source-native 통합과 사용자 평가 기준

문서 유형: 상세 설계 · 상태: 계획(제품 미구현)

## Problem

독립 multi-package workspace와 dcode 원본이 서로 다른 pyproject/lock/source tree를 갖고 있어 그대로 덮어쓸 수 없다. 기존 20×2 증거표는 사용자가 제공한 15개 세부 배점과 다르다.

## Proposal

실행 코드는 `deepagents_code.cyrano.*`, 기반 테스트는 native tests/unit_tests/cyrano에 이관하고 개발 문서·계약은 libs/code/cyrano로 분리한다. 최신15항목/40점과 실제 제품 증거를 연결한다. [구조](../DCODE_INTEGRATION.ko.md), [테스트 전략](../../testing/STRATEGY.ko.md), [실행계획](../../development/TEST_DEVELOPMENT_PLAN.ko.md)을 따른다.

## Alternatives considered

**R2 pyproject로 dcode 덮어쓰기:** upstream local dependency와 build/test 정책을 파괴하므로 제외한다.

**별도 에이전트 loop:** 실제 dcode 경로에서 개발하고 검증하려는 C 요구와 다르므로 제외한다.

**40점 자동 자체평가:** signed actual evidence 없이 fixture 점수로 평가를 왜곡하므로 제외한다.

## Acceptance criteria

source import 이관·오프라인 회귀·overlay 충돌/rollback·문서팩 원문 보존을 검사한다. 실제 dcode 모드 matrix와 Python·plan·memory/improvement·trace 제품 사례는 별도 구현·실행하고 현재 성능이라고 주장하지 않는다.

## Risks

native SDK/CLI가 pre-stable이므로 private API drift와 upstream test config 충돌을 검증해야 한다. source 구조 통합은 보안 경계 통합이 아니며 broker의 별도 권한은 유지한다.
