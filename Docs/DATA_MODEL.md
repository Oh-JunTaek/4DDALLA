# 4 DDALLA — Data Model

- Version: 1.0.0
- Status: LOGICAL_SCHEMA_BASELINED; physical SQL DDL and migrations **not yet verified**
- Last updated: 2026-11-11

## 1. 무결성 원칙

내부 객체 UUID와 외부 장소 ID 분리, 공급자별 데이터 권리·TTL 적용, 출처 원문과 분석 결과·승인본·공개본 분리, 행사와 출처의 다대다 관계, 필드별 근거, 검수 결정과 모든 오류 이력, 중복 처리 방지. 장소정보를 API에서 받았다는 사실만으로 저장/AI 처리 권한이 확보되지는 않는다.

## 2. 기본 타입

| 대상 | 규칙 |
|---|---|
| 기본키 | UUID |
| 시각 | `TIMESTAMPTZ` UTC, 표시 기준 Asia/Seoul |
| 날짜형 행사 | `DATE` 및 시간대/근거 상태 별도 |
| 가격 | `INTEGER` KRW, 음수 금지, 미확인 값은 NULL + 확인 상태 |
| 위치 | 권한 확보 시 `geography(Point,4326)` + GiST |
| 비정형 AI 출력 | `JSONB` + 스키마 버전; 주요 검색값은 정형 칼럼 |
| 외부 URL | 원본 URL, 정규화 URL, 사용권/출처 메타데이터 |
| 변경 이력 | created_at/updated_at, 원본 버전 및 검증 버전 |

## 3. 엔터티 목록

### 매장·공급자

- `brands`: canonical_name, 별칭·상태.
- `stores`: nullable brand_id, category, operational_status; 내부 매장 ID는 장소 API ID와 무관.
- `store_aliases`: 공식·검증된 지점 별칭과 유효 범위.
- `store_identity_evidence`: 매장 합치기/별칭 판정 근거.
- `store_facts`: 독립적으로 사용할 권리가 확보된 매장 사실, 출처.
- `data_providers`: 공급자, 계약 버전.
- `data_usage_policies`: 허용된 저장·노출·분석 목적, 만료/삭제 정책.
- `provider_place_refs`: provider_id, external_id, store_id.
- `place_observations`: 정책상 허용된 임시 관측 정보 및 만료 시각.

### 출처·콘텐츠

- `sources`: channel_type, canonical_url, collection_permission, permitted_method.
- `source_links`: source_id + **브랜드 또는 매장 중 정확히 하나**, identity_status.
- `source_evidence`: 출처 소유 공식성 근거(유형, 근거 참조, 검증 시각).
- `source_contents`: source_id, external_content_id(nullable), canonical_url.
- `content_versions`: source_content_id, version_number, content_hash, asset_hash, 관측 시각.
- `source_checkpoints`: 마지막 정상 목록/상세 감시 상태(ETag/수정일 등).
- `content_observations`: NEW/UPDATED/MISSING_FROM_LIST 등의 관측 이벤트.

### 행사·판정·발행

- `promotions`: 논리적 행사 ID, 브랜드 소속, lifecycle.
- `promotion_sources`: **content_version ↔ promotion 다대다 연결** 및 근거 역할.
- `promotion_items`: 행사별 상품, benefit_type, original_price_krw(nullable), sale_price_krw(nullable).
- `promotion_rules`: 행사 또는 상품별 쿠폰/시간/결제/주문 조건.
- `promotion_scopes`: ALL_STORES/ALL_EXCEPT/SELECTED_STORES/REGIONAL/UNKNOWN 및 COMPLETE/INCOMPLETE/UNKNOWN.
- `promotion_store_rules`: INCLUDED/EXCLUDED, 원문 지점명, resolved_store_id(nullable), 근거.
- `store_promotions`: 개별 지점 수동 판정 또는 선택적 캐시. 전국 행사를 모든 지점 행으로 물질화하지 않아도 됨.
- `promotion_evidence`: 행사 필드 경로↔출처 콘텐츠 블록·이미지 좌표 근거.
- `extraction_runs`: engine/model/version, input_version, raw_candidate 및 오류.
- `promotion_revisions`: 검증·승인된 행사 수정 버전.
- `field_overrides`: 운영자 정정 필드, 변경 전후, 입력 근거, 보호 상태.
- `publication_records`: 공개 버전과 변경·비공개 이력.

### 운영

- `collection_jobs`: 작업, 멱등성 키, lease, 재시도, next_run_at.
- `collection_attempts`: 개별 실행 시도, 결과, 소요 시간.
- `error_events`: **모든 실패 발생 건**, 심각도, 코드, fingerprint, 안전 문맥.
- `review_tasks`: 검수 대상, 사유, 우선순위, 상태.
- `review_decisions`: 담당자, 근거, 변경 전후, 시각.
- `user_reports`: 비회원 제보, 중복/남용 대응.
- `area_requests`: 미지원 지역 추가 요청.

## 4. 관계와 필수 제약

- brands 1:N stores; sources N:M brands/stores via source_links.
- sources 1:N source_contents 1:N content_versions.
- **content_versions N:M promotions** via promotion_sources.
- promotions 1:N items/rules/scope rules; stores N:M promotions through 판정·예외.
- `source_links`: `(brand_id IS NOT NULL) <> (store_id IS NOT NULL)` CHECK.
- `provider_place_refs`: UNIQUE(provider_id, external_id).
- `source_contents`: UNIQUE(source_id, external_content_id) WHERE external_content_id IS NOT NULL; ID 없는 URL은 별도 정규화 규칙.
- `content_versions`: UNIQUE(source_content_id, version_number).
- `store_promotions`: UNIQUE(store_id, promotion_id) for current 판정/캐시; 이력은 별도 버전/감사 테이블.
- 입력버전·엔진버전·스키마버전을 포함하는 작업 결과 멱등성 제약.
- 원문 지점명 해석 불확실성을 빈 제외 목록으로 변환하지 않는다.
- 검수된 수동 판정은 자동 계산 캐시와 구분한다.

## 5. 데이터 변경·충돌 정책

자동 추출 결과 → 검증된 행사 revision → 공개 projection으로 단계 분리. 동일한 원문 재분석은 운영자 field override를 덮어쓰지 않는다. 원문이 바뀌고 핵심 값이 충돌하면 재검수하고 관련 공개 판정을 제한한다. 종료·취소·중대한 조건 오류에 대한 안전 차단은 단순 수동 수정 보호보다 우선한다.

## 6. 위치 조회·캐시

허용된 좌표에 GiST 인덱스. 반경 조회 `ST_DWithin`, 거리 정렬. 브랜드 전체 행사는 기본 scope와 예외만 저장하고 조회 지역에 맞는 매장에 대해 지연 계산하며, 캐시는 행사·매장·규칙 버전에 종속시켜 무효화한다.

## 7. 로그·보존

수집 작업 1건에 여러 attempts, 각 실패 시도에 별도 error_events. UI에서는 fingerprint로 집계하되 원본 실패 건수를 잃지 않는다. API 키·개인정보·인증 헤더 저장 금지. 원본 콘텐츠와 오류 로그에는 각각 출처 약관/보존 기간/삭제 정책을 적용한다.

## 8. P1에서 확정할 물리 스키마 항목

전체 SQL DDL·Alembic 마이그레이션, 정규화 URL 유일성, provider별 관측 TTL, 동시 검수/갱신 충돌, 대용량 이미지 저장, 각 테이블의 CHECK·FK·인덱스와 마이그레이션 롤백. 이 문서는 **구조 계약 기준**이지 이미 실행·검증한 DB 스키마가 아니다.
