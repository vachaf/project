# docs/

`docs/`는 현재 프로젝트를 이해하고 재현하는 데 필요한 **최소 기준 문서와 runtime support 자산**을 관리한다.

## 1. 먼저 읽을 문서

1. [00_current_architecture.md](./00_current_architecture.md)  
   현재 `main`에서 시스템이 실제로 어떤 경계와 데이터 흐름으로 연결되는지 설명한다.

2. [00_apache_logs_only_evidence_boundary.md](./00_apache_logs_only_evidence_boundary.md)  
   Apache logs-only 분석에서 관찰 가능한 사실과 단정하면 안 되는 보안 의미의 경계를 정의한다.

3. [operations/README.md](./operations/README.md)  
   DB/환경/Worker 재현에 필요한 최소 실행 절차와 SQL/config 자산을 안내한다.

## 2. 코드 영역 문서

| 문서 | 역할 |
| --- | --- |
| [../src/README.md](../src/README.md) | Analysis Job Worker부터 분석 pipeline까지의 코드 구조 |
| [../src/prepare/README.md](../src/prepare/README.md) | Prepare 내부 policy ownership과 모듈 구조 |
| [../web/README.md](../web/README.md) | Web/Live/Job Detail/Viewer 계층 |
| [../scripts/README.md](../scripts/README.md) | regression/lint/lab 보조 스크립트 |

## 3. Runtime support assets

`operations/` 아래의 다음 자산은 일반 문서와 다르게 실제 재현 또는 테스트 계약에 사용된다.

~~~text
operations/sql/
  MariaDB DDL / DCL / verification SQL

operations/examples/
  Apache security LogFormat 예시
~~~

일부 테스트는 `docs/operations/sql/`의 SQL 원문을 직접 읽어 schema/constraint/grant 계약을 검증한다. 따라서 이 파일들은 단순 historical 문서로 취급하지 않는다.

## 4. 문서 관리 원칙

현재 architecture와 module README가 이미 승계한 과거 설계안, candidate review, investigation, 비교 실험, 작업 계획, UI phase 문서는 current 문서 진입점에서 제외한다.

과거 설계·실험·검토가 필요하면 Git history에서 해당 revision을 확인한다.

~~~text
Current docs
  -> 지금 코드를 이해하기 위한 문서

Git history
  -> 설계 과정 / 실험 / 과거 검증 provenance
~~~

문서 정리 시에는 삭제 전에 반드시 repository 전체 역참조를 확인한다.

- 코드/테스트가 파일 내용을 직접 읽는가
- 현재 README가 상대 경로로 참조하는가
- script/config가 운영 문서 경로를 참조하는가
- 삭제 대상끼리의 참조인지, 살아남을 파일에서 들어오는 참조인지

삭제 대상끼리만 연결된 historical link는 함께 제거할 수 있지만, 살아남을 파일에서 삭제 대상으로 들어오는 참조는 먼저 현재 기준 문서로 교체한다.

## 5. 목표 구조

발표 준비용 `docs/final/` 자산을 제외하면 장기적으로 다음 정도의 구조를 기준으로 한다.

~~~text
docs/
├─ README.md
├─ 00_current_architecture.md
├─ 00_apache_logs_only_evidence_boundary.md
└─ operations/
   ├─ README.md
   ├─ sql/
   └─ examples/
~~~

발표/검증을 위해 일시적으로 필요한 문서는 발표 종료 전까지 별도로 유지할 수 있다.
