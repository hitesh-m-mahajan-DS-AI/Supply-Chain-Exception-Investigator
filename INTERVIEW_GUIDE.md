# Explain F2 in an interview

## A one-minute introduction

I built a local case-investigation workbench for supply-chain exceptions. React provides a queue, timeline and citation inspector; Python retrieves case-scoped evidence using SQLite FTS5 and TF-IDF. A local Qwen model generates a structured stance and exact supporting quotes. The app checks the citation IDs and quoted text, preserves the raw draft and keeps analyst review notes separate. On 18 held-out questions across six fictional cases, 15 matched strict source/value/stance checks. Retrieval found all required sources for 12 answerable questions, but valid quotations did not guarantee a correct stance. I documented the failures rather than claiming the system was fully reliable.

## A three-minute demo

1. Open the delay case from the inbox. Explain that every record and procedure is fictional and that priorities are authored labels.
2. Run the suggested question using the selected 1.5B/v2 local model. Inspect the returned quote and click its citation to highlight the original text.
3. Point out the distinction between a supplier's estimated arrival and confirmed receipt. The app does not automatically adjudicate that distinction.
4. Add an analyst note labelled as a demo review, then reopen the same investigation from history. The original draft stays unchanged.
5. Change the question or mode. Show the notice that current exports still describe the saved request.
6. Run search-only mode and show that no model was called. This mode is not presented as a generated answer.
7. Open Evaluation lab. Compare source retrieval (12/12), correct abstentions (5/6), output checks (17/18) and exact task checks (15/18).
8. Explain the three failed held-out checks and export the case brief or complete JSON evidence.

## Questions to prepare for

**Is this RAG?** The local-AI path retrieves source passages and uses them in a real local generation call. It is deliberately extractive RAG with schema-constrained quotes, not unrestricted prose generation. Search-only mode is explicitly not generative RAG.

**Why no neural embeddings/vector database?** The fixture has 31 short passages. FTS5 and TF-IDF provide a small, inspectable lexical baseline without a model download or separate server. A larger corpus would require a measured retrieval comparison before changing tools.

**What does quote verification prove?** Only that the output follows the schema and cited text occurs in the retrieved source. It does not prove relevance, correct stance, real event truth or operational suitability.

**What failed?** For the count-discrepancy question, the model quoted both counts but chose supported rather than conflict. For the ETA-conflict question, it returned conflict with no evidence and was withheld. For the unconfirmed-recipient question, it chose conflict instead of insufficient, despite citing real excerpts.

**How was leakage limited?** The app never reads gold labels. Model context contains only the question and retrieved passage IDs/kinds/text. Development used two cases, and a frozen configuration was then scored on questions from six other cases in the existing index. This is not a claim of generalization to new unseen documents or real companies.

**Why report 15/18 instead of calling it 83.33% accuracy?** The check is a strict, small, authored stance/source/value fixture. Calling it general system accuracy would hide its narrow population, exact gold source-set assumption and limited sample size.

**What happens when Ollama is unavailable?** Retrieval still works. The app labels unavailable or explicit search-only output and does not invent a model answer.

**What is saved?** The question/settings, case/source snapshots, retrieved passages, raw model JSON, checks, configuration digests and timings. Human notes append separately; they are not edits to model output.

**What would production need?** Authorized real documents, reliable source versioning, authentication and case permissions, privacy controls, broader independent evaluation, operational ownership and validated escalation rules. No such production qualification is claimed by this local portfolio project.
