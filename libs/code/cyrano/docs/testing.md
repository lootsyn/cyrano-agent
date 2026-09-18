# 테스트 문서 위치

[현재40점 테스트 전략](testing/STRATEGY.ko.md)이15개 평가 항목과 실제 evidence를 정의한다. [증거와 점수](testing/EVIDENCE_AND_SCORING.ko.md), [상세90사례](../tests/assessment/cases.json), [Python60사례](../tests/assessment/python-pack-cases.json), [테스트 개발계획](development/test-work-plan.json), [실행 runbook](execution/TEST_RUNBOOK.ko.md)이 구현 기준이다.

`tests/unit_tests/cyrano/`의 준비·순수함수 검사는 제품 보안·효과 증거가 아니다. mandatory 제품 tests의 missing/0/skip/xfail은 blocked다. negative testcase의 성공은 실제 거부와 부작용 부재를 oracle로 검증한 경우만 뜻한다. 실제 native upstream regression도 별도로 실행해야 한다.
