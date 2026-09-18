# Cyrano Agent 개발 지침

Base는 dcode다. 작업 cwd는 `libs/code/`, 새 제품 코드는 `deepagents_code/cyrano/`, 이 폴더는 설계·개발 지원이다. 상위 dcode 지침을 보존한다.

필수 인터뷰의 현재 요구·범위·완료 조건을 확인하고 정확한 파일·인터페이스·순서·검증 계획을 작성한다. 독립 AI 리뷰의 finding을 처리하고 신뢰된 계획 동의와 필요한 실행 허가 이후에만 변경한다. 사용자 의도·권한·budget·검증 기준이 바뀌면 영향범위를 재검토한다.

[작은 길잡이](docs/NAVIGATION.ko.md)와 할당 작업을 읽는다. `python cyrano/scripts/doc_route.py --task <ID> --content`로 관련 자료만 선택한다. 전체 통합본·reference·evidence를 상시 prompt에 넣지 않는다. 각 원본의 bytes·scope·유효성을 확인한다.

별도 보완팩·납품 이력을 만들지 않는다. 현재 소유 설계·WP·테스트·schema를 직접 갱신하고 `python cyrano/scripts/dev.py docs`로 카탈로그·라우터·목차·통합본을 함께 재생성한다. 이 절차는 아직 미구현인 제품 runtime guard를 대신하지 않는다.

모델별 거대한 행동 프롬프트·별도 agent loop·새 중복 DB를 만들지 않는다. 규칙·권한·완료 판정은 결정적 코드가 담당하고 skill은 제안·절차만 담당한다. 기억 검색≠적용, 후보 생성≠효과, 승격≠다음 작업 적용, 로그 존재≠전수 계측이다.

실제 source/runtime/policy/suite에 결속된 명령·종료코드·원시결과로 검증한다. 0 tests·skip·준비 검사·가짜 provider를 제품 PASS로 쓰지 않는다. 미검증은 blocked/not_run으로 보고한다. PEP8·명명·import·docstring 의미를 검사한다.

사용자 요청 없는 commit/push/배포·유료 호출·자동 학습·전역 설치를 수행하지 않는다. cleanup은 소유 fixture와 허가된 사본만 대상으로 하며 다른 사용자 변경을 보존한다.
