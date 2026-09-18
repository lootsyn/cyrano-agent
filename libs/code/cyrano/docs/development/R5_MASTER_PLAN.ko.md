# Cyrano Agent · 통합 개발계획

문서 유형: 개발계획 — 현재 단일 기준.

이 문서는 현재 전체 개발의 실행 순서를 설명한다. 제품 구현 상태는 `.agents/work/plan.json`이 관리한다. WP가 주 작업 소유자이고 TS·RC·RF는 그 작업의 테스트·세분 의무다. 별도 NG 또는 추가팩을 먼저 설치하는 절차는 없다.

## 선행 관계와 구현 순서

계약(WP01), runtime 조사(WP00)는 독립적으로 시작한다. 원장(WP02)과 plugin 수명주기(WP04) 이후 권한·실행 격리(WP03), context(WP05), dcode 포트(WP06)를 연결한다. 인터뷰 kernel(WP07)과 UI·blind handoff(WP08), Memory(WP11), 전수 관측(WP13)이 있어야 계획·리뷰·승인과 dispatch(WP09)를 실제 검증할 수 있다. 그 뒤 실제 구현·검증(WP10)과 평가(WP20)를 연결한다. A/B 개선은 자신의 선행 작업을 통과한 뒤에만 실행한다. 최종 승격(WP21)·패키징/품질/복구(WP22)·실제 효과(WP23)는 마지막이다.

정확한 topological order는 plan.json에서 계산된다. 숫자순으로 WP14→WP15→WP20을 진행하면 평가기가 없어 막히므로 번호를 순서로 해석하지 않는다. 초기 release는 사람이 검토한 seed이며 학습 엔진이 자신을 승인해야 부팅되는 의존 순환을 만들지 않는다.

## 개발 lane과 실행 lane

테스트 코드는 제품 완성 전에도 fake port를 사용해 먼저 작성할 수 있다. 그러나 이를 native runtime·권한 경계·모델 효과 증거로 보고하지 않는다. 각 TS의 `depends_on`은 작성 의존성, `execute_requires_wp`는 실제 실행 선행 조건이다. bootstrap 작업에는 개발자의 명시적 변경 허가와 독립 리뷰를 사용하며 아직 없는 Cyrano 승인 기능으로 자신을 승인했다고 하지 않는다.

## 품질 검사 시점

품질은 WP22 마지막에 몰아서 하지 않는다. 모든 Python 변경에서 dcode 환경의 scoped Ruff lint/format과 native ty, docstring의 역할·입출력·오류 의미 리뷰를 수행한다. 도구 설치 불가·기존 실패는 baseline과 원인을 기록하고 통과로 바꾸지 않는다. WP22는 초기 검사 도입이 아니라 깨끗한 배포물과 전체 결과 재검증이다.

## 병렬 실행과 공통 파일

계약/원장/runtime/context의 owner를 분리한다. 두 작업이 같은 schema·agent.py·command registry·잠금파일을 수정하면 지정 owner가 통합하고 변경된 인터페이스의 모든 consumer를 다시 검증한다. 서로 다른 worktree도 승인·credential·메모리·실험 결과를 공유 쓰기하지 않는다. 공유 budget은 합산 예약이며 자식에게 전체 예산을 복제하지 않는다.

## 완료와 다음 작업 인계

각 WP는 요구→파일→테스트→원시 결과→리뷰를 묶어 evidence를 남긴다. 새 구현과 mock·선언·설계를 구분하고 blocked/not_run을 유지한다. 데이터 계약 변경 시 관련 schema와 fixture·skills 설명·작업 문서·라우터를 같이 갱신한다. commit/push/publication은 사용자의 별도 권한이 있을 때만 한다.

## 단계별 준비도와 통합 증거

plan.json의 depends_on은 해당 선행 WP의 `interface_ready`를 요구한다. 이는 API 선언만이 아니라 실제 구현된 포트·저장·오류/거부 경로를 검증한 상태다. 모든 하위 기능을 연결한 `product_verified`와 분리한다. Memory 서비스가 계획 엔진의 선행조건인데, Memory 서비스 완료를 다시 계획 엔진의 통합 실행에 종속시키는 순환은 금지한다. WP11/RF04는 저장/검색/적용 판정 포트를 먼저 검증하고, WP09/WP10 이후 native 새 작업의 실제 활용을 검사한다. WP13/RF09는 durable ingest/query/UI 포트를 먼저 검증하고, downstream 생산자가 완성된 뒤 전체 timeline을 검사한다. 최종 WP22/WP23은 모든 mandatory 제품 acceptances의 product_verified를 요구하며 포트만 통과한 작업에 점수를 부여하지 않는다.
