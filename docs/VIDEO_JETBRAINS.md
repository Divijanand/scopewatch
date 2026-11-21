# Video: the JetBrains segment (about 40–50 s)

Talking points and shots for the part of the demo video about how we built Scopewatch. Every claim here is in `AI_SHOWCASE.md`; say nothing it doesn't show.

| Time | Show on screen | Say |
|---|---|---|
| 0–8 s | PyCharm with the run configuration dropdown open (ingest, store, train, evaluate…) | "Scopewatch is built in PyCharm. Every step, from raw GRID feeds to the trained models, is a shared run configuration, so a teammate runs the whole pipeline from here." |
| 8–20 s | A brief in `docs/briefs/`, then the Junie panel working on it | "Junie built four of our features and model experiments. We gave it briefs like tickets: the files, the rules, what done means, and the checks to run." |
| 20–35 s | The AI_SHOWCASE review table, one row highlighted (label leakage or the unregistered metric) | "Then we reviewed its work like a pull request: ran it, reproduced its numbers, and sent findings back. Review caught label leakage and a metric that wasn't wired in, and once a mistake in our own brief." |
| 35–45 s | The evaluation table for a model experiment (e.g. step 4b: "no variant helps beyond noise") | "And we report what didn't work: if a feature doesn't beat the current model beyond noise, it doesn't ship." |
| 45–50 s | AI_SHOWCASE.md scrolling | "Every task, model and review round is logged in the repo." |

**Don't show:** real player data rows, the demo password, licence codes, or the Junie panel with any settings that reveal account details.
