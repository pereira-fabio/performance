# The local language model

Performance can have a language model write commentary on your training. It runs on **your own hardware**, through [Ollama](https://ollama.com), and the feature does not exist unless you configure one.

This document covers what it does, exactly what data it is given, what it is never given, and how to set it up.

---

## What it is, and what it is not

**It phrases. It never calculates.**

Every number in the app is computed by the physiology engine from your activity data. The model is handed those numbers, already formatted, and asked to write a few sentences about what they mean. It is told not to produce a number that is not in front of it.

That boundary is the whole design. It means:

- **No figure anywhere in the app comes from a model.** If the coach is off, unreachable, or writes nonsense, every measurement and estimate is exactly the same.
- Generated prose is presented as a third kind of thing, distinct from a measurement and from an estimate. Every note says which model wrote it and when, and carries a line saying it phrases figures rather than measuring anything.
- It is never load-bearing. Nothing downstream reads it.

**It is not a medical tool and not a training plan.** The prompts forbid medical advice, forbid suggesting you may be ill or injured, and forbid prescribing training. It may say a session was hard or a week was light; it may not tell you what to do tomorrow.

---

## Setting it up

### 1. Run Ollama

On any machine your server can reach:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b
```

Ollama binds to `127.0.0.1` by default. To reach it from the container, bind it to the network:

```bash
# systemd
sudo systemctl edit ollama
# add:
#   [Service]
#   Environment="OLLAMA_HOST=0.0.0.0:11434"
sudo systemctl restart ollama
```

### 2. Point Performance at it

In `docker-compose.yml`:

```yaml
- OLLAMA_URL=http://192.168.1.50:11434
- OLLAMA_MODEL=qwen2.5:7b
```

Then `docker compose up -d`. **Leave `OLLAMA_URL` empty to turn the feature off entirely** — no requests, no coach sections, nothing.

> The value shipped in the repository points at the address this instance uses. Change it to yours or empty it.

### 3. Check it

```bash
curl -s http://localhost:8000/api/v1/coach/status -H "Authorization: Bearer $TOKEN"
```

```json
{ "enabled": true, "url": "http://192.168.1.50:11434", "model": "qwen2.5:7b",
  "reachable": true, "available_models": ["qwen2.5:7b", "llama3.1:8b"] }
```

`reachable: false` means the URL is wrong, Ollama is bound to localhost, or a firewall is in the way.

### Hardware and model choice

The briefs are short and the replies are shorter, so this is undemanding. Anything up to about **8B parameters fits comfortably in 8 GB of VRAM**.

`qwen2.5:7b` is the default and is what this has been used with. Any instruction-following model of a similar size — `llama3.1:8b`, `mistral:7b` — should work; nothing in the app assumes a particular one, so swapping is a config change and a **Rewrite**.

What to watch for when trying one: whether it invents numbers, and whether it respects the sentence limit. Those are the two rules that matter, and a model that breaks the first is not usable here regardless of how well it writes.

Reasoning models work but waste the token budget thinking out loud, so requests set `think: false`.

CPU-only inference works. It is slow — tens of seconds — which is why every request is cached and nothing blocks on it.

---

## Where it appears

| Place | Covers | Length |
| :-- | :-- | :-- |
| A monthly or yearly report | The finished period, against the one before it | 4–6 sentences |
| Inside a PDF report | The same review, embedded | 4–6 sentences |

**Only months and years.** There is no note on an individual run, on the week, or on the home page. A week is short enough to read from the figures, and a note on every screen turned generated prose into furniture rather than something you stop and read. The endpoints for the shorter notes still exist; nothing calls them.

Reports use a prompt with a longer budget than a short note would, because a review has a comparison to make and cutting it off mid-sentence is worse than the extra seconds.

---

## Exactly what is sent

A brief is plain text built entirely from figures the server already computed. This is a real one:

```
Session on Thursday 13 August 2026, running.

What was measured:
- Distance: 17.88 km
- Moving time: 1 hour 38 minutes
- Average pace: 5:30 per km
- Grade-adjusted pace: 5:26 per km
- Average heart rate: 143 bpm, peaking at 181 bpm
- Cadence: 172 steps per minute
- Ascent: 125 m
- Calories: 1216
- Pace and heart rate held together reasonably well, drifting apart by 4.1
  percent, which is normal

What was estimated from those figures:
- Training load: 111, against a typical session of 62 for this athlete
- Training effect: 3.2 out of 5

Where the athlete stands:
- Fitness, meaning their 42-day average training load: 46
- Form, meaning fitness minus recent fatigue: -7, so carrying some fatigue
- This was their longest run in the past 28 days
```

Note the structure: measured, estimated, and standing are separated, and each term is glossed in place, so the model does not have to know what CTL means.

### What is never sent

- **Your name, username, account id or any identifier.** The brief says "the athlete".
- **GPS coordinates, or any raw stream.** Only aggregates.
- **Cycle tracking data.** Never, in any context.
- **Data-quality figures.** See below.
- **Anything from another account.**

Nothing is sent to any third party. The only outbound request is to the address you configured.

---

## Three findings that shaped the briefs

These came out of testing against real models, and each one is now handled before the model sees anything.

### Coverage percentages read as effort

Given `heart_rate_coverage_pct: 97`, **every model tested** read it as intensity — *"you pushed to 97% of your maximum"* — rather than as how much of the session was measured.

Data-quality fields are now excluded entirely. Coverage decides **server-side** whether a metric is trustworthy enough to include in the brief at all, and is then never mentioned.

Related: anything the server could not measure is left out rather than marked absent. A model told a field is missing tends to speculate about why.

### Small models should not do arithmetic

Given `74` minutes, one model wrote "just under an hour". Every value now arrives pre-formatted the way it should be read aloud — `1 hour 38 minutes`, `5:30 per km`, `143 bpm`.

### Numbers carry their own baggage

Given "decoupling 10.9 percent" a model reaches for fatigue **even when the value is negative** and the brief says the opposite. So a good result is described in words alone and only a genuine drift is quantified:

| Decoupling | What the brief says |
| :-- | :-- |
| ≤ 0% | "Pace and heart rate held together well; the athlete was no less efficient by the end" |
| under 5% | "…drifting apart by 4.1 percent, which is normal" |
| 5% or more | "Heart rate drifted upward relative to pace by 7.2 percent, which is more than usual" |

The same applies to changes between periods. A leading minus is read as a small number, and pace "improving" by falling is read backwards — so directions are words: *"down by 40 m, which is 11 percent less"*, *"quicker than the period before"*. Sports are nouns too, because `1 walking` came back as "one walking".

---

## The instructions

Two prompts, in `backend/app/services/coach.py`.

**Per activity and per week** — `SYSTEM_PROMPT`:

1. Never state a number that does not appear in the brief. Do not convert, round or recalculate anything.
2. Do not restate the whole brief. Pick the two or three things that actually matter.
3. Never give medical advice, and never suggest the athlete may be ill or injured.
4. Do not prescribe specific training.
5. At most three sentences, plain prose, no headings or lists.

**Per finished period** — `REVIEW_SYSTEM_PROMPT`: the same constraints, but it is told to say what changed against the previous period and given four to six sentences.

Request parameters: `temperature 0.3`, `stream false`, `think false`, `num_predict` 200 or 400, timeout 120 s.

---

## Caching

A note is stored against a **fingerprint of the brief plus the model plus the prompt**. It is only regenerated when one of those actually changes.

So a finished week is narrated once, not on every visit; editing an activity produces a new note because the figures changed; and rewording a prompt regenerates rather than serving text written under the old instructions.

**Rewrite** on any note forces a new one. Notes live in the `insights` table and are deleted with the account.

---

## When it fails

Softly, always. An unreachable or slow model leaves the dashboard exactly as it was.

- If a note cannot be written and one was written before, the previous one is shown.
- If there is none, the section does not appear at all.
- A PDF is generated without the note rather than not generated.
- No training data depends on it in any way.

**Nothing to say is a valid outcome.** With no training in a period, the coach reports that there is nothing to comment on rather than inventing encouragement.

---

## Troubleshooting

**No coach section anywhere**
`OLLAMA_URL` is empty, or `/coach/status` reports `reachable: false`.

**`Could not reach the model at …`**
Ollama is bound to `127.0.0.1`. Set `OLLAMA_HOST=0.0.0.0:11434` and restart it.

**`The model returned nothing`**
The model name is wrong or not pulled. `available_models` in `/coach/status` lists what the server can actually see.

**Notes are slow the first time and instant afterwards**
Working as intended — that is the cache.

**The note mentions a number that is not on the page**
A genuine bug worth reporting: the brief is the only source it has. Check what was sent with `build_activity_brief` for that activity.

**The note is stale after changing a threshold**
Recalculating rebuilds the fitness curve but does not recompute stored per-activity load, so the brief's figures may not have changed. Press **Rewrite**.

---

## Why local

The obvious alternative is an API key and someone else's model. This does not do that, for the same reason the rest of the application does not:

- Your training data is a detailed record of where you go, when, and how your body responds. It stays on your hardware.
- No key to rotate, no bill, no rate limit, no terms that change.
- It works with no internet connection.
- The model is yours to swap. Nothing in the app assumes a particular one.

The cost is that a 7B model is not a good coach. It is a competent writer of three sentences about numbers it has been handed — which, given it is not allowed to calculate anything, is all it is being asked to be.
