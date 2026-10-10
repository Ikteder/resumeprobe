# ResumeProbe 0.1 Implementation Specification

Date: 2026-10-09
Status: Approved for implementation under the user's instruction to continue project work.

## Selection

Manual Friday continuation. Seed `20261009`, Python `random.Random`, mode roll `0.6671329806093301`: distinct open-source project or extension (35% branch). Reconciled completed scheduled focuses are 5 (October 8), 4 (October 5), and 3 (October 1). Eligible focuses `[1, 2, 6, 7]`, uniform index 1: evaluation and reliability. No redraw.

## User and evidence

AI application engineers need to know whether their agent repeats or loses tool effects after process death. LangGraph tasks, Temporal Activities, and Restate durable side effects all have a boundary between an external effect committing and the orchestrator durably recording its result. LangGraph issue 8039 also reports a persistence ordering race. This is motivation, not a claim that this project reproduces that issue.

Existing local workflow and insight-review projects test their application-specific receipts and decisions. Neither launches crashed workers and checks a separate effect sink. FallbackLens statically audits route contracts; RelayFault injects HTTP faults but does not audit checkpoint recovery. A separate portable harness with a real LangGraph adapter is the appropriate home.

## Vertical slice

- Supervisor launches fresh worker processes and injects abrupt `os._exit(86)` without Python cleanup.
- Five scenarios: no crash, before the effect, after effect commit before task return, after task result persistence, and after workflow checkpoint before response acknowledgement.
- Two independently implemented adapters: a small reference checkpoint protocol and LangGraph Functional API with persistent SqliteSaver.
- Compare naive, stable idempotency key, and regenerated-per-attempt key tool modes.
- Separate SQLite sink records committed effects, attempts, and durable trace events. The stable mode atomically binds the key, payload digest, effect, and result in one local sink transaction.
- Strict report schema and independent audit: completion alone is the baseline; count, intent digest, result identity, and crash-reached evidence determine contract outcome.
- CLI matrix, portable JSON, offline HTML with trace details, generated comparison SVG, tests, package, README, full dated records.
- No model, provider, email, payment, remote service, or production tool runs.

## Acceptance

1. Both adapters execute every declared boundary and resume in a different worker process.
2. All stable-key scenarios produce exactly one effect and the same final result. Naive and regenerated-key modes expose duplicates at the after-effect boundary.
3. A crash that was not reached, worker error, timeout, missing effect, duplicate effect, payload drift, or result mismatch cannot be marked safe.
4. A completion-only baseline has at least one false-safe outcome on actual process experiments.
5. Repeat each matrix cell three times. Report all failures, observed counts, versions, and timings. No statistical production reliability inference.
6. Same input seed produces stable scenario identities and payloads; process IDs and measured timings are explicitly nondeterministic evidence.
7. Unit, subprocess integration, real LangGraph integration, malformed input, packaging, clean install, lint, vulnerability audit, style, and visual checks pass.
8. User output paths are never silently overwritten. Reports escape labels and paths. SQLite artifacts remain local and ignored.
9. Public repository only after verification. Preserve accurate local work if account setup blocks repository creation.

## Risks and boundaries

SQLite FULL synchronous commits test process death, not machine power loss or remote-service atomicity. Synthetic effects do not prove a payment provider honors keys. LangGraph saver hooks test task-result persistence at a documented public saver interface; they do not emulate all scheduler interleavings in issue 8039. Version the adapter and record exact packages. Timeout is inconclusive, never safe. No claim of universal exactly-once execution.

## Publication and continuation

Independently authored MIT code, optional MIT LangGraph and SQLite saver dependencies. No upstream code copied. Publish `Ikteder/resumeprobe` after tests; add CI if authorized credentials support workflow files, otherwise document exact setup. Once this slice is verified and cataloged, continue with the strongest measured limitation rather than treating the initial build as the stopping point.
