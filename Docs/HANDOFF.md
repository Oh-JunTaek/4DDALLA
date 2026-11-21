# 4 DDALLA — Session Handoff

- Status: HANDOFF v15 (P1-DB-02B 라이브 검증·마무리 완료·로컬 커밋 / P1-DB-HARDEN-01 로컬 완료(8edd333·c3fd0e6·1a438e5 등) / P1-DB-HARDEN-02 안정화 항목 로컬 완료(77140e0·4dcf7ae)·기본 검증 통과 / 2026-11-19 Engine 접속 회복→라이브 부분 재검증(§G), 잔여 항목 보류 / P1-DATA-01 물리 모델 설계 초안(9cdd1bd) → **1차 도메인 스키마 구현(2026-11-21, 로컬·미적용, §M**: ORM+002 작성·구현 검사 통과·라이브/적용 미실행 / 원격 push·main 병합·배포는 사용자 승인 대기)
- 원칙: 짧고 정확한 사실만 기록. 확인되지 않은 정보는 `미확인`으로 표기. API 키·비밀정보·개인정보 기록 금지. 실제 Git 상태와 다르면 실제 상태를 재확인하고 차이를 보고한다.

## A. 프로젝트 개요

- 서비스: 4 DDALLA(사딸라) — 대한민국 음식점·카페·베이커리의 공식 할인·혜택을 발견·검증해 지도/목록으로 제공하는 반응형 웹. 최초 실증 성남시 분당구 서현역, 기본 반경 800m·선택 1km.
- 현재 단계: P0 설계 기준선 + P1 기초 계약/부트스트랩 구현 완료(로컬). GIT-REORG-01(세션 복구·Git 운영 정리) 완료. P1-DB-01 환경 진단(읽기 전용) 후 P1-DB-01B로 로컬 개발 DB(PostgreSQL 17+PostGIS 3.7) 구축 완료. 이어서 P1-DB-02(앱–DB 연결·마이그레이션 기반) 구현·로컬 커밋, P1-DB-02B로 라이브 DB 통합 테스트·Alembic 온라인 검증·마무리 완료(2026-11-16, 로컬; 엔진 재기동 포함 — 데이터 볼륨 무변경). 이후 P1-DB-HARDEN-01(코드 리뷰 후속) 지시 접수 — 읽기 전용 분석(§K) 후 ①·② 구현·검증·커밋(2026-11-17; 커밋 6121953), ③ 문서화·설정 검증까지 로컬 완료(핸드오프 v9). 2차 코드 리뷰 지시(2026-11-17)는 ① skip 조건 실제 평가화·실행 검증·스크래치 대상 검증, ② 연결 장애 503 정규화 — 로컬 구현·기본 검증·커밋 완료(8edd333·c3fd0e6; 핸드오프 v10). 라이브 DB 전건·격리 실제 실행·컨테이너 health는 Engine 접속 불가로 보류·미실행. 2026-11-18 검증 시도 — 비-DB 회귀 통과, 라이브 검증은 Engine 3회 재시도 미도달로 보류(사용자 기동 필요). 같은 날 P1-DB-HARDEN-02 안정화 항목(격리 필수 실행 보장·오류 분류 정밀화·rollback 견고성) 코드·테스트 로컬 처리·기본 검증·커밋.
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
9. `Docs/LOCAL_DEV.md` — Windows 로컬 개발/검증 가이드(부트스트랩 범위; 2026-11-17 DB 검증 티어·현황 갱신 반영).

## C. 실제 Git 상태(2026-11-20 로컬 확인·원격 재확인; 원격 관찰 11-18~19)

- 로컬 커밋: 4a38fe4(GIT-REORG-01 문서)·0bc8f61·a3d1d4b(핸드오프 v4)·5fac38e(P1-DB-02)·40d38db(핸드오프 v5)·d385ddd(핸드오프 v5 계보 보정)·1a7af5a(Alembic path_separator)·65f30e3(핸드오프 v7)·6121953(P1-DB-HARDEN-01 ①·②)·2e87668(핸드오프 v8)·6c83a71(③ compose)·b216e8d(③ LOCAL_DEV)·284150f(핸드오프 v9)·8edd333(2차 리뷰 ② 소스)·c3fd0e6(2차 리뷰 ①·테스트)·1a438e5(핸드오프 v10)·59fe67b(핸드오프 v11)·77140e0(P1-DB-HARDEN-02 ② 소스)·4dcf7ae(P1-DB-HARDEN-02 ①·테스트)·b1e2db0(핸드오프 v12)·2ed9b31(핸드오프 v11-18 정정)·50738e3(핸드오프 v12 수치 정정)·9cdd1bd(P1-DATA-01 설계 초안·v13). HEAD = develop.
- 원격 `develop`: 11-18 `ls-remote` 59fe67b → 2026-11-19 확인 → 이번 세션 재확인 **50738e3**(로컬 원격추적 ref와 일치). 이후 원격이 추가 전진해 **cabc15a**(11-21 확인) — 반영 경로·시점 미확인(외부 요인 단정 안 함) → 사용자 확인 권장·임의 정리 금지. ※핸드오프 v1의 "원격 develop 없음" 기재와 불일치 — 2026-11-15 확인 시점에 이미 존재. ※4a38fe4→9b937e8 변동은 이전 턴(P1-DB-01B) 관찰.
- 원격 feature 브랜치 3개(`feature/P1-01-bootstrap`, `feature/P1-CONTRACT-01`, `feature/P1-CONTRACT-02`)는 이번 작업에서 삭제 완료(존재·main 포함 관계 선확인 후). `docs/DOC-001-baseline`은 원격 ref 없음(로컬만 존재→삭제).
- 로컬 삭제 브랜치 tip(e46e01d, 6f506b2, b43cbb9, 563e1e6) 모두 main 조상임을 `merge-base --is-ancestor`로 확인 → 커밋/파일 내용 main에 보존. develop의 main(d205bbd) 대비 진전: 문서·P1-DB 시리즈·핸드오프 커밋(상세 §D·§L).
- 커밋(최신 9cdd1bd) 이후 기준 작업트리: 추적 파일 변경·삭제 없음(2026-11-19 확인). 로컬 `develop` = 9cdd1bd, 로컬 원격추적 ref = 50738e3, 네트워크 `ls-remote` = 50738e3 — 마지막 확인 시점 정합(세 참조 중 2개 일치·로컬이 최신). 경로·시점 미확인(§C·§I). 미추적 파일(변경·삭제·추적 금지): `Docs/draft.md`(이전 세션 발견, 보호 대상·미수정). `ses1`(1,434,427B, 2026-11-14 12:47) — 사용자 확인: 세션 대화 백업(민감정보 포함 가능) → 원문 비출력 원칙, 삭제·이동·추적 금지(별도 승인 전).
- 참고: 최종 main 갱신·브랜치 정리 이후 로컬 상태 기준. 그 사이 외부 변경 여부는 보장 불가 → 다음 세션에서 재확인.

## D. 완료 작업(커밋/파일로 검증된 범위)

- DOC-001 문서 기준선: b03027f, e46e01d.
- P1-01 bootstrap(162376f) + 테스트 보완(6f506b2): 스캐폴딩, 계약, 테스트, CI.
- CONTRACT-01 b43cbb9(공유 envelope 계약 강화), CONTRACT-02 563e1e6(엄격 version·unknown-field 정책) → ENGINE_SPEC §12.1에 반영.
- P1-DB-HARDEN-01 ①·② 로컬 구현·기본 검증(2026-11-17, 커밋 6121953): ①왕복 테스트를 기본 실행 경로에서 분리(명시적 opt-in 게이트)하고, 파싱된 URL 성분(dialect·loopback host·port·비보호 DB명 — 이름만으로 판정 금지) 검증 통과 시에만 UUID 스크래치 DB에서 업그레이드/다운그레이드/재적용 + 생성·정리(강제 드롭·잔존 확인·실패 시 보장)·부정 가드 단위 테스트 ②DB 오류 경계 테스트(연결 실패 503 정적 본문·자격증명/접속정보 비노출·롤백·커넥션 반환, 비연결 SQLAlchemyError 500 비-503) — 기본 실행 DB-free 유지. 상세 §G·§K.
- P1-DB-HARDEN-01 2차 리뷰(사용자 지시, 2026-11-17) 수정: ① skip 조건을 즉시 평가되는 bool로 변경 — opt-in 시 반드시 실행(기존 lambda는 pytest가 callable을 bool() 처리해 상시 skip이었음), 비활성화 시 정상 skip, 잘못된 값은 명시적 수집 실패; 실행·스크래치 대상 검증 강화 ② `get_db`가 연결 장애급 SQLAlchemy/psycopg 예외를 DatabaseUnavailableError로 정규화 — 제약 위반·쿼리 오류 비-503, rollback·세션 종료 유지, 접속정보 비노출; 무-DB 실제 요청 503 테스트·분류기 단위 테스트 추가. 커밋 8edd333·c3fd0e6; 기본 스위트 108 passed/8 skipped·Ruff 통과; 라이브 전건·격리 실제 실행은 환경 보류(§G·§K).
- P1-DB-HARDEN-01 ③ 로컬 처리(2026-11-17): `docker/compose.yaml` db healthcheck 추가(`docker compose config` 파싱 확인 — 런타임 health 미검증; 커밋 6c83a71), `Docs/LOCAL_DEV.md` DB 검증 티어·로컬 DB 현황 갱신(커밋 b216e8d), sessionmaker 검토 기록, `001` 처리 방침 문서 제안(제품 결정 필요). 상세 §G·§K.
- P1-DB-HARDEN-02(2차 안정화, 2026-11-18, 커밋 77140e0·4dcf7ae): 격리 검증을 클래스 레벨 skipif 영향 밖(모듈 레벨)으로 이동 — 옵트인 시 전제 미충족(URL 없음)이 skip이 아닌 실패로 드러남; 오류 분류를 cause 기반(클래스명 단독 판정 금지)으로 정밀화 + rollback 실패 시 원 오류·분류 보존(정적 로그); 분류기 단위·롤백 실패·무-DB 실제 요청 503·옵트인 규칙 테스트 추가. 기본(DB-free) 실행 유지.
- 핸드오프 문서 갱신 v8·v9·v10·v11·v12·v13 (2026-11-17~19; 문서 커밋 2e87668·284150f·1a438e5·59fe67b·b1e2db0·2ed9b31·50738e3·9cdd1bd; 9cdd1bd = v13 초안 문서 반영). 코드 커밋 77140e0·4dcf7ae(2차 안정화)는 별도.
- PR #1(fedd3dd), #2·#3(d205bbd) 병합으로 origin/main=d205bbd. (원격 CI 성공은 이전 세션 보고 사실 — 로컬에서 재실행/확인 불가, 미검증.)
- GIT-REORG-01/세션 복구: fetch, `main` eeacba3→d205bbd fast-forward(발산·충돌 없음), `develop` 생성(d205bbd), 로컬 4개 브랜치 안전 삭제(일반 삭제), 원격 3개 feature 브랜치 삭제(승인 범위), AGENTS.md 개정 + 본 HANDOFF 생성. 후속 develop에 문서 커밋 4a38fe4.
- P1-DB-01B 개발 DB 구축(2026-11-15, 로컬·승인 범위): Docker Engine 연결 정상 확인 후 `postgis/postgis:17-3.7` pull, Compose로 컨테이너 `4ddalla-db` 기동(`127.0.0.1:5432` 바인딩), PostgreSQL 17.12 접속, PostGIS 3.7 활성화 확인, 테스트 행 재시작 후 보존 검증(1→1), 테스트 표 삭제. 로컬 전용 `docker/.env` 생성(값 비기록·Git 제외 확인). 상세 §G.
- P1-DB-02 앱–DB 연결·마이그레이션 기반(2026-11-16, 로컬·승인 범위): `app/db` 패키지(config·engine·errors·base·dependencies), `app/main.py` 핸들러 등록, 의존성 핀(Alembic==1.20.1·SQLAlchemy==2.0.57·psycopg[binary]==3.3.9 — 로컬 `.venv` 설치), `alembic.ini`+`alembic/env.py`+최초 마이그레이션(검증용 임시 표 `p1db02_migration_probe`, 도메인 테이블 없음), 통합 테스트 `tests/test_db_layer.py`. 로컬 커밋 5fac38e.
- P1-DB-02B 라이브 검증·마무리(2026-11-16, 로컬·승인 범위): 엔진 접속 확인, 정지돼 있던 컨테이너 `4ddalla-db` 기동(볼륨 무변경), `tests/test_db_layer.py` 라이브 4건 포함 15 passed, Alembic 온라인 왕복(base→001→downgrade→재적용; 최종 001 적용 — 검증 표만 추가, 기존 데이터·확장 표 보존), `alembic.ini` path_separator 보강(1a7af5a). 상세 §G·§K.

## E. 미완료 작업

- 원격 `develop` push: 미실행(승인 범위 밖). 로컬 `develop` = 9cdd1bd 계열, 원격 `develop`(**cabc15a**, 최근 확인) 대비 로컬 1커밋 앞섬(c55b4b6 — 본 티켓 구현). 반영 경로 주체·시점 미확인(§C·§I). 로컬 원격추적 ref = cabc15a. 이 세션 push·fetch·원격 쓰기 없음.
- main 병합/배포/릴리스: 미실행(사용자 승인 필요).
- P1-DB-01/01B 개발 DB 환경 구성: 로컬 완료 — PostgreSQL 17.12 + PostGIS 3.7, Compose 로컬 실행, 명명 볼륨 영속(재시작 후 데이터 유지 확인), 개발 전용 `docker/.env`(값 비기록·Git 제외). 운영 환경 배포·서비스 스키마 구현 아님.
- P1-DB-02B 라이브 검증: 완료(2026-11-16) — 컨테이너 기동 후 pytest DB 4건 포함 15 passed, Alembic 온라인 왕복 검증. 참고: 재검증이 필요하면 §J 절차(엔진 미가동 시 사용자 기동 필요·설치/재설치 금지).
- P1-DB-HARDEN-01/02: 2차 리뷰 수정 + 2차 안정화 항목 로컬 커밋 완료(6121953·8edd333·c3fd0e6·2e87668·6c83a71·b216e8d·77140e0·4dcf7ae, 문서 커밋 별도; 2026-11-17~19; 상세 §K·§L). 라이브: 11-17~18 Engine 미도달로 보류 → 11-19 Engine 접속 회복·부분 재검증(§G: 라이브 전 그룹 통과·스냅샷·불변 확인; 격리 실측은 당시 가드가 앵커를 거부해 미실행). 잔여: 컨테이너 health 런타임·비정상 엔드포인트 실측(사용자 결정·환경 확인 필요); 격리 왕복 문제는 2026-11-21 정책 수정으로 해소(실실행은 엔진 미도달로 대기 — §M.3).
- Windows 기능(WSL/가상화 관련) 상태 진단 자체는 미확인 — 기능 쿼리 실패, 권한 상승·우회 시도 안 함. 단 Docker Desktop 구동·Engine 연결은 2026-11-15 확인 정상이었고, 2026-11-18 재시도(3회) 결과는 §E·§G 참조.
- 원격 CI 상태: 로컬에서 확인 불가(미검증).

## F. 최근 변경 파일

- GIT-REORG-01: `AGENTS.md`(Git 운영 정책·핸드오프 규칙 개정), `Docs/HANDOFF.md`(신규) — develop 커밋 4a38fe4.
- P1-DB-01/01B: 진단(읽기 전용) 후 로컬 DB 구축. 로컬 전용 `docker/.env` 신규 생성 — 값 비기록·`.gitignore` 제외 확인, 커밋 대상 아님. `docker/.env.example` 무변경. `docker/compose.yaml`은 2026-11-17 db healthcheck 1건 추가(6c83a71) — 기존 구성 대비 최소 추가. 본 HANDOFF 갱신은 로컬 커밋.
- 이전 병합(d205bbd)에서 4DDALLA_AGENTS.md·4DDALLA_PROJECT_BRIEF.md 삭제 — 커밋 이력으로 보존.
- P1-DB-02: `app/db/` 신규 패키지(7파일), `app/main.py` 수정, `alembic.ini`·`alembic/` 신규(env.py·script.py.mako·versions/001_p1db02_migration_probe.py), `tests/test_db_layer.py` 신규, `requirements.txt` 핀 3종 추가.
- P1-DB-02B: `alembic.ini` path_separator 보강(DeprecationWarning 제거, 1a7af5a).
- P1-DB-HARDEN-01 2차 리뷰(사용자 지시, 2026-11-17) 수정: ① skip 조건을 즉시 평가되는 bool로 변경 — opt-in 시 반드시 실행(기존 lambda는 pytest가 callable을 bool() 처리해 상시 skip이었음), 비활성화 시 정상 skip, 잘못된 값은 명시적 수집 실패; 실행·스크래치 대상 검증 강화 ② `get_db`가 연결 장애급 SQLAlchemy/psycopg 예외를 DatabaseUnavailableError로 정규화 — 제약 위반·쿼리 오류 비-503, rollback·세션 종료 유지, 접속정보 비노출; 무-DB 실제 요청 503 테스트·분류기 단위 테스트 추가. 커밋 8edd333·c3fd0e6; 기본 스위트 108 passed/8 skipped·Ruff 통과; 라이브 전건·격리 실제 실행은 환경 보류(§G·§K).
- P1-DB-HARDEN-02(2차 안정화, 2026-11-18): 격리 검증을 클래스 레벨 skipif 영향 밖(모듈 레벨)으로 이동 — 옵트인 시 전제 미충족(URL 없음)이 skip이 아닌 실패로 드러남; 오류 분류를 cause 기반(클래스명 단독 판정 금지)으로 정밀화 + rollback 실패 시 원 오류·분류 보존(정적 로그); 분류기 단위·롤백 실패·무-DB 실제 요청 503·옵트인 규칙 테스트 추가 — 커밋 77140e0·4dcf7ae, 기본(DB-free) 실행 유지.
- P1-DATA-01 설계 준비(2026-11-19): `Docs/P1-DATA-01-physical-draft.md` 신규 — brands·stores·store_aliases·sources·source_links·source_evidence 물리 모델 초안, 사실/제안/미확정 구분, 정식 ORM·DDL·Alembic 002 미작성(DATA_MODEL v1.0.0·ENGINE_SPEC v1.0.0 근거, §8 확정 항목 잔여 목록화).
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
- 2026-11-16 P1-DB-02: Ruff `check .` → All checks passed. Pytest(DATABASE_URL 미설정): 81 passed, 4 skipped(DB 그룹 skip — 설계대로), 경고 1(기존 StarletteDeprecationWarning, 비실패). Alembic 오프라인 경로(`upgrade head --sql`): ini 파싱·스크립트 발견·SQL 방출 정상, 자격증명 미출력. 라이브 DB 그룹 4건·online 마이그레이션: 엔진 정지로 미실행. 참고: `alembic.ini` 비-ASCII 문자가 configparser(cp949 locale) 파싱을 깨뜨려 ASCII로 수정. 커밋 시 LF→CRLF 정규화 경고 확인(core.autocrlf=true 동작; 저장소는 LF 정규화).
- 주의(검증 한계): 실제 `.env` 작성 후 `docker compose config` 재실행 안 함(값 출력 가능 — 회피; 기동 성공이 변수 해석의 실제 증명). 전체 `docker inspect`·컨테이너 env 덤프 회피(비밀 노출 방지). 호스트 PATH에 `psql`·네이티브 PostgreSQL 없음(서버는 컨테이너 내; 비전형 설치 경로 배제 못 함 — 미설치 단정 아님). 부트스트랩 스위트는 DB-free이며, DB 통합 테스트는 이후 추가되어 별도 운영.
- 2026-11-16 P1-DB-02B(라이브 검증): Docker Engine 접속 정상(29.9.3), `4ddalla-db` 정지(Exited 255) → `docker start` 기동, psql 정상·포트 `127.0.0.1:5432` 유지. 사전 상태(4ddalla DB): 사용자/도메인 테이블·데이터 없음, PostGIS/토폴로지 확장 부트스트랩 표만, alembic_version·프로브 없음. pytest(로컬 `docker/.env` 유래 DATABASE_URL 주입, 값 비기록): `tests/test_db_layer.py -v` → **15 passed**(라이브 4건: 접속 성공·commit/rollback·커넥션 반환·Alembic 경유 upgrade/downgrade). Alembic 온라인: `current`(base) → `upgrade head`(001) → 표·버전 확인 → `downgrade base`(프로브 제거; `alembic_version` 표는 0행 잔존 — Alembic 동작) → `upgrade head` 재적용 확인 → 최종 revision 001 적용(되돌리기 가능·검증 표만 추가, 기존 데이터/확장 표 보존, 잔여 테스트 표 없음). 발견: (a) `alembic.ini` path_separator DeprecationWarning → 보강(1a7af5a); (b) psycopg/SQLAlchemy 원본 예외는 접속정보(conninfo) 표시 가능(관측) — 자체 계층은 정규화·억제. 보안: URL/값 미출력, `docker/.env` 무시·비추적 유지, 다른 컨테이너·볼륨 무변경. 프론트엔드: 변경 없음 → 미재실행(2026-11-15 기록 참고).
- 2026-11-17 P1-DB-HARDEN-01 ①·② 기본 검증(로컬·DB-free): Ruff 0.17.4 `.venv\Scripts\ruff.exe check .` → All checks passed(미커밋 변경분 I001 1건 자동 정렬·B008 3건은 `# noqa: B008`+docstring으로 FastAPI DI 의도 명시). Pytest `.venv\Scripts\python.exe -m pytest -q -ra -p no:cacheprovider` → **92 passed, 8 skipped**(DATABASE_URL 미설정 — DB 그룹 6건 skip은 설계상, 격리 opt-in 미활성 2건), 경고 1(기존 StarletteDeprecation — 비실패), **실패 0**. DATABASE_URL은 프로세스/사용자/머신 환경 모두 미설정 확인. 라이브 DB·Alembic 온라인 재검증 미실행 — 미검증 유지. `git diff --check` 공백 오류 없음(LF↔CRLF 변환 안내만). 변경 규모 +341/−25.
- 2026-11-17 2차 리뷰 수정 검증(로컬·DB-free): Ruff 0.17.4 `.venv\Scripts\ruff.exe check .` → All checks passed. Pytest `.venv\Scripts\python.exe -m pytest -q -ra -p no:cacheprovider` → **108 passed, 8 skipped**(DATABASE_URL 미설정 — DB 그룹 6건 skip은 설계상, 격리 opt-in 미활성 2건), 경고 1(기존 StarletteDeprecation — 비실패), 실패 0. 신규분 +16: skip 조건 의미론 8(파라미터 7·오류 1)·분류기 7·무-DB 실제 요청 503 1. 근본원인 진단: pytest 9.2.0은 skipif 비문자 조건을 bool() 평가(_pytest/skipping.py:139) — 기존 lambda는 상시 skip이었고 잘못된 env 값도 무시됐음(임시 재현 진단 후 파일 삭제; 수정 전 tree는 커밋 diff로 검증).
- 2026-11-17 2차 리뷰 라이브 검증 시도: Docker Engine 접속 시도 — 현재 컨텍스트(`desktop-linux`, npipe dockerDesktopLinuxEngine) 엔드포인트 부재로 실패. 설치·재설치·컨텍스트 우회 없음(핸드오프 규칙) → 라이브 전건·격리 실제 실행·컨테이너 health 상태 확인 보류. 컨테이너·볼륨·DB 무접촉(연결 시도 없음), 미검증. → 11-19 Engine 재접속 성공(29.9.3), 이후 진행은 신규 항목.
- 2026-11-18 검증 시도 추가(비-DB·라이브 시도): 비-DB 회귀 — Ruff 0.17.4 `All checks passed`; pytest 108 passed/8 skipped(설계상 skip: DB 미설정 6·opt-in 미활성 2), 경고 1 비실패·실패 0. 라이브 — Docker Engine 접속 3회 재시도(20초 간격, 현재 컨텍스트 엔드포인트 부재) 모두 실패: 설치·재설치·컨텍스트 우회 없음(핸드오프 §J 규칙) → 라이브 전건·격리 실제 실행·스크래치 생성/왕복/삭제 독립 확인·베이스라인/사후 일반 DB 비교·컨테이너 상태/health 런타임 **미실행·보류**(사용자 기동 필요). 컨테이너·볼륨·DB 무접촉(연결 시도 없음), 미검증.
- 2026-11-18 P1-DB-HARDEN-02 비-DB 검증·강제 실행 확인: Ruff 0.17.4 `All checks passed`; `pytest -q` 114 passed/8 skipped(설계상 skip: DB 미설정 6·opt-in 미활성 2), 실패 0. 옵트인+URL 미설정 강제 실행 → 격리 2건 **failed**(44 passed/6 skipped, 파일 단위) — 전제 미충족이 skip 아님; 옵트인+도달 불가 URL → 7 failed/45 passed/0 skipped — 연결 실패 은폐 없음(단 5432 접속이 거부가 아닌 타임아웃으로 실패해 대상 소유 확인 불가 → 생성·왕복 등 파괴적 단계 중단·대상/권한 확인 후 재개).
- 2026-11-17 (③ 마무리): `docker compose -f docker/compose.yaml config --no-interpolate --no-env-resolution` → 구조 파싱 정상·healthcheck 인식, `$$` 리터럴 유지·값 비출력; 컨테이너 기동·health 상태 관찰 없음(당시 미검증). 마크다운/compose 변경분 — ruff·pytest 대상 아님.
- 2026-11-19 라이브 검증(Engine 접속 회복, 사용자 기동 후):
  · 접속·기동: `docker info` ServerVersion 29.9.3 정상; `docker start 4ddalla-db` → running(기존 볼륨 유지). Compose 정의 `healthcheck`[6c83a71]는 **실행 컨테이너에 반영돼 있지 않음**(런타임 health 객체 부재 — 재생성류 필요, 시나리오·시점 사용자 결정; 이번에 변경하지 않음).
  · 사전(읽기 전용) 스냅샷: DB `4ddalla` · PostgreSQL 17.12 · alembic revision **001** · 테이블 `alembic_version, layer, p1db02_migration_probe, spatial_ref_sys, topology` · 격리 scratch iso **없음** · 역할 superuser/CREATEDB(플래그만 확인·부여 없음).
  · 라이브 테스트: `pytest tests/test_db_layer.py -v`(URL 주입, 값 비출력) → **50 passed, 2 skipped**(2 = opt-in 미활성 격리·설계상 skip; warning 1 비실패) — 라이브 전건 수행.
  · 전체 스위트(URL 주입) → **120 passed, 2 skipped**.
  · 격리 강제 실행: (11-18 기록) 옵트인+URL 미설정 → 격리 2건 **failed**(44 passed/6 skipped, 파일 단위) — 전제 미충족은 skip 아님; 옵트인+도달불가 URL(5432 타임아웃) → **7 failed / 45 passed / 0 skipped** — 연결 실패 은폐 없음. (11-19 실기) 옵트인+URL 설정(개발 DB 대상) → 당시 가드가 앵커를 거부해 2건 failed·왕복 미실행 — 실제 대상(스크래치)과 접속 기준(앵커) 혼동으로 판정된 정책 오설계(2026-11-21 가드 정책 수정 — §M.3).
     - ⚠ 11-19 실기 당시 설정 URL의 대상 DB가 개발용 `4ddalla`였고 가드(당시 정책)가 앵커를 거부해 **2건 failed·왕복 미실행** — 안전 실패 표면화였으나 원인은 정책 오설계 — 11-21 가드 정책 수정: `4ddalla` 등 앵커 허용 + 대상 스코프(생성·업그레이드·다운그레이드·삭제)=스크래치 UUID 강제 검증 + 서버·권한 사전 식별 + 불확실 시 미시작 (§M.3; 재실행은 엔진 도달 시).
  · 사후(읽기 전용) 스냅샷 = 사전과 동일(revision 001, 테이블 동일 집합, 스크래치 잔존 없음; 테스트 임시 표는 신규 테스트가 생성 후 정리) → **데이터·revision 불변 확인**.
  · 런타임 health 객체 없음(compose 정의 `healthcheck`≠실행 컨테이너) — 반영엔 재생성류 필요, 사용자 결정 사항, 이번에 변경하지 않음. 임시 스크립트(세션분) 정리 완료; 이전 관찰 미출처 3건 §I 유지.
- 2026-11-21(본 티켓): 격리 가드 **정책 수정** — 앵커는 로컬 개발 루프백 DB 허용(`4ddalla` 등), 생성·업그레이드·다운그레이드·삭제 스코프=UUID 스크래치 강제 검증, 서버 식별·피어·CREATE 권한 사전 점검, 불확실 시 미시작(§M.3). 엔진 1회 확인 **미도달**(환경 차단 — 반복 재시도 안 함) → 격리 강제 실행·개발 DB 스냅샷·health 조회 **미실행**. 오프라인 DDL 방출 rc 0·구현 검사·DB-free 회귀 통과(§M.4).

## H. 개발 환경(관측값)

- Python 3.11.9; `.venv` 사용(관측: pytest 9.2.0; ruff 0.17.3 관측 후 2026-11-17 `.venv\Scripts\ruff.exe --version` = 0.17.4로 requirements 핀과 일치 — 그 사이 환경 갱신 경위는 미확인).
- Node v24.21.0, npm 11.19.0, Git(로컬 user: Oh-JunTaek <aa39043533@gmail.com>).
- Docker CLI 29.9.3 + compose 플러그인. 컨텍스트 2개: `default`(npipe docker_engine)·`desktop-linux`(진단 시점 현재 선택). 진단 단계에선 `desktop-linux` 엔진 연결이 실패했고 Desktop 실행 파일 일반 경로·서비스·파이프도 미확인이었으나, **사용자가 Docker Desktop 최초 실행·초기 설정을 완료(2026-11-15)한 뒤 Engine 연결 정상 확인**(`docker info` ServerVersion 29.9.3) — 이전 "설치/실행 미확인" 관측은 이 시점 기준으로 해소. 단, 그 이전 항목들은 당시 기준 기록으로 보존. 2026-11-18: 현재 컨텍스트 엔드포인트(npipe dockerDesktopLinuxEngine) 부재로 Engine 도달 불가 — 20초 간격 3회 재시도 동일; 설치·재설치·컨텍스트 우회 없음, 사용자 기동 필요(§G). **2026-11-19: Engine 접속 성공(29.9.3)·컨테이너 기동·라이브 검증 진행** — 그간 미도달의 계기·경로·일시 미상(단정 금지, 기록만); 잔여 미실행 항목은 필요 시 §J 6절차.
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
- 원격 `develop` 변동 관찰: 관찰값 순차 9b937e8 → d385ddd → 65f30e3 → 284150f → 1a438e5 → 59fe67b(11-18) → 50738e3(11-19; 로컬 원격추적·재확인 일치) / 로컬 추가 77140e0 → 4dcf7ae → b1e2db0 → 2ed9b31 → 50738e3 → 9cdd1bd. 최신 확인: 로컬 `develop` 9cdd1bd, 원격 50738e3 — 차이 1(9cdd1bd) · 그 이전 정렬 경로·시점 미확인 → 사용자 확인 권장·임의 정리 금지(필요 시 확인).
- `%LOCALAPPDATA%\Temp\opencode` 에 출처 미확인 진단 스크립트 3건 관찰(2026-11-18): `probe2.py`(1,472B)·`probe_envelope.py`(2,342B)·`probe_iso.py`(1,868B). 이 세션 작성 여부 확인 불가 — 내용 미열람·미수정·미삭제(사용자 확인 권장).
- docker/.env·컨테이너 DB·볼륨(`docker_db-data`)은 **로컬 개발용**: 비밀번호 등 값은 어떤 문서·보고서·Git에도 기록 금지(준수 — 핸드오프·보고 비기록). 볼륨 삭제 금지(예: `down -v`·volume rm — 향후 티켓 포함). DB 포트는 `127.0.0.1` 바인딩(외부 미노출).
- 애플리케이션–DB 연결 코드는 P1-DB-02로 구현 완료(로컬 커밋 5fac38e, 로컬 전용), P1-DB-02B로 라이브 검증 완료. 참고(관측): psycopg/SQLAlchemy 원본 예외는 접속정보(conninfo)를 표시할 수 있음 — 자체 계층(check_connection·alembic env·핸들러)은 정규화·억제; 원시 예외를 그대로 로깅·출력하지 않도록 유의. 로컬 개발 값은 비커밋·비기록.
- HANDOFF와 실제 상태 불일치 가능(특히 원격·타 세션 변경) → 다음 세션에서 실제 상태 재확인.
- 원격 CI·머지 이후 외부 변경은 로컬에서 검증 불가(미검증).

## J. 다음 세션 지시(우선 순서)

1. `AGENTS.md` 읽기 → 2. 본 `Docs/HANDOFF.md` 읽기 → 3. 해당 명세 읽기 → 4. 실제 상태 재확인: `git status --short`, `git branch -avv`, `git log --oneline -5`, `git rev-parse develop main origin/main`, `git ls-remote --heads origin` — HANDOFF와 다르면 실제 상태 기준 갱신·차이 보고(원격 develop 변동 주체·시점 미확인 — 필요 시 사용자 확인) → 5. 다음 작업은 **현재 사용자 승인 티켓 지시 우선** — P1-DB-HARDEN-01·02 로컬 작업 완료(커밋 2026-11-17~19, 11-19 라이브 부분 재검증 §G); 잔여: 격리 스크래치 왕복(대상 소유·설정 확인 필요)·컨테이너 health 런타임(사용자 결정·환경 확인); 승인 대기: 원격 `develop` push(로컬 1커밋 c55b4b6 — 원격 cabc15a 대비, 최근 확인)·main 병합·배포(§E). → 6. 라이브 DB 확인(절차 분리): 개발 DB(`4ddalla`)는 **읽기 전용 점검만** — `alembic current`·revision/표 확인, 마이그레이션 적용 전 사전 점검(프로브 표 데이터 유무·예상 스키마 대조; 이탈 시 적용 중단). 마이그레이션 적용은 변경 티켓의 승인 범위에서 `upgrade head`로 수행(**개발 DB에서 `downgrade base` 실행 금지** — 스키마 복원 목적 다운그레이드는 일반 운영 절차가 아니며, 복원이 필요하면 별도 복구·백업 정책을 따른다). 파괴적 왕복(upgrade→downgrade→재적용, 스크래치 생성·삭제)은 **로컬 Docker PostgreSQL 서버의 UUID 스크래치 DB에서만**: `tests/test_db_layer.py`의 격리 검증(옵트인 `DDALLA_TEST_ISOLATED_MIGRATION_DB=1`)이 앵커·서버·권한·스코프를 사전 식별하고 생성·왕복·정리·잔존 여부를 확인하며, 식별이 불확실하면 시작하지 않는다. (구버전 가이드의 '개발 DB 대상 왕복' 서술은 폐기 — 역사 기록(§G 11-19 항목 등)에만 남김.)

## K. P1-DB-HARDEN-01 — ①·②·③ + 2차 리뷰 수정 + 2차 안정화 항목 완료 / 라이브 부분 재검증(2026-11-19)·잔여 보류(핸드오프 v14, 2026-11-17~20)

지시 접수(2026-11-16): P1-DATA-01 전 코드 리뷰 후속. ①(P0) 마이그레이션 왕복 테스트 격리 ②(P1) 실제 FastAPI 엔드포인트 오류 처리·구분·비노출 ③ 운영 안정성(컴포즈 healthcheck·테스트 명령 분리·sessionmaker 검토·001 후속 제거 문서화) ④검증. 도메인 테이블 신규 생성 없음. develop 작업·로컬 커밋·핸드오프 갱신·보호 파일(ses1·Docs/draft.md) 준수·push/PR/병합/deploy 금지.

상태: ①·②·③ 로컬 처리 완료 + 2차 리뷰 수정 2건 + 2차 안정화 항목 로컬 처리 완료(2026-11-17~18; 커밋 6121953·2e87668·6c83a71·b216e8d·8edd333·c3fd0e6·77140e0·4dcf7ae — §D·§G). 세부: ③ 중 healthcheck는 설정 파싱까지 확인(런타임 health 미검증), 문서화·검토 기록 완료, `001`은 방침 문서 제안까지. 2차 리뷰(사용자 지시) ①·② 및 안정화 항목(격리 필수 실행 보장·분류 정밀화·rollback 견고성) 로컬 구현·기본 검증 완료(아래). 도메인 테이블 신규 생성 없음 · 원격 작업 없음. 라이브·격리 실제·스크래치 독립 확인·베이스라인 비교·health: Engine 미도달(11-18)로 보류 → 11-19 접속 회복 후 라이브 전 그룹 통과·사전/사후 스냅샷 동일·scratch 없음 확인; 격리 왕복은 가드 차단(보호 범용 DB 대상)으로 미실행; 컨테이너 런타임 health 객체는 부재(재생성류 필요 — 사용자 결정); 비정상/도달불가 엔드포인트 실측은 설계상 대상 아님.

2차 안정화 항목 처리(2026-11-18, 커밋 77140e0·4dcf7ae; 로컬·기본 실행 검증):
- 격리 검증을 모듈 레벨로 이동해 클래스 레벨 `skipif` 간섭 제거 — 옵트인 시 전제 미충족(URL 없음)·연결 실패가 **skip이 아닌 실패**로 표면화(기본 실행 114 passed/8 skipped, 실패 0; 강제 실행에서 격리 2건 failed — §G).
- 분류기 cause 기반 정밀화(드라이버 원인·engine/pool 가용성만 연결 클래스; 클래스명 단독 판정 금지 — 리뷰 요구) + rollback 실패 시 원 오류·분류 보존(정적 debug 로그; 세션 close는 유지).
- 테스트: 분류기 단위·rollback 실패 2종·무-DB 실제 요청 503·옵트인 규칙 — §G의 강제 실행 결과 참조.

읽기 전용 분석 기록(분석 시점 사실; 해소 항목 표시):
- (분석 시점 구조 → ①로 해소) `TestLiveDatabase`가 클래스 레벨 `skipif(not DATABASE_URL)`; 왕복 테스트가 `get_database_url()` 대상에 `command.upgrade/downgrade`를 실행 — DATABASE_URL이 일반 개발 DB를 가리키면 그 DB에 `downgrade base`가 실행될 수 있는 구조였음(이번 P0의 직접 대상).
- (③ 검토 기록) `app/db/dependencies.py`: `get_db`가 요청마다 `sessionmaker` 생성(Engine은 캐시) — 검토 메모: 변경 불요(Engine 지연·캐시 바인딩, 세션은 사용 시에만 연결, 생성 비용 미미; 모듈 상수화는 지연 초기화·무환경 import 제약과 충돌). 채택 여부는 리뷰어 확인 가능.
- (2차 안정화) 분류기 cause 기반 정밀화(그룹별 원인 직접 인상/래핑 `orig`; 클래스명 단독 판정 금지) 및 rollback 실패 보존(리뷰 지적분, 2026-11-17 구현).← 2차 안정화 즉시 반영(77140e0).
- (②에서 해소) 분석 시점 `app/main.py` 라우트는 `/health`뿐 — 시험 방식은 **테스트 내 소형 probe 앱**(기존 핸들러·`get_db` 재사용)으로 결정·구현(배포 라우트 추가 없음) — 기록.
- (③ 처리) `docker/compose.yaml`: db 서비스 healthcheck 없음 → 추가·파싱 확인(`pg_isready`, 변수 `$$` 이스케이프·최소 파라미터; 런타임 health 미검증). 자격값은 `docker/.env` 유래·비기록 유지.
- Alembic 이력: `001` 단일 root(검증용 프로브 표). P1-DB-02B 중 로컬 dev DB에 001 적용됐던 상태(데이터·볼륨 무변경; 검증 표 잔존) → ③ 잔여: 처리 방침 문서 제안(서비스 마이그레이션 추가 후 별도 후속 마이그레이션으로 드롭) — 제품 결정 필요, 임의 삭제·이력 재작성 금지.
- DB 역할 `4ddalla`: superuser·CREATEDB 보유(서버 내 스크래치 DB 생성 가능 — 격리 실행 경로 후보; 최소권한 정비는 후속 과제).
- 도구 확인: SQLAlchemy `URL.render_as_string(hide_password=True)` 존재('***' 마스킹; `False`면 평문 노출 — 출력 금지 원칙 유지). `docker compose config`에 `--no-interpolate`·`--no-env-resolution` 있음(변수 비추출 검증 후보; 이번엔 --help 확인만).
- 로컬 헬퍼(비커밋·세션 로컬): `%LOCALAPPDATA%\Temp\opencode\run_with_db_env.py` — docker/.env(POSTGRES_USER/PASSWORD/DB)로 URL 조립·주입, 값 비출력.

구현·검증 결과(2026-11-17~18, 로컬·기본 실행 기준)와 ③ 잔여·2차 리뷰·2차 안정화 결과:
- ①(완료): 왕복 테스트 기본 경로 제외·명시적 opt-in(`DDALLA_TEST_ISOLATED_MIGRATION_DB`=1/true/yes/on); 대상 검증은 파싱된 URL 성분 — dialect `postgresql+psycopg`·loopback `127.0.0.1`/`::1`·포트 5432·비보호 DB명(이름만으로 판정 금지 유지); 스크래치명 UUID 생성(설정에서 가져오지 않음); 유지 엔진으로 스크래치 생성→`upgrade head`→`downgrade base`→재적용→강제 드롭(`WITH (FORCE)`)+잔존 확인, 실패 시에도 정리; 부정 가드 단위 테스트(미활성/보호 DB/비루프백·타 포트/타 dialect/미해석 URL).
- ②(완료): 연결 계열 오류→503 정적 본문(비노출·롤백/커넥션 반환 확인), 비연결 SQLAlchemyError→500 계열(비-503; 합성 시험+라이브 그룹 설계); 자격증명·접속정보 응답/로그 비노출. 시험 방식은 테스트 내 probe 앱 채택(배포 라우트 추가 없음).
- ③(완료·문서화/검증 경계): docker/compose db healthcheck(`pg_isready`·`$$` 이스케이프; 설정 파싱 확인, 런타임·라이브 DB 재검증 미실행) + 테스트 명령 3단 문서화 — 기본 DB-free / DB 검증 명시 명령 / 격리 opt-in(CI 무변경, LOCAL_DEV) + sessionmaker 검토 기록(의견: 변경 불요 — 위 사유) + `001` 처리 방침 문서 제안 — 제품 결정 필요.
- 2차 리뷰 ①(완료·기본 검증): skip 조건을 즉시 평가되는 bool로 변경 — pytest가 callable 조건을 bool() 평가해 기존 lambda는 상시 skip·잘못된 env 값 무시였음(소스 확인+재현 진단, 임시파일 삭제). opt-in 시 실행 조건(False)·비활성 정상 skip·잘못된 값은 수집 단계 명시 실패. 클래스 밖(모듈 레벨) 배치로 클래스 레벨 skipif 간섭 제거, 실행·대상 검증: 격리 왕복이 in-force DATABASE_URL·인스펙터 대상이 스크래치임을 단언, 드롭 후 잔존 0 확인 로직 유지 — 라이브 실행은 재판정 대상(보류).
- 2차 리뷰 ②(완료·기본 검증): 분류기 — 드라이버 원인 기반(OperationalError류·Disconnection/Timeout·psycopg 연결/인터페이스 클래스, wrapped `orig` 포함) 수용, 무-운전 원인 `OperationalError`·IntegrityError/ProgrammingError/일반 오류 거부; rollback 실패 시 원 오류·분류 보존(정적 로그); 아무 DB 없는 실제 요청에서 도달 불가 엔드포인트→503 정적 본문·응답/로그 무유출·풀 반환. 라이브 연결 실패·제약 위반 확인은 전건 실행 시(보류).
- ③ 잔여·보류(11-19 진행분 제외): 격리 마이그레이션 실제 실행 — 가드가 보호 범용 DB 대상 실행을 차단해 미실행(대상 소유·설정 확인 필요; 생성/업그레이드/다운그레이드/삭제·권한 부여 안 함, 기존 불변); 컨테이너 런타임 health 객체 — compose 정의≠실행 컨테이너, 반영엔 재생성류 필요(사용자 결정, 이번에 변경 안 함); 비정상/도달불가 엔드포인트 라이브 실측은 설계상 대상 아님. 컨테이너·볼륨·개발 DB 데이터는 불변.
- 제약: 로컬 개발 DB만(운영·타 프로젝트 금지), 볼륨·기존 데이터·이력 보호, `docker/.env` 값 비기록, 보호 파일 불변.
- 2026-11-19 라이브 재검증(Engine 접속 회복 후, 사용자 기동): 접속 정상(29.9.3), `docker start 4ddalla-db` → running(기존 볼륨 유지). 사전 스냅샷(읽기 전용): DB `4ddalla`·PG 17.12·rev **001**·테이블 `alembic_version, layer, p1db02_migration_probe, spatial_ref_sys, topology`·격리 scratch 없음·역할 플래그(부여 없음). 라이브 `pytest tests/test_db_layer.py` → **50 passed, 2 skipped**(opt-in 미활성 격리 2·설계상; warning 1 비실패); 전체 스위트 → **120 passed, 2 skipped**(URL 주입). 격리 강제 실행: ①옵트인+URL 미설정 → 격리 2건 **failed**(44 passed/6 skipped) — 전제 미충족 비은폐 ②URL 설정(개발 DB) → 가드 **거부**로 2건 failed·왕복 미실행(안전 동작·표면화). 사후 스냅샷 = 사전 동일(rev 001·테이블 동일·scratch 없음) → **데이터·revision 불변 확인**. 런타임 health 객체 부재(재생성류 필요 — 사용자 결정, 이번에 변경 안 함). 임시 스크립트(세션분) 정리 완료; 이전 관찰 미출처 3건 §I 유지.

## L. 최종 갱신

- 갱신: 2026-11-16 — P1-DB-02B 완료: 라이브 통합 테스트 15 passed(라이브 4건 포함)·Alembic 온라인 왕복 검증·설정 보강(1a7af5a)·본 핸드오프 갱신(커밋 해시는 작업 보고 참조). 원격 `develop` = d385ddd 재확인 — 직전 턴(9b937e8) 대비 변동, 주체·시점 미확인(사용자 확인 권장). 핸드오프에 비밀정보 기록 금지 준수 — `.env` 실제 값 미기재.
- 갱신: 2026-11-16 — P1-DB-HARDEN-01 접수·읽기 전용 분석(코드 무변경, 커밋 없음): 현행 왕복 테스트 구조·핸들러 범위·compose·역할 권한 등 사실 기록과 격리/오류구분/운영 항목 **설계 방향**만 §K에 인계.
- 갱신: 2026-11-17 — 핸드오프 v8: 미커밋이던 P1-DB-HARDEN-01 ①·②를 린트 정리→기본 검증(92 passed/8 skipped, 실패 0)→로컬 커밋(6121953, +341/−25). 원격 `develop` = 65f30e3 재확인(읽기 전용) — 로컬 트래킹과 동일 커밋, 이 세션 원격 조작 없음, 반영 경로 주체·시점 미확인(사용자 확인 권장). 핸드오프 v1 '원격 develop 부재' 기재 이후 반복 관찰된 원격 변동 계열 — 임의 정리 금지. 비밀정보 비기록 준수 — `.env` 실제 값 미기재.
- 갱신: 2026-11-17 — 핸드오프 v9: ③ 마무리 커밋(6c83a71 `docker/compose.yaml` healthcheck — config 파싱 확인·런타임 미검증; b216e8d `Docs/LOCAL_DEV.md`). 로컬 `develop` = 원격 `develop`(=65f30e3, 이후 284150f로 전진 확인 §C) 대비 커밋 5개 앞섬(6121953·2e87668·6c83a71·b216e8d·284150f, 미push); push/PR/병합/deploy 미실행(승인 범위 밖). 라이브 DB 재검증은 §J 6절차(필요 시·미실행). 비밀정보 비기록 준수 — `.env` 실제 값 미기재.
- 갱신: 2026-11-17 — 핸드오프 v10: 2차 리뷰 수정 2건 구현·기본 검증·로컬 커밋(8edd333·c3fd0e6; 기본 스위트 108 passed/8 skipped·Ruff 통과). 라이브 DB 전건·격리 실제 실행·컨테이너 health: Engine 접속 불가(현재 컨텍스트 엔드포인트 부재)로 보류·미실행 — 사용자 기동 시 §J 6절차로 재개; 컨테이너·볼륨·DB 무접촉. 원격 `develop` = 284150f 재확인(읽기 전용) — 로컬 2커밋 앞섬, 반영 경로 미확인. 비밀정보 비기록 준수 — `.env` 실제 값 미기재.
- 본 갱신은 develop 로컬 커밋으로 반영(커밋 해시는 작업 보고에 명시). 핸드오프에 비밀정보 기록 금지 준수 — `.env` 실제 값 미기재.
- 갱신: 2026-11-18 — 핸드오프 v11: 최종 검증 절차 시도 기록 — 비-DB 회귀(Ruff·기본 pytest 108 passed/8 skipped, 실패 0) 통과; 라이브 검증은 Docker Engine 3회 재시도 미도달로 전면 보류·미실행(설치·재설치·컨텍스트 변경 없음, 컨테이너·볼륨·DB 무접촉) — 사용자 기동 후 §J 6절차 재개. 라이브 `ls-remote`: 원격 `develop` = 1a438e5(로컬 HEAD 동일; 직전 보고 284150f에서 전진 — 주체·시점 미확인). `%LOCALAPPDATA%\Temp\opencode` 출처 미확인 진단 스크립트 3건 관찰·미접촉. 비밀정보 비기록 준수 — `.env` 실제 값 미기재.
- 갱신: 2026-11-18 — 핸드오프 v12: P1-DB-HARDEN-02 안정화 항목 구현·기본 검증·커밋(77140e0·4dcf7ae; 문서 커밋 b1e2db0·2ed9b31·50738e3; Ruff 통과·기본 pytest 114 passed/8 skipped, 실패 0; 옵트인 강제 실행 시 전제 미충족·연결 실패가 skip 아님=failed로 확인). 라이브 항목은 당시 Engine 미도달로 보류·미실행(컨테이너·볼륨·DB 무접촉). 원격 `develop` = 59fe67b 재확인(읽기 전용; 2026-11-18) — 로컬 4커밋 앞섬(77140e0·4dcf7ae·b1e2db0·2ed9b31). 비밀정보 비기록 준수 — `.env` 실제 값 미기재.
- 갱신: 2026-11-21 — 핸드오프 v15: P1-DATA-01 1차 구현 기록(§M) — 검증된 항목과 미실행 항목 구분 명시. 개발 브랜치 로컬 선두 1커밋(c55b4b6)으로 갱신. (커밋 해시는 작업 보고 참조)

## M. P1-DATA-01 — 1차 도메인 스키마 구현(2026-11-21, 로컬·미적용)

**사용자 티켓 기준: develop `cabc15a` 대비 구현 진행, develop 로컬 커밋 시리즈(해시는 작업 보고 참조).** HANDOFF보다 현재 코드·사용자 지시 우선; 충돌 발견 없음 — 초판 초안의 "같은 티켓 도메인 신설 안 함" 서술은 본 티켓으로 superseded(초안 §8 표기).

**M.1 확정 설계(요약)** — brands / stores(nullable brand FK, category, operational_status, nullable geography(Point,4326)+GiST) / store_aliases(alias, valid_from/to+범위 CHECK) / sources(channel_type, canonical_url, collection_permission=공유 Enum, permitted_method) / source_links(source + **브랜드 또는 매장 중 정확히 하나** CHECK, identity_status=공유 Enum) / source_evidence(evidence_type, evidence_ref, verified_at). 기반: `Docs/DATA_MODEL.md` §2–§4·§6; 공유 Enum `SourceIdentityStatus`/`CollectionPermissionStatus`는 `app/contracts/enums.py`(ENGINE_SPEC §2) 재사용. 논리→물리 차이표: 초안 문서 §8.

**M.2 산출물(로컬 작성·미적용)** — `app/db/models.py`(ORM), `alembic/versions/002_p1data01_domain_tables.py`(drop 검증 프로브 `p1db02_migration_probe` + 6 테이블 + FK/UNIQUE(없음 — URL 정규화 미확정)/CHECK/인덱스; downgrade=스키마 역복원+프로브 형태 재생성, **행 미복구** 명문화), `tests/test_domain_models.py`(구조 검사 9건), `alembic/env.py`(모델 등록 import), `requirements.txt`(geoalchemy2 핀), 문서: 초안 상태·차이표·최소 확정안/확장 방침. ※ 검증 전용 프로브뿐이던 `stores`/`brands` 등은 **001에 없음** → 신규 생성.

**M.3 격리 가드 정책 수정(§3 완수)** — 앵커(로컬 루프백 DB, `4ddalla` 허용)와 마이그레이션 대상(스크래치) 분리; 스크래치=런타임 UUID 생성; 실행 직전 URL 재검증; 생성·업그레이드·다운그레이드·삭제 전부 스크래치 검증; 서버 식별·루프백 피어·CREATE/DELETE 권한 사전 점검; 실패 시 정리·잔존 확인; 불확실 시 미시작. `_PROTECTED_DBNAMES` 단순 삭제 아님 — 앵커 허용+타깃 스코프 강제로 재설계. 테스트 갱신·추가: 앵커 허용, 스크래치 명명·비충돌, 비루프백/비표준/미해석 거부, 모드/skip 의미론, 무결성·기계론 유지.

**M.4 검증(실측 구분)** — `ruff check` All checks passed; 포매트(본 티켓 파일만); DB-free `pytest -q` **124 passed, 8 skipped**, 1 warning(기존 non-fatal). 오프라인 `alembic upgrade head --sql` **rc 0**: 6 CREATE TABLE·프로브 DROP·gist·FK 6·CHECK 4 방출 확인. **미실행(환경)**: 격리 강제 실행(엔진 미도달 — 1회 확인, 반복 안 함), 개발 DB 스냅샷, 헬스 조회, 002 라이브/개발 DB 적용. **미해결**: 격리 왕복·적용 판단은 검증 조건+사용자 결정 대기.

**M.5 결정 게이트/미확정** — (i) 격리 왕복 → (ii) 개발 DB 사전점검(프로브 데이터·스키마 대조; 이탈 시 중단) → (iii) 적용 여부(사용자). 도메인 사전 통제(category/channel/operational/evidence 등)·정규화 URL 규칙·별칭 중복·삭제 정책 세부는 초안 §9 미확정 유지 — 본 구현에서 임의 확정 없음. 컨테이너 health 재생성은 11-19 기록대로 사용자 결정(볼륨 무사용 재생성 경로 검토, 타 프로젝트 무변경).
