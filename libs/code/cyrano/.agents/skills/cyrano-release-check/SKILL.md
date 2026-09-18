---
name: cyrano-release-check
description: 프로젝트 검증·배포 준비 시 적용하는 CYRANO 개발 절차.
---

# cyrano-release-check

## 적용 조건

프로젝트 검증·배포 준비 시 이 skill을 읽는다. 상세 제품 계약은 해당 주제의 docs/design 원본과 schema가 소유한다.

## 절차

1. 실제 foundation/quality/schema/integration/live 명령 증거를 구분한다.
2. wheel/lock/dcode compatibility·schema rollback을 확인한다.
3. 깨끗한 압축 해제 디렉터리에서 startup/test를 실행한다.
4. manifest/hash·.env/secret/cache 제외·reference 원본 보존을 검사한다.
5. 원격 commit/push/promotion은 별도 사용자 허가 없이는 수행하지 않는다.

## 완료 기준

할당 WP의 산출물·거부 사례·실제 검증 evidence가 연결되어야 한다. 코드가 없는데 README만으로 구현 완료라고 표시하지 않는다. missing tool/network는 차단 사유이며 PASS로 바꾸지 않는다.
