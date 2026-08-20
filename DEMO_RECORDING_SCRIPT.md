# Contextline — Demonstration Recording Script

**Estimated duration:** 4–6 minutes
**Objective:** Demonstrate the actual local system, its evidence-first behavior, and the limits of the current latency evidence without overstating performance.

## Recording preparation

Use a browser window with `http://127.0.0.1:8000` open and the local server already healthy. Close terminals, file explorers, password managers, notifications, `.env` files, provider dashboards, and any other material that could reveal credentials or personal information. Set browser zoom so the question box, language selector, response badges, sources, and timing cards remain readable.

The demonstration must be recorded with the same code and local indexes referenced in `SUBMISSION_READINESS.md`. If the generation provider is unavailable on recording day, do not pretend the model produced an answer; instead, demonstrate the system’s visible fail-closed behavior and explain the limitation plainly.

| Before recording | Required condition |
|---|---|
| Application health | `GET /api/health` has reported Hindi, Kannada, and Telugu available. |
| Microphone | Browser microphone permission is allowed for the voice segment. |
| Generation provider | Confirm whether it can return a cited grounded answer before recording. |
| Evidence | Keep `artifacts/evaluation/live_text_api_benchmark.md` and `artifacts/evaluation/chunking_strategy_comparison.md` ready in separate tabs. |
| Privacy | No API keys, local file paths containing private data, or account information are visible. |

## Narrated recording sequence

### 1. Opening — 0:00 to 0:30

> “This is **Contextline**, a local voice-enabled retrieval-augmented generation prototype. It supports Hindi, Kannada, and Telugu retrieval over a bounded development slice of the `ai4bharat/MSMARCO-XI` validation corpus. The system retrieves source chunks before any optional generated answer and displays the evidence used.”

Show the page title, language selector, Generate-answer switch, voice-record button, and evidence area. Do not call the prototype publicly deployed unless the displayed URL is a real public deployment.

### 2. Hindi grounded retrieval — 0:30 to 1:20

Select **Hindi**. Enter a clearly corpus-relevant Hindi question, such as:

> `कंपनी का निगमन किसके कानूनों द्वारा शासित होता है?`

Leave **Generate answer** enabled only if the provider has just been confirmed working. Submit the question and wait for a response. Point out the language badge, whether the result was grounded or refused, source chunks, and the timing cards.

> “The response is presented with retrieved source chunks. If answer generation runs, the response is constrained to cite those chunks. If evidence or the provider is unavailable, the system should refuse rather than invent an uncited answer.”

### 3. Real voice-to-answer flow — 1:20 to 2:20

Keep Hindi selected. Click **Record voice**, say the same question naturally, stop the recording, and wait for the result. Hold the completed page still for several seconds so the transcript, answer/refusal, source chunks, and timing cards are all visible.

> “This is the real browser microphone path. The displayed transcript comes from speech-to-text, then the retrieved evidence is used for the response. The cards show the observed browser and server timing for this request.”

Do **not** claim this run satisfies a specific end-to-end latency requirement unless the measured result, exact test conditions, and the claim have all been independently documented. A voice capture is the only valid support for a voice-to-answer timing claim.

### 4. Kannada and Telugu coverage — 2:20 to 3:00

Switch first to **Kannada**, then to **Telugu**. For each, submit one short corpus-relevant typed query and pause on the result. The query may be written in the selected language or taken from a known corpus-relevant example that the team has tested beforehand.

> “The application keeps separate local indexes for Hindi, Kannada, and Telugu. The language badge and returned source chunks confirm the selected route for each demonstration.”

Do not use one successful Hindi response as evidence that all language routes work; show each language selector and its own result.

### 5. Safety and evidence-bound refusal — 3:00 to 3:35

Demonstrate either a safely described unsafe-request refusal or an unsupported query for which the corpus does not provide evidence. Use a short, non-graphic request and do not show instructions for harmful conduct.

> “The system has an early safety check and an evidence threshold. When a request is unsafe or the retrieved context does not support an answer, it returns a refusal rather than attempting to fabricate an answer.”

Show the refusal badge and the absence of unsupported sources or generated claims.

### 6. Benchmark and chunking evidence — 3:35 to 4:30

Open `artifacts/evaluation/chunking_strategy_comparison.md` and point to the five strategies: fixed, fixed-overlap, sentence-aware, semantic, and passage-preserving. Then open `artifacts/evaluation/live_text_api_benchmark.md`.

> “This chunking comparison is reproducible over saved official validation records. The live API table measures the local text retrieval path using generation disabled. These values exclude microphone capture, remote speech-to-text, and answer generation, so they are not presented as full voice-to-answer latency.”

### 7. Closing — 4:30 to 5:00

> “Contextline demonstrates multilingual local retrieval, voice integration, source-backed responses, fail-closed behavior, and reproducible evaluation artifacts. The repository and submission package identify the current development scope and distinguish verified local benchmarks from the remaining team-owned deployment and publication steps.”

End on the browser interface with a completed source-backed response or a clear grounded refusal.

## Post-recording checklist

| Item | Required check |
|---|---|
| Legibility | The question, language, response status, source chunks, and timing cards can be read at normal playback resolution. |
| Truthfulness | Every spoken claim is supported by what appears on screen or by a linked evidence artifact. |
| Voice proof | At least one uninterrupted browser microphone run is included if the video claims voice capability. |
| Safety | The recording contains no credentials, personal data, or harmful instructions. |
| Evidence boundary | Retrieval-only benchmark figures are clearly labelled as excluding STT and generation. |
| Export | Save the source recording and the final exported video with a date and version in the submission hand-off folder. |

## Reference

[1]: https://docs.google.com/document/d/1gzPyuYMaJGnv7mjPZ7Z_e20VxP0j5PMOPi8WmBi8rFk/edit "HH Goa 2026 Task 2 competition brief"
