# release rollback과 영향 작업 재검토

상태: 제품 기능 구현 후 사용할 목표 운영 절차. 현재 실제 운영에서 수행한 기록이 아니다. 구현되지 않은 CLI를 가정하지 않는다.

## 선행

관련 WP가 verified이고 해당 작업의 trusted authority와 runtime evidence가 있어야 한다.

## 순서

1. 새 dispatch를 중지하고 incident와 affected run을 기록한다.
2. rollback target과 DB schema 호환성을 검증한다.
3. 승인된 authority로 active pointer를 CAS 전환한다.
4. 현재 run은 revoke 정책에 따라 pause/rebind하고 unknown 외부 결과를 reconcile한다.
5. 이미 사용자 원본에 적용한 patch는 별도 복구 허가로 처리한다.

## 즉시 중단 조건

incompatible migration, missing rollback authority, unknown external effect

## 결과 기록

actor·scope·subject digest·actual commands/receipts·미확인 side effects·복구 결과·승인 이력을 로컬 evidence 원장에 연결한다. 성공하지 않은 단계는 완료로 표시하지 않는다.
