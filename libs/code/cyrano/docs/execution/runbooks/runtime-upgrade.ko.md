# 경로 B runtime 코드 배포

상태: 제품 기능 구현 후 사용할 목표 운영 절차. 현재 실제 운영에서 수행한 기록이 아니다. 구현되지 않은 CLI를 가정하지 않는다.

## 선행

관련 WP가 verified이고 해당 작업의 trusted authority와 runtime evidence가 있어야 한다.

## 순서

1. 별도 CYRANO snapshot의 reviewed code diff·CI·clean wheel을 확인한다.
2. 의존성 lock·wheel hash·migration과 rollback plan을 확인한다.
3. 새 환경에 설치하고 actual dcode probes·paired tests를 실행한다.
4. 운영자 approval 뒤 새 process/Run에만 binding한다.
5. 실패하면 호환성에 맞는 approved 복구를 수행한다.

## 즉시 중단 조건

same interpreter hot edit, unreviewed wheel, future DB schema

## 결과 기록

actor·scope·subject digest·actual commands/receipts·미확인 side effects·복구 결과·승인 이력을 로컬 evidence 원장에 연결한다. 성공하지 않은 단계는 완료로 표시하지 않는다.
