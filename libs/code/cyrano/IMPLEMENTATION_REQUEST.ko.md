# Cyrano Agent · AI 개발 수행 지시

`libs/code`에서 실행하라. dcode base는 이미 clone한 monorepo이고 `deepagents_code/cyrano/`는 우리가 추가 개발할 제품 코드다. `cyrano/`는 설계·개발 자료이며 독립 실행 제품 루트가 아니다.

처음에 상위 dcode `AGENTS.md`, `cyrano/AGENTS.md`, `cyrano/docs/NAVIGATION.ko.md`, `cyrano/docs/execution/DEVELOPER_GUIDE.ko.md`를 읽어라. 추가 보완팩이나 과거 납품판을 요구하지 말고 현재 `.agents/work/plan.json`을 기준으로 한다.

1. 현재 checkout과 실제 설치·시험환경, 명시적으로 허용된 변경·비용·외부 행동을 확인한다. 기준 소스를 무음 업그레이드하지 않는다.
2. 선행 WP의 실제 완료 증거를 확인하고 준비된 WP를 고른다. TS·RC·RF와 implementation_units는 해당 WP의 일부다. 같은 원본 파일은 하나의 owner가 최종 통합한다.
3. `python cyrano/scripts/doc_route.py --task <ID> --content`로 해당 작업의 설계·실행·테스트 자료를 읽는다. schema·case 원본은 manifest의 resource_refs에서 필요한 항목만 추가 조회한다.
4. 인터뷰 결과의 요구·범위·완료 조건을 확정한다. 구현 파일·API·순서·검증·실패/복구를 구체화하고 독립 AI 계획 리뷰와 사람의 결정을 받는다. 계획 승인과 실행 허가는 다르다.
5. 부정 시험과 fixture를 먼저 만들고 실제 소유 service에 연결한다. 없는 native 기능은 blocked다. fake/skip/zero-tests를 제품 완료로 사용하지 않는다.
6. 코드·schema·설계·WP·test oracle의 의미를 함께 유지한다. 기준을 약화해 실패를 숨기지 않는다. branch 통합 후 새 snapshot에서 검증한다.
7. 실제 명령·cwd·exit·source/runtime/policy/suite·case 결과·리뷰 finding·복구 한계를 기록한다. 기억·개선은 후속 실제 적용까지, 모니터는 원시 호출과 화면 숫자까지 확인한다.
8. 현재 문서를 직접 수정하고 `python cyrano/scripts/dev.py docs`를 실행해 router/catalog/index/full guide를 함께 갱신한다. 새 날짜별 보완문서·납품 이력은 만들지 않는다.

실제 제품 보안이 구현되기 전에는 개발용 외부 승인과 advisory 실행이라고 표시하라. 모든 외부 부작용은 명시 허가 범위 안에서만 수행한다. 자격증명·숨은 평가·승인키·active release를 일반 에이전트에 쓰기 가능하게 하지 않는다.

완료 응답은 실제 검증 범위와 미실행 항목을 분리한다. 프로젝트가 문서·fixture를 제공한다고 제품 평가 40점을 획득했다고 보고하지 않는다. 현재 범위를 넘는 신규 요구는 변경 분석·재검토로 처리한다.
