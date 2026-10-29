# Fictional corpus and evaluation provenance

All case records, company names, events, quantities, procedures and evaluation questions were authored for this portfolio demonstration. They do not represent real shipments, customers, suppliers or company policies. The border-document procedure is fictional, not customs/legal guidance. No private files, login-required dataset or paid API is needed.

`prepare_data.py` reproducibly writes eight cases, 24 case records and seven shared procedure documents: **31 documents / 31 paragraphs** in the current fixture. It uses Python `random.Random(42)` for the fixture quantities and deterministic evaluation-question order. Narrative templates, source identifiers, dates and case categories are explicitly authored; they are not claimed to be random observations.

- Final corpus SHA-256: `c1345f9f7bd7b1516b0017100897ffd7a1da014589ed367422f8fc4daa06ca9f`.
- Cases EX-1042 and EX-1043 supply **six development questions**.
- Cases EX-1044 through EX-1049 supply **18 held-out questions**: 12 answerable source/value checks (including two conflict questions) and six questions with unavailable requested information.
- Case and procedure text is available to the retrieval index. Holding out case questions does not mean their source documents are excluded from the index; this is a retrieval application over a fixed corpus.
- `.gitattributes` preserves the bytes of the corpus and evaluation script across Git checkouts, so Windows newline conversion cannot silently invalidate their recorded checksums.
- Evaluation gold labels, required source IDs and value fragments live in `evaluation_questions.json`. They are read only by the offline evaluator, not by the investigation API, retriever fitting or model context.
- Each passage ID is document ID plus `:pN`. Paragraph boundaries preserve an inspectable route back to the original text. Stable source IDs are not gold-answer labels.
- Case priority, summary and flags are authored scenario metadata. They are displayed as such and are not generated predictions or automated conflict detection. The model receives only retrieved passage IDs/kinds/text and the user's question.
- Source `recorded_at` values describe fictional record ingestion, not necessarily the event time written in the source. The final fixture records documents at 14:00/14:20/14:40 UTC, after the earlier same-day carrier events described in their text.

An initial development round used earlier record-ingestion timestamps. That chronology metadata was corrected before held-out evaluation. Its 24 raw model results, summary and protocol remain archived as `outputs/development_round1_*`. Final development used the corrected corpus, the same prompt versions and the same predeclared configuration-selection rule. No held-out generation had been run before this correction.

Ollama and model weights are installed runtime prerequisites, not dataset assets or Git contents. Actual recorded models were local Qwen2.5 0.5B and 1.5B, with model digests preserved in every completed generation. The selected 1.5B digest is `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`; the local runtime reported Ollama 0.40.11. No model training, fine-tuning, neural-embedding download or real operational intervention was performed.
