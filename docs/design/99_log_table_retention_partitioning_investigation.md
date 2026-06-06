# Log Table Retention / Partitioning Investigation

- Status: investigation only
- Date: 2026-06-06
- Scope: `apache_access_logs`, `apache_security_logs`, `apache_error_logs`
- Non-goal: DB schema change, SQL migration, worker/pipeline/Web implementation

## 1. 목적과 범위

Apache source log tables의 장기 운영 리스크를 줄이기 위해 보존(retention)과 파티셔닝(partitioning) 후보 정책을 조사한다. 이번 문서는 현재 schema/query pattern, growth risk, migration risk, 사전 점검 SQL, smoke plan을 정리하는 조사 산출물이다.

이번 문서는 어떤 SQL도 적용하지 않는다. 특히 `ALTER TABLE`, partition DDL, index 변경, 데이터 삭제, archive/drop 작업은 포함하지 않는다.

## 2. 현재 schema/query pattern

현재 DDL 기준 문서는 `docs/operations/sql/01_apache_log_tables.sql`이다. 세 테이블 모두 `ENGINE=InnoDB`, `utf8mb4`, `log_time DATETIME(3) NOT NULL`, `created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)`를 사용한다. 시간 저장 기준은 UTC naive `DATETIME(3)`이다.

### `apache_access_logs`

- Primary key: `PRIMARY KEY (id)`
- Time index: `KEY idx_access_log_time (log_time)`
- Other indexes:
  - `KEY idx_access_client_ip (client_ip)`
  - `KEY idx_access_status_code (status_code)`
- Wide columns:
  - `raw_request TEXT`
  - `uri TEXT`
  - `query_string TEXT`
  - `referer TEXT`
  - `user_agent TEXT`
  - `raw_log LONGTEXT`

### `apache_security_logs`

- Primary key: `PRIMARY KEY (id)`
- Time index: `KEY idx_security_log_time (log_time)`
- Other indexes:
  - `KEY idx_security_request_id (request_id)`
  - `KEY idx_security_error_link_id (error_link_id)`
  - `KEY idx_security_src_ip (src_ip)`
  - `KEY idx_security_status_code (status_code)`
  - `KEY idx_security_log_schema (log_schema)`
  - `KEY idx_security_client_ip_source (client_ip_source)`
- Wide columns:
  - `remoteip_proxy_chain TEXT`
  - `raw_request TEXT`
  - `request_target TEXT`
  - `uri TEXT`
  - `query_string TEXT`
  - `location TEXT`
  - `referer TEXT`
  - `origin TEXT`
  - `user_agent TEXT`
  - `x_forwarded_for TEXT`
  - `raw_log LONGTEXT`

### `apache_error_logs`

- Primary key: `PRIMARY KEY (id)`
- Time index: `KEY idx_error_log_time (log_time)`
- Other indexes:
  - `KEY idx_error_error_link_id (error_link_id)`
  - `KEY idx_error_request_id (request_id)`
  - `KEY idx_error_log_level (log_level)`
- Wide columns:
  - `message LONGTEXT`
  - `raw_log LONGTEXT`

### Export/query pattern

`src/export_db_logs_cli.py`의 `TABLE_MAP`은 세 source table을 동일한 exporter path로 다룬다.

```sql
SELECT *
FROM <table_name>
WHERE log_time >= %s
  AND log_time < %s
ORDER BY log_time ASC, id ASC
```

현재 pipeline은 사용자가 KST로 입력한 범위를 UTC DB time으로 변환한 뒤 export한다. 기본 table option은 `security`지만, `access`, `security`, `error` 모두 동일한 `log_time` range scan pattern이다.

기대되는 index access는 각 테이블의 `idx_*_log_time` range scan이다. 단, `ORDER BY log_time ASC, id ASC`는 time index만으로 완전히 커버되지 않을 수 있다. row count가 크거나 동일 `log_time` row가 많은 경우 `log_time, id` composite index가 필요한지 별도 EXPLAIN으로 확인해야 한다. 이번 문서는 index 변경을 제안만 하며 적용하지 않는다.

`web/services/analysis_job_repository.py`는 `analysis_jobs`/`analysis_reports`/`job_events` control table을 조회/변경한다. source log table retention/partitioning과 직접 schema coupling은 없다. 다만 analysis job의 `time_from`/`time_to`가 source log export window로 전달되므로 retention 정책은 사용자가 조회 가능한 최대 과거 기간과 운영 runbook에 영향을 준다.

## 3. table growth risk

세 source table은 append-heavy 로그 테이블이다. 특히 `apache_security_logs`는 컬럼 수와 text field가 많고, access/error table도 `raw_log`/message 계열 long text를 보관한다. 장기 운영 시 주요 리스크는 다음과 같다.

- `idx_*_log_time` range scan이 계속 동작하더라도 index/tree와 table size가 커져 backup, restore, optimize, DDL 시간이 증가한다.
- raw text columns가 많은 row는 buffer pool pressure와 backup volume을 증가시킨다.
- time-bounded export는 일반적으로 최근 기간을 조회하지만, unbounded 또는 넓은 기간 export는 큰 I/O를 만들 수 있다.
- retention 없이 무기한 보관하면 delete 작업이 대량 undo/redo, replication lag, lock pressure를 유발할 수 있다.
- drop/archive 단위가 없으면 오래된 로그 정리가 느린 `DELETE WHERE log_time < ...` 형태가 되기 쉽다.

## 4. partitioning options

### Option A: no partition, keep current indexes

현재 schema를 유지하고 `idx_*_log_time` 및 운영 retention runbook만 보강한다. 즉시 migration risk가 없고, 기존 PK와 insert path를 건드리지 않는다. 단, 오래된 데이터 삭제는 batched delete 또는 archive-copy-delete 방식이 필요하다.

### Option B: monthly RANGE partition by `TO_DAYS(log_time)`

예상 형태:

```sql
PARTITION BY RANGE (TO_DAYS(log_time)) (
  PARTITION p202606 VALUES LESS THAN (TO_DAYS('2026-07-01')),
  PARTITION p202607 VALUES LESS THAN (TO_DAYS('2026-08-01')),
  PARTITION pmax VALUES LESS THAN MAXVALUE
)
```

장점:

- `WHERE log_time >= ? AND log_time < ?` 조건에서 partition pruning 기대.
- 월 단위 `DROP PARTITION`으로 오래된 raw logs를 빠르게 제거 가능.
- MariaDB partition maintenance 문서도 time-range partition을 recent query pruning과 fast drop 용도로 설명한다.

주의:

- MariaDB partitioning 제한에 따르면 partitioning expression에 사용된 모든 column은 table의 모든 unique key에 포함되어야 한다.
- 현재 세 table은 `PRIMARY KEY(id)`이므로 `log_time` partitioning을 적용하려면 PK를 `(log_time, id)` 또는 `(id, log_time)` 형태로 재설계해야 할 가능성이 높다.
- PK 변경은 auto increment semantics, secondary index size, insert locality, downstream code의 `id` 정렬/참조 가정에 영향을 줄 수 있다.
- 기존 large table에 `ALTER TABLE ... PARTITION BY ...`는 table rebuild와 긴 metadata lock을 유발할 수 있다.

### Option C: monthly RANGE COLUMNS partition by `log_time`

예상 형태:

```sql
PARTITION BY RANGE COLUMNS (log_time) (
  PARTITION p202606 VALUES LESS THAN ('2026-07-01 00:00:00.000'),
  PARTITION p202607 VALUES LESS THAN ('2026-08-01 00:00:00.000'),
  PARTITION pmax VALUES LESS THAN (MAXVALUE)
)
```

장점은 Option B와 유사하며 `DATETIME(3)` column을 직접 표현할 수 있다. MariaDB는 `RANGE COLUMNS`를 지원한다. 다만 unique/primary key partition-key 포함 제약은 여전히 확인해야 하며, 실제 MariaDB version과 optimizer behavior를 staging에서 검증해야 한다.

### Option D: archive table split without native partitioning

예상 방식:

- hot table: 최근 N개월만 유지
- archive table: 월별 또는 기간별 archive table로 이관
- Web/worker export는 우선 hot table만 조회

장점은 current hot table schema를 크게 바꾸지 않고 운영 가능하다는 점이다. 단점은 archive 조회가 별도 tooling/runbook을 필요로 하고, export가 archive까지 자동 조회하지 않는 한 과거 분석 UX가 제한된다.

## 5. retention options

후보 정책:

- Lab/dev: 1-3개월 보존. 재현성 필요한 실험 기간은 run artifact로 보존하고 raw source logs는 짧게 유지.
- Small production: 3-6개월 hot retention. 월별 logical backup 후 삭제.
- Higher-volume production: 6-12개월 또는 규정 기반. 월별 partition drop 또는 archive 후 drop을 고려.

삭제 전 필수 원칙:

- drop/delete 전 backup 또는 archive 완료 확인.
- backup restore smoke 또는 최소한 archive row count/hash sampling 확인.
- retention cutoff는 KST 운영 캘린더와 UTC DB 저장 기준을 혼동하지 않도록 UTC cutoff로 계산한다.
- `analysis_jobs`/`analysis_reports` artifact는 source log table retention과 별도로 보존 여부를 결정한다. source raw log가 삭제되어도 이미 생성된 artifact/report는 남을 수 있다.

## 6. migration risks

파티셔닝 migration의 주요 위험:

- 현재 `PRIMARY KEY(id)`가 partition key `log_time`을 포함하지 않는다. MariaDB partitioning 제약상 PK 변경이 필요할 수 있다.
- PK 변경은 모든 secondary index leaf에 포함되는 clustered key 크기 증가로 storage/index size가 늘 수 있다.
- large table `ALTER`는 긴 rebuild, disk temp space, metadata lock, replication lag를 유발할 수 있다.
- `AUTO_INCREMENT`와 composite PK 조합은 insert/order semantics를 검증해야 한다.
- `ORDER BY log_time ASC, id ASC` 쿼리와 partitioned table의 filesort 여부를 EXPLAIN으로 검증해야 한다.
- `DROP PARTITION`은 되돌리기 어렵다. backup/restore 절차 없이는 운영 적용하면 안 된다.
- application user grants, backup tooling, monitoring, DDL deployment process가 partitioned table을 정상 처리하는지 확인해야 한다.

MariaDB 공식 문서 참고:

- Partitioning limitations: https://mariadb.com/docs/server/server-usage/partitioning-tables/partitioning-limitations
- Partition pruning and selection: https://mariadb.com/docs/server/server-usage/partitioning-tables/partition-pruning-and-selection
- Partition maintenance: https://mariadb.com/docs/server/server-usage/partitioning-tables/partition-maintenance
- RANGE COLUMNS/LIST COLUMNS: https://mariadb.com/kb/en/range-columns-and-list-columns-partitioning-types/

## 7. recommended MVP policy

MVP 권장 결론:

1. 즉시 native partition을 적용하지 않는다.
2. 먼저 live row count, monthly distribution, table/index size, EXPLAIN을 수집한다.
3. 현 schema에서는 `idx_*_log_time` 기반 time range export가 이미 명확하므로, 초기 운영은 index health와 retention runbook으로 시작한다.
4. retention은 환경별로 분리한다.
   - lab/dev: 1-3개월 raw source logs 보존
   - production 후보: 3-6개월 hot raw logs 보존
5. 오래된 raw logs 삭제는 첫 단계에서 batched delete + backup-before-delete로 검토한다.
6. row volume이 월 수백만-수천만 단위로 커지거나 delete/backup 시간이 운영상 문제가 되면 partition migration을 별도 설계/검증한다.
7. partition을 채택한다면 월 단위 RANGE/RANGE COLUMNS가 1순위 후보이며, migration은 shadow table 또는 maintenance window 기반으로 설계한다.

즉, MVP는 "partition first"가 아니라 "measure first, retain safely, partition only after evidence" 정책을 권장한다.

## 8. required pre-migration checks

실제 DB에서 아래 SQL을 먼저 수집해야 한다. 이 문서 작성 시점에는 실행하지 않았다.

### Version / engine / partition support

```sql
SELECT VERSION();

SHOW VARIABLES LIKE 'have_partitioning';

SELECT TABLE_NAME, ENGINE, TABLE_ROWS, DATA_LENGTH, INDEX_LENGTH, AUTO_INCREMENT
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'web_logs'
  AND TABLE_NAME IN ('apache_access_logs', 'apache_security_logs', 'apache_error_logs');
```

### Schema / index confirmation

```sql
SHOW CREATE TABLE apache_access_logs\G
SHOW CREATE TABLE apache_security_logs\G
SHOW CREATE TABLE apache_error_logs\G

SHOW INDEX FROM apache_access_logs;
SHOW INDEX FROM apache_security_logs;
SHOW INDEX FROM apache_error_logs;
```

### Monthly growth distribution

```sql
SELECT 'access' AS table_name,
       DATE_FORMAT(log_time, '%Y-%m-01') AS month_utc,
       COUNT(*) AS row_count,
       MIN(log_time) AS min_log_time,
       MAX(log_time) AS max_log_time
FROM apache_access_logs
GROUP BY DATE_FORMAT(log_time, '%Y-%m-01')
UNION ALL
SELECT 'security',
       DATE_FORMAT(log_time, '%Y-%m-01'),
       COUNT(*),
       MIN(log_time),
       MAX(log_time)
FROM apache_security_logs
GROUP BY DATE_FORMAT(log_time, '%Y-%m-01')
UNION ALL
SELECT 'error',
       DATE_FORMAT(log_time, '%Y-%m-01'),
       COUNT(*),
       MIN(log_time),
       MAX(log_time)
FROM apache_error_logs
GROUP BY DATE_FORMAT(log_time, '%Y-%m-01')
ORDER BY table_name, month_utc;
```

### Query plan checks

```sql
EXPLAIN
SELECT *
FROM apache_security_logs
WHERE log_time >= '2026-06-01 00:00:00.000'
  AND log_time < '2026-06-02 00:00:00.000'
ORDER BY log_time ASC, id ASC;

EXPLAIN
SELECT *
FROM apache_access_logs
WHERE log_time >= '2026-06-01 00:00:00.000'
  AND log_time < '2026-06-02 00:00:00.000'
ORDER BY log_time ASC, id ASC;

EXPLAIN
SELECT *
FROM apache_error_logs
WHERE log_time >= '2026-06-01 00:00:00.000'
  AND log_time < '2026-06-02 00:00:00.000'
ORDER BY log_time ASC, id ASC;
```

### Old data retention candidate sizing

```sql
SELECT COUNT(*) AS old_rows
FROM apache_security_logs
WHERE log_time < UTC_TIMESTAMP(3) - INTERVAL 6 MONTH;

SELECT COUNT(*) AS old_rows
FROM apache_access_logs
WHERE log_time < UTC_TIMESTAMP(3) - INTERVAL 6 MONTH;

SELECT COUNT(*) AS old_rows
FROM apache_error_logs
WHERE log_time < UTC_TIMESTAMP(3) - INTERVAL 6 MONTH;
```

## 9. test/smoke plan

No schema-change smoke:

1. Collect row count/monthly distribution/table size.
2. Run EXPLAIN for representative 1-hour, 1-day, 7-day export windows.
3. Run export smoke for each table with a small recent window.
4. Confirm output ordering remains `log_time ASC, id ASC`.
5. Confirm pipeline full_report still exports expected table/window.

Partition migration smoke, if later approved:

1. Create staging copy or shadow table with identical data sample.
2. Test `RANGE COLUMNS(log_time)` and `RANGE(TO_DAYS(log_time))` variants.
3. Confirm required PK/index shape on the target MariaDB version.
4. Compare EXPLAIN partition pruning for 1-hour, 1-day, cross-month windows.
5. Test insert path from log shipper against partitioned table.
6. Test monthly partition add/drop procedure on staging only.
7. Test backup before drop and restore of a dropped month.
8. Prepare rollback: keep original table intact or use rename-based cutover with verified backup.

## 10. do-not-change list

This investigation does not change:

- DB schema
- SQL migration files
- production tables
- retention/delete/archive state
- worker/pipeline code
- Web UI
- analysis job state transitions
- `analysis_reports` mapping
- source log parsing semantics

No commit should be created for this investigation unless explicitly requested later.
