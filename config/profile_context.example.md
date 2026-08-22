# Candidate Context

This file is free-form Markdown, not structured data. It is passed verbatim to the
LLM evaluation stage (`job_bot/ollama_client.py::build_evaluation_prompt`) alongside
`config/profile.json`, so the LLM can reason about fit with more nuance than keyword
matching allows. It has no effect on the deterministic score in `job_bot/matcher.py`.

There is no required schema. Write it like a note to a recruiter who needs context
on how to read your CV. A few sections that tend to help:

## Professional Profile

Who you are, what stage of your career you're at, and what you're actually looking for.

## Core Technical Profile

Your strongest skills, and what you've actually built with them (not just a tool list).

## Transferable Skills

Explicitly tell the model which missing exact-keyword requirements should NOT count
against you, and why. Example: "Experience with PostgreSQL should count for other
relational databases; I have not used Oracle but the concepts transfer."

## Experience-Level Interpretation

State what seniority you're targeting, and which terms (e.g. "Senior", "Staff",
"Head of") should lower the score unless the description clearly says otherwise.

## Evaluation Principle

A closing statement telling the model how to weigh an imperfect match, e.g.:
"Favor applying when I'm reasonably qualified, even if the match isn't perfect."
