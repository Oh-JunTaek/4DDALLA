# 4 DDALLA — Session Handoff

- Status: HANDOFF v1 (GIT-REORG-01 / 세션 복구 시점)
- 원칙: 짧고 정확한 사실만 기록. 확인되지 않은 정보는 `미확인`으로 표기. API 키·비밀정보·개인정보 기록 금지. 실제 Git 상태와 다르면 실제 상태를 재확인하고 차이를 보고한다.

## A. 프로젝트 개요

- 서비스: 4 DDALLA(사딸라) — 대한민국 음식점·카페·베이커리의 공식 할인·혜택을 발견·검증해 지도/목록으로 제공하는 반응형 웹. 최초 실증 성남시 분당구 서현역, 기본 반경 800m·선택 1km.
- 현재 단계: P0 설계 기준선 + P1 기초 계약/부트스트랩 구현 완료(로컬). GIT-REORG-01(세션 복구·Git 운영 정리) 완료. 신규 기능 구현은 시작하지 않음.
- 기술 스택(설계 기준선): Frontend React + TypeScript + Vite / Backend Python + FastAPI + Pydantic / DB PostgreSQL + PostGIS / 백그라운드 PostgreSQL 작업 큐 + Python 워커. OCR·LLM·지도/장소·호스팅 공급자는 미정(DECISIONS OPEN-001~011). 개발 에이전트 OpenCode + EXAONE 2.5(런타임 OCR/LLM과 별개).

## B. 문서 기준선(유효·우선순위)

1. `AGENTS.md` — 운영/권한/Git 규칙(최상위). 문서 간 충돌 시 작업 중단·보고.
2. `Docs/HANDOFF.md` — 본 인수인계 문서.
3. `Docs/ENGINE_SPEC.md` v1.0.0 — 공통 Enum/모듈 계약. §12.1은 P1-CONTRACT-02(2026-11-14) 구현 확정 사항.
4. `Docs/PRODUCT_SPEC.md` v1.0.0(2026-11-12 보완) — 정책 P-001~P-020.
5. `Docs/ARCHITECTURE.md` v1.0.0 — 구성/서버·로컬 책임.
6. `Docs/DATA_MODEL.md` v1.0.0 — 논리 스키마 기준선. 물리 SQL DDL·마이그레이션 미검증.
7. `Docs/DECISIONS.md` v1.0.0 — ADR-001~015, 미정 OPEN-001~011.
8. `Docs/BACKLOG.md` — 골격(DRAFT), 세부 다수 `미확정`.
9. `Docs/LOCAL_DEV.md` — Windows 로컬 개발/검증 가이드(부트스트랩 범위).

## C. 실제 Git 상태(2026-11-15 로컬 확인)

- 로컬 브랜치: `main` = d205bbd, `develop` = d205bbd(이번 작업에서 생성). HEAD = develop.
- 원격: `origin/main` = d205bbd, `origin/HEAD` → origin/main. 원격 `develop` 없음(푸시 안 함·승인 필요).
- 원격 feature 브랜치 3개(`feature/P1-01-bootstrap`, `feature/P1-CONTRACT-01`, `feature/P1-CONTRACT-02`)는 이번 작업에서 삭제 완료(존재·main 포함 관계 선확인 후). `docs/DOC-001-baseline`은 원격 ref 없음(로컬만 존재→삭제).
- 로컬 삭제 브랜치 tip(e46e01d, 6f506b2, b43cbb9, 563e1e6) 모두 main 조상임을 `merge-base --is-ancestor`로 확인 → 커밋/파일 내용 main에 보존. main·develop 트리 동일(`git diff --stat` 공란).
- 작업트리 미추적 파일(변경·삭제·추적 금지): `Docs/draft.md`(이전 세션 발견, 보호 대상), `ses1`(1,434,427B, 앞부분 `{"info":` JSON 텍스트로 보이나 정체 미확인 — 읽기만 수행, 내용 미확인).
- 참고: 최종 main 갱신·브랜치 정리 이후 로컬 상태 기준. 그 사이 외부 변경 여부는 보장 불가 → 다음 세션에서 재확인.

## D. 완료 작업(커밋/파일로 검증된 범위)

- DOC-001 문서 기준선: b03027f, e46e01d.
- P1-01 bootstrap(162376f) + 테스트 보완(6f506b2): 스캐폴딩, 계약, 테스트, CI.
- CONTRACT-01 b43cbb9(공유 envelope 계약 강화), CONTRACT-02 563e1e6(엄격 version·unknown-field 정책) → ENGINE_SPEC §12.1에 반영.
- PR #1(fedd3dd), #2·#3(d205bbd) 병합으로 origin/main=d205bbd. (원격 CI 성공은 이전 세션 보고 사실 — 로컬에서 재실행/확인 불가, 미검증.)
- GIT-REORG-01/세션 복구: fetch, `main` eeacba3→d205bbd fast-forward(발산·충돌 없음), `develop` 생성(d205bbd), 로컬 4개 브랜치 안전 삭제(일반 삭제), 원격 3개 feature 브랜치 삭제(승인 범위), AGENTS.md 개정 + 본 HANDOFF 생성.

## E. 미완료 작업

- 원격 `develop` push: 미실행(승인 범위 밖).
- main 병합/배포/릴리스: 미실행(사용자 승인 필요).
- 다음 승인 티켓의 기능 작업: 미시작(이번 범위는 기존 작업 재개·정리·문서).
- Docker/PostgreSQL 통합 검증: 미실행(사유는 G).
- 원격 CI 상태: 로컬에서 확인 불가(미검증).

## F. 최근 변경 파일

- 이번 세션: `AGENTS.md`(Git 운영 정책·핸드오프 규칙 개정), `Docs/HANDOFF.md`(신규).
- 이번 세션에서 위 2개 외 파일 수정·삭제 없음. `frontend/dist/`는 build 산출물(gitignore).
- 이전 병합(d205bbd)에서 4DDALLA_AGENTS.md·4DDALLA_PROJECT_BRIEF.md 삭제 — 커밋 이력으로 보존, `git cat-file`/이력 확인 가능.
- 미추적 2건(Docs/draft.md, ses1)은 변경 없음.

## G. 테스트(2026-11-15 실행, 로컬)

- Ruff: `.venv\Scripts\ruff.exe check .` → All checks passed.
- Pytest: `.venv\Scripts\python.exe -m pytest -q` → 70 passed, 1 warning(StarletteDeprecationWarning: httpx/starlette TestClient — 비실패). 실패·스킵 없음.
- 프론트: `npm ci`(44 packages, 감사 0 vulnerabilities) → `npm run test` Vitest 1 file/1 test passed → `npm run build` Vite 8.3.8 성공, `dist/` 생성(gitignore).
- 미실행: Docker·PostgreSQL 계열 — `docker info` 데몬 미도달(fail), `docker compose` CLI만 존재, `psql` PATH 미설치, 부트스트랩 스위트는 DB-free(DB 통합 테스트 부재), `docker/compose.yaml`·이미지 태그 미검증. → 통과로 보고하지 않음.

## H. 개발 환경(관측값)

- Python 3.11.9; `.venv` 사용(관측: pytest 9.2.0, ruff 0.17.3 — requirements 핀 ruff 0.17.4와 불일치 관측).
- Node v24.21.0, npm 11.19.0, Git(로컬 user: Oh-JunTaek <aa39043533@gmail.com>).
- Docker CLI 29.9.3 + compose 플러그인 존재, 데몬 미실행. psql 미설치.
- line ending: core.autocrlf=true(문서 기재 — 실측 미확인). OS Windows.

## I. 위험 및 미결정

- OPEN-001~011(장소/지도/OCR/LLM/검색/호스팅/로컬→서버 전달/점검주기/보관/알림/DDL·클래스) 미정 — 에이전트 독자 확정 금지(DECISIONS).
- 승인 범위 밖 금지: 원격 push/PR/main 병합/배포, force push·강제 삭제·reset --hard·rebase·cherry-pick·이력 재작성, 승인 범위 밖 main 새 병합·코드 수정.
- `Docs/draft.md`: 사용자 별도 지시 전 수정·삭제·추적 금지, 없어도 재생성 금지.
- `ses1`: 정체 미확인 대형(1.4MB) 미추적 파일 — 삭제·이동·추적 금지, 내용 미확인.
- HANDOFF와 실제 상태 불일치 가능(특히 원격·타 세션 변경) → 다음 세션에서 실제 상태 재확인.
- 원격 CI·머지 이후 외부 변경은 로컬에서 검증 불가(미검증).

## J. 다음 세션 지시(우선 순서)

1. `AGENTS.md` 읽기 → 2. 본 `Docs/HANDOFF.md` 읽기 → 3. 해당 명세(ENGINE_SPEC 등) 읽기 → 4. 실제 상태 재확인: `git status --short`, `git branch -avv`, `git log --oneline -5`, `git rev-parse develop main origin/main` — HANDOFF와 다르면 실제 상태 기준 갱신·차이 보고 → 5. 승인 티켓 작업 착수 시 `develop`에서 작업, 티켓별 신규 브랜치 만들지 않고 로컬 커밋으로 구분 → 6. 작업 완료·중단·실패·세션 교체 시 HANDOFF 갱신(별도 요청 없어도 필수 완료 조건) → 7. 원격 push/PR/merge/deploy는 사용자 승인 전 금지. 새 기능 구현 착수는 이번 범위 아님(승인 티켓 필요).

## K. 최종 갱신

- 갱신: 2026-11-15(KST, 로컬 시각) — GIT-REORG-01/세션 복구 작업 브랜치 `develop` 기준 커밋 d205bbd.
- 본 문서 + `AGENTS.md` 개정은 단일 로컬 커밋으로 develop에 반영(커밋 해시는 최종 보고에 명시).
