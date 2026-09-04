# Reports and coaching

## Recaps

A dashboard answers *where am I now*. A recap answers *what did I just do, and was it more or less than before* — a different question, so it gets its own screen.

**Comparison is the organising idea.** Every headline figure carries the same figure from the period before it, because 42 km means nothing until you know last week was 28.

### The weekly recap

The home page shows a **Last week** card — distance, how that compares, days trained — which opens the full recap.

"Last week" means the week that **finished**, Monday to Sunday. A rolling seven-day window would put Sunday's long run in two different summaries and never settle on a verdict; a completed week stops changing, which is what makes it worth reading on Monday morning. The card is badged on Monday and Tuesday, when it is actually news.

The recap contains:

- Distance, time, runs and load, each with its change
- Distance by day, with rest days drawn as empty slots because the gaps are part of the picture
- A comparison table: days trained, sessions, elevation, average pace, average heart rate, calories
- The detail — longest, quickest, GAP, cadence, stride, decoupling, fitness, form
- Best efforts set that week, personal records marked
- Other sports, counted separately and kept out of the running averages
- Every session

### Picking a week

Weeks are picked off a **calendar marked with the days you trained**, one dot per sport. Stepping back an arrow-press at a time is fine for last week and hopeless for last March, and the marks mean an empty fortnight is visible at a glance rather than discovered by paging through it. Chevrons remain for nudging one week either way.

### How the averages are computed

**Weighted, never a mean of means.** A week's average pace is its total distance over its total time.

Averaging the pace of a 20 km run with that of a 2 km jog put the figure **49 s/km** out in testing — it would flatter or punish you based only on how many short sessions you did. The same applies to heart rate, cadence and stride.

Cycles outside plausible bounds are excluded from averages but kept in the history, so one mis-entry does not drag every figure after it.

---

## PDF reports

**Settings → Printable reports.** Choose a month or a year, with or without the written review, and download.

The list of periods is built from your actual training rather than from the calendar, so there is no empty February to pick.

A report contains headline figures, a distance chart, the full comparison against the previous period, the detail, best efforts, other sports, the coach's note if you asked for it, and a table of every run.

Details worth knowing:

- **A year is charted by month**, not as 365 bars.
- **Empty buckets are kept.** The gaps in a training month are as informative as the sessions.
- **Against a period with no training**, the comparison is replaced by a sentence saying so, rather than a table of everything being up by its own value.
- Rendered with ReportLab — pure Python, no system libraries — so the image builds anywhere.
- Downloads work in the Android app too, through a bridge that reads the blob out of the page. Files land in Downloads and open in your PDF viewer.

---

## The coach

Optional written commentary from a language model **running on your own hardware**. Set `OLLAMA_URL` to your Ollama instance; leave it empty and the feature disappears entirely.

It appears in three places: under an activity, on the home page for the current week, and inside a recap or PDF as a review of the finished period.

### What it is allowed to do

It **phrases**; it never calculates. It is given only figures this server has already computed, pre-formatted the way they should be read aloud, and is told not to produce a number that is not in front of it.

The system prompt forbids medical advice, forbids suggesting illness or injury, and forbids prescribing training. It may say a week was heavy or a session was easy; it may not write next week's plan.

Notes are cached against the facts they describe, so a finished week does not get re-narrated on every visit. The prompt is part of the cache key, so rewording it regenerates rather than serving text written under the old instructions.

### Three things testing changed

Real models got these wrong repeatedly, so the brief handles them before the model sees anything:

- **Data-quality fields had to be removed entirely.** Given `heart_rate_coverage_pct: 97`, every model tested read it as effort — *"you pushed to 97% of maximum"* — rather than as how much of the session was measured. Coverage now decides server-side whether a metric is trustworthy enough to include, and is then never mentioned.
- **Small models should not do arithmetic.** Given `74` minutes, one model wrote "just under an hour". Every value now arrives pre-formatted.
- **A leading minus is read as a small number,** and pace "improving" by falling is read backwards. Directions are words now: "down by 40 m, which is 11 percent less", "quicker than the period before".

### What it never sees

**Cycle tracking data is never sent to the coach**, and no cycle figure enters a recap or a PDF.

### Failure

An unreachable or slow model leaves everything exactly as it was. Nothing in your training data depends on it. If a note cannot be written, the last one is shown; if there is none, the section does not appear.

```bash
curl -s http://localhost:8000/api/v1/coach/status -H "Authorization: Bearer <token>"
```

Anything up to about 7B parameters is fine on 8 GB of VRAM. `qwen2.5:7b` is the default.
