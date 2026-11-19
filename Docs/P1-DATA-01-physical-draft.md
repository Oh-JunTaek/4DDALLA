# 4 DDALLA — P1-DATA-01 Physical Model Draft (brands · stores · store_aliases · sources · source_links · source_evidence)

- Status: **DRAFT — 설계 제안(초안), 미확정.** 물리 실행·검증된 스키마가 아니며 정식 ORM 클래스·DDL·Alembic 002는 **이 문서로 작성·실행하지 않는다.**
- 근거 기준선: `Docs/DATA_MODEL.md` v1.0.0(§2 기본 타입, §3 엔터티 목록, §4 관계·필수 제약, §5 변경·충돌, §6 위치 조회, §7 로그·보존, §8 P1 확정 물리 항목) + `Docs/ENGINE_SPEC.md` v1.0.0(§2 상태값 단일 기준, §3 StoreDiscovery, §4 SourceDiscovery, §10 오류·멱등성, §11 불변식, §12 계약 버전).
- 관계: `DATA_MODEL.md` 상태 = `LOGICAL_SCHEMA_BASELINED; physical SQL DDL and migrations not yet verified`; 두 문서 모두 물리 스키마를 검증하지 않았으므로 아래 물리 진술은 **문서에 있는 규칙의 적용 제안 또는 미확정 항목**이다.
- 표기: **[문서]** 문서에 명시된 규칙 / **[제안]** 이번 초안의 설계 제안(미승인) / **[미확정]** 출처 문서·공급자·정책 확인이 필요한 항목. 임의 기본값 단정 금지.

## 0. 공통 원칙(전 엔터티 공통)

- 기본키 UUID / 시각 `TIMESTAMPTZ`(UTC 저장, 표시 Asia/Seoul) / `created_at`·`updated_at` — **[문서]** DATA_MODEL §2, §3(변경 이력).
- 내부 객체 UUID와 외부 공급자 키 분리: 공급자 외부 ID는 내부 PK로 쓰지 않는다 — **[문서]** §1·§3(provider_place_refs 별도), ENGINE_SPEC §3.
- 삭제·보존: 출처·공급자별 권리와 TTL, 만료·삭제 정책 준수, 오류 이력 보존 — **[문서]** §1·§7(`data_usage_policies`, `data_providers`, `place_observations` 등 별도 엔터티가 이 역할).
- 상태값 도메인 분리: `SourceIdentityStatus`(공식성)와 `CollectionPermissionStatus`(수집 권한)은 **다른 컬럼/다른 판정**이며 하나로 합치지 않는다 — **[문서]** ENGINE_SPEC §2·§4(권한 `ALLOWED` 아니면 자동 수집 금지).
- 수집 방식(`OFFICIAL_API`·`RSS`·`HTML`·`WEBHOOK`·`MERCHANT_SUBMISSION` 등)은 수집 **허가 상태와 별도 필드** — **[문서]** ENGINE_SPEC §2.
- 물리 제약·인덱스·마이그레이션 롤백 확정은 P1 물리 항목(§8) — **[문서]** 데이터 분석상 일부는 이 초안의 제안.

## 1. `brands`

- `id` UUID PK — **[문서]** §2.
- `canonical_name` — **[문서]** §3(필드 존재). 비공백·정규화 규칙 — **[미확정]**.
- "별칭·상태" 필드 — **[문서]** §3에 존재만 기술, 이름·구조 미확정. 별칭 보관 테이블을 별도 두는 관행은 `store_aliases`(매장 한정, §3) 전례 참고 — **[제안/검토]**.
- 상태값 Enum: ENGINE_SPEC §2에 브랜드 전용 상태 Enum 없음 — 공유 Enum 신설 여부는 구현 티켓 검토 — **[미확정]**.
- `created_at`·`updated_at` — **[문서]** §2.

## 2. `stores`

- `id` UUID PK; 내부 매장 ID ≠ 장소 API 외부 ID — **[문서]** §1·§3·ENGINE_SPEC §3.
- `brand_id` UUID FK → `brands.id`, **NULL 허용**(nullable brand_id) — **[문서]** §3. FK 옵션(ON DELETE/UPDATE) — **[미확정/제안: 기본 제한(RESTRICT) 검토]**.
- `category`(업종) — **[문서]** §3(필드 존재). 값 집합·정규화 — **[미확정]**.
- `operational_status` — **[문서]** §3(필드 존재). 허용값 Enum 부재(ENGINE_SPEC §2에 매장 상태 Enum 없음) — **[미확정]**.
- 위치: 권한 확보 시 `geography(Point,4326)` + GiST — **[문서]** §2·§6. 권리 근거(독립 확보 사실 vs 공급자 관측) 필드·정책 — **[미확정/설계 검토]**, §3 `store_facts`(독립 권리 확보 사실)와 `place_observations`(공급자·TTL) 경계 유지.
- `created_at`·`updated_at` — **[문서]** §2.

## 3. `store_aliases`

- `id` UUID PK; `store_id` UUID FK → `stores.id` — **[문서]** §2·§3(공식·검증된 지점 별칭과 유효 범위).
- `alias` — **[문서]** 존재(필드명·타입 — **[미확정]**).
- "유효 범위" — **[문서]**; 구현 형태(예: `valid_from`/`valid_to`, 검증 상태·근거) — **[미확정/제안]**, 적용 시점 규칙은 정책 확인.
- 동일 별칭 중복·충돌 정책 — **[미확정]**.
- 별칭 판정 근거는 §3 `store_identity_evidence`와 구분 — **[문서]** §3 (근거 테이블 혼용 금지).

## 4. `sources`

- `id` UUID PK — **[문서]** §2.
- `channel_type` — **[문서]** §3(필드 존재). 값 집합·구분 기준 — **[미확정]** (ENGINE_SPEC에 channel_type Enum 없음).
- `canonical_url` — **[문서]** §3. 정규화 URL 컬럼·유일성 규칙은 §4 "ID 없는 URL은 별도 정규화 규칙"·§8 — **[미확정/제안]**, 정규화 규칙 명문화 후 UNIQUE 판단.
- `collection_permission` — **[문서]** §4(필드 존재) + ENGINE_SPEC `CollectionPermissionStatus`(ALLOWED·RESTRICTED·UNKNOWN) — **[문서]** §2/§4. 값 `담지` 시 도메인 준수.
- `permitted_method`(수집 방식; 허가 상태와 별도) — **[문서]** ENGINE_SPEC §2. 값 집합 — **[문서]** §2(열거 예), 구현 Enum 매핑은 후속.
- 소유 공식성 **근거**는 본 테이블의 상태 필드가 아니다 — §6 `source_evidence`가 담당(공식성 근거와 수집 허가의 분리, §7 검토 항목 4) — **[문서]** DATA_MODEL §3("출처 소유 공식성 근거").
- 저장·노출·분석 목적과 만료/삭제 정책 — **[문서]** §3 `data_usage_policies`(별도), 소스와의 연결 정책 — **[미확정/검토]**.

## 5. `source_links`

- `id` UUID PK; `source_id` UUID FK → `sources.id` — **[문서]** §2·§3.
- `brand_id`·`store_id` UUID FK(각 `brands`/`stores`), **브랜드 또는 매장 중 정확히 하나** — **[문서]** §4 CHECK: `(brand_id IS NOT NULL) <> (store_id IS NOT NULL)`.
- `identity_status` — **[문서]** §3(필드) + ENGINE_SPEC `SourceIdentityStatus`(VERIFIED·REVIEW_REQUIRED·REJECTED) — **[문서]** §2·§4.
- 복합 유일성(예: source–brand, source–store 쌍) — **[미확정/제안]**, 판정 직전 정책 확인.
- `created_at`·`updated_at` — **[문서]** §2.

## 6. `source_evidence`

- `id` UUID PK; `source_id` UUID FK → `sources.id` — **[문서]** §2·§3("출처 소유 공식성 근거").
- 유형 — **[문서]** "유형"만 기술; 값 집합 — **[미확정]**, 후속 구현 계약.
- 근거 참조(무엇을 근거로 삼았는지: 문서·등록정보·통보 등) — **[문서]** "근거 참조" 존재; 표현 형식(문자열/JWT? no — JSON 호환 메타/참조) — **[미확정], 민감정보 저장 금지(§1/§7 원칙).
- `verified_at` TIMESTAMPTZ — **[문서]** "검증 시각".
- 공식성 **상태**(VERIFIED 등)는 도출·판정 계층(검수)과 연결 — **[문서]** §4·§7·ENGINE_SPEC 흐름; 근거와 판정 상태의 저장 위치·이력 규칙 — **[미확정/검토]** (검수 결정·이력 테이블과 정합: DATA_MODEL §3 `review_*`, §5).
- 근거·출처 데이터의 보존기간·삭제 정책은 출처 약관·정책 적용 — **[문서]** §7.

## 7. 검토 항목 대조 메모

- 필드·타입: §2 기본 타입 적용. `JSONB`는 "비정형 AI 출력" 용도(§2) — 출처 근거·고정 필드 오용 금지, 주요 검색값은 정형 칼럼(§2).
- UUID·FK: 전 엔터티 UUID PK; 위 서술 FK 외 신규 관계 — **[미확정]**(근거 없이 추가 금지).
- UNIQUE/CHECK: 문서 명시 = `source_links` CHECK(§4), 기타(브랜드명·별칭·출처 정규화 URL 등) 유일성은 §8 확정 항목/정책 확인 — **[미확정]**, 부분 유니크 인덱스 필요 시 구현 티켓.
- 공식성 ↔ 수집 권한 분리: `SourceIdentityStatus`≠`CollectionPermissionStatus`, 수집 방식 별도 필드 [문서 §2·§4]; 출처 "소유 공식성 근거"와 "수집 허가"는 별개 기록(근거 §5, 허가 §4) — **[문서]** 취지.
- 좌표/PostGIS: `geography(Point,4326)`+GiST [문서 §2·§6]; 권한 확보 전제 [문서 §1·§2]; 필드 위치(stores 직접 vs 권리 확보 사실 경유) — **[미확정/설계 검토]**.
- 공급자 권리 ↔ 독립 사실 경계: 공급자 계열은 `data_providers`·`data_usage_policies`·`provider_place_refs`·`place_observations`(TTL)로 관리, 독립적으로 사용할 권리가 확보된 매장 사실은 `store_facts` — **[문서]** §3. `stores` 좌표·속성 병합 근거는 권리 확보된 사실 — **[제안/검토]**, 공급자 관측만으로 merge 금지.
- **Alembic 002의 검증용 테이블 제거**: ▸ 001은 검증 전용 `p1db02_migration_probe`만 담은 마이그레이션(도메인 테이블 없음). ▸ 002(신규, down_revision=001)에서 `op.drop_table(...)`하는 **방안을 제안**하되 — ① 운영·데이터 영향 검토 기록 ② 온라인 격리 스크래치 DB에서 upgrade→001→002→downgrade→재적용 왕복 검증(기존 격리 시험 하네스 재사용) ③ 다운그레이드 시 스키마 복원·데이터 비복원(드롭은 되돌리기 불가) 정책 명문화. ▸ 같은 티켓에서 도메인 테이블을 신설하지 않음 — 슬롯 점검 후 별도. ▸ 구버전 파일 수정·이력 재작성(rebase/edit) 금지, forward 전용.
- **upgrade/downgrade·데이터 보존 정책(준용)**: 추가 우선(additive-first); 삭제·중의 의미 변경은 증거·검토 기반·승인 후; 자동추출→검증 revision→공개 projection 단계 분리(§5); 원문 재분석이 운영자 `field_override` 덮지 않음(§5); 종료·취소·조건 오류 안전 차단 우선(§5). Alembic 다운그레이드는 **스키마 복원이며 드롭된 데이터 복원이 아님** — 데이터 제거는 별도 정책·백업/보존 규칙.
- 멱등성·이력(연습 없음): 재처리 중복 금지·버전 명시 [문서 §1·§10]; 이벤트/오류 기록 원칙 §7·ENGINE_SPEC §10 준용.

## 8. 미확정·결정 필요(요약)

1. 필드명·값 집합(특히 `channel_type`, `operational_status`, 브랜드 상태·별칭 구조, evidence 유형·형식) — 문서 미열거.
2. 출처 정규화 URL 규칙·유일성(§4·§8 확정 항목).
3. 공급자별 관측 TTL·보존/삭제 정책 연결(§1·§8).
4. 좌표 필드 위치·권리 근거 표현, 별칭 유효 범위 표현.
5. Alembic 002 드롭 방식·검증·다운그레이드 스키마 복원 정책(사용자 결정 사항).
6. 동시 검수/갱신 충돌·대용량 이미지 등 §8 나머지 확정 항목(범위 밖).
7. 본 초안은 **설계 제안** — 정식 물리 스키마/ORM/마이그레이션 아님; 확정은 설계 검토·후속 티켓.

## 9. 이번 단계 범위 준수

- 정식 ORM 모델 클래스·DDL·Alembic 002 **작성하지 않음**(지시). 테이블 생성·수정·삭제 명령 실행 없음. 기존 논리 모델·문서 변경 없음.
