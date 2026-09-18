# R5 실행 증거의 수준

`test_r5_foundation.py`는 실제 Python 순수 코드를 실행한다. IndexBinding·경로·read capability·memory delta·MonitorProjection·toolchain 동의/lock 전제를 검사한다. 외부 서버나 제품 DB를 시작하지 않으므로 이 결과는 product integration PASS가 아니다.

`check_r5.py`는 RF 의존성·문서 route·현재 전체 사례 연결·23개 schema fixture·목표 SQL DDL을 검사한다. 72개 신규 제품 사례의 execution_status는 not_run을 유지한다. template test는 실제 suite에 연결하기 전까지 수용 통과 수에 포함하지 않는다.

`monitor_demo.py`는 합성 JSON·HTML 또는 optional Textual component를 보여 준다. Textual이 없을 때는 blocked를 반환한다. HTML screenshot은 문서/화면 설계 검토이지 제품 UI Pilot 테스트나 native 계측 증거가 아니다.

도구별 resolve/install/probe, 실제 dcode import/build, OS isolation, 제공자 cache, memory/skill 개선의 효과는 별도 RF 증거다. 품질 도구 미설치·스타일 부채를 fixture 검사로 통과시키지 않는다. 공식 rubric 상태는 not_evaluated다.
