# Project Coding Guidelines (claude.md)

These guidelines are a concise, always-on checklist derived from [REQUIREMENTS.md](REQUIREMENTS.md).
All contributors and automated agents must follow these rules when writing or modifying code in this repository.

## Primary Requirements

- Detect log anomalies within < 30 seconds of occurrence.
- Support continuous, uninterrupted ingestion from multiple services.
- Handle throughput of 50k–200k log events per minute.
- Ensure no data loss under normal operation or during failures.
- Support horizontal scaling and fault-tolerant, distributed execution.

## Design & Implementation Rules

- Use stream-based ingestion (recommended: Kafka or equivalent) for production systems.
- Use windowed, low-latency processing (recommended: Dask or streaming-capable frameworks).
- Design lightweight, streaming-friendly anomaly detection models that can run online.
- Prioritize non-blocking I/O and backpressure-aware consumers to avoid pipeline stalls.
- Implement acknowledgement, durable storage, or replication to prevent data loss (exact mechanism depends on chosen platform).

## Performance & Reliability

- End-to-end detection latency must be < 30 seconds.
- System must handle spikes without data loss or severe degradation.
- Implement retries, idempotency, and safe restarts for processing components.
- Add health checks, metrics, and alerting for throughput, lag, error rates, and processing latency.

## Coding Practices

- Follow repository style and linters (use PEP8 / black / flake8 for Python code).
- Write clear, minimal, and well-tested changes. Include unit and integration tests where appropriate.
- Avoid large, unrelated refactors in feature PRs — keep changes focused and reviewable.
- Document design decisions and operational runbooks in README.md or relevant docs.

## CI / Deployment

- Ensure CI validates linting, tests, and basic integration checks before merging.
- Include load / smoke tests for streaming pipelines when possible.
- Provide deployment and rollback instructions for streaming components.

## PR Checklist (must be satisfied before merging)

1. Tests added/updated for new behavior.
2. Linting and formatting passed in CI.
3. Performance implications considered (latency, throughput).
4. Observability: metrics/logs/health checks added or validated.
5. Data safety: acking, retries, and no-single-point-of-loss considered.
6. Documentation updated (README, design notes, runbooks).

## Maintenance

- Keep this file up to date if requirements change.
- If a technical decision deviates from these rules, record the rationale in a design note and link it here.

---

These rules are authoritative for development in this repository and must be followed by all contributors and automation.

---

## 🎨 Code Style Guidelines

### Core Development Principles
**CRITICAL: Keep code simple and efficient - DO NOT over-engineer!**

- ✅ Write straightforward, readable code
- ✅ Optimize for efficiency when needed
- ❌ Avoid unnecessary abstractions
- ❌ Don't add features "for future flexibility"
- ❌ No premature optimization
- ❌ Keep it minimal and functional

**Rule of thumb:** If it's not explicitly required, don't build it.

### Function Docstrings
Always use this format for function docstrings:

```python
def function_name(param1: int, param2: str) -> bool:
    """
    Brief description of what the function does.

    param param1: Description of param1.
    param param2: Description of param2.
    """
```

**Requirements:**
- Always include type hints in function signature.
- Use multi-line docstring format (even for single line descriptions).
- Document parameters using `param parameter_name: description` format.
- Include return type hint (use `-> None` for void functions).

### Punctuation Rules
- Always end comments with a period (`.`).
- Always end list items in markdown files with a period (`.`).
- All sentences and descriptions must be properly punctuated.

### Type Hints (Python 3.13)
- Use built-in collection types directly: `list`, `dict`, `set`, `tuple`.
- DO NOT import from `typing` for basic collections.
- Use `typing` only for advanced types like `Optional`, `Union`, `Callable`, etc.

```python
# ✅ Correct (Python 3.9+).
def process_items(items: list[str]) -> dict[str, int]:
    pass

# ❌ Wrong - don't import List, Dict.
from typing import List, Dict
def process_items(items: List[str]) -> Dict[str, int]:
    pass
```

---

## 📁 Project Structure (To Be Established)

This section will be updated as the project structure is created.

---

**Remember**: Always consult [REQUIREMENTS.md](REQUIREMENTS.md) first!
