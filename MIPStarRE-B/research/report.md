# QPBT Formalization Workflow Report

## Scope

This report records the formalization of the quantum Pauli basis test from
arXiv:2001.04383v3 in Lean 4 and the evolution of its local multi-agent workflow.
The record is observational: unavailable metrics are `null`, approximate timing
is labelled, and successful no-op reviews or scouts remain visible.

## Method

For every stage and issued session, record elapsed time, agent role and lineage,
subagent count, token usage when exposed, owned paths, accepted artifacts,
compile attempts and failures, cache hit/wait/build timing, review rounds and
findings, proof-debt delta, incidents, and active protocol revision. Canonical
machine-readable state is under `workflow/state/`; raw run data is ignored and
retained only locally.

## Stage summary

| Stage | Status | Start | End | Sessions issued | Token data | Key output |
| --- | --- | --- | --- | ---: | --- | --- |
| 1. Workflow skeleton | completed | 2026-08-30 09:31 +08 | 2026-08-31 01:25 +08 | 35 including root | 5 completed CLI sessions exposed usage; collaboration/root totals unavailable | protocols, ledgers, local tooling, frozen-review harness |
| 2. Source split | in progress | 2026-08-31 01:33 +08 | - | 60 terminal sessions plus 1 retained issued attempt; peak concurrency 4 | collaboration usage unavailable; failed reviewers emitted no usage | local immutable review approved; endpoint-dependent transport gate remains |
| 3. Lean blueprint | in progress | 2026-08-31 03:45 +08 | - | 36 terminal sessions; peak concurrency 3 | collaboration usage unavailable | full immutable blueprint approved; exact second-commit rehearsal passed; QPBT-023 tracks the newly found leaf-contract gap |
| 4A. Minimal skeleton | in progress | 2026-08-31 03:45 +08 | - | 266 total issued attempts (265 non-coordinator); 134 Stage-4A attempts; peak concurrency 4 | collaboration usage unavailable | QPBT-020 merged at `4bfdd120`; approved source/blueprint ranges integrated at `65315213`; repair, cache-readiness, and contract lanes were recycled at the measured ceiling |
| 4B. Complete skeleton | planned | - | - | 0 | - | - |
| 4C. Proofs | planned | - | - | 0 | - | - |
| 5. Final audit | planned | - | - | 0 | - | - |

## Baseline observations

The mature MIPStarRE workflow evolved in response to four recurring classes:
paper-statement drift, stale Lean artifacts, duplicated review/build work, and
issue/automation races. Its current design moves fast integrity checks to local
hooks, reviews only after a successful build, keeps deterministic bookkeeping
out of model agents, and caches only main because per-PR caches exhausted the
GitHub budget.

TeXRA adds execution lineage, explicit plan-versus-call state, bounded fan-out,
fresh completion audits, and a third-occurrence rule for extracting abstractions.
Its campaign evidence identifies concurrency duplication as the leading
non-quality failure and treats zero-edit simplification as success.

The local protocol combines those lessons. The campaign has recorded 39
incidents so far, beginning with invalid empty Git metadata, hanging Git
transport, missing expected references, upstream documentation/pin drift, and
ambiguous paper-source redistribution rights. Later incidents came from state
and event-envelope gaps, review persistence and timeout boundaries, explicit
external-disclosure authorization, endpoint transport, and probe construction.
These were recorded before integration so protocol changes remain traceable to
evidence rather than hindsight.

## Stage 1 observations

The deterministic gate grew from the initial workflow checks to 83 tests after
adversarial fixes to cache identity and transactions, immutable review targets,
session/PR/state invariants, interrupt-safe subprocess bounds, and compact
frozen evidence. All current tests pass locally. The active protocol evolved
from `0.1.0` through `0.1.4`. Revision `0.1.1` compacted the review packet after
a small endpoint health probe succeeded but two full review packets produced no
model work. The second packet ran for 1,800.154375 seconds and contained 36,041
bytes; the integrity-preserving replacement is constant in manifest cardinality
and keeps the full manifest digest-bound in the isolated harness. Revision
`0.1.2` then separated instruction isolation from provider routing: the launcher
retains `--ignore-user-config` but supplies the authorized provider name, HTTPS
base URL, Responses wire API, and authentication mode as validated non-secret
overrides before `exec`. Revision `0.1.3` distinguishes frozen-core approval
from the terminal lifecycle and seal that can only be recorded after the
reviewer returns. It also canonicalizes that trusted phase record and binds the
captured core back to the reverified freeze after evidence capture.

Reviewer transport evidence is deliberately retained rather than averaged
away: A04 failed locally before thread creation in 10.292274 seconds; A05 was
manually interrupted after about 1,277 seconds and motivated the timeout
wrapper; A06 was rejected before launch pending explicit disclosure authority;
A07 timed out after 900.154354 seconds; A08 timed out after 1,800.154375
seconds; and compact A10 timed out after 900.152341 seconds. None conferred a
verdict. A10 ruled out packet size and exposed that reviewer isolation had also
disabled the custom provider routing used by the successful endpoint probe,
which took 15.196164 seconds and exposed 17,214 input, 19 output, and 17,233
total tokens. A repository-free canary using the corrected isolated routing
then completed in 15.787069 seconds and exposed 15,166 input, 11 output, and
15,177 total tokens. A12 then completed the first full isolated review in
80.312839 seconds, exposing 219,938 input, 1,878 output, and 221,816 total
tokens. Its blocked verdict identified an impossible pre-return lifecycle/seal
ordering rather than a frozen-core defect. The follow-up fix received two
adversarial trust-boundary findings, closed both, and passed fresh re-review.
The resulting A14 review approved with no findings in 101.945834 seconds after
independently matching all 59 frozen-core entries and all 66 captured files; it
exposed 391,459 input, 3,590 output, and 395,049 total tokens. Its approval was
superseded only because the later staged gate exposed the untracked whitespace
blind spot. A16 then approved the corrected protocol `0.1.4` snapshot with no
findings in 111.408903 seconds after matching all 61 frozen-core files and all
69 captured entries. It exposed 577,028 input, 3,288 output, and 580,316 total
tokens, of which 474,880 input tokens were cached. Other per-agent
token counts were unavailable and remain `null`.

After sealing A14's approved snapshot, the first staged-index check reported 14
new files with blank lines at EOF. The frozen `git diff --check` had inspected
no untracked files, so its recorded success did not cover the eventual root
commit. This concrete failed acceptance test reopened Stage 1, invalidated the
seal for commit purposes, and added a focused untracked-text hygiene gate before
the next freeze. Revision `0.1.4` now rejects a final empty logical line in every
frozen core text file. Its regression and aggregate gates pass 9/9 and 83/83,
respectively; disposable full-tree staging also passes the cached diff check
without touching the real index. An independent child reviewer verified the 14
edits as exact one-LF removals against the prior hashes and approved with no
findings.

The Stage 1 session tree has issued 34 subagents plus the root coordinator,
with observed peak concurrency four. A compact-packet fixer used one child
reviewer; the child requested five integrity properties and approved the
corrected shape. A transport fixer likewise used an independent child reviewer,
which approved the explicit-routing boundary with no findings. The bootstrap
ordering fixer was independently rejected once for helper-level authority
injection and a verification-to-capture race; its fresh re-review approved the
canonicalized, post-capture-bound result. The whitespace fixer also delegated a
fresh reviewer, while a separate read-only closeout audit reconciled the stale
A14 evidence and final allowlist before refreeze. Exact collaboration timing
and token usage were not exposed, so those records use bounded windows rather than
estimates. Three additional read-only scouts used the review wait to prepare
Stage 2 and Stage 3 without claiming writable ownership or changing their
deliverables.

The package-style focused unittest command also failed for the fourth time.
Rather than reopen accepted tooling for convenience, the recurrence is tracked
as `INC-017` and deferred to numbered issue `QPBT-011`.

## Stage 2 observations

The first Stage 2 implementation issue took 1,918.229633 coordinator-observed
seconds and used four logical child attempts. The collaboration backend kept
completed nodes in its four-node tree and exposed no deletion operation, so the
orchestrator reused two retained physical workers under new stable logical
session names. This kept observed project concurrency at four without claiming
that a reused backend thread was a fresh reviewer. Per-agent tokens were not
exposed and remain `null`.

The transport gate now has 38 focused tests and the aggregate suite has 121.
Three live acquisitions succeeded with exact prior checksums: the 233,859-byte
arXiv source directly, the 1,989,153-byte MIPStarRE archive after bounded Git
timeout and REST/codeload fallback, and the 10,743,872-byte TeXRA archive after
Git failure and the same fallback. One preliminary attempt invoked the internal
HTTP worker without its bounded parent and was interrupted after its intended
outer window; the public commands were then used for all acceptance evidence.
This failure reinforced that internal worker entry points are not acquisition
commands and that independent process bounds must surround socket-level timeouts.

The split audit independently fixed the full-document partition at fifteen
inclusive ranges, verified exact CRLF-preserving hashes, and separated three
exact-cover groups from intentionally sparse dependency excerpts. It also found
646 label occurrences and confirmed that duplicate labels require occurrence
records rather than a one-to-one map.

The first fresh transport reviewer attempt prepared its immutable harness but
exited after 10.31035 seconds before creating a thread or contacting the model.
Its 197-byte diagnostic exactly matched `INC-010`: the outer workspace sandbox
made Codex persistence read-only. A 163.832202-second diagnostic scout separated
that host-process failure from the correctly configured provider/model argv.
The immediate protocol remains approved host-level persistence for the wrapper
around a nested read-only, instruction-isolated reviewer. Permanent preflight
and ordinary-failure byte accounting are deferred to `QPBT-012`; the failed
attempt supplied no verdict or token usage.

A later 217-second supplemental local review of the immutable transport head
requested three changes while explicitly not replacing the required external
review. REST fallback checked that the expected commit existed but dropped the
requested revision binding; a hard link to the original temporary inode could
survive publication because only device/inode substitution was checked; and
`communicate()` could retain unbounded child output in memory until timeout.
`LPR-001` is now changes-requested while a scoped fixer adds revision-bound REST,
single-link descriptor invariants, and bounded streaming diagnostics.

To increase throughput without weakening dependency acceptance, two read-only
split scouts ran concurrently for 314 and 294 seconds and produced independent
security and manifest/test contracts. QPBT-002 implementation then started on
an isolated branch based on the immutable QPBT-010 candidate. This work is
explicitly speculative: it may compile and test in parallel, but it cannot be
accepted or merged until QPBT-010 has an authorized independent review and is
integrated. Retained collaboration nodes are represented as new logical
sessions with their physical reuse recorded, not as fresh processes.

The source split orchestrator ran for 2,099.27766 seconds and issued five
security/fidelity audit rounds. Its initial 27 focused and 148 aggregate tests
produced 39 inventory-bound files and 646 label occurrences with inventory
SHA-256 `04548808c30c476e9b2b7cb2f728a6d0c348a6706a8ed1bc9fb9945f20a124f4`.
A later root acceptance preflight found that recursive cleanup could leave a
markerless live-transaction directory. The 390-second fixer replaced deletion
with an atomically renamed, startup-recognizable tombstone and added four crash
regressions; root independently reproduced 31/31 focused and 152/152 aggregate
tests. A 77-second follow-up review attempt was reassigned before verdict and is
recorded as interrupted, not approval. A fresh 187-second reviewer then found
that rollback could follow a symlinked backup boundary and move an external
tree, and that a post-delete fsync failure could be reported as retained state
when no state remained. The 219-second fixer bound rollback through no-follow
directory descriptors, validated all saved trees before mutation, used
directory-relative renames, and distinguished retained paths from deletion
durability uncertainty. Root reproduced 35/35 focused and 156/156 aggregate
tests plus the exact 39-file, 646-label materialization. A different physical
reviewer is still required. QPBT-002 also remains blocked on an approved,
integrated QPBT-010 base.

That next 286-second reviewer used pathname- and entry-swap reproductions and
found two high TOCTOU defects plus one medium state-coherence defect. Rollback
closed its validated descriptors before fsync and cleanup, so a renamed runtime
path could redirect cleanup into an external tree. A saved backup entry could
also be swapped after static validation but before rename, and a declared
original tree with neither backup nor current destination was silently treated
as successful recovery. This is a recurring lesson: no-follow validation at
one instant is not a durable authority boundary. The 474-second fixer keeps
bound descriptors live across the transaction and adds deterministic swap and
missing-state regressions. It passes 40/40 focused and 161/161 aggregate tests
plus exact materialization verification; a different physical reviewer is now
auditing the result.

That 206-second review confirmed the repaired rollback helper but reproduced
the same runtime-path redirection through older pathname-based tombstone helpers
still used by successful publication, stale recovery, markerless startup, and
initialization cleanup. The current fix applies one descriptor-bound cleanup
authority model to every reachable call site, with normal-publication and
markerless-startup swap regressions.

A 346-second ledger audit inspected 18 pre-import Stage 2 sessions, 17 terminal
metrics, the pending QPBT-010 reviewer, and three independently observed
four-way intervals. The same import added the finding, fixer, interrupted
review, audit, and QPBT-012 implementation for 23 issued Stage 2 sessions. It
also identified that syntactically valid stage counters could drift from the
session ledger. QPBT-012 now derives the count, checks metric issue/stage
identity, emits canonical lifecycle session identifiers, records bounded
ordinary-failure digests, and probes host persistence before evidence
preparation. Its first 217-second review found a duplicate-probe ordering
defect. A 242-second fix split private post-probe execution from the public API,
and a fresh reviewer on a different physical node approved with no findings in
243 seconds after 34/34 local-agent, 34/34 workflow, and 93/93 aggregate tests.
The issue was then frozen as
`67ead7513109a4dd76ba367c1368f7d7c4e364f3`. A 133-second immutable-head
reviewer approved the exact six-path commit with no findings after reproducing
the same focused and aggregate gates plus a strict historical-event replay.
`LPR-003` is approved; integration remains deferred until after the requested
blueprint milestone commit so it does not consume the second `main` commit.

## Stage 3 preflight observations

Three additional read-only scouts mapped the pinned upstream Lean API, the
source-labelled proof DAG, and the local blueprint toolchain. Upstream provides
finite-field trace/Fourier, measurement, state-distance, Naimark, isometry, and
classical LDT components, but not generalized Pauli/EPR definitions, pure-state
transport through local isometries, dependent-outcome Naimark packing, or the
QPBT-to-LDT strategy adapter. The proof DAG has no genuine cycle, but six
soundness nodes remain blocked by concrete paper gaps; completeness is an
independent reachable branch.

The installed TeX toolchain can build a deterministic local PDF and Graphviz
dependency view. Web generation is not yet a reproducible gate because
`leanblueprint`, plasTeX, and TexRA are absent or unpinned; this is recorded as
unavailable rather than silently installed. The blueprint will therefore use a
standard-library source/DAG checker, local PDF build, statement-integrity
tables, and explicit paper-gap links before any optional web artifact.

A further 231-second scout converted the gap dispositions into an acyclic
definition/theorem DAG and thirteen issue-ready work packages. Completeness
branches directly after the typed game. Soundness proceeds through simultaneous
Naimark dilation, finite win consequences, expanded observables, fiberwise
linearity, restricted lines and direct-axis LDT, global measurement, exact
Pauli representation, extraction, and a proved squared-norm-to-norm robustness
bridge. Every paper repair remains an internal proved lemma rather than a new
public hypothesis.

The speculative blueprint implementation then ran for 1,219 seconds and
produced 46 declaration nodes, 12 dependency chapters, 13 explicit paper-gap
dispositions, a deterministic JSON/DOT graph, and a 41-page PDF. Root reproduced
all 8 tests, the acyclic/source-anchor checks, the PDF build, and text extraction.
The first 320-second independent review requested three changes: replace a
provisional soundness-critical tensor-code source with an authoritative exact
version contract, validate the semantic closure of every transitive-definition
set, and prevent a long Lean identifier from clipping past the PDF page edge.
The 431-second fixer pinned the published-version source contract, made the
checker derive and enforce definition-only strict prerequisite closures, and
added breakable identifier rendering plus physical-page and extraction gates.
The repaired blueprint passes 15/15 tests and preserves all 103 planned Lean
identifiers in a 42-page PDF. The 232-second follow-up review confirmed the
content and closure fixes but showed that a coherent repin away from
`2111.08131v3` still passed and that the PDF checker ignored left, top, and
bottom overflow. A small validator/test fix now binds the complete expected
external contract and all four physical page edges. The 173-second fix passes
17/17 tests, exact source-root validation, and the 42-page/103-identifier PDF
gate. A fresh final review is still required; no finding is treated as accepted
by passing canonical artifacts alone.

## Stage 4 preflight observations

The upstream Lean project is pinned at commit
`507e81220d95266ff3d589d125b2f87c7300a9fb`, Lean 4.32.0, and Mathlib
`81a5d257c8e410db227a6665ed08f64fea08e997`. The authenticated 1,989,153-byte
archive has SHA-256
`656d92a4ad1fb24216ab0b26c6956b1cfb88ba7816257baa0e668415c0a7adcc`.
It contains no license, COPYING, or NOTICE file. The workflow therefore does
not vendor its 5,976,199 bytes of Lean/project source. QPBT-004 instead uses a
strict checksum-pinned local materializer, keeps upstream bytes ignored, and
tracks only project-authored QPBT files and provenance. The hot-cache design
will bind the materializer and source inventory and elect one builder per key,
so parallel agents do not repeat the Lean dependency build.

The speculative QPBT-004 implementation took 1,292 seconds. Its exact local
materialization contains 337 files / 5,970,111 bytes with inventory SHA-256
`d8d9e7632f5dcdb0cbe7bceeb55c71a0dbbcf6f901c6efd7f4c4814090d096db`,
while `git ls-files MIPStarRE` remains empty. Root reproduced 11/11
materializer tests, 14/14 cache tests, 95/95 aggregate tests, compile checks,
and the exact materialized verification. A fresh independent review is active.
The actual Lean build remains unexecuted because Lean 4.32.0 and the pinned
Mathlib package cache are absent; invoking Lake would perform an unauthorized
download. This missing acceptance gate is recorded rather than inferred from
the Python and provenance checks.

The 407-second review requested one high cache-integrity change. A test-time
build callback could mutate ignored materialized foundation source after the
initial exact check; the builder rechecked tracked inputs but still published
`READY` without revalidating or attesting the source inventory. The 436-second
fix now performs exact post-build verification, binds the source commit,
inventory, file and byte counts, and authored-QPBT digest evidence into cache
publication, and validates the closed contract on hits and after seeding. Its
11/11 materializer, 17/17 cache, and 98/98 aggregate tests pass; independent
re-review remains required.

A separate 178-second environment audit confirmed that this machine is not
offline-build ready: Elan 4.1.2 has zero installed toolchains, its cached
3,850,240-byte Lean archive is truncated, none of the nine exact Lake package
commits exists locally, and no hot-main cache has been published. The pinned
MIPStarRE archive is present and authenticated. One coordinator-authorized
elected builder must therefore acquire Lean, packages, and Mathlib cache data;
parallel agents must wait on the same cache key rather than initiate duplicate
downloads or compilation.

The coordinator then performed the single authorized toolchain acquisition.
It began after the audit ended at `20:10:05Z` and was verified complete at
`20:24:17Z`, so the retained timing is a bounded interval of at most 852
seconds rather than a fabricated exact duration. The installed 2.8-GiB
toolchain reports Lean 4.32.0 at commit
`8c9756b28d64dab099da31a4c09229a9e6a2ef35` and Lake 5.0.0. No subagent ran a
competing installer. The one elected Lake dependency acquisition is now
fetching the nine exact manifest revisions before any build begins.

A 468-second read-only QPBT-005 scout mapped the minimal skeleton to ten Lean
files and four dependency-ordered packages. Two foundation packages can run in
parallel; the game interface follows, then the soundness surface. It identified
four statement hazards before elaboration: upstream `LDT.Parameters` silently
adds `0 < m`, the project has two incompatible measurement namespaces, family
approximation is a squared defect while the public state conclusion is an
unsquared norm, and the real-exponent robustness term needs `Real.rpow`. The
plan uses ordinary structures rather than axioms or opaque assumptions.

A separate 154-second theorem-fidelity audit then corrected the plan before any
Lean declaration was written. `PauliExtraction.Realizes` must transparently
state the mapped-state norm bound and four Alice/Bob X/Z family bounds; family
distance is a sum of squared state-dependent norms bounded by `delta`, not
`delta^2`; the public strategy remains an arbitrary POVM bitstring strategy
unless the typed/detyped equivalence is proved; and the field model is derived
from admissibility rather than added as a theorem hypothesis. The ideal system
is `M = 2^m` separate `q`-dimensional EPR pairs, with local carrier
`Fin M -> F_q` and cardinality `q^M`. With all data definitions transparent,
the minimal no-axiom budget is exactly one tracked `sorry`, on
`pauliSoundness` itself.

A 380-second foundation-signature scout then reduced the Lean adaptation
surface to four explicit wrappers: admissible prime-power field data, a
projective-family view over the arbitrary quantum measurement API, a
normalization-bearing distribution bundle, and vector/Euclidean isometries.
It found no reason to expose `LDT.SymStrat` or `LDT.Test.Defs` through the QPBT
public API; both would add assumptions not present in the paper.

Two Stage 2 fixes completed in parallel with that interface work. The
453-second source-split fix moved startup, recovery, publication, and rollback
cleanup beneath one open runtime-directory descriptor. Root reproduced 42/42
focused and 163/163 aggregate tests, exact 39-file/646-label materialization,
compile, and diff checks. A subsequent 256-second non-independent adversarial
audit found that staging writes still escaped back to pathnames and that the
lock could bind a different runtime-directory incarnation. This result cannot
approve the change because that physical session authored an earlier fix, but
its deterministic external-write reproduction reopened the candidate and
triggered descriptor-relative staging and locking work.

The 714-second transport fix addressed all three local-review findings. REST
now resolves the URL-quoted declared revision and compares the returned full
SHA before codeload; temporary publication stays bound to its original file
descriptor and requires a single-link regular inode at each boundary; and
each subprocess stream is capped at 64 KiB while raw byte totals and SHA-256
digests remain available as evidence. Root reproduced 49/49 focused and
132/132 aggregate tests plus compile, workflow, and diff checks. One new
overflow regression initially assumed a pipe write was all-or-nothing; the
test was corrected to loop over legal partial writes before the final passing
run. A 155-second independent candidate review found no material issue and
bound patch digest
`6d14746c525f0ded5a7b3bd56114a0864879a481bcbae3bd9ed8fc3d74936b7f`.
The exact patch is frozen at commit
`e93d949d06af2a7f4407d198a37aad315deac6aa` for immutable re-review. The
separately required external `gpt-5.6-sol` review remains blocked on explicit
authorization to disclose that packet to the user-named endpoint.

The first elected `lake update` attempt ran from approximately `20:24:43Z` to
`20:38:05Z` and failed while cloning Mathlib with a TLS receive error, early
EOF, and invalid pack output. It removed the incomplete checkout and left no
live acquisition process. Exactly one retry was started with HTTP/1.1 and
bounded Git low-speed settings; no agent launched a competing package fetch or
build.

The parallel 283-second game-signature and 257-second soundness-signature
scouts made the planned Lean boundary compile-oriented before implementation.
The public game remains a normalized finite bitstring distribution with
arbitrary POVM strategies; dependent question and answer types sit behind
explicit codecs rather than strengthening the strategy type. The verifier has
seven exhaustive typed checks, and the ideal local carrier is
`Fin (2 ^ m) -> F_q`. The soundness file will contain transparent extraction,
isometry, tensor/reindex, target-state, and four Alice/Bob X/Z family
definitions. Its public theorem derives field data from admissibility and has
one proof placeholder only, on `pauliSoundness`.

The 244-second QPBT-004 re-review found two further cache-integrity defects:
untracked QPBT source created by a build was invisible to the post-build Git
check, and valid-shaped source provenance could be changed together with a
recomputed `READY` digest. The 325-second fix now binds exact committed QPBT
blob facts and pin-derived semantic source facts into the cache identity,
rejects tracked or untracked project-source drift, and exact-compares the
source contract after build, on hits, and after seeding. It passes 20/20 cache,
11/11 materializer, and 101/101 aggregate tests; a new independent candidate
review is active.

A newly spawned reviewer requested as `gpt-5.6-sol` approved immutable
QPBT-010 commit `e93d949d06af2a7f4407d198a37aad315deac6aa` after 236.172
seconds with no findings. It reproduced 49/49 focused and 132/132 aggregate
tests plus a hostile infinite-output probe, compile, workflow, and diff gates.
The runtime identified only the GPT-5 family and did not expose its endpoint,
so the record distinguishes this valid local immutable approval from the
still-unattested review at `https://api.finite-dimensional.space`.

The first bounded Lake retry preserved and checked out exact Mathlib commit
`81a5d257c8e410db227a6665ed08f64fea08e997`, then timed out connecting to
GitHub for the transitive `plausible` package after 129.828 seconds. No build
started. A single policy-authorized unsandboxed retry also failed to connect;
all acquisition processes are terminal and the exact clean Mathlib checkout
remains preserved. The unchanged retry path is now closed rather than repeated.

The 529-second QPBT-002 fix then bound the runtime directory before lock
acquisition and made transaction, staging, backup, publication, rollback,
tombstone, and cleanup operations descriptor-relative. It passed 45/45 focused
and 166/166 aggregate tests. A fresh 256-second independent review nevertheless
found one remaining high-severity boundary defect: default archive acquisition
reconstructed a runtime pathname after descriptor binding, so a directory swap
could split cache authority. A bounded repair now acquires into a private
transport directory and publishes only through the already-bound descriptor.
That 510-second repair passed 46/46 focused and 167/167 aggregate tests, exact
39-file/646-label materialization, archive inspection, compile, workflow, and
diff gates without network access. It remains unapproved by its author.

The first immutable blueprint review took 386 seconds and rejected two
source-inaccurate graph edges despite all 17 tests passing. Generic
orthonormalization incorrectly depended on the Magic Square game, and
completeness incorrectly depended on rigidity. A 118-second fix removed both
edges, added a targeted regression, regenerated the graph and TeX, and passed
18/18 tests plus a fresh 42-page PDF build. The repaired immutable head is
`10d47ce1e8c295c6f924ab7d140e027fa2db3f8e`. A fresh independent review then
approved it with no findings after a 68-second validation window, reproducing
18/18 tests, all 46 source anchors, the fresh PDF checks, and a clean worktree.

A 351-second offline Lake scout replaced blind Git retries with a verifiable
archive path. Lake 5 accepts path package overrides but does not accept plain
source directories for unchanged Git dependencies. The resulting protocol
therefore authenticates each commit and tree through repository metadata,
checks the extracted archive with local `git write-tree`, and passes an explicit
package override to every Lake invocation. One worker owns materialization, so
parallel review and blueprint work cannot duplicate downloads or builds.

The corresponding 862-second implementation added a strict eight-package
archive materializer and complete Lake path override. It bounds ustar and PAX
parsing, validates link targets, authenticates local Git tree identity through
an isolated index, caps transport output, and publishes all packages as one
rollback-capable transaction. Its first focused run exposed and fixed removal
of a pre-existing override during rollback. The final offline gates passed 9/9
focused and 110/110 aggregate tests; production intentionally fails closed
until authenticated archive, API tree, size, and inventory fields are filled.

A 148-second retarget scout found no path or API conflict between the repaired
QPBT-010 transport and the seven-path QPBT-002 candidate. The integration plan
preserves an immutable old-base candidate commit, applies it into a new worktree
rooted at `e93d949d06af2a7f4407d198a37aad315deac6aa`, records retarget provenance,
and then requires fresh 49-test transport, 46-test source, 178-test aggregate,
materialization, and immutable-review gates.

The 735-second Lean namespace scout then replaced several abstract skeleton
assumptions with exact current APIs. QPBT admissibility is `q = 2^k` for odd
`k` plus `m | q`; field data must use a concrete characteristic-two Galois
field; the public POVMs must use `MIPStarRE.Quantum.Measurement`, not the
incompatible projective LDT hierarchy; and raw LDT distributions need a
normalization proof. It also fixed the sigma codec, Euclidean state,
isometry/conjugation, five-bound `Realizes`, `Real.rpow`, and explicit-instance
plans. The 398-second compatibility repair changed exactly 12 blueprint paths,
added targeted regressions, and preserved the theorem and exactly-one-`sorry`
plan. It passes 19/19 tests, 46-node graph checks, compile and diff gates, and a
fresh 43-page PDF containing 106 planned identifiers. A 399-second independent
review found one high statement-fidelity defect despite those green gates: A15
had replaced the paper's squared extraction premise with the public unsquared
contract, leaving R05's conversion lemma without its premise. The 148-second
repair introduced a dedicated squared certificate at A15 and made R05 alone
derive `Realizes`; 19/19 tests and a 43-page PDF with 107 identifiers pass. A
212-second independent review approved the corrected candidate with no findings.
The exact 12 paths were then frozen at
`76cd5f6e46832930a8bb802ed0faa776f661b85f`. A 344-second incremental
immutable review approved the delta from the previously approved head with no
findings, reproducing all 19 tests and the fresh PDF. A final full base-to-head
review then found two intra-page collisions in the generated gaps table that
the physical-edge-only geometry gate missed. It also confirmed that the exact
source-anchor gate cannot pass on the standalone blueprint commit because its
base intentionally lacks the Stage 2 split manifest. A 579-second repair made
anchors breakable, added intra-page word-box checks, and eliminated both
collisions; 19 tests and the 43-page PDF pass. The 309-second candidate review
then found a medium exact-boundary defect: binary-float subtraction classifies
nominal `0.100pt` overlaps inconsistently. Decimal geometry and below/exact/
above threshold regressions are now under focused repair. Source anchors will
be reviewed on the combined immutable Stage 2/3 tree before the second commit.

The 458-second A14 source review confirmed the A12 directory-incarnation defect
fixed but found a new medium file-identity defect: the archive-cache partial and
published inode were not required to retain exactly one link. A local
no-network reproduction left a second name able to mutate the published cache.
Its complete request-changes envelope arrived before an automated classifier
marked the final turn failed; INC-026 records both facts. A separate 431-second
fix now checks identity and exactly one link through write, fsync, hash, replace,
directory fsync, and final readback. Its new regression and all 47 focused and
168 aggregate tests pass. A 235-second independent review reproduced the former
race, approved the repaired candidate with no findings, and bound digest
`5d08b189dc075e551870ddd9fc236b54a986cabaafc0378918447e2a65bce40a`.
The candidate was then committed, replayed without conflicts onto approved
transport base `e93d949d06af2a7f4407d198a37aad315deac6aa`, and frozen at
`cb8ad4144a099a933e1dca6e2b7155494ef5040c`. Clean-base gates pass 49/49
transport, 47/47 source, and 179/179 aggregate tests. The 452-second immutable
review nevertheless found a high rollback race: after final-verification
failure, rollback reopened the mutable `reference_root` pathname, so replacing
that pathname redirected deletion and backup restoration into unrelated data.
All other gates passed. A descriptor-threading fix and replacement-directory
regression then passed 49/49 transport, 48/48 source, and 180/180 aggregate
tests. It was frozen at `7f4a65e03d0386df28c320f0c5235de21efb5f31`.
Because the earlier exact-head checks were executed after the
review began, INC-028 retains the defect evidence but excludes A16 from the
formal PR review ledger; the next review may launch only after SHA-bound checks
have completed and been recorded. The corrected head's checks were therefore
run and canonically recorded before reviewer dispatch. The first replacement
review attempt was classifier-interrupted before returning evidence. A neutral
reissue completed in 228 seconds and entered the formal ledger, but found a
new high restart defect: the transaction marker binds the reference-root text
without binding the selected directory instance. A 345-second focused repair
now records `(st_dev, st_ino)` authority and validates it before verification,
rollback, or cleanup; 49/49 source and 181/181 aggregate tests pass, and an
independent candidate review is active.

A disposable combined-tree rehearsal applied QPBT-010, QPBT-002, QPBT-012,
and the current blueprint diffs without conflict. It materialized and verified
39 source files with 646 labels, passed the exact blueprint source-anchor gate,
49 transport tests, 48 source tests, and 190 aggregate tests, and built the
43-page PDF with all 107 planned identifiers. This is integration evidence,
not acceptance of the heads now under repair.

The 483-second package-materializer review found four blockers despite 9/9
focused and 110/110 aggregate tests. Hot-cache identity and detached builds did
not include or invoke package materialization; multi-package publication had no
durable restart recovery; timeout handling could leave another process-group
member active; and Lake update modes bypass overrides. Pin fail-closed behavior,
manifest reconciliation, archive/tree checks, and ordinary override parsing
were otherwise sound. Package download stays deferred until all four boundaries
are fixed and independently re-reviewed.

The coordinator's first eight public commit/tree metadata probes stopped before
network access because `gh api` required a local login. INC-027 changed the
fallback to credential-free GitHub HTTPS REST with exact returned-commit
equality. All eight responses matched their pinned revisions and supplied root
tree SHAs in 2.401 seconds. The sole acquisition owner then downloaded the eight
immutable codeload archives in parallel in 3.998 seconds: 4,672,955 compressed
bytes total, with per-file SHA-256 and gzip sizes captured under the ignored
runtime directory. No archive has been published, no pin has been changed, and
no Lake command has run while the materializer corrections remain under way.
The first 102-second fail-closed fact-capture pass then exposed a real-format
gap immediately: codeload emitted its root directory with mode `0775`, while the
parser accepted only `0755`. It emitted no downstream facts after that rejection.
The corrected frozen parser then validated all eight real archives and exactly
reproduced seven Git root trees. The sole mismatch was explained by Aesop's
tracked `lean_packages/std` gitlink, mode `160000`, which codeload intentionally
omits; it is not an export-ignore file. The package repair now binds that exact
omitted path/type/SHA as pinned data, requires empty omission sets for the other
seven packages, and keeps the archive inventory distinct from reconstructed Git
tree identity. No Lake command has run during these parser probes.

The resulting 1,602-second package/cache repair binds package inputs into cache
identity and detached builds, adds durable all-eight recovery and complete
process-group cleanup, rejects Lake update modes, and fills the closed schema-v2
pin. It passes 14/14 package, 22/22 cache, and 117/117 aggregate tests. Direct
production inspection matched all eight archives, including the separate Aesop
archive-subset and reconstructed-tree identities. A 21-second audit also made
the 14-record digest framing explicit and reproduced `eea89232522a...` without
byte drift.

The next package review still found four material blockers: a clean detached
worktree lacks the ignored Mathlib manifest required before package
materialization; Lake's `-U` and bundled forms bypass the no-update gate;
package names admit path traversal; and a symlinked `.lake` redirects runtime
operations outside the repository. All 14 package, 22 cache, and 117 aggregate
tests passed, illustrating why adversarial review remains separate from test
success. A 1,552-second repair added an exact tracked Mathlib manifest for
clean detached bootstrap, rejected all short and bundled update forms, closed
package-name grammar, and descriptor-bound package/runtime/recovery paths. It
passes 18 package, 22 cache, and 121 aggregate tests and rechecks all eight
production archives. Independent candidate review is active; no Lake cache
fetch or build has run.

A 516-second read-only declaration planner converted the immutable blueprint
into ten Lean files and four nonoverlapping implementation packages. It fixed
the public boundary at raw `BitVec` POVM alphabets with codecs, internal field
choice from admissibility, separate squared and unsquared realization
certificates, `Real.rpow` robustness, and exactly one mechanically checked
`sorry` on `MIPStarRE.QPBT.pauliSoundness`. No file or build was changed.

The restart directory-identity candidate was committed as
`63037ddceada7a88436f9afa9ed1ef4d74319098`, then passed 49 transport, 49
source, and 181 aggregate tests plus isolated 39-file/646-label
materialization before reviewer dispatch. The 381-second A20 formal review
independently reproduced those gates and approved the exact seven-path range
with no findings. QPBT-002 is locally complete; its issue remains blocked only
because QPBT-010 still awaits authorization for disclosure to the explicitly
requested external endpoint or an explicit disposition of that gate.

The exact Decimal PDF candidate was approved, then frozen at
`38e199c89140e2b188c7464f76e5fff4c0d0e1c1`. Its 39-path base patch is
324,172 bytes with SHA-256 `ed865e4d8081...`; the explicitly framed content
manifest is 4,263 bytes with SHA-256 `e420e4f0b1a4...`. Before review dispatch,
20 tests, 46-node/12-chapter graph checks, exact combined source anchors,
compile and diff gates, and a forced 43-page/107-identifier PDF all passed. A
354-second parallel pre-review scout nevertheless found two high, two medium,
and two low fidelity gaps: two source repairs were silent, canonical complexity
contracts overclaimed their anchors, non-soundness targets were unchecked, the
minimal-skeleton one-hole wording was ambiguous, and empty PDF geometry did not
fail closed. The immutable head is therefore superseded by a bounded repair
rather than being sent prematurely to formal review.

The bounded 433-second repair records both source corrections as new gap
entries, restores F10's arbitrary tensor-length contract, narrows K03/K04 and
adds their source-anchored dependencies, validates every public target and the
minimal one-hole contract, and rejects empty PDF geometry. Its exact 13-path
candidate passes 26 tests, a 48-node graph, combined source anchors, compile and
diff gates, and a fresh 45-page/109-identifier PDF. Independent candidate
review started immediately; no freeze or formal disposition has been claimed.

Package work also benefited from the expanded four-session wave. A 1,354-second
fix moved same-process recovery onto held descriptors and passed 21 package, 22
cache, and 124 aggregate tests. A simultaneous read-only audit then reproduced
three additional high findings: selected package and override sources could be
substituted before backup, and an authenticated staged child could be replaced
before publication. Its final envelope was classifier-interrupted after the
complete non-approving findings had already arrived; `INC-029` now records the
fourth such transport event and permits the findings to block acceptance but
never to approve it. A new bounded fixer started immediately. No Lake command,
cache acquisition, or Lean build has run while these findings remain open.

## Parallel wave and current gate

The coordinator expanded the Stage-4A wave to the local collaboration ceiling:
four physical workers were active concurrently while the root retained sole
ownership of canonical ledgers and Git integration. Independent lanes covered
the package fixer, QPBT-011 review/fix, and QPBT-013 through QPBT-016 API
reconnaissance; completed workers were recycled under new logical session IDs
with their physical reuse recorded. This has produced 78 issued Stage-4A sessions
and no overlapping writable paths. The observed ceiling is four because the
local collaboration service exposes four slots; increasing fan-out beyond that
would only create queued or duplicate work.

The immutable QPBT-004 head `4de452495228aad3debe05f166097e746b97b2e5` and the
QPBT-011 head `ae95a5de1374237b006c8e66787ac30bf3a57dfd` both have independent
approvals. The QPBT-004 cache-gate audit (233 seconds, tokens unavailable)
confirmed that the per-key `flock` elects one builder and makes waiters reuse a
published artifact, but the singleton warm is currently fail-closed: the
canonical `main` ref is still the pre-pin commit, the cache is a miss, and
`MIPSTARRE_ARCHIVE` plus `LAKE_PACKAGE_ARCHIVES` are unset. No build or network
operation was started. QPBT-013 through QPBT-016 therefore remain sequentially
gated behind QPBT-004 integration; their read-only API contracts are ready for
immediate dispatch once that gate is satisfied.

The audit also identified a documentation drift in
`protocols/local-development.md`: the prose cache-key list omits the additional
identity files and package verification fields enforced by the canonical
recipe. This is recorded as a numbered protocol follow-up rather than folded
into the already-approved Stage-1 surface.

## Parallelism follow-up and cache outcome

The four-slot local collaboration ceiling was kept full during the QPBT-018
cache gate: the root coordinator retained canonical ledger ownership while
three physical workers handled independent preflight, ledger, and workflow
audits. Completed physical workers were recycled as fresh logical sessions;
the ledger now records 78 non-coordinator Stage-4A sessions and no overlapping
writable claims. The cache builder itself remained singleton per cache key.

QPBT-018's first candidate warm invocation used the wrong script path and
failed in 0.095936 seconds at `git clone --local` with `EXDEV`; no fallback or
artifact was published (INC-035). The one changed-hypothesis retry used the
absolute candidate script, completed cross-device fallback plus source and
8/8 package archive materialization/verification, then ran for 1009.665499
seconds before the pinned mathlib Git fetch failed with a TLS early EOF. It
published no `READY` snapshot (INC-036), so the candidate remains blocked until
a local pinned mathlib source is supplied.

The direct throughput requirement is implemented by QPBT-019. The first
immutable review requested changes because duplicate planned orchestrators
were admissible, unknown capacity masked ownership diagnostics, and three
compatibility/parser contracts needed explicit treatment. Retry head
`7669f70be786a53ba1a0a92c1d347f5fe7544681` fixed all five findings and passed
59 focused tests, 166 aggregate tests, the three-test workflow checker,
compilation, validation, and diff hygiene. A fresh 341.603-second immutable
review approved that exact head with no new findings. LPR-008 was then
fast-forwarded to `main`; the same gates passed on the integrated tree, with
the aggregate suite taking 111.220 seconds. QPBT-019 and LPR-008 are closed.
The dispatcher now separates observed concurrency from explicit capacity,
computes active leases and ownership under the state lock, rejects duplicate
orchestrators, and admits deterministic atomic prefixes.

The local mathlib acquisition audit validated a shallow, clean mirror at commit
`81a5d257c8e410db227a6665ed08f64fea08e997` and tree
`5ea66b811b8461daae82f14d356fed2a287d7c40`. Lake honored a package-scoped
`LAKE_PKG_URL_MAP` in 9.1 seconds with zero network traffic; the separate
cache-executable probe remained blocked by the read-only default Reservoir
cache. The result is recorded in `i018-auditor-a09-mathlib-local` and motivates
QPBT-021, now running concurrently in its own worktree to make the source map
and artifact-cache boundary deterministic.

A parallel QPBT-004 cache-gate recheck confirmed the approved main identity is
a cache miss and that all eight non-mathlib archives match their pinned facts,
but the pinned MIPStarRE archive and a local mathlib source/artifact are absent.
The bounded warm probe failed closed at the cross-device local clone in about
1.3 seconds, before any Lake command, network call, or READY publication.
This was recorded as a terminal audit rather than retried blindly.

The QPBT-021 lane produced immutable pre-rebase head
`54fb701176383d23e5dc1ba9d73c3cb53e06e1d6`, whose 32 focused and 150 aggregate
tests pass while authenticating the real 51,938,317-byte mathlib archive. The
earlier audit's symlink, manifest, and count findings were fixed. A fresh audit
then reproduced a higher-severity boundary: repository-local
`core.fsmonitor` configuration executes during `git status` before the source
is accepted or rejected. The old head remains immutable evidence while a
separate worktree rebases onto integrated main and isolates all authentication
Git commands from executable configuration. No warm, Lake build, or network
call is part of these lanes.

QPBT-020's first candidate added session claim, result import, and recovery
helpers, but an independent real-WorkflowStore audit requested changes. It
reproduced running-lease leaks after output setup and generic runner failures,
incomplete role/parent/name authority binding, imports that bypass launch and
overwrite start provenance, duplicate retry events, terminal-event/archive
incompatibility, non-idempotent recovery, malformed-field acceptance including
`NaN`, and mock-only coverage. A new orchestrator lease is repairing those
eight findings on integrated main. In parallel, the QPBT-021 rebase and
read-only security audit occupy the other two worker slots; canonical dispatch
shows three active non-coordinator leases under the explicit capacity-four
ceiling.

### Current parallel dispatch snapshot

At the latest coordinator checkpoint the ledger contains 266 issued attempts
(265 non-coordinator), including 134 Stage-4A attempts. The root plus three
worker threads are the measured four-node collaboration ceiling. The latest
wave admitted three independent read-only audits concurrently by recycling
completed worker threads: a QPBT-013 leaf-contract audit, a QPBT-017 cache-
protocol audit, and a QPBT-004 gate audit. All three reports are archived and
there is currently no active non-coordinator lease. Recycling retained threads
preserved their external-session provenance while avoiding the collaboration
service's completed-thread limit.

The following frontier wave again filled all three worker lanes concurrently.
The QPBT-010 endpoint-gate audit confirmed that authorization and the health
canary pass, but the recorded LPR-005 approval is not the current-main head, so
an exact-head governed review is still required. The QPBT-018 audit found that
its candidate object is stranded in a temporary clone, has stale ancestry, and
has no accepted READY cache; it must wait for the QPBT-021 cache repair. The
QPBT-021 audit found a real serial-aggregate failure at
`tests/test_local_agent.py:500`, reproduced on the unchanged baseline, plus a
malformed diff-check ledger entry. These are recorded as no-go evidence rather
than parallel repair work because the candidate paths overlap. All three
audits were read-only, made no build or network calls, and are now archived.

The post-merge evidence wave passed the full checker (187 tests in 53.704 s)
after the three leases were archived. The cache probe remains a miss, so the
next build still has one elected builder; additional workers would only add
read-only analysis or review capacity, not shorten that build.

The immutable integration wave replayed the approved source and blueprint
ranges in dependency order (`LPR-001 -> LPR-002 -> LPR-004`) without conflicts.
Its combined disposable tree passed the 49-test transport suite, 49-test
source suite, 26 blueprint tests, source-root verification (39 files/646
labels), 45-page PDF geometry, 285-test aggregate checker, compileall, and
diff hygiene. The ranges are now integrated on canonical main at
`65315213d047d9181804ad74d573f533c904ef4f` (tree
`a65bd1bd6f2fa5191d099897ad02ee64b964dd04`), and all three PR records carry
that immutable integration SHA. The endpoint-specific QPBT-010 review
disposition remains an explicit gate.

The coordinator interruption at 2026-08-31 07:30 UTC terminated two earlier
QPBT-020 workers before they could publish evidence. `INC-040` records the
process-liveness and clean-worktree checks; both leases were explicitly marked
failed and archived, then replaced by new attempt identities. This preserves
the failed attempts as provenance while reclaiming capacity without silently
rerunning an external session.

This wave demonstrates the local replacement for GitHub parallelism: each
writable lane has an immutable base, disjoint owned paths, and a separate
worktree; reviewers are read-only and candidate evidence is imported only by
the coordinator. The hot-main cache remains a singleton per cache key, so
parallel analysis and repairs do not trigger duplicate Lean/Lake builds.

The collaboration service also retains completed thread objects against its
thread limit. A fourth fresh scout therefore failed before launch even though
the logical capacity planner had room; `INC-041` records the event. The
coordinator preserved that attempt as failed provenance and reused an explicitly
completed thread through `followup_task` with a new governed logical session
ID. This increases useful fan-out without weakening external-ID or ownership
checks.

The local launcher probes the installed Codex CLI's review/fork/resume surface
in an isolated configuration before nested review execution. The probe is
bounded and fail-closed; only mocked parser evidence exists so far, and no
model/network child was launched by the API scouts.

The cache audit confirms that the singleton builder and private seeding locks
already permit safe bounded fan-out; the CLI audit found no exposed worker
multiplier. The practical speed-up is therefore three independent analysis or
review lanes around one serialized hot-main build, not competing Lake builds.
The QPBT-013 audit additionally found that its leaf writer cannot be admitted
until exact callable signatures and the self-dual-normal-basis obligation are
recorded; the QPBT-004 audit found no repair lane and requires a fresh
current-head review plus authenticated archive inputs before the cache gate.
The remaining unapproved gates are QPBT-021 (fresh review approved after its
rebase cleared the aggregate baseline timeout, `INC-038`, with cache/integration
still pending) and QPBT-018 (draft, awaiting the singleton cache gate).
QPBT-020's nine recorded findings are resolved by the
fresh immutable approval and its candidate is merged at `4bfdd120`; QPBT-022
is also merged. The QPBT-020 post-merge Python/checker/compile/validation gates
pass, while the hot-main cache is a miss and the full Lake build remains
pending. `INC-039` remains historical evidence for the repaired cache resolver.
These gates remain queued for their explicit repair or cache prerequisites
rather than being hidden by a passing focused suite.

### Capacity-3 review wave (2026-08-31)

After the QPBT-021 rebase, the coordinator archived the repair orchestrator
and two read-only scouts, then atomically dispatched two fresh reviewers and a
third cache-input scout. The active wave therefore uses all three available
non-coordinator lanes concurrently: an immutable QPBT-021 review, an
endpoint-backed QPBT-010 review, and a QPBT-018 input audit. The root remains
the fourth collaboration node and the only canonical-state writer.

The prior repaired QPBT-021 head is `63d1e9e9807412008f7174199fdcd1ca11787890`
(tree `204ca4af35939f989c85828da97012cea8879fb9`, parent current main). Its
42 focused tests, 299-test serial aggregate, workflow checker, compileall,
validation, and corrected SHA-bound diff check passed before review. The
endpoint lane uses the user-authorized `gpt-5.6-sol` profile at
`https://api.finite-dimensional.space` and the base-target contract; it is
separate from the cache review, so neither lane duplicates a build. The third
scout is read-only and has no cache/build authority.

This was the practical speed-up boundary for that wave: three independent analysis or
review lanes around one serialized hot-main cache builder. More workers would
not shorten a single Lake build and would either queue behind the singleton
lock or violate the measured collaboration-service ceiling. Completed physical
threads are recycled into fresh logical session IDs to avoid the service's
completed-thread limit while preserving provenance. At the prior checkpoint the
ledger has 259 issued attempts (258 non-coordinator); the two endpoint retries
are recorded as blocked before transmission by host persistence and
external-evidence policy, and the exact-base QPBT-021 review requires a replay
onto immutable base `7669f70`. Token counts remain null with an explicit
backend-unavailable reason.

### Current capacity wave (2026-08-31)

The coordinator then reused the three physical worker lanes for an exact-base
QPBT-021 repair, two independent read-only frontier scouts, and a fresh PR
review in succession. The repair corrected one false `37/37` changelog claim
to the measured `42/42` result and preserved the exact five-path range at head
`6303aab63eeed144fe176969ca7c87f5a852b967`. The cache-readiness scout and the
QPBT-023 contract scout ran concurrently with the repair/review transitions;
both reported no-go blockers without starting a build or network operation.

The live dispatch probe recorded `active_non_coordinator: 3` and
`available_capacity: 0` under `python3 scripts/workflow.py dispatch
--capacity 3`, while the host exposed 128 CPUs. This separates service
capacity from host CPU capacity: a fourth worker is not admitted, and extra
builders would still serialize on the per-key hot-main lock. At the current
checkpoint the ledger has 266 issued attempts (265 non-coordinator), including
134 Stage-4A attempts; token usage remains unavailable and is recorded as
`null`. One provisional-identity launch was cancelled and replaced with an
exactly identified session, preserving auditable provenance rather than
leaving an unverifiable parallel result.

The fresh immutable review then approved the corrected QPBT-021 head and
resolved the changelog-count finding. The cache key is still a miss and the
warm/seed gate remains deferred because the authenticated runtime inputs and
required environment are not yet available; no additional independent ready
issue is currently admitted.
