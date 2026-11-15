# 4 DDALLA — Session Handoff

- Status: HANDOFF v4 (P1-DB-01B 완료 + 원격 develop 변동 관찰 시점)
- 원칙: 짧고 정확한 사실만 기록. 확인되지 않은 정보는 `미확인`으로 표기. API 키·비밀정보·개인정보 기록 금지. 실제 Git 상태와 다르면 실제 상태를 재확인하고 차이를 보고한다.

## A. 프로젝트 개요

- 서비스: 4 DDALLA(사딸라) — 대한민국 음식점·카페·베이커리의 공식 할인·혜택을 발견·검증해 지도/목록으로 제공하는 반응형 웹. 최초 실증 성남시 분당구 서현역, 기본 반경 800m·선택 1km.
- 현재 단계: P0 설계 기준선 + P1 기초 계약/부트스트랩 구현 완료(로컬). GIT-REORG-01(세션 복구·Git 운영 정리) 완료. P1-DB-01 환경 진단(읽기 전용) 후 P1-DB-01B로 로컬 개발 DB(PostgreSQL 17+PostGIS 3.7) 구축 완료 — 신규 기능 구현은 시작하지 않음.
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

- 로컬 브랜치: `main` = d205bbd(변경 없음), `develop` = 9b937e8 + 본 갱신 로컬 커밋(해시는 작업 보고 참조). HEAD = develop.
- 원격: `origin/main` = d205bbd, `origin/develop` = 9b937e8, `origin/HEAD` → origin/main. ※핸드오프 v1의 "원격 develop 없음" 기재와 불일치 — 2026-11-15 확인 시점에 이미 존재. ※**이 턴 중 `refs/heads/develop`이 4a38fe4→9b937e8로 변동된 것을 `ls-remote`로 확인** — 우리 명령 중 push 없음(외부 요인 추정, 주체·시점 미확인; fetch로 트래킹만 갱신, 삭제·변경 시도 없음).
- 원격 feature 브랜치 3개(`feature/P1-01-bootstrap`, `feature/P1-CONTRACT-01`, `feature/P1-CONTRACT-02`)는 이번 작업에서 삭제 완료(존재·main 포함 관계 선확인 후). `docs/DOC-001-baseline`은 원격 ref 없음(로컬만 존재→삭제).
- 로컬 삭제 브랜치 tip(e46e01d, 6f506b2, b43cbb9, 563e1e6) 모두 main 조상임을 `merge-base --is-ancestor`로 확인 → 커밋/파일 내용 main에 보존. develop은 d205bbd + 문서 커밋들(4a38fe4, 9b937e8, 본 갱신)만큼 앞서며 코드 차이 없음(커밋 stat으로 확인).
- 작업트리 미추적 파일(변경·삭제·추적 금지): `Docs/draft.md`(이전 세션 발견, 보호 대상·미수정). `ses1`(1,434,427B, 2026-11-14 12:47) — 사용자 확인: 세션 대화 백업(민감정보 포함 가능) → 원문 비출력 원칙, 삭제·이동·추적 금지(별도 승인 전).
- 참고: 최종 main 갱신·브랜치 정리 이후 로컬 상태 기준. 그 사이 외부 변경 여부는 보장 불가 → 다음 세션에서 재확인.

## D. 완료 작업(커밋/파일로 검증된 범위)

- DOC-001 문서 기준선: b03027f, e46e01d.
- P1-01 bootstrap(162376f) + 테스트 보완(6f506b2): 스캐폴딩, 계약, 테스트, CI.
- CONTRACT-01 b43cbb9(공유 envelope 계약 강화), CONTRACT-02 563e1e6(엄격 version·unknown-field 정책) → ENGINE_SPEC §12.1에 반영.
- PR #1(fedd3dd), #2·#3(d205bbd) 병합으로 origin/main=d205bbd. (원격 CI 성공은 이전 세션 보고 사실 — 로컬에서 재실행/확인 불가, 미검증.)
- GIT-REORG-01/세션 복구: fetch, `main` eeacba3→d205bbd fast-forward(발산·충돌 없음), `develop` 생성(d205bbd), 로컬 4개 브랜치 안전 삭제(일반 삭제), 원격 3개 feature 브랜치 삭제(승인 범위), AGENTS.md 개정 + 본 HANDOFF 생성. 후속 develop에 문서 커밋 4a38fe4.
- P1-DB-01B 개발 DB 구축(2026-11-15, 로컬·승인 범위): Docker Engine 연결 정상 확인 후 `postgis/postgis:17-3.7` pull, Compose로 컨테이너 `4ddalla-db` 기동(`127.0.0.1:5432` 바인딩), PostgreSQL 17.12 접속, PostGIS 3.7 활성화 확인, 테스트 행 재시작 후 보존 검증(1→1), 테스트 표 삭제. 로컬 전용 `docker/.env` 생성(값 비기록·Git 제외 확인). 상세 §G.

## E. 미완료 작업

- 원격 `develop` push: 미실행(승인 범위 밖) — 현재 원격 `develop` = 9b937e8(존재 확인; 4a38fe4→9b937e8 변동은 이 턴 중 관찰, 외부 요인 추정·주체 미확인).
- main 병합/배포/릴리스: 미실행(사용자 승인 필요).
- P1-DB-01/01B 개발 DB 환경 구성: 로컬 완료 — PostgreSQL 17.12 + PostGIS 3.7, Compose 로컬 실행, 명명 볼륨 영속(재시작 후 데이터 유지 확인), 개발 전용 `docker/.env`(값 비기록·Git 제외). 운영 환경 배포·서비스 스키마 구현 아님.
- Windows 기능(WSL/가상화 관련) 상태 진단 자체는 미확인 — 기능 쿼리 실패, 권한 상승·우회 시도 안 함. 단 Docker Desktop 구동·Engine 연결은 정상 확인되어 DB 작업에는 지장 없었음.
- 원격 CI 상태: 로컬에서 확인 불가(미검증).

## F. 최근 변경 파일

- GIT-REORG-01: `AGENTS.md`(Git 운영 정책·핸드오프 규칙 개정), `Docs/HANDOFF.md`(신규) — develop 커밋 4a38fe4.
- P1-DB-01/01B: 진단(읽기 전용) 후 로컬 DB 구축. 로컬 전용 `docker/.env` 신규 생성 — 값 비기록·`.gitignore` 제외 확인, 커밋 대상 아님. `docker/compose.yaml`·`docker/.env.example` 무변경(기존 구성 그대로 사용). 본 HANDOFF 갱신은 로컬 커밋.
- 이전 병합(d205bbd)에서 4DDALLA_AGENTS.md·4DDALLA_PROJECT_BRIEF.md 삭제 — 커밋 이력으로 보존.
- `frontend/dist/`는 build 산출물(gitignore). 미추적 `Docs/draft.md`·`ses1`은 변경 없음.

## G. 테스트(2026-11-15 실행, 로컬)

- Ruff: `.venv\Scripts\ruff.exe check .` → All checks passed.
- Pytest: `.venv\Scripts\python.exe -m pytest -q` → 70 passed, 1 warning(StarletteDeprecationWarning: httpx/starlette TestClient — 비실패). 실패·스킵 없음.
- 프론트: `npm ci`(44 packages, 감사 0 vulnerabilities) → `npm run test` Vitest 1 file/1 test passed → `npm run build` Vite 8.3.8 성공, `dist/` 생성(gitignore).
- Docker/DB(2026-11-15, 로컬): Docker Desktop 최초 실행·초기 설정(사용자) 후 Engine 연결 정상 — `docker info` ServerVersion **29.9.3**. `docker compose -f docker/compose.yaml up -d db` 정상: 네트워크·볼륨(`docker_db-data`) 생성, 컨테이너 `4ddalla-db` Up, **`127.0.0.1:5432` 바인딩(루프백 전용)**, 기동 로그 "database system is ready to accept connections".
- 접속: `docker exec 4ddalla-db psql -U 4ddalla -d 4ddalla` 성공 — **PostgreSQL 17.12 (Debian 17.12-1.pgdg13+1)**.
- PostGIS: 확장 활성화 확인 — **PostGIS 3.7 USE_GEOS=1 USE_PROJ=1 USE_STATS=1**(`PostGIS_Version()`).
- 영속성: 테스트 표 `persistence_probe` 1행 삽입 → `docker compose restart db`(볼륨 유지, `down -v` 아님) → 재시작 후 1건 확인 → 테스트 표 삭제. 볼륨 `docker_db-data`(driver local) 잔존 — 의도된 영속 데이터 볼륨.
- 이미지: `postgis/postgis:17-3.7` pull 성공(태그 실재 확인).
- 주의(검증 한계): 실제 `.env` 작성 후 `docker compose config` 재실행 안 함(값 출력 가능 — 회피; 기동 성공이 변수 해석의 실제 증명). 전체 `docker inspect`·컨테이너 env 덤프 회피(비밀 노출 방지). 호스트 PATH에 `psql`·네이티브 PostgreSQL 없음(서버는 컨테이너 내; 비전형 설치 경로 배제 못 함 — 미설치 단정 아님). 부트스트랩 스위트는 DB-free(DB 통합 테스트 부재) — 변경 없음.

## H. 개발 환경(관측값)

- Python 3.11.9; `.venv` 사용(관측: pytest 9.2.0, ruff 0.17.3 — requirements 핀 ruff 0.17.4와 불일치 관측).
- Node v24.21.0, npm 11.19.0, Git(로컬 user: Oh-JunTaek <aa39043533@gmail.com>).
- Docker CLI 29.9.3 + compose 플러그인. 컨텍스트 2개: `default`(npipe docker_engine)·`desktop-linux`(진단 시점 현재 선택). 진단 단계에선 `desktop-linux` 엔진 연결이 실패했고 Desktop 실행 파일 일반 경로·서비스·파이프도 미확인이었으나, **사용자가 Docker Desktop 최초 실행·초기 설정을 완료(2026-11-15)한 뒤 Engine 연결 정상 확인**(`docker info` ServerVersion 29.9.3) — 이전 "설치/실행 미확인" 관측은 이 시점 기준으로 해소. 단, 그 이전 항목들은 당시 기준 기록으로 보존.
- WSL: `wsl` 명령 동작. 진단 시점 배포판 목록에 `docker-desktop` Stopped(컬럼 값 2 — 출력 인코딩 일부 깨짐, 판독 한계), `wsl --status` 세부 출력 판독 불가. 이후 WSL 배포판 상태 재측정은 안 함(DB 작업에 불필요 — Engine은 Desktop 컨텍스트로 동작).
- 가상화·하드웨어(CIM 관측값, 신뢰도 한계 명시 — 미지원 단정 금지): HypervisorPresent True, VirtualizationFirmwareEnabled True, SecondLevelAddressTranslationExtensions False, Windows 11 Pro 빌드 26300, AMD Ryzen 5 7500X3D 6코어/12스레드, 물리 메모리 ≈31GiB, 보드 Gigabyte B650M K.
- PostgreSQL: 호스트 PATH·서비스 목록에서 psql/pg_ctl/postgres/initdb 및 postgres 서비스 미발견(비전형 설치 경로 가능성 — 미설치 단정 아님; 서버는 컨테이너로 제공: PostgreSQL 17.12). winget 존재, choco/scoop 미발견.
- .env: 진단 시점 `.env`·`docker/.env` 부재였음(템플릿 `docker/.env.example`만 존재) → P1-DB-01B에서 **로컬 전용 `docker/.env` 생성**(개발 값·값 비기록·`.gitignore` 제외 확인). 템플릿 무변경. line ending: core.autocrlf=true(문서 기재 — 실측 미확인). OS Windows.

## I. 위험 및 미결정

- OPEN-001~011(장소/지도/OCR/LLM/검색/호스팅/로컬→서버 전달/점검주기/보관/알림/DDL·클래스) 미정 — 에이전트 독자 확정 금지(DECISIONS).
- 승인 범위 밖 금지: 원격 push/PR/main 병합/배포, force push·강제 삭제·reset --hard·rebase·cherry-pick·이력 재작성, 승인 범위 밖 main 새 병합·코드 수정.
- `Docs/draft.md`: 사용자 별도 지시 전 수정·삭제·추적 금지, 없어도 재생성 금지.
- `ses1`: 세션 대화 백업(사용자 확인, 1,434,427B) — 민감정보 포함 가능, 원문 비출력 원칙, 삭제·이동·추적 금지(별도 승인 전).
- Windows 시스템 수준 변경(설치·기능 활성화·재부팅·권한 상승)은 승인 범위 아님 — P1-DB-01 진단은 읽기 전용이었고, P1-DB-01B의 이미지 pull·컨테이너 기동은 본 티켓 승인 범위 내 로컬 작업. 다른 프로젝트 Docker 리소스 미변경(진단 시점 컨테이너·볼륨 전무 → 작업 후 `4ddalla-db`·`docker_db-data`만 존재).
- 원격 `develop`(9b937e8) 존재·변동 확인 — 이 턴 중 4a38fe4→9b937e8 변화 관찰(외부 요인 추정, 주체·시점 미확인; 우리 push 없음). 임의 정리 금지(필요 시 사용자 확인).
- docker/.env·컨테이너 DB·볼륨(`docker_db-data`)은 **로컬 개발용**: 비밀번호 등 값은 어떤 문서·보고서·Git에도 기록 금지(준수 — 핸드오프·보고 비기록). 볼륨 삭제 금지(예: `down -v`·volume rm — 향후 티켓 포함). DB 포트는 `127.0.0.1` 바인딩(외부 미노출).
- 애플리케이션–DB 연결 코드는 이번 범위 아님(미구현) — 다음 티켓에서 별도 승인·설계 필요.
- HANDOFF와 실제 상태 불일치 가능(특히 원격·타 세션 변경) → 다음 세션에서 실제 상태 재확인.
- 원격 CI·머지 이후 외부 변경은 로컬에서 검증 불가(미검증).

## J. 다음 세션 지시(우선 순서)

1. `AGENTS.md` 읽기 → 2. 본 `Docs/HANDOFF.md` 읽기 → 3. 해당 명세 읽기 → 4. 실제 상태 재확인: `git status --short`, `git branch -avv`, `git log --oneline -5`, `git rev-parse develop main origin/main`, `git ls-remote --heads origin` — HANDOFF와 다르면 실제 상태 기준 갱신·차이 보고(원격 develop 생성 주체·시점 미확인 — 필요 시 사용자 확인) → 5. 다음 작업은 **현재 사용자 승인 티켓 지시 우선**(로컬 개발 DB 접속 검증됨 — 후속 티켓에서 사용 가능; 스키마/마이그레이션·수집·OCR·LLM·지도 연동은 별도 승인·설계 필요) → 6. 작업 완료·중단·실패·세션 교체 시 HANDOFF 갱신(별도 요청 없어도 필수 완료 조건) → 7. 원격 push/PR/merge/deploy 금지. 새 기능 구현 착수는 승인 티켓 필요.

## K. 최종 갱신

- 갱신: 2026-11-15(KST, 로컬 시각) — P1-DB-01B PostgreSQL+PostGIS 로컬 DB 구축 완료 / 브랜치 `develop` 기준 커밋 9b937e8 + 갱신 커밋 0bc8f61 + 본 갱신 커밋(해시는 작업 보고 참조). ※원격 `develop`은 9b937e8로 관찰됨(이 턴 중 변동, 주체 미확인 — 사용자 확인 권장).
- 본 갱신은 develop 로컬 커밋으로 반영(커밋 해시는 작업 보고에 명시). 핸드오프에 비밀정보 기록 금지 준수 — `.env` 실제 값 미기재.
