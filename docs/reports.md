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

## Monthly and yearly reports

**Menu → Stats → Reports.** Choose a month or a year and it is shown on screen, compared with the period before it; **Download PDF** saves the same report as a file.

The report on screen and the report in the PDF are the same report. The download is a way to keep it, not a different document.

The list of periods is built from your actual training rather than from the calendar, so there is no empty February to pick.

Stats also holds what the home page used to: lifetime distance and time, the attribute profile, and where your time goes by sport. Those answer a slower question than "how is this week going", and they were being read every time anyone opened the app, above the week they could still change.

A report contains headline figures, a distance chart, the full comparison against the previous period, the detail, best efforts, other sports, the coach's note if you asked for it, and a table of every run.

Details worth knowing:

- **A year is charted by month**, not as 365 bars.
- **Empty buckets are kept.** The gaps in a training month are as informative as the sessions.
- **Against a period with no training**, the comparison is replaced by a sentence saying so, rather than a table of everything being up by its own value.
- The written review is included in the PDF when a model is configured.
- Rendered with ReportLab — pure Python, no system libraries — so the image builds anywhere.
- Downloads work in the Android app too, through a bridge that reads the blob out of the page. Files land in Downloads and open in your PDF viewer.

---

## The coach

Recaps and PDF reports can carry a written review from a language model **running on your own hardware**. It is given only the figures in the report, already formatted, and told not to produce a number that is not in front of it — it phrases, it never calculates.

A review of a finished period uses a longer prompt than a per-activity note, because it has a comparison to make. It is cached against the facts it describes, so a finished week is narrated once rather than on every visit.

Turn it off by leaving `OLLAMA_URL` empty; leave it off and the report is simply generated without a note.

**Cycle tracking data is never sent to the coach**, and no cycle figure enters a recap or a PDF.

See **[The local language model](coach.md)** for setup, model choice, exactly what data is sent, and the prompt rules.
