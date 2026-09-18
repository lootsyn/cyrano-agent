# 출처와 조사 범위

조회 기준: 2026-09-16. 공개 자료는 변경될 수 있다. 논문·웹 문서 분석과 실제 런타임 검증은 구분한다.

## [S01] DREAM 프로젝트 페이지

https://dream-rsi.com/

개념·공개 결과·주장 범위. 데모는 설명용이다.

## [S02] DREAM 논문 PDF

https://dream-rsi.com/assets/dream-rsi.pdf

36쪽 기술 보고서. §3 정책/replay, §4–5 평가, 부록 B 운영 prompt를 확인했다. 전체 정책 엔진의 실행 재현은 하지 않았다.

## [S03] DREAM 공식 저장소

https://github.com/zhengkid/Dream-RSI

조회 시 README Release plan에서 full codebase/reproduction scripts는 공개 준비 중. 논문 부록의 코드 조각과 전체 코드베이스 공개는 구분한다.

## [S04] dcode Python extensions

https://raw.githubusercontent.com/langchain-ai/deepagents/main/libs/code/EXTENSIONS.md

실험적 async extension 등록, middleware/tools/backend/shutdown, slash command 제외, 격리·승인 책임. main은 불변 버전이 아니므로 WP-D00에서 실제 설치 artifact를 고정한다.

## [S05] dcode Hooks

https://raw.githubusercontent.com/langchain-ai/deepagents/main/libs/code/HOOKS.md

lifecycle hooks, 동시 실행, exit/timeout 의미. 일반 오류를 fail-closed 보안 장치로 간주하지 않는다.

## [S06] Deep Agents Memory

https://docs.langchain.com/oss/python/deepagents/memory

파일/backend 기반 장기 기억과 scope, short-term state와의 구분. UDH 승격 엔진이 내장됐다는 뜻이 아니다.

## [S07] Deep Agents Skills

https://docs.langchain.com/oss/python/deepagents/skills

절차 기억과 on-demand loading. 모델별 특화 layer 도입 근거가 아니다.

## [S08] LangChain custom middleware

https://docs.langchain.com/oss/python/langchain/middleware/custom

node/model/tool lifecycle 확장 표면. 모든 nested 호출 관측은 실제 통합 검사가 필요하다.

## [B01] 기존 UDH 설계

사용자 Library의 `UDH_FULL_DESIGN.ko.md`, 2026-09-15, 버전 1.0. 모델 비특화·dcode core 무수정·대상 repo 설치 비침습·인터뷰/계획/메모리/관측/개선/복구 요구와 LEARN 상태기계를 확인했다. 이 패키지는 원본의 대체본이 아니라 확장 명세다.

## 중요한 해석 경계

DREAM의 성과를 범용 코딩 에이전트의 보장 수치로 옮기지 않는다. 고정된 실행 이력에서 관측된 결과를 재사용하는 정합성과 새 업무에서의 일반화 성능은 다른 주장이다. 전체 코드는 공개 준비 중이므로 논문의 내부 helper API를 설치 가능한 SDK로 가정하지 않는다. 외부 프로그램 코드는 이 패키지에 복제하지 않았다. 추후 코드 차용 시 당시 라이선스·의존성·보안·재현성을 별도로 확인한다.
