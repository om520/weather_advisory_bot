### Failure Case 1: Geocoding Ambiguity (Planets vs. Cities)

**Query:** `Boating on Mars today.`

**Actual Behavior (Failure):**
Instead of returning an error or unrecognized location for "Mars", the geocoding API blindly resolved "Mars" to a real municipality named "Mars, Pennsylvania, United States". It then fetched the actual weather for that town and provided standard outdoor guidance.

**Output Captured:**
```text
### 50. Boating on Mars today.
**Badge:** ⚪ No guidance

**Reply:**
No weather hazard policy for boating was triggered for Mars, Pennsylvania, United States (today). That is not an all-clear. This check covers weather only, not traffic, road works, road surface or air quality.
```

**Architectural Note / Fix Required:**
The system needs a validation boundary for unreasonable geographic locations or a context-aware intent parser that can reject queries meant as jokes (like boating on other planets) before sending them to the weather API.

---

### Failure Case 2: Severe API Rate Limiting (LLM Backend)

**Context:**
During the batch evaluation of 50 queries, a massive volume of requests failed with HTTP Read Timeouts.

**Log Analysis & Root Cause:**
An inspection of the backend LLM API logs (`gpt-oss-120b`) reveals a strict quota enforcement pattern. Grouping the log entries by minute (07:08, 07:09, 07:10, 07:11, 07:12) shows exactly **4 successful HTTP 200 responses per minute**. Every request sent beyond that ceiling within the same minute is rejected with an HTTP 429 error: `Requests per minute limit exceeded - too many requests sent.`

**The Rate Limit:**
The current LLM provider account/tier is hard-capped at **4 Requests Per Minute (RPM)**. 

**Architectural Note / Fix Required:**
1. **Client-Side Throttling:** For automated testing, `evaluate_model.py` must be updated to sleep for at least 15 seconds between requests (`60 seconds / 4 requests = 15s delay`) to prevent tripping the 4 RPM limit.
2. **Production Queuing:** If this specific model tier is used in production, the FastAPI server needs an asynchronous queue or a rate-limiting semaphore. Otherwise, concurrent users will cause the system to hang and eventually time out.
