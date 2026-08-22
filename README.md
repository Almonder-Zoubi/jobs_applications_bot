# Jobs Applications Bot

Daily assistant for finding suitable jobs, scoring them against your profile, writing tailored motivation letters, and preparing up to 20 applications per day.

The default implementation is conservative: it creates application packets and records them in a ledger. Automatic submission should be added only for job boards that permit automation and only after you have reviewed the generated profile data, answers, and letters.

## What It Does

- Reads your candidate profile from `config/profile.json`
- Reads free-form background/decision guidance from `config/profile_context.md` (used by the LLM evaluation stage only)
- Reads job postings from `data/jobs.json`
- Runs the same two-stage apply/no-apply decision (deterministic keyword score + local LLM review) used by the single-URL evaluator — see [How the apply/no-apply decision is made](#how-the-applyno-apply-decision-is-made)
- Only prepares a letter and ledger entry for jobs where both stages agree on `apply`
- Generates a tailored motivation letter, and suggests which pre-written cover letter template (`config/motivation_templates.json`) best fits the role
- Enforces a daily application limit, defaulting to 20
- Writes application packets to `out/applications/YYYY-MM-DD/`
- Writes same-day digests — `out/to_apply_<YYYY-MM-DD>.json` for clean passes and `out/to_preview_first_<YYYY-MM-DD>.json` for qualified jobs that still raised a flag — each with score, strengths, concerns, and suggested letter
- Tracks prepared jobs in `data/applications_ledger.jsonl` so reruns never duplicate a decision

## Candidate Profile Formats

`config/profile.json` supports two shapes, auto-detected by `job_bot.config.load_profile`:

- **Flat schema** — matches `config/profile.example.json` exactly (`name`, `cv_summary`, `background: [...]`, `interested_roles: [...]`, etc.). Used as-is via `CandidateProfile.from_dict`.
- **Structured CV schema** — detected when the file has a `surname` or `experience` key (this is the format the real `config/profile.json` uses). It mirrors a full CV: `skills` as nested categories, `experience`/`education`/`projects` as structured entries, `preferred_locations` as a `{"Country": [cities]}` map, `salary_expectations` as `{"currency", "amount"}`, plus `languages` and `soft skills`. `job_bot/profile_data.py` flattens all of this into the same internal `CandidateProfile` the matcher and LLM use — experience, education, and project bullets all feed into `background`; skills and soft skills merge into `skills`.

Whichever schema you use, field names matter: an unrecognized key is silently ignored rather than erroring, so a typo (e.g. `avoid roles` instead of `avoid_roles`) will fall back to a generic default instead of failing loudly. If a value in the exported evaluation JSON looks generic instead of like your real data, check the key names in `config/profile.json` first.

## Candidate Context (`config/profile_context.md`)

This is a free-form Markdown document — not structured data — where you explain your background, transferable skills, career stage, and how you want job fit judged (e.g. "don't reject me just because a posting asks for a language I haven't used"). It is passed verbatim into the LLM's evaluation prompt (see `job_bot/ollama_client.py::build_evaluation_prompt`) so the LLM stage can reason with the nuance that keyword matching alone can't capture. It has no effect on the deterministic keyword score in `job_bot/matcher.py`. There's no required schema — write it like a note to a recruiter who needs context.

## Quick Start

1. Edit `config/profile.json` with your real CV, certificates, background, preferred roles, and constraints. A placeholder/example structure is available in `config/profile.example.json`.
2. Edit `config/profile_context.md` with background/decision-guidance for the LLM stage. A placeholder is available in `config/profile_context.example.md`.
3. Add job postings to `data/jobs.json`. A placeholder file is already present locally, and `data/jobs.example.json` shows the expected structure.
4. Run:

```bash
python3 -m job_bot.run_daily
```

Generated letters and summaries will appear under `out/applications/`.

## Test One Job Link

Start Ollama in one terminal:

```bash
ollama serve
```

Then evaluate one real job posting with `gemma3:12b`:

```bash
python3 test_url.py --url "https://example.com/job-posting"
```

The command is evaluate-only. It does not apply, does not write a motivation letter, and does not touch `data/applications_ledger.jsonl`.

It prints JSON and also exports the same result to `out/evaluations/`. The top-level `decision` is always either `apply` or `no apply`.

You can also choose an explicit output path:

```bash
python3 test_url.py --url "https://example.com/job-posting" --output out/evaluations/latest.json
```

For a smoke test without Ollama:

```bash
python3 test_url.py --url "https://example.com/job-posting" --no-llm
```

The older script still works too:

```bash
python3 scripts/evaluate_job_url.py "https://example.com/job-posting"
```

### How the apply/no-apply decision is made

Every evaluation (single-URL or daily batch) runs two independent checks and only decides `apply` if both agree:

1. **Deterministic keyword match** (`job_bot/matcher.py`) — scores the job against `profile.json` skills, roles, and locations; applies a hard veto if the job **title** matches `avoid_roles`; and applies a softer score penalty (not a veto) if the full job **description** contains seniority signals — a "Senior"/"Staff"/"Principal"/"Lead"/"Head of"/"Director" title or a "N+ years" requirement where N ≥ 4. This is a soft penalty rather than a veto because body text can mention seniority in passing (e.g. "mentored by senior engineers") without the role itself requiring it — the LLM stage weighs the actual context.
2. **LLM review** (`job_bot/ollama_client.py`, model `gemma3:12b` by default) — receives the same candidate/job/score data, the detected seniority signals, and the full text of `config/profile_context.md`, and independently returns `APPLY`/`NO_APPLY` plus a structured breakdown (`direct_matches`, `transferable_matches`, `missing_skills`, `hard_requirement_failures`, `experience_fit`, `interest_fit`, `reason`). A non-empty `hard_requirement_failures` always forces `no apply`, regardless of the LLM's own top-level decision. It's explicitly instructed not to invent requirements that aren't in the job text and not to claim a skill is missing without checking the candidate's skills/background lists first.

The exported JSON's `decision_basis` block shows exactly what fed each stage, including `profile_context_used_by_llm` so you can confirm your guidance document was actually read for that run. Use `--no-llm` to see the keyword-only fallback decision in isolation.

**On job fetching quality:** `job_bot/job_fetcher.py` first looks for `schema.org JobPosting` structured data (`<script type="application/ld+json">`), which most modern job boards (Ashby, Greenhouse, Lever, Workday, etc.) embed specifically so Google Jobs can index the posting without running JavaScript — this gets the full real description even on JS-rendered pages. If that's missing, it falls back to scraping visible page text, which can be thin or empty on heavily JS-rendered pages the fetcher can't otherwise read. Either way, the fetched job carries a `description_confidence` (`"high"`/`"low"`, based on extracted text length) that's surfaced to the LLM so it treats a thin extraction cautiously instead of confidently guessing — check `role_description_full` in the evaluation JSON if a decision looks off; a near-empty value means the fetch, not the model, is the problem.

## Configuration

`config/settings.json` controls:

- `daily_limit`: max applications prepared per calendar day
- `minimum_match_score`: minimum keyword score required before preparing an application
- `mode`: currently `prepare`
- `output_dir`: where application packets (`out/applications/...`) are written
- `to_apply_dir`: where the daily `to_apply_<date>.json` digest is written (default `out`)
- `ledger_path`, `jobs_path`, `profile_path`, `profile_context_path`: input/output file locations
- `use_llm`: whether `run_daily` uses the LLM stage (default `true`; `--no-llm` overrides per run)
- `model`, `ollama_url`, `ollama_timeout`: which local model to use for the LLM stage. `llama3.3` (70B) is also available locally and reasons more reliably than the default `gemma3:12b` — slower, but worth trying via `"model": "llama3.3"` if you want a second opinion on a borderline decision.
- `ollama_keep_alive`: how long Ollama keeps the model resident in memory after a request (default `"30m"`). `run_daily` also sizes one shared `num_ctx` for the whole batch and explicitly unloads the model (`keep_alive: 0`) once the run finishes, so the model loads once, stays loaded across every job in that run, and is freed from RAM when done instead of lingering or reloading per job.

## Adding Job Sources

This repo starts with a file-based job source. Good next additions are:

- LinkedIn saved-search export/manual import
- Indeed/RSS feeds where available
- Greenhouse, Lever, Workable, Ashby company job boards
- A browser-based submitter for a specific site, after checking site terms

## Important Notes

- Do not submit false information. The bot should use only your real CV/background.
- Review generated letters before sending them.
- Many job platforms restrict automated submissions. Prefer official APIs, company ATS job boards, or a human-review workflow.

## Running Daily

On macOS or Linux, schedule this command once per day from this project folder:

```bash
python3 -m job_bot.run_daily
```

For each job in `data/jobs.json` not already in the ledger, it runs the same two-stage evaluation as `test_url.py` (see [How the apply/no-apply decision is made](#how-the-applyno-apply-decision-is-made)) against `config/profile.json` and `config/profile_context.md`. Only jobs where both stages agree on `apply` get a generated letter, an `out/applications/YYYY-MM-DD/...` packet, and a ledger entry; everything else is skipped and printed with the reason (including the LLM's stated concern, if any).

Every run writes two digests, split by whether anything raised a flag worth a second look:

- `out/to_apply_<YYYY-MM-DD>.json` — qualified jobs with **no** flags: no LLM concern, no seniority/experience-level signal, and a high-confidence description. These are the closest thing to a clean pass.
- `out/to_preview_first_<YYYY-MM-DD>.json` — qualified jobs that still raised something (see `review_reasons`). A letter is still generated for these (drafting is cheap and you should review every letter regardless — see Important Notes), but treat the fit itself as unverified until you've read the job yourself.

Both files share the same entry shape:

```json
[
  {
    "job_id": "...",
    "title": "Applied AI Engineer",
    "company": "Nexxa.AI",
    "url": "...",
    "decision": "apply",
    "keyword_score": 65,
    "llm_confidence": 80,
    "fit_summary": "...",
    "strengths": ["..."],
    "missing_or_concerns": ["..."],
    "description_confidence": "high",
    "review_reasons": ["LLM raised a concern"],
    "suggested_letter_template": {
      "category": "ai_ml_llm",
      "english": "files/Cover_Letter_AI_ML_LLM.docx",
      "german": "files/Anschreiben_AI_ML_LLM.docx"
    },
    "generated_letter_path": "out/applications/.../motivation_letter.txt"
  }
]
```

`suggested_letter_template` is picked from `config/motivation_templates.json` by matching the job's title/requirements against each category's `target_roles`; it's `null` if nothing matches well enough. It's a suggestion for which of your existing `.docx` cover letters to send, alongside the auto-generated `motivation_letter.txt` (which remains a template-filled draft, not LLM-written — review both before sending anything).

The ledger prevents duplicate applications and enforces the configured daily limit. Options: `--limit N` and `--min-score N` override the settings values for one run; `--no-llm` skips the LLM stage entirely (faster, keyword-only, useful if Ollama isn't running).
