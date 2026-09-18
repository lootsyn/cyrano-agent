# A/B 실제 개선 평가

상태: 제품 기능 구현 후 사용할 목표 운영 절차. 현재 실제 운영에서 수행한 기록이 아니다. 구현되지 않은 CLI를 가정하지 않는다.

## 선행

관련 WP가 verified이고 해당 작업의 trusted authority와 runtime evidence가 있어야 한다.

## 순서

1. 사용자 scope와 비용 한도·실험 permit을 확인한다.
2. family/time splits와 primary criteria·pair 수·순서를 봉인한다.
3. baseline/candidate 실제 실행과 usage/receipt를 수집한다.
4. missing pair·safety·quality·총비용을 독립 분석한다.
5. inconclusive는 baseline 유지, eligible은 별도 review/approval에 전달한다.

## 즉시 중단 조건

no budget, sealed leak, zero actual pairs

## 결과 기록

actor·scope·subject digest·actual commands/receipts·미확인 side effects·복구 결과·승인 이력을 로컬 evidence 원장에 연결한다. 성공하지 않은 단계는 완료로 표시하지 않는다.
