# CYRANO product plugin

이 폴더는 공식 dcode Python extension manifest와 runtime skill/역할 원본이다. 개발 assistant용 `.agents/skills`와 구분한다. 고객 repo에 이 폴더를 복사하는 설치 방식은 사용하지 않는다.

manifest는 확인된 `com.langchain.deepagents.code.pythonExtensions` 항목만 사용한다. 다른 JSON 구성은 CYRANO가 읽을 계획이며 dcode native role config라고 주장하지 않는다. 역할 바인딩은 WP06에서 공식 extension/subagent 표면과 연결한다.

현재 extension은 명시적 diagnostic만 제공하며 기본 미구현 runtime은 오류로 종료한다. setup 실패를 dcode가 기록하고 계속 시작할 수 있으므로 외부 launcher가 health attestation 없이 업무를 dispatch하지 않아야 한다.

configs/skills/*.template.json의 scope는 배포 시 binding해야 하고 status=candidate, approval/release=null이다. 이것을 active skill release로 오인하지 않는다. 모든 resource와 prompt는 hash로 고정하고 native loader root·duplicate·inheritance를 실제 probe한다.
