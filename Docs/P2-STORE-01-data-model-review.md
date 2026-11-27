# 4 DDALLA — P2-STORE-01 데이터 모델 검토 (문서 전용)

- Related ticket: P2-STORE-01 (StoreDiscovery 최초 구현)
- Status: 검토 기록. **새 Alembic 리비전·SQL DDL·물리 스키마 변경 없음** (별도 승인 전).
  DATA_MODEL.md의 논리 엔터티 목록과 StoreDiscovery 요구사항을 대비한다.
- Last updated: 2026-11-27

## 1. 전제

- 개발 DB 스키마 기준선: Alembic revision 002 — `brands`, `stores`,
  `store_aliases`, `sources`, `source_links`, `source_evidence` 6테이블.
- 원칙: 내부 객체 UUID와 외부 공급자 장소 ID 분리(ADR-006, ENGINE_SPEC §3,
  DATA_MODEL §1). 공급자 외부 ID는 내부 키가 아니다.
- 권리: 공급자/출처의 보관·재표시·분석 권한 확인 전 원본 영구 저장·자동
  수집·AI 처리 금지(구현 불변식 §9, 정책 P-010, DECISIONS OPEN-001).
  StoreDiscovery 응답은 이 규칙의 예외가 아니다 — 결과 객체는 저장/공개를
  뜻하지 않는다.
- 동명 상호만으로 자동 병합 금지. 공급자 ID를 내부 UUID로 쓰지 않는다.

## 2. 이번 구현이 실제로 만드는 것 (DB 비결정)

P2-STORE-01은 계약·인터페이스·실행 로직·합성 공급자·테스트만 구현한다.

- 입력 계약: 지역 식별자, 중심 좌표, 반경(800/1000m), 대상 업종, 허용 공급자.
- 출력 계약: 후보(좌표·상호·근사거리·증거·사용권), 공급자 외부 참조,
  중복 신호(동일 공급자 외부 ID 반복), 실행 상태 + 구조화 이슈.
- 후보 `candidate_id`는 결과 객체 식별용 엔진 생성 UUID이며 엔티티 PK가 아니다.
- 물리 저장 없음: 후보·공급자 참조·관측은 현재 어떤 테이블에도 기록되지 않는다.

## 3. DATA_MODEL.md §3 후보 엔터티별 검토

| 엔터티 | 논리적 의미(DATA_MODEL) | 현재 rev 002 | StoreDiscovery와의 관계/차이 | 물리화 시 결정 필요 |
|---|---|---|---|---|
| `store_identity_evidence` | 매장 합치기/별칭 판정 근거 | 없음 | 지금은 후보별 evidence 목록(외부 ID·상호·좌표·수집 시각 등 공급 필드 관찰)만; 합치기/별칭 판정은 후속 | 근거 유형·강도·판정 상태 매핑 |
| `store_facts` | 독립적으로 사용할 권리가 확보된 매장 사실, 출처 | 없음 | 후보/관측은 권리 확보 전제가 아니며 영구 "사실" 아님 | 사실 확정 절차·권리 게이트·필드별 출처 표현 |
| `data_providers` | 공급자, 계약 버전 | 없음 | 계약 객체가 `provider_id`/`contract_version` 문자열을 운반 | 공급자·계약버전 메타 관리, 식별 체계 |
| `data_usage_policies` | 허용된 저장·노출·분석 목적, 만료/삭제 정책 | 없음 | 구현은 `DataUseRights` 선언값(STORE_ALLOWED/DISPLAY_ONLY/UNKNOWN)만 취급; UNKNOWN이면 후보 차단+이슈 | 권리 값의 확정 출처·검증, 목적별 정책, 만료/삭제·TTL, 정책 버전관리 |
| `provider_place_refs` | provider_id, external_id, store_id, UNIQUE(provider_id, external_id) | 없음 | 외부 ID는 응답 내 references(후보별 tuple)로만 존재; 참조 대상 내부 매장 없음 | 내부 매장과의 관계 수명주기, 고유성·충돌 처리 |
| `place_observations` | 정책상 허용된 임시 관측 정보와 만료 시각 | 없음 | 후보+근사거리+`collected_at`(있는 경우) 수준의 관찰 표현 | 관측 TTL/만료, 허용 관찰 유형, 정책 허용 범위 |

공통 미확정: 업종/권리 모형 값이 실체 정책으로 검증되기 전에는 정책 확정으로
취급 금지(공급자별 권리는 OPEN-001 판정 전 임의 확정 금지).

## 4. 설계 시 유의

- 권리 미확인 결과는 응답에 담되 "저장/공개 가능"을 함의하지 않는다 — 현
  구현은 UNKNOWN 권리 프로세스를 스킵+이슈로 기록한다.
- 중복 "가능성"과 "확정"은 다르다. 동일 공급자 정확 외부 ID 반복만 신호이며,
  공급자 간 중복 페어링 키는 미정의(이름·좌표 추정 금지).
- 거리 필터는 본 구현에서 반경 이하(≤) 포함 — 제품 정책 확정이 아니라 시험으로
  고정한 구현 선택이다.
- 관측 시각은 제공자 보고값(있는 경우)이며 엔진이 발명하지 않는다.
- 물리 저장 요구(후보/제공자/관측 테이블)와 새 Alembic 리비전은 별도 승인·티켓 사안이다.

## 5. 참조

- `Docs/DATA_MODEL.md` §2–§4, §8; `Docs/ENGINE_SPEC.md` §3;
  `Docs/DECISIONS.md` OPEN-001·OPEN-011; `Docs/BACKLOG.md`(P2 세부 미확정);
  Alembic 002.
