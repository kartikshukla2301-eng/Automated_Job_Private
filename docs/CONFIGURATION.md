# Configuration Guide and Reference

The AI Job Application Agent employs a tiered configuration model combining static YAML defaults (`config/config.yaml`), persistent runtime overrides (`PersistentConfigManager`), and environment variables (`.env`).

---

## 1. Environment Variables (`.env`)

Environment variables take precedence for deployment topology, infrastructure secrets, and critical safety barriers.

| Variable Name | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `REAL_SUBMIT_GATE_ENABLED` | bool | `false` | **Non-negotiable safety invariant**. Must strictly remain `false` until production submit verification criteria are satisfied. |
| `PORT` | int | `8000` | Port on which FastAPI server listens. |
| `ENVIRONMENT` | string | `development` | Deployment environment (`development`, `staging`, `production`). |
| `LOG_LEVEL` | string | `INFO` | Logging severity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `OPENROUTER_API_KEY` | string | — | API key for OpenRouter LLM Gateway. |
| `OPENROUTER_BASE_URL` | string | `https://openrouter.ai/api/v1` | OpenRouter endpoint URL. |
| `LLM_DEFAULT_MODEL` | string | `anthropic/claude-3.5-sonnet` | Default primary LLM model. |
| `SUPABASE_URL` | string | — | Supabase PostgreSQL project URL. |
| `SUPABASE_KEY` | string | — | Supabase service key. |
| `TELEGRAM_BOT_TOKEN` | string | — | Telegram bot token for real-time operator alerts. |
| `TELEGRAM_CHAT_ID` | string | — | Authorized operator chat ID. |
| `PERSISTENT_CONFIG_PATH` | string | `config/runtime_config.json` | Path to persistent dynamic configuration overrides. |

---

## 2. Baseline Configuration (`config/config.yaml`)

### 2.1. Autonomy (`autonomy`)
Controls the operating autonomy tier per provider and globally:
- `L0`: Human Approves Everything (Dry-run only, zero auto-submit).
- `L1`: Human Approves Form Before Submission (Mandatory human sign-off).
- `L2`: Conditional Submission (Submit only if confidence threshold met, 0 sensitive fields).
- `L3`: Full Auto (Unattended execution; forbidden for restricted providers).

```yaml
autonomy:
  default_level: "L0"
  per_provider:
    greenhouse: "L0"
    lever: "L0"
    naukri: "L0"
    wellfound: "L0"
    ashby: "L0"
    linkedin: "L0" # LinkedIn is hardcoded to never exceed L1
```

### 2.2. Daily and Cooldown Caps (`caps`)
Prevents over-application, spam, and vendor rate-limiting:

```yaml
caps:
  global_per_day: 20
  per_provider_per_day:
    greenhouse: 15
    lever: 15
    naukri: 20       # Governed by capacity ramp (S0: 2/day, S1: 5/day, etc.)
    wellfound: 10
    ashby: 10
    linkedin: 10
  per_company_per_30d: 1  # 30-day anti-spam cooldown per company
  per_company_per_day: 2  # Max applications to same company per calendar day
```

### 2.3. Scheduling and Active Window (`schedule`)
Constrains execution to reasonable candidate working hours in IST:

```yaml
schedule:
  timezone: "Asia/Kolkata"
  active_hours: "09:00-23:00"
  delay_seconds:
    - 30
    - 90
```

### 2.4. Matching and Scoring (`matching`)
Defines thresholds for hard filter enforcement and semantic scoring:

```yaml
matching:
  threshold: 65          # Minimum score required for MATCH decision
  borderline_band:       # Score range invoking LLM scoring chain
    - 55
    - 70
  max_job_age_hours: 24  # Jobs older than 24h are excluded
```

### 2.5. Approval Queue (`approval`)
Defines time-to-live for human approval gates:

```yaml
approval:
  expire_hours: 24       # Stale applications auto-expire after 24h
```

### 2.6. Profile Source (`profile`)
Controls candidate profile ingestion and freshness:

```yaml
profile:
  source: "devleveler"   # Options: "devleveler", "local_file"
  stale_after_days: 7
  cache_ttl_hours: 24
```

---

## 3. Dynamic Configuration via PersistentConfigManager

The system supports hot-reloading dynamic configuration parameters through the `/api/v1/ops/config` REST endpoints.
- In-memory modifications are written atomically to `config/runtime_config.json`.
- Changes persist across worker restarts without modifying the source-controlled `config/config.yaml`.
- Invalid configurations (e.g. attempting to elevate LinkedIn to L2/L3 or specifying negative caps) are rejected at the schema boundary.
