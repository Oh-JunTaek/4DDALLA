# 4 DDALLA — Engine Contracts

- Version: 1.0.0
- Contract namespace: `4ddalla.contracts.v1`
- Status: CONTRACT_BASELINED (logical contracts; Pydantic implementation pending)
- Last updated: 2026-11-12 (DOC-001 보완 반영)

## 1. 공통 Envelope / 실행 결과

모든 엔진은 `schema_version`, `run_id: UUID`, `job_id: UUID`, `input_ref{object_type, object_id: UUID, version}`, `requested_at: TIMESTAMPTZ`를 받는다. 출력은 `execution_status`, `result_ref`, `evidence_refs`, `issues`, `processed_at`, `engine_version`을 포함한다. 엔진별 `input`/`output`은 별도 Pydantic 타입으로 구현한다. **예시 ID 문자열을 실제 UUID로 오해하지 않는다.**

```json
{
  "schema_version": "1.0",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_id": "550e8400-e29b-41d4-a716-446655440001",
  "input_ref": {
    "object_type": "SOURCE_CONTENT_VERSION",
    "object_id": "550e8400-e29b-41d4-a716-446655440002",
    "version": 1
  },
  "requested_at": "2026-11-11T11:00:00Z"
}
```

## 2. 상태값 단일 기준

| Enum | 허용값 |
|---|---|
| `SourceIdentityStatus` | VERIFIED, REVIEW_REQUIRED, REJECTED |
| `CollectionPermissionStatus` | ALLOWED, RESTRICTED, UNKNOWN |
| `PromotionValidationStatus` | VALIDATED, REVIEW_REQUIRED, REJECTED |
| `StoreApplicabilityStatus` | CONFIRMED, UNCERTAIN, EXCLUDED |
| `PromotionLifecycle` | UPCOMING, ACTIVE, ENDED, CANCELLED, UNKNOWN |
| `PublicationBucket` | CONFIRMED_LIST, UNCERTAIN_LIST, UPCOMING_LIST, HIDDEN |
| `ExecutionStatus` | SUCCESS, UNCHANGED, PARTIAL, FAILED, RESTRICTED |
| `ContentClassification` | PROMOTION, NON_PROMOTION, UNDETERMINED |
| `MonitorChangeType` | NEW, UPDATED, ASSET_UPDATED, MISSING_FROM_LIST, UNAVAILABLE |
| `PromotionScopeType` | ALL_STORES, ALL_EXCEPT, SELECTED_STORES, REGIONAL, UNKNOWN |
| `ScopeCompleteness` | COMPLETE, INCOMPLETE, UNKNOWN |
| `ErrorSeverity` | CRITICAL, HIGH, MEDIUM, LOW |

상태값의 도메인을 섞지 않는다. 구조 변경(`STRUCTURE_CHANGED`) 같은 상세 실패는 issue.code로 표현한다. 수집 방식 `OFFICIAL_API`, `RSS`, `HTML`, `WEBHOOK`, `MERCHANT_SUBMISSION`은 수집 **허가 상태와 별도** 필드다.

## 3. StoreDiscovery

- **입력:** 지원 지역, 중심점, 800/1000m, 업종, 허용 공급자.
- **출력:** 매장 후보, 외부 장소 참조, 중복 후보, 식별 근거, 데이터 사용·보존 권한.
- **제약:** 공급자 외부 ID를 내부 ID로 쓰지 않는다. 공급자 보관·표시·분석 제한 준수. 페이지네이션·밀집 지역 분할 조회·중복 후보 확인 절차를 정의한다(공급자 요청 한도·약관 범위 내).

## 4. SourceDiscovery

- **입력:** 매장/브랜드 내부 ID, 사용 권한이 확보된 상호/주소 등, 기존 공식 링크, 검색 예산.
- **출력:** 후보 URL, 공식성 증거 및 SourceIdentityStatus, CollectionPermissionStatus, 검수 필요 여부.
- **규칙:** 검색 순위/이름 유사도/LLM 자신감만으로 공식 판정 금지. 동명 매장 충돌 검증. 이용자 후기 단서만 활용. 권한이 `ALLOWED`가 아니면 자동 수집 금지. URL 안전성 검사.

## 5. SourceMonitor

- **입력:** VERIFIED 채널, ALLOWED 수집 방식, checkpoint, 요청 상한.
- **출력:** NEW/UPDATED/ASSET_UPDATED/MISSING_FROM_LIST/UNAVAILABLE 관측, checkpoint 후보, 오류, 분석 필요 여부.
- **규칙:** 목록 사라짐≠행사 종료. HTML 정규화 및 본문·이미지 지문 별도. 변경 없음이면 OCR/LLM 재호출 금지(명시적 모델 재평가는 예외). 데이터 저장+후속 작업 생성과 checkpoint 커밋 원자화. HTTP 429/Retry-After 및 접근 정책 준수.

## 6. PromotionExtractor

- **입력:** source_content_version ID, 권한 있는 HTML/이미지, 모델·추출 스키마 버전.
- **출력:** 콘텐츠 유형, 0개 이상 행사 후보, 상품·혜택·금액·기간·이용조건·매장 범위, 필드별 원본 증거, unresolved_fields, 실행 모델/버전.
- **규칙:** HTML 우선. 이미지 OCR은 bbox/polygon·인식 신뢰도·이미지 ID 보존. 작은 제외 조건 재인식; 판독 불가면 표시. 가격과 메뉴 관계, 연도 누락, 제외 지점 불완전성은 추측하지 않는다. 정상가 없음/1+1/증정은 정상적인 데이터 형태다. 행사 후보 0건은 실패가 아니며('조사·추출 성공, 대상 없음'), 실행 상태(SUCCESS 계열)와 실패/미확인을 구분해 기록한다.

## 7. PromotionValidator

- **입력:** 추출 후보, 공식 출처 증거, 원본·추출 버전, 검증 규칙 버전.
- **출력:** VALIDATED/REVIEW_REQUIRED/REJECTED, checks{code,result}, blocking issues, 증거, 검수 요청.
- **규칙:** 혜택·가격·기간·필수 조건·지점 제한·원문 근거·모순 검사. 해석 실패는 일괄 REJECTED가 아니라 REVIEW_REQUIRED. 승인된 종료일 미정 예외는 추적·재검증 조건 필수. `VALIDATED` ≠ 자동 공개.

## 8. StorePromotionMatcher

- **입력:** VALIDATED 행사 revision, scope, 브랜드·지점 identity evidence, 명시적 포함/제외, 수동 판정.
- **출력:** CONFIRMED/UNCERTAIN/EXCLUDED, reason_codes, evidence_refs, conditions, requires_review.
- **규칙:** 지점명 유사도만으로 확정 금지. 불완전한 제외 목록은 '제외 없음'이 아니다. 상충 증거는 검수. 쿠폰/시간/결제 조건은 지점 참여 여부와 분리. 전국 공통 행사에 모든 매장 행을 강제하지 않는다.

## 9. PublicationService

- **입력:** 검증된 행사 revision, 지점 판정, 매장 상태, 기간/시간 조건, 공개 권한/관리자 차단, 현재 시각.
- **출력:** CONFIRMED_LIST/UNCERTAIN_LIST/UPCOMING_LIST/HIDDEN과 공개 전용 projection.
- **규칙:** 검증+지점 확인만으로 현재 이용 가능 보장 금지. 종료·취소·폐업·긴급 차단 우선. 예정 및 적용 미확인은 별도 목록. 시간대·쿠폰 조건 표시. 최신성 초과 시 경고/제한. OCR/LLM 원시 내용과 관리자 메모 미노출. 공개 API 요청 중 OCR/LLM 금지.

## 10. 오류·멱등성 공통 규칙

오류에는 event_id, job_id/run_id, module, error_code, severity, occurred_at, retryable, fingerprint, redacted_context 포함. **모든** 실패 발생 건 기록. 대시보드 집계와 알림은 별도. 재처리는 `(input_id, input_version, engine_version, schema_version, operation)` 등의 명시적 멱등성 키로 중복 차단. LLM 모델 교체 재분석은 새 실행 기록이나 같은 행사 중복 게시 금지.

## 11. 불변식 / 계약 테스트

1. AI가 원문에 없는 가격·날짜·적용 매장을 확정하지 않는다.
2. 미확인 공식성·수집 권한을 성공으로 취급하지 않는다.
3. 행사 후보→검증→지점 적용→공개는 각각 독립 승인 계층이다.
4. 입력/출력 UUID, enum, 날짜·가격 검증; 필수 근거 누락 검출.
5. 원문 수정·수동 정정 충돌 발생 시 검수, 덮어쓰기 금지.
6. 동일 콘텐츠 반복 수집과 워커 재시도로 중복 행사가 생기지 않는다.
7. 서버만 최종 공개를 결정하고, 로컬 워커는 직접 공개할 수 없다.
8. 공개 차단/만료/시간 조건 변경은 캐시에서도 즉시 유효하다.
9. 작업 실패 이력이 누락되지 않고 checkpoint 안전성이 유지된다.
10. 실제 OCR/검색 공급자·계약 숫자는 POC 전까지 미정이다.
11. 테스트 픽스처·평가 샘플은 사용 권한이 확인된 자료만 사용하고, 평가 기준표를 정하기 전에는 수집·추출 정확도를 주장하지 않는다.

## 12. 계약 버전 정책

호환 가능 필드 추가는 minor 버전, 필드 삭제/의미 변경/호환되지 않는 enum 수정은 major 버전. Pydantic 모델, 테스트 픽스처, API 및 관련 문서를 함께 변경한다. 세부 클래스·물리 테이블은 첫 구현 티켓에서 이 문서에 맞춰 생성하고 테스트한다.

### 12.1 구현 확정 사항 (P1-CONTRACT-02, 2026-11-14)

- `input_ref.version`: 엄격 정수(`StrictInt`)·1 이상. bool·문자열·실수·0·음수 거부.
- `schema_version`: `MAJOR.MINOR` 형식이며 지원 버전을 명시적으로 검사(현재 지원 집합 `{"1.0"}`). 지원 집합 확대·형식 변경은 §12의 계약 변경 절차로 처리한다.
- `engine_version`: `MAJOR.MINOR.PATCH` 형식. 프리릴리스 접미사(예: `-bootstrap`)는 허용하지 않으며, 필요해지면 계약 변경으로 처리한다.
- 미지 필드: 공식 엔진 입력·출력 계약은 거부(`extra="forbid"`). 엔진별 상세 스키마는 후속 티켓에서 같은 기반을 상속해 정의한다.
- `ExecutionIssue`: `event_id` 필수 UUID, `job_id`·`run_id` 필수, `redacted_context`는 JSON 호환 데이터만 허용. 민감정보 검열은 오류 생성 단계의 별도 책임(§6).
- 이력: 위 항목은 문서상 명시가 없던 구현 세부를 구현 계약(P1-CONTRACT-02)이 확정한 것. §1–§11의 기존 필드·Enum 의미와 충돌하지 않으며 제약을 강화한 변경이다.
