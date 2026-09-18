# 조사 근거

저장소 관련 판단은 다음의 고정 스냅샷을 기준으로 한다. 코드 파일·SKILL 지시·테스트 명세의 근거 수준은 서로 다르다. 소스 확인은 제품 실행이나 성능 벤치마크가 아니다.

## Gajae

기준: `Yeachan-Heo/gajae-code@9da99cdd708ce3b97d64111d8eefc98a7e0921ee`

- [G1] `packages/coding-agent/src/defaults/gjc/skills/deep-interview/SKILL.md`: 조사 구간 1–240, 450–625, 635–805. Threshold/프레이밍/컴포넌트 평가/ontology/closure/handoff 규칙. 전체 파일의 모든 경로를 런타임 검증했다고 주장하지 않는다.
- [G2] `packages/coding-agent/src/gjc-runtime/deep-interview-ambiguity.ts`: floor와 답변 철회, 현재/최신 라운드 점수 clamp 구현.
- [G3] `packages/coding-agent/src/gjc-runtime/deep-interview-stage.ts`: 조사 구간 1–210. revision+digest, core-schema 검증, recorder 소유 필드 경계.
- 보조 확인: `deep-interview-state.ts`, `deep-interview-state.test.ts`의 locked intent 삭제/대체 방지 검색 결과.

## Ouroboros

기준: `Q00/ouroboros@e4defa1bb36304b38646140f45a0a5b287bf7354`

- [O1] `src/ouroboros/bigbang/ambiguity.py`: 조사 구간 1–465. threshold, 차원별 floor, completion 검사, optional per-dimension scorer.
- [O2] `src/ouroboros/bigbang/interview.py`: 조사 구간 1–440. tool-less interview 역할, answer provenance, canonical input fingerprint와 cache 무효화.
- [O3] `src/ouroboros/auto/grading.py`: 조사 구간 1–235. ledger-only/safe-default/degraded 경로와 유지되는 목표·위험 차단 조건.
- [O4] `src/ouroboros/auto/ledger.py`: 조사 구간 1–205. source/status/provenance, required sections, evidence-backed 분류, LedgerEntry.
- [O5] `tests/unit/mcp/tools/test_interview_done_streak.py`: 조사 구간 1–230. done/streak 회귀 테스트와 safe-default 분리. 테스트 코드를 읽었으며 실행하지 않았다.
- [O6] `skills/interview/SKILL.md`: main raw 페이지와 pinned 구간 485–710. host/MCP 경계, refine, tri-panel acceptance guard, restate 규칙.

## 외부 설계 참고

- [R1] Dong et al., *Value of Information: A Framework for Human-Agent Communication*, arXiv:2601.06407, 2026-01-10. 질문 이득과 인간 부담을 함께 고려하는 이론적 참고. 소프트웨어 인터뷰 플러그인의 성능 검증으로 사용하지 않았다.
  `https://arxiv.org/abs/2601.06407`
- [R2] Vijayvargiya et al., *Asking What Matters: Reward-Driven Clarification for Software Engineering Tasks*, arXiv:2604.14624v1, 2026-04-16. 관련성·답변 가능성·후속 테스트 기반 평가 방향 참고. 모의 사용자/제한된 실험의 일반화 한계를 유지한다.
  `https://arxiv.org/html/2604.14624v1`
- [R3] GitHub Spec Kit, `templates/commands/clarify.md`, 조사 시점 main. 범주별 누락과 영향도 기반 질문 우선순위 참고. 이 파일은 위 두 저장소와 달리 commit pin을 별도로 확보하지 않았다.
  `https://github.com/github/spec-kit/blob/main/templates/commands/clarify.md`

## 해석 경계

Gajae가 Ouroboros를 참고했다고 명시한 점, 양쪽에 이미 존재하는 기능을 누락하지 않도록 했다. 본 설계의 그래프·승인 브로커·평가 계획은 조사 사실 자체가 아니라 제안이다. 두 제품의 라이선스 적합성 검토나 코드 재배포는 이 패키지의 범위가 아니다.
