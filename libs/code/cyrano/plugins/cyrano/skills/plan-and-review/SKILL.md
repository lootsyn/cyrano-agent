---
name: plan-and-review
description: 필수 인터뷰 결과를 검증 가능한 계획으로 만들고 독립 리뷰·사람 결정·별도 실행 허가에 연결한다.
---

# 계획과 독립 리뷰

현재 역할이 허용한 scope·source·요구·AgentTask 입력만 사용한다. 모든 단계를 프롬프트만으로 강제했다고 주장하지 않는다. 실제 강제는 runtime kernel과 Broker가 담당한다.

1. 유효한 InterviewContract의 요구·비목표·완료 조건과 MemoryView를 확인한다. 답한 질문을 되묻지 않되 준비도 검사는 생략하지 않는다.
2. 각 작업의 정확한 파일/변경 종류, 소비·생산 API, dependency·독점 자원, argv/cwd/env/timeout, budget, oracle·반례·복구를 작성한다.
3. 요구 coverage·작업 cycle·인터페이스 불일치·경합·범위 밖 부작용·필수 테스트 누락을 기계 검사에 제출한다.
4. 별도 read-only reviewer 실행에 같은 immutable subject와 근거를 제공한다. finding에 수정을 반영하거나 반증 자료를 제출한다. 작성자가 직접 resolved로 닫지 않는다.
5. 사람에게 범위·위험·비용·검증·미해결·변경점이 있는 동일 표시본을 제시한다. 조건부 동의는 수정 요청이다. 계획 승인과 실행 허가를 분리한다.
6. 변경·철회·stale source를 발견하면 영향을 계산하고 재검토한다. 정상 승인 계보 안의 candidate 진전은 일괄 재승인 사유가 아니지만 새 효과를 추가할 수 없다.

산출물은 `GovernedWorkPlan`과 `PlanReviewSubject` 후보이며 서명된 receipt가 아니다. output_schema_ref와 현재 registry를 따른다. review 상한 도달·권한 누락·test 불가·사람 보류를 완료로 표시하지 않는다.

필요한 단계에서만 [체크리스트](references/checklist.md)를 읽는다. 제품 설치에서 개발 문서 경로를 runtime resource라고 가정하지 않는다.
