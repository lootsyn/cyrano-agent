# 10. 실제 dcode 연결

## 10.1 네이티브 지원과 새 구현을 구분한다

공식 문서에서 확인한 네이티브 surface:
AGENTS/Skills, 파일 기반 subagents, hooks.json의 Stop/PreToolUse/PostToolUse,
실험적 Python extensions의 register_tool/register_middleware가 있다. [S08–S10,S13,S14]

새로 구현할 UDH surface:
`quality_inspect`, `quality_verify`, `quality_status`, `request_completion`,
QualityService, immutable receipts, quality_completion kernel, baseline comparison.
`dcode quality`, 임의 `after_task` Hook, AGENTS의 `tools: read_only`가 이미 있다고 가정하지 않는다.

## 10.2 개발용 1차 연결

기존 root AGENTS에 Python invariant를 merge하고 `.agents/skills/python-engineering/SKILL.md`를
배치한다. native dcode에서 발견·본문 로딩·로컬 검사 수행 여부를 실제로 확인한다.
현재 skill resolution path/digest를 evidence로 남긴다. 이 단계는 local_advisory다.

최초 도입에서는 native config 우선순위에 따라 global skill이 덮였는지, 기존 AGENTS가 중복됐는지,
프로젝트 trust가 필요한 확장/Hook이 실제로 로드됐는지 확인한다. 읽지 않은 Skill을 읽었다고
보고하게 하는 문자열 규칙만으로 통과시키지 않는다.

## 10.3 Python extension 연결

확인된 공식 형태는 아래와 같다. import 가능한 `udh_dcode.quality_bridge`와 실제 service가
구현·설치된 뒤에만 이 adapter를 배포한다. 제공하는 template은 런타임 완제품이 아니다.

```python
from deepagents_code.extensions import ExtensionAPI
from udh_dcode.quality_bridge import build_quality_tools


async def extension(api: ExtensionAPI) -> None:
    """Register the approved quality service tools."""
    for tool in build_quality_tools(cwd=api.cwd):
        api.register_tool(tool)
```

공식 문서는 확장을 experimental로 설명하며, 명시적 experimental gate와 extension discovery가
필요하다고 한다. 설치 버전의 실제 활성화 조건을 adapter capability probe로 검증한다.
일반 프로젝트에서 임의 `.deepagents/extensions` 코드를 자동 신뢰하지 않는다. governed 실행에서는
검토된 extension을 후보 repo 밖의 immutable profile에서 로드한다. [S14]

`build_quality_tools`는 model-facing input을 최소화한다. tool docstring은 실제 입력과 반환 의미를
설명하며 tool schema 추론 오류가 없도록 작성한다. user/session/attempt binding은 서버 context에서
얻고 prompt의 임의 workspace/attempt ID를 신뢰하지 않는다. 인증 credential은 model에 전달하지 않는다.

quality_verify는 trusted registry의 현재 attempt에 대해서만 동기 실행한다. 취소와 timeout을
controller에 전파한다. tool 결과는 report_id/verdict/진단 excerpt/evidence refs를 포함한다.
request_completion은 승인 서비스에 제한된 요청을 전달할 뿐 상태를 직접 설정하지 않는다.

## 10.4 Hook 사용 범위

PreToolUse: Edit/Write의 명시적 경로를 빠르게 검사해 허가되지 않은 편집을 사용자에게 안내한다.
Bash 문자열 정규식으로 모든 우회 쓰기·import·shell redirection을 차단했다고 주장하지 않는다.
실제 강제는 sandbox의 쓰기 scope와 controller의 postimage guard가 담당한다.

PostToolUse: 변경 신호와 짧은 점검 피드백을 기록한다. 이미 실행된 작업을 취소했다고 표시하지 않는다.
Stop: controller에 해당 prompt/attempt의 현재 quality status를 조회한다. PASS/valid review면 종료를
허용한다. missing/fixable이면 제한된 재작업 피드백을 반환한다. 사용자 취소/실행 불가/예산 소진이면
대화 종료를 허용하지만 UDH 상태는 CANCELLED/BLOCKED를 유지한다.

Stop의 반환 예:

```json
{"decision":"block","reason":"현재 snapshot의 필수 검증이 없습니다. quality_verify를 실행하세요."}
```

공식 Hook에서 JSON은 exit 0일 때 처리되며, exit 2는 event별 blocking/feedback으로 동작한다.
그 외 nonzero와 timeout은 non-blocking failure다. Stop continuation에도 상한이 있으므로
Hook만으로 완료 강제를 보장할 수 없다. **Hook 실패·상한 도달·미설치 여부와 무관하게 controller에
유효한 completion receipt가 없으면 제품 작업 상태는 성공이 아니다.** [S13]

## 10.5 Hook handler 구현 절차

stdin JSON을 1 MiB 이하로 읽고 `hook_event_name`, `session_id`, optional prompt_id를 검증한다.
`cwd`와 `transcript_path`를 임의 read 명령의 인자로 사용하지 않는다. trusted session mapping으로
workspace를 조회하며 unknown이면 diagnostic + 미완료 유지다.

status lookup 내부 deadline은 2초, Hook timeout은 5초로 둔다. Hook은 테스트 전체를 실행하지 않는다.
stdout에는 유효 JSON 하나만, 로그는 stderr에 출력한다. credentials/전체 transcript를 출력하지 않는다.
`stop_hook_active` 및 controller repair count를 함께 확인하고 자기 반복을 무한히 만들지 않는다.

handler crash/timeout 시 native dcode가 종료해도 external launcher는 completion store를 확인한다.
launcher의 최종 machine-readable result는 `assistant_message`와 `work_status`를 분리한다.
사용자의 취소·질문 대답·blocked 보고를 gate 미통과라는 이유로 영원히 막지 않는다.

## 10.6 capability tests

필수 probes: dcode distribution version, SDK/extension import, Skill 발견 경로, 두 AGENTS 결합 여부,
확장 tool 등록·호출, Stop block/allow/timeout, cancellation, tool names, reviewer read-only isolation,
remote sandbox 내부 repo mapping, checkpoint resume, runtime/profile pin.

실제 지원이 확인되지 않은 기능은 UNSUPPORTED_CAPABILITY로 보고한다. import 성공만으로
모델이 tool을 호출한 E2E 성공이라고 기록하지 않는다. dcode auto update를 실험 중 비활성화하고
pin을 변경할 때 이 contract test를 다시 실행한다. [S08]
