# 승인·비밀·평가 오염 사건 대응

상태: 제품 기능 구현 후 사용할 목표 운영 절차. 현재 실제 운영에서 수행한 기록이 아니다. 구현되지 않은 CLI를 가정하지 않는다.

## 선행

관련 WP가 verified이고 해당 작업의 trusted authority와 runtime evidence가 있어야 한다.

## 순서

1. 새 실행과 affected release를 즉시 pause한다.
2. 비밀 body를 전파하지 않고 최소 event·hash·영향 범위를 보존한다.
3. 현재 permit revocation·관련 memory dependency를 무효화한다.
4. unknown 작업 결과와 사용자 원본 변경 영향을 확인한다.
5. 재현·수정·실제 검증·trusted 승인 이후에만 재개한다.

## 즉시 중단 조건

secret exfiltration suspicion, judge tamper, audit storage failure

## 결과 기록

actor·scope·subject digest·actual commands/receipts·미확인 side effects·복구 결과·승인 이력을 로컬 evidence 원장에 연결한다. 성공하지 않은 단계는 완료로 표시하지 않는다.
