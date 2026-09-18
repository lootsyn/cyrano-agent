---
name: cyrano-development
description: dcode base 위 Cyrano Agent 개발 작업의 문서·계획·검증 경로를 선택할 때 사용한다.
---

# Cyrano 개발 workflow

dcode 원본을 base로 사용한다. 할당 WP/TS/RC/RF를 먼저 정하고 `libs/code`에서 `python cyrano/scripts/doc_route.py --task <ID> --stage plan --content`를 실행해 필요한 원본만 읽는다. 모든 참고팩과 generated full을 읽지 않는다.

요구·범위·완료조건·파일·순서·검증 계획을 작성한다. 독립 reviewer finding을 반영하고 신뢰된 승인 후 수정한다. 범위가 바뀌면 재검토한다. source/runtime/policy/suite에 결속된 실제 테스트 evidence를 남긴다. native 연결이 없으면 component 완료로만 보고한다. 문서 역할·오류·rollback의 자세한 내용은 선택된 canonical 원본을 따른다.

캐시를 위해 고정 지침에 시각·진행률·nonce·동적 memory 결과를 섞지 않는다. 이 skill은 개발 절차이며 제품의 승인 보안 장치나 native 자동 loader 설정이 아니다.

code/skill/config/provider를 구분한다. 도구 설치·CLI native 화면·메모리 승인·효과 검증은 skill 문구만으로 완성되지 않는다. 세분 의무는 해당 WP의 RF 항목을 읽으며 외부 도구 설치는 명시적 local recipe만 사용한다.

문서 변경은 원본 WP reading_refs와 담당 설계에 직접 반영하고 `python cyrano/scripts/dev.py docs`를 실행한다. 기존 라우터·목차·통합본이 자동으로 갱신된다. 테스트 단계는 `--stage test`, 개별 사례는 `case_route.py --task WPxx --case ID`로 선택한다.
