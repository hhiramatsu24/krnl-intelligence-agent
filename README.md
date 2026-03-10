# Kernel Market Intelligence Agent

Automated competitive intelligence pipeline for [Kernel](https://kernelbrowsers.com) — monitors Reddit, Hacker News, and Browserbase's own website for developer pain signals, competitive moves, and sales opportunities. Produces a structured weekly briefing via Claude in under 5 minutes.

Built with Kernel, Claude, and Playwright. March 2026.

---

## What It Does

The highest-intent sales leads for Kernel are developers who are already using Browserbase and hitting its limits — they announce this publicly. This agent finds them automatically.

Every run:
1. Searches Reddit for Browserbase complaints and alternative-seeking posts
2. Finds the top HN threads about Browserbase and browser automation
3. Visits Browserbase's pricing, changelog, and careers pages with a Kernel cloud browser
4. Deep-reads the most relevant posts using two parallel Kernel browsers running simultaneously
5. Feeds everything to Claude, which produces a four-section actionable briefing

**Sample output from March 9, 2026 — 89 items collected, 5 HOT signals, $0.02 cost:**

```
## 1. EXECUTIVE SUMMARY
Browserbase launched Stagehand caching on Feb 17, delivering 2x faster execution
and 30% cost reduction — a major competitive move. Developers are actively seeking
alternatives due to reliability issues, presenting clear sales opportunities.

## 4. RECOMMENDED ACTIONS
1. Reply to reddit.com/r/AI_Agents/comments/1ralwha/ highlighting Kernel's sub-150ms
   cold starts and 72-hour session support — developer explicitly named Browserbase
   in the context of long-running agent reliability failures.
2. Update positioning against Stagehand caching — either match the capability or
   emphasize Kernel's differentiated strengths.
3. Create outreach to unfunded AI agent teams emphasizing Kernel's 2x cost advantage
   over Browserbase's Developer tier.
```

---

## Architecture

| Module | Method | Kernel Used? |
|--------|--------|-------------|
| `reddit_monitor_nk.py` | Reddit JSON API | No — API is faster and has no bot-detection risk |
| `hn_monitor.py` | Algolia API + Kernel browser | Yes — confirms thread loads for Phase 5 deep read |
| `browserbase_tracker.py` | Kernel browser (stealth) | Yes — React site requires real browser rendering |
| `intelligence_briefing.py` | 2x parallel Kernel browsers + Claude API | Yes — asyncio.gather() for simultaneous deep reads |

**Why two browsers run in parallel:**
`asyncio.gather()` runs the Reddit and HN deep reads simultaneously — two independent Kernel sessions, each visiting 5 URLs, both running at the same time. Total runtime for 10 URLs equals roughly 5 serial reads.

**Why Reddit uses an API instead of Kernel:**
Reddit's bot detection has been heavily reinforced since their 2023 API controversy. Even with stealth mode enabled, a Kernel browser returned 0 results consistently. Reddit's public JSON API returns cleaner structured data with no bot risk — the right tool for the job.

---

## Signal Scoring

Every item collected across all sources is scored HOT, WARM, or MONITOR:

| Score | Trigger | Meaning |
|-------|---------|---------|
| **HOT** | alternative, replace, migrate, reliability, broken, failing, browserbase down | Developer actively seeking alternatives or experiencing critical failures — immediate sales opportunity |
| **WARM** | issue, problem, bug, slow, expensive, pricing, timeout, crash | Developer experiencing friction — worth monitoring |
| **MONITOR** | Everything else that passes the Browserbase-relevance check | Related to the space but no immediate pain signal |

A Browserbase-relevance pre-check runs before scoring — items must mention `browserbase`, `browser automation`, `playwright`, or `puppeteer` to qualify. This reduced false HOT signals from 15 to 0 on the first test run.

---

## File Structure

```
├── intelligence_briefing.py   # Master orchestrator — runs all modules, deep reads, calls Claude
├── reddit_monitor_nk.py       # Reddit monitor via JSON API
├── hn_monitor.py              # HN monitor via Algolia API + Kernel browser visits
├── browserbase_tracker.py     # Browserbase website tracker — pricing, changelog, careers
├── main.py                    # Standalone test script — visits a URL and returns page title
├── reddit_monitor.py          # Original browser-based Reddit monitor (kept for comparison)
├── .env.example               # Required environment variables
└── .gitignore
```

---

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/hhiramatsu24/krnl-intelligence-agent.git
cd krnl-intelligence-agent
```

**2. Install dependencies**
```bash
pip install anthropic kernel-python playwright python-dotenv requests
playwright install chromium
```

**3. Set up environment variables**

Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

```
KERNEL_API_KEY=your_kernel_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

**4. Run the full pipeline**
```bash
python intelligence_briefing.py
```

Or run individual modules:
```bash
python reddit_monitor_nk.py      # Reddit pain signals only
python hn_monitor.py             # HN threads only
python browserbase_tracker.py    # Browserbase website only
```

---

## Cost & Performance

| Metric | Value |
|--------|-------|
| Full pipeline runtime | 3–5 minutes |
| Kernel browser sessions per run | 4 total (2 monitors + 2 parallel deep read) |
| Pages visited per run | 8–12 pages |
| Claude API cost per run | ~$0.02 |
| Annual cost at weekly cadence | ~$1.04 / year |
| Recommended cadence | Weekly |

---

## Key Engineering Decisions & Issues Log

**Reddit bot detection → switched to JSON API**
The Kernel browser returned 0 posts consistently even with stealth mode. Reddit's anti-automation investment since their 2023 API controversy is significant. Switched to the public JSON API — returned 11 relevant posts immediately and freed a Kernel session for higher-value use.

**HN returning 15 false HOT signals → added relevance pre-check**
Posts like "Ask HN: Gmail alternative?" scored HOT because they contained the word "alternative." Added a Browserbase-relevance check before applying keyword scoring. False positives dropped from 15 to 0.

**Stack Overflow returning 0 via browser → switched to Stack Exchange API**
Kernel browser loaded the page but CSS selectors returned empty lists — bot detection was serving a CAPTCHA. Replaced with the Stack Exchange public API. Went from 0 to 12 results with better structured data.

**HN comment extraction too brittle → deferred to Claude**
CSS selectors for HN's nested table structure were unreliable. Rather than shipping fragile scrapers, comment extraction was deferred to Claude in Phase 5. Claude understands context — it knows why a signal matters, not just that keywords match.

**Careers page returning nav links instead of job titles → structural pattern extraction**
Multiple CSS selector approaches returned wrong content. Final solution: job titles on Browserbase's careers page are always followed by a department name on the next line. That structural pattern is more reliable than any selector and survives site redesigns.

---

## Competitive Intelligence — March 2026 Snapshot

- **Browserbase pricing:** Developer tier at $0.12/browser-hour. Kernel is approximately 2x cheaper at comparable usage levels.
- **Recent features:** Stagehand Caching (Feb 17) — automatic LLM call reduction with DOM hashing, claims 2x speed and 30% cost reduction. Vercel Marketplace integration (Feb 12) — targeting the Next.js ecosystem.
- **Hiring signal:** 9 GTM roles vs 5 engineering as of March 2026 — full revenue-scaling motion underway.

---

## About

Built by Hugo Hiramatsu — UCLA Aerospace Engineering, sophomore, March 2026.

`hhiramatsu24@g.ucla.edu` 
