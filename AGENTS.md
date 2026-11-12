# AGENTS.md — 4 DDALLA Coding Agent Rules

> OpenCode + EXAONE 2.5에 적용. 현재 단계: 설계 기준선 수립 완료, 실제 구현/테스트는 별도 티켓 승인 필요.

## 1. 프로젝트

4 DDALLA(사딸라): 대한민국 음식점·카페·베이커리의 공식 할인·혜택을 발견·검증하여 서현역부터 지도 기반으로 제공하는 반응형 웹 서비스. 기본 반경 800m/선택 1km. 사용자가 접속할 때 수집·OCR·LLM 호출 금지.

## 2. 업무 시작 전에 읽을 문서

1. `AGENTS.md`
2. `Docs/PRODUCT_SPEC.md` — 사용자 정책 P-001~P-019
3. `Docs/ARCHITECTURE.md` — 전체 구성과 서버/로컬 책임
4. `Docs/DATA_MODEL.md` — 관계·무결성·이력
5. `Docs/ENGINE_SPEC.md` — **공통 Enum과 모듈 계약**
6. `Docs/DECISIONS.md` — 미정 공급자·검증 과제
7. 현재 사용자 승인 티켓

**문서 간 충돌을 발견하면 해당 작업을 멈추고 정확한 절·대안·영향을 보고한다.** 임의 결정 금지. 구 버전의 예시 JSON보다 현재 `Docs/ENGINE_SPEC.md`가 우선한다.

## 3. 역할과 권한

- 제품 정책 및 주요 설계 최종 결정: 사용자와 설계 검토 역할의 ChatGPT.
- 구현·테스트·작업 보고: EXAONE.
- 코드/diff·테스트 증거 검토: ChatGPT 및 사용자.
- `main` 병합·푸시·배포 최종 승인: 사용자.

**허용된 티켓 내에서:** 작업 브랜치 생성, 코드와 테스트 작성, 관련 문서 갱신, 로컬 명령 및 테스트, 로컬 커밋.

**명시적 승인 필요:** remote push, PR 생성, main 병합, 배포, 유료 서비스 가입/호출, 비인가 외부 API 연결, 계약 깨는 스키마 변경, 정책 변경, 대규모 범위 외 리팩터링.

## 4. Git 정책

- `main`: 검수 및 승인된 안정 기준선
- `feature/<ticket-id>-<short-name>`, `fix/*`, `docs/*`, `chore/*`
- 단일 티켓의 작고 검수 가능한 변경을 선호. `develop` 브랜치 불필요.
- 작업 전 `git status`/현재 브랜치 확인. 기존 변경사항을 덮어쓰거나 강제 reset 금지.
- 사용자 승인 없이 push/PR/merge/deploy 금지. 승인 시 squash merge 권장.

## 5. 구현 불변식

1. 모든 모듈 경계에 Pydantic 계약과 단일 공유 Enum 사용.
2. 공식성 확인, 수집 권한, 행사 검증, 매장 적용, 공개 상태는 서로 다른 판정.
3. 출처 근거 없는 가격·기간·매장 적용 추론 금지.
4. 쿠폰·시간대·주문 방식·제외 지점의 미해결 조건을 숨기지 않는다.
5. OCR/LLM 결과는 후보. 최종 공개는 서버가 결정한다.
6. 동일 콘텐츠 재처리 및 워커 재시도에 따른 결과 중복 방지.
7. 운영자 수동 수정은 증거 없이 덮어쓰지 않는다.
8. 로컬 PC 자원 사용은 선택적인 배치 처리; PC 미가동 시 서버 조회 유지.
9. 장소 공급자/웹/SNS의 이용조건을 확인하기 전 원본 영구 저장·자동 수집·AI 전송 금지.
10. 모든 실패 발생 건 기록, 민감한 값은 로그에서 제거.
11. 사용자 요청 시 OCR·LLM·실시간 웹 수집 실행 금지.
12. 공급자 미정 상태에서 특정 지도/OCR/LLM API 하드코딩 금지.

## 6. 필수 검증

1. 해당 티켓·현재 브랜치·기존 변경 파일 확인.
2. 영향받는 문서·계약·데이터 권한 확인.
3. 실패 재현 테스트 또는 기능 수용 테스트 작성.
4. 티켓 범위 내 구현.
5. 포맷·린트·단위 테스트 실행.
6. 계약 테스트 및 관련 통합 테스트(허용된 범위만) 실행.
7. 스키마 마이그레이션이 있다면 업·다운·재실행 검증.
8. 최종 diff 및 비밀정보 노출 검사.
9. 미실행/실패/건너뛴 테스트를 통과로 보고하지 않는다.

## 7. 완료 보고 형식

```text
Ticket: <ID, title>
Summary: <what changed, why>
Changed files: <added/modified/deleted>
Contract & migrations: <compatibility and impacts>
Verification: <commands, exact pass/fail/skip results>
Security/data rights: <checks, unresolved items>
Known limitations: <unverified behavior>
Git: <branch, commit, push/PR state>
Approval needed: <exact requested action>
```

## 8. 1차 구현 범위 가이드

첫 승인 티켓은 저장소 스캐폴딩, FastAPI/Vite 최소 구동, PostgreSQL/PostGIS 로컬 연결, 공통 Enum·Pydantic 계약 골격, 테스트·CI 기본 환경을 대상으로 한다. **실제 스크래핑, 지도 API 연동, OCR/LLM 상용 연결, 자동 공개는 제외.** 외부 유료 API 키 없이 로컬에서 실행·테스트 가능해야 한다.

## 9. 문서 상태 주의

현재 6개 문서는 설계 계약 기준선이다. SQL DDL과 구체 Pydantic 클래스, 실제 외부 공급자 권한은 **미구현/미검증**. 문서에 표시된 계약 버전을 코드 릴리스 완료로 해석하지 않는다.
