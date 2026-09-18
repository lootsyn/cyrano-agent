# 검증된 dcode 운영 시작

상태: 제품 기능 구현 후 사용할 목표 운영 절차. 현재 실제 운영에서 수행한 기록이 아니다. 구현되지 않은 CLI를 가정하지 않는다.

## 선행

관련 WP가 verified이고 해당 작업의 trusted authority와 runtime evidence가 있어야 한다.

## 순서

1. current runtime lock와 required probes를 검증한다.
2. CYRANO_HOME이 target 밖이고 control/agent/execution principals가 분리됐는지 확인한다.
3. approved release subject/authority/schema compatibility를 확인한다.
4. 고객 source snapshot과 permit을 고정하고 extension health handshake를 확인한다.
5. 허가된 read/scratch smoke 후에만 업무 dispatch를 연다.

## 즉시 중단 조건

runtime mismatch, extension unhealthy, scope/approval mismatch

## 결과 기록

actor·scope·subject digest·actual commands/receipts·미확인 side effects·복구 결과·승인 이력을 로컬 evidence 원장에 연결한다. 성공하지 않은 단계는 완료로 표시하지 않는다.
