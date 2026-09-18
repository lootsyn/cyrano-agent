# dcode runtime 검증 경계

`requirements.in`은 공식 upstream main에서 관측한 deepagents-code0.1.69를 조사 입력으로 기록한다. 이 artifact가 현재 환경에 설치되었거나 호환성 검증을 통과했다는 의미가 아니다. runtime-lock.template.json의 null과 not_tested를 가짜 값으로 채우지 않는다.

`python scripts/probe_runtime.py`는 distribution metadata와 executable 존재만 읽는다. 모델/프로세스를 실행하거나 package를 설치하지 않는다. WP00에서 실제 wheel/source hash·dependency lock·공식 API·probe 결과를 수집하여 runtime-lock.json을 생성한다.

plugins/cyrano/extension.py는 명시적 advisory_diagnostics에서 읽기 전용 상태 도구만 등록할 수 있다. 기본 production 연결은 아직 없고 fail closed한다. 실제 실행 bridge·tool interception·approval·격리는 WP03/06에서 구현해야 한다. extension 파일의 존재를 governed launch 근거로 사용하지 않는다.
