# Hybrid RAG Project — Stakeholder Report

**Status date:** 25 November 2026
**Project maturity:** Working local prototype / portfolio project; not production-ready

## Executive summary

This project is a document question-answering application. A user asks a question; the system searches indexed documents, gives an answer based on relevant passages, and shows citations so the user can check the source. When the evidence is not sufficient, it is designed to say that it does not know.

The current demonstration uses **6,466 unique text chunks** from Kubernetes documentation versions 1.30 and 1.31. Kubernetes is the example corpus, not the intended limit of the product. The ingestion code also supports unversioned Markdown documents, so the underlying approach can serve teams with technical guides, product manuals, procedures, policies, support articles, and other written knowledge.

The strongest measured result is **74 correct answers out of 89 questions (83.1%)** for the full system with its adaptive retrieval router. This is a useful development result, not a guarantee of accuracy: the set is small, its labels were corrected after inspecting evidence, and it is not an independent test set.

The project has functioning authentication, role-based document filtering, citations, a prompt-injection check, answer caching, an admin metrics view, and a Docker-based local deployment. Important product work remains: users cannot upload arbitrary files or connect a document service through the UI; there is no concurrent load test; dollar cost has not been measured; and semantic caching has inconsistent false-match results.

## What the product is

Retrieval-augmented generation (RAG) combines document search with a language model. Rather than asking the model to answer from memory alone, the system:

1. Finds passages in the selected document collection that may answer the question.
2. Gives those passages and the question to a language model.
3. Shows the answer with citations to the passages used.
4. Abstains when its document context does not support a document-specific answer.

The application is intended for people who need to find answers in a body of documents without reading every file: for example, engineering and operations teams, customer-support teams, policy and compliance teams, and product organizations. It is not limited to Kubernetes, but its quality has only been measured on the Kubernetes sample corpus.

### Capabilities implemented today

- **Document-grounded answers:** The answer-generation prompt asks for a direct, well-written response grounded in relevant context.
- **Clickable citations:** Users can inspect the cited passages and document version.
- **Abstention:** The model is instructed to say “I don't know” for document-specific questions unsupported by retrieved context.
- **Hybrid search:** BM25 keyword search is combined with dense semantic search using reciprocal-rank fusion.
- **Version awareness:** Identical chunks across document releases are deduplicated and retain release metadata. Normal app queries use the latest indexed version by default. The current UI does not let a user select an older version.
- **Adaptive retrieval:** A small router chooses a retrieval depth of 0, 2, 5, or 10 passages. Complex questions receive a minimum retrieval depth.
- **Caching:** Exact-question and semantic-response cache tiers exist. Cache identity includes the corpus/runtime and access group so a response is not intentionally reused across those boundaries.
- **Accounts and roles:** Users register as ordinary users. Admin accounts are provisioned separately. An admin can retrieve public and restricted documents and see request metrics.
- **Document suggestions:** Suggested questions are drawn from the documents available to the signed-in user.
- **Chat experience:** Conversations remain in browser storage until sign-out. Markdown formatting is rendered in answers. The composer remains visible while the message history scrolls, with a jump-to-latest control.
- **Basic general conversation:** Common capability questions and some simple conversational/general questions can be handled without document retrieval.

### Current document and access boundaries

The current corpus is sourced from the public Kubernetes documentation repository. Its 6,466 chunks are now classified as public. A Markdown document can be marked `access_group: restricted` in YAML front matter; restricted documents are intended to be available to admins only. With no restricted documents in the current sample index, users and admins currently see the same corpus.

The ingestion path currently handles Markdown from a configured repository or local directory. It does **not** provide a user upload screen, a cloud-drive connector, or arbitrary URL ingestion. Do not treat it as supporting arbitrary PDFs, Word documents, or private repositories until those ingestion paths and their access rules are implemented and tested.

Documents without access metadata currently default to public. Before indexing private material, the source must be correctly labelled restricted. A production ingestion workflow should require an explicit owner/access decision rather than relying on an unnoticed default.

## How it works

```text
Question
  -> prompt-injection check / capability fast path
  -> local query embedding
  -> exact or semantic cache lookup
  -> adaptive router
  -> filtered BM25 + dense search
  -> answer generation
  -> citation validation and response
```

Documents are split into heading-aware chunks of about 200 tokens, with a 300-token target cap. Titles and section paths are included to help retrieval. The current vector collection uses 384-dimensional dense embeddings plus BM25 sparse vectors. The embedding and prompt-guard models run locally on CPU; answer generation uses a Groq-hosted Qwen model. Qdrant stores and searches the document vectors.

The router is a logistic-regression model over query embeddings. It is inexpensive to run, but its output is only a prediction about how much evidence to retrieve; it does not judge whether the final answer is true.

### Main technology

| Component | Current choice |
|---|---|
| API | FastAPI / Python |
| Document index | Qdrant, run locally with Docker Compose |
| Dense embedding | `BAAI/bge-small-en-v1.5`, 384 dimensions, CPU |
| Keyword search | BM25 with reciprocal-rank fusion |
| Answer model | Groq API, `qwen/qwen3.8-27b` in the current configuration |
| Prompt-injection classifier | Llama Prompt Guard 2, local CPU |
| Adaptive router | scikit-learn logistic regression |
| Authentication | SQLite account/session store; passwords hashed with scrypt |
| Frontend | Static HTML, CSS, and JavaScript; no frontend build system |
| Local development host | Windows 11 / Docker Desktop with WSL 2; 16 GB RAM, Intel Core Ultra 5 225U, no GPU |

## Evaluation and quality

### Golden question set

The current evaluation set has 89 questions:

| Question type | Count |
|---|---:|
| Single-passage answer | 38 |
| Multi-passage answer | 15 |
| Unanswerable | 9 |
| Version trap | 7 |
| Conversational | 20 |

The final evaluation compares a dense baseline, fixed-depth hybrid retrieval, and the full system with the corrected-label router v2. Correctness is scored by an LLM judge against the reference answers. A 30-answer judge-agreement check reported 100% agreement, but it was small and AI-assisted; it is not an independent human study.

### End-to-end results

| Configuration | Correctness | Faithfulness below 1.0 | Correct abstention | False abstention | Citation hit | Mean tokens |
|---|---:|---:|---:|---:|---:|---:|
| Dense baseline | 61/89 (68.5%) | 13.3% | 9/9 (100%) | 25.0% | 55/60 (91.7%) | 1,567 |
| Hybrid, fixed k=5 | 63/89 (70.8%) | 20.6% | 7/9 (77.8%) | 23.8% | 56/60 (93.3%) | 1,594 |
| Full router v2 | **74/89 (83.1%)** | **14.5%** | 7/9 (77.8%) | **10.0%** | 56/60 (93.3%) | **1,455** |

“Faithfulness below 1.0” is the project’s RAGAS-based proxy for unsupported answer content, not a universal definition of hallucination. For router v2, faithfulness was scored on 62 answered records; 9 were below 1.0. “Correct abstention” means correctly refusing the nine questions labelled unanswerable. “False abstention” means refusing an answerable question. Citation hit rate counts whether at least one cited chunk matched the gold evidence, among questions with gold citations.

The router v2 result is 11 more correct answers than fixed hybrid k=5 on this set. Treat this as a promising development result, not proof of a general improvement: the golden label for one question was corrected after reviewing model evidence, and the router was evaluated on that same set. A fresh, independently labelled test set is needed before making a general accuracy claim.

### Retrieval and version results

On 59 document-retrieval questions, hybrid search achieved recall@5 of 0.907 and NDCG@5 of 0.826. Dense-only search had recall@5 of 0.924 and NDCG@5 of 0.823. Hybrid search ranked relevant evidence slightly better overall by NDCG, though it did not retrieve every relevant passage as often as dense search.

For the seven version-trap questions, an outdated passage appeared in the top five for 6/7 questions without the latest-version filter and 0/7 with it. Incorrect answers citing an outdated passage fell from 2/7 to 0/7. The sample is too small to establish a broad guarantee, and one answer remained incorrect even with the latest filter.

A cross-encoder reranker was tested but not selected. Hybrid retrieval took about 28 ms p50 / 32 ms p95 in the ablation; hybrid plus reranking took about 872 ms p50 / 1,080 ms p95, without a measured overall quality gain.

### Semantic-cache safety

Exact caching and semantic caching are not equally safe. Exact caching reuses a stored response for the same normalized question; it can save generation work, but it can still repeat an answer that was wrong when first generated. Semantic caching may reuse an answer for a different question, so a false match can directly return the wrong answer.

The project has positive evidence for the semantic tier: in one live golden-question run, 38 of 45 paraphrases were cache hits, and none of those returned answers was judged incorrect against the reference. However, separate near-miss tests produced less reassuring results:

- On a fresh 45-pair safety set, the configured matching stages served 51.1% of paraphrases and also served 15.6% of near-misses incorrectly.
- A 41-pair development set with the verifier showed a 4.9% near-miss false-hit rate, but the settings were assessed on that development set.
- An earlier held-out 15-pair test had a 46.7% false-hit rate after retrieval-consistency filtering, before the final verifier stage.

These are different test sets and stages, so they should not be combined into a single score. Taken together, they show that semantic-cache safety is not yet established for new corpora or questions. The current configuration enables semantic caching, but it should be considered experimental; a conservative release should disable it until it passes a larger independent set of paraphrases and near-misses. Exact caching can remain separately enabled and monitored.

## Latency and cost

### Measured latency

The API was run sequentially on 89 questions. These measurements are **not** a concurrent load test.

| Run | Cache hit rate | Total p50 | Total p95 | Client p50 | Client p95 |
|---|---:|---:|---:|---:|---:|
| Cold cache | 0% | 713 ms | 60.9 s | 717 ms | 60.9 s |
| Warm/mixed cache | 74.16% (66/89) | 254 ms | 3.05 s | 259 ms | 3.08 s |

The warm-cache median is faster, but its p95 is still over three seconds. Across the 23 warm-run cache misses, generation had a p50 of about 460 ms and a p95 of about 55.7 seconds. This large tail is the main observed user-facing latency risk. Provider response time, retries, and rate limits can also make individual requests much slower than the median.

Other stage measurements show local query embedding around 20–23 ms p50, routing around 0.5 ms p50, and hybrid retrieval around 9–21 ms p50 in the recorded API runs. The local prompt-injection guard takes about 141–169 ms p50 and roughly 256–270 ms p95. These stages matter, but the language-model call dominates the worst latency.

### Dollar cost

**The project has not measured or reported actual dollar spend per request.** Development used the available Groq API tier, but that does not make a hosted product free. Provider prices and quotas can change, and the recorded results do not include a billing export.

The final router evaluation used an average of about **1,455 prompt-plus-completion tokens per question**. This is a token count, not a dollar estimate. The LLM wrapper records prompt and completion tokens, but there is no report that applies the provider’s price schedule to those records. A reliable estimate should use the current input/output token rates for the chosen model:

```text
request cost =
  (input tokens / 1,000,000 × input price per million)
  + (output tokens / 1,000,000 × output price per million)
```

An operational cost report should also track model, cache tier, retry count, and provider price version. Exact/semantic cache hits avoid generation calls, but this application still computes a local query embedding before its exact-cache lookup. Local embedding, guard, Qdrant hosting, storage, backups, monitoring, and application hosting have their own compute or infrastructure costs.

## Scaling evidence and constraints

The project includes a separate Qdrant benchmark using **1 million 768-dimensional vectors** and 1,000 benchmark queries. This is a vector-search experiment, not a one-million-document end-to-end RAG test; the application’s current embedding size is 384 dimensions.

With the benchmark’s 2 GB Qdrant container and HNSW `m=16`, `ef=256`:

| Vector representation | Recall@10 | Search p95 | Measured container RAM |
|---|---:|---:|---:|
| Float32 | 0.978 | 19.18 ms | 122 MB reported |
| Scalar quantization | 0.976 | 13.15 ms | 899 MB |
| Binary quantization | 0.927 | 11.54 ms | 272 MB |

The float32 RAM figure is misleading by itself: the original float32 vectors were kept on disk, and Docker’s process-memory figure excludes page cache. The test indicates that scalar quantization can reduce the in-memory vector footprint while retaining recall close to float32 in this benchmark. Binary quantization was faster but lost more recall. These results help guide a future large-index configuration; they do not establish application throughput, end-to-end latency, or multi-user capacity.

The demonstrated app is a local Docker Compose deployment with one API service and one Qdrant service. No concurrent user load test, autoscaling test, high-availability test, or recovery test has been recorded.

The reported latency was measured on the local development setup, with answer generation sent to the configured Groq API. It should not be treated as a cloud-hosting or production-capacity benchmark.

## Important limitations and failure modes

| Risk or failure | User impact | Practical next step |
|---|---|---|
| Relevant content is missing, poorly chunked, stale, or classified incorrectly | Wrong answer, abstention, or a user/admin visibility difference | Add ingestion validation, document-level ACL checks, source freshness monitoring, and per-corpus retrieval tests. |
| Semantic cache matches a near-miss | The user receives a plausible but incorrect cached answer | Disable semantic caching for a conservative release; test on independent paraphrase and negative pairs across multiple corpora. |
| Model provider is slow, unavailable, rate-limited, or changes behavior | Long waits, errors, or variable answer quality | Add measured timeouts and retry budgets, streaming, provider health monitoring, quota controls, and a fallback/clear error path. |
| The router chooses too little evidence | Missing evidence or a false abstention | Measure router errors on new domains and add retrieval-depth fallbacks for detected multi-part questions. |
| Prompt-injection guard misses an attack | A malicious prompt may influence answer behavior | Do not treat the classifier as an authorization control. Keep access enforcement in the API and retrieval filter; add ongoing red-team tests and conservative output handling. |
| Qdrant is unavailable or the index is damaged | Search fails and users cannot get document answers | Add backups, restore drills, health monitoring, and a rebuild procedure. Current full indexing recreates the collection, so production updates need a safer blue/green index swap. |
| A private document has no restricted label | It may be indexed as public under the current default | Require explicit access classification and test tenant/access isolation before ingesting private customer content. |
| Browser storage is cleared or the user changes devices | Chat history is lost or unavailable elsewhere | Store history server-side if cross-device recovery, retention rules, or team sharing are required. |
| A request exceeds context/provider limits | Generation can fail or need a retry with less context | Preserve context limits, add representative long-document tests, and report truncation clearly. |

The prompt-guard evaluation used 60 attacks and 145 benign prompts. At the current configured threshold of 0.1, it blocked 16.7% of tested attacks with 0% false positives in that sample. Lowering the threshold blocked more attacks but also increased false positives. This is a modest safety signal, not protection against all attacks. The benign set also included prompts used during threshold selection, which makes the estimate optimistic.

## Security, privacy, and operations

- Authentication uses validated email addresses, parameterized SQL, salted scrypt password hashes, and an HTTP-only session cookie.
- Self-registration creates user accounts only; admin accounts are provisioned separately.
- The API derives the access group from the authenticated account, rather than accepting a client-selected group.
- Qdrant filters documents during retrieval. Current document access is public by default or restricted when explicitly labelled; the existing Kubernetes sample has no restricted chunks after the recent access-label correction.
- For cache misses, the question and retrieved document context are sent to the configured Groq model. Review the provider’s data handling and retention terms before using confidential or regulated documents.
- `AUTH_COOKIE_SECURE=true` should be set behind HTTPS.
- Browser chat history is stored locally and cleared at sign-out. It is not server-synced or shared across devices.
- The earlier access-leak test reported zero leaks in 40 public requests and restricted evidence reached in 19/20 admin positive controls. It predates the move from synthetic chunk labels to explicit document-level labels, so it must be rerun with a real restricted test document before using it as current security evidence.
- The app has no user-submitted URL ingestion today. If URL ingestion is added, it needs SSRF protections: strict source allowlists, redirect and DNS/IP checks, private-network blocking, size/time limits, and isolated parsing.
- This project has not had an independent security audit or production privacy review.

## Recommended next work

### Release gates

1. **Keep exact caching separate from semantic caching.** Disable semantic reuse for a reliability-focused release until independent near-miss tests meet an explicit false-hit target on several unrelated corpora.
2. **Create a fresh evaluation set.** Use questions and answer labels not used to tune the router, prompt, or cache. Include answerable, unanswerable, multi-part, version-specific, and near-miss cache pairs. Include human review for a sample of model-judge decisions.
3. **Run an authenticated access test with explicit restricted documents.** Test search, exact cache, semantic cache, citations, and suggestions for both roles after the latest access-label changes.
4. **Instrument latency and cost.** Report p50/p95/p99 by stage, generation input/output tokens, retries, cache tiers, provider charges, and per-user/request limits.
5. **Perform a concurrent load test.** Set an acceptable p95 latency and error-rate target, then measure users per API instance and Qdrant resource use.

### Product and scale roadmap

1. Add document-source adapters for file uploads and selected repositories/services, beginning with clearly supported formats such as Markdown, PDF, and DOCX.
2. Add document ownership, tenant isolation, explicit access classification, deletion/retention workflows, and auditable re-indexing before accepting private or customer data.
3. Add guarded, administrator-controlled URL ingestion only after the SSRF protections above are implemented.
4. Add explicit version selection and “compare versions” questions; current app queries default to latest documents.
5. Move SQLite account state and local model cache to managed/shared services before running multiple API replicas. Coordinate provider rate limits across replicas.
6. Make indexing asynchronous and incremental. Use versioned collections and an atomic switch so users are not exposed to a deleted or partially rebuilt index.
7. Add server-side chat history only if users need cross-device access, team sharing, retention management, or centralized recovery.
8. Add operational monitoring, backup/restore drills, secret management, dependency updates, and incident procedures before hosting for real organizations.

## Overall assessment

The project demonstrates the core of a useful document assistant: hybrid retrieval, citations, abstention, version-aware indexing, access filtering, caching, and an adaptive retrieval experiment. Its best current evaluation score is encouraging, and the separate 1M-vector experiment shows that memory/recall trade-offs can be measured.

The right description today is **a production-style RAG prototype with useful evaluation work**, not a production-ready document platform. The most important gaps are general-corpus validation, safe and user-friendly ingestion, independent semantic-cache safety evidence, long-tail latency, explicit restricted-document testing, and measured operating cost.

## Reproducibility and source records

Run the local tests from PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
docker compose up --build -d api
```

Key supporting records:

- [`README.md`](README.md) — current setup and product overview.
- [`config.yaml`](config.yaml) — active model, retrieval, router, access, and cache settings.
- [`results/final_eval_router_v2.md`](results/final_eval_router_v2.md) — final router comparison.
- [`results/ablation.md`](results/ablation.md) — retrieval quality and latency comparison.
- [`results/latency_stages_cold.md`](results/latency_stages_cold.md) and [`results/latency_stages_warm.md`](results/latency_stages_warm.md) — sequential API latency.
- [`results/cache_fresh.md`](results/cache_fresh.md), [`results/cache_heldout.md`](results/cache_heldout.md), and [`results/cache_development.md`](results/cache_development.md) — distinct semantic-cache safety experiments.
- [`results/bench_capped.md`](results/bench_capped.md) and [`results/bench_memory.md`](results/bench_memory.md) — 1M-vector memory/latency benchmark.
- [`results/injection_guard.md`](results/injection_guard.md) — prompt-guard threshold results.
- [`results/access_leak.md`](results/access_leak.md) — historical access-filter summary; rerun after explicit restricted documents are indexed.

The older end-to-end development report is retained locally but omitted from this repository because it contains superseded intermediate details.
