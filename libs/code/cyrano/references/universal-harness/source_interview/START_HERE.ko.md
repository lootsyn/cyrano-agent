# Decision Interview 설계 패키지

이 패키지는 에이전트 기반 인터뷰 플러그인의 **설계·계약·테스트 요구사항**이다. 실행 가능한 완성 플러그인이나 검증된 우승 제품이 아니다. 조사한 저장소의 전체 코드를 복제하지 않았다.

읽는 순서: `DESIGN.ko.md` → `IMPLEMENTATION_PLAN.ko.md` → `contracts/` → `fixtures/` → `prompts/`.

핵심 권고는 Ouroboros의 호스트/엔진 분리, Gajae의 사용자 의도와 상태 보호를 참고하되, 결정·근거·검증·승인을 공통 커널에서 관리하는 것이다. 현재 Ouroboros auto에도 이미 ledger-first 종료가 있다는 점을 비교에 반영했다.

기준 스냅샷:
- Ouroboros: `e4defa1bb36304b38646140f45a0a5b287bf7354`
- Gajae: `9da99cdd708ce3b97d64111d8eefc98a7e0921ee`

`policy.example.json`의 예산은 초기 제안값이다. 숫자를 낮췄다고 안전·승인 조건이 느슨해지면 안 된다.

`contracts/`는 외부 입출력의 핵심 경계를 정의한다. 스키마 검증은 의미·출처·서명·권한·상태 전이 검증을 대체하지 않는다.

`fixtures/readiness-cases.json`은 개발할 테스트의 입력과 기대 규칙이다. 테스트 실행 보고서가 아니다. 패키지 생성 시 수행한 파일/스키마 검증은 `VALIDATION.md`에 구분해 기록한다.

기존 저장소의 실행, 벤치마크, 변경, 커밋, 푸시는 이 작업 범위에 포함되지 않았다.
