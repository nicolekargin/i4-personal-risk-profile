# Stasis — Personalized Health Profile of Inspiration 4 Subject C003

**Live dashboard:** https://nicolekargin.github.io/i4-personal-risk-profile/

A multi-omics health profile of one SpaceX Inspiration 4 crew member (C003), measured against their own pre-flight baseline rather than population norms. Built for Track 2 (Individualized Risk Profile) of the Sovereignty Hackathon at the University of Austin, May 2026.

**Tagline:** Personal baselines. Real data.

---

## The thesis in one paragraph

Standard medicine asks: "Is this patient's lab value within the population reference range?" That question can answer "yes" while missing the fact that an individual has shifted dramatically from their own healthy baseline. Subject C003's white blood cell count one day after returning from spaceflight was 7.0 K/μL — comfortably within the clinical reference range of 3.8–10.8 K/μL, the kind of result a standard clinic visit would call normal — but 10 standard deviations below C003's own pre-flight baseline of 9.57 K/μL. Across 71 cytokine measurements, 48% never returned to personal baseline within 194 days post-flight. Population-based reference ranges are not designed to detect these signals. Personal-baseline analysis is.

---

## The headline findings

| Finding | Value | What it means |
|---|---|---|
| **IL-6 elevation at R+1** | 2.9× above C003's baseline | Confirms textbook acute-phase inflammatory response; concordant across all 4 crew |
| **WBC depression at R+1** | 10.2 SD below personal baseline, in clinical range | The thesis: clinically normal, personally extreme |
| **Incomplete recovery** | 48% of cytokines unresolved at R+194 | Nearly half of immune perturbations remain 6 months post-flight |
| **Type-2 immune activation** | IL-4 5.15× elevated, persistent through R+194 | Pattern consistent with type-2 activation; formal Th2 hypothesis partially supported (2 of 6 pre-registered predictions strictly passed) |
| **Cohort heterogeneity** | IFN-γ elevated in C001, suppressed in C002/C003/C004 | Within a 4-person cohort, individual responses diverge by 10-fold; the central argument for personal-baseline analysis |

Every number on the dashboard traces to a CSV row in `data/processed/`.

---

## Datasets

Three NASA OSDR datasets:

- **OSD-569** — Complete Blood Count (CBC), 23 clinical analytes, 7 timepoints
- **OSD-575** — Eve cytokine panel, 71 immune analytes, 7 timepoints
- **OSD-572** — Oral/nasal microbiome metagenomics with KEGG functional annotations, 8 timepoints including in-flight

Source publication: Overbey EG, Kim JK, Tierney BT et al. *The Space Omics and Medical Atlas (SOMA) and international astronaut biobank.* Nature 632, 1145–1154 (2024). doi:10.1038/s41586-024-07639-y

---

## Why C003

C003 was selected before any signal preview, on the basis of data completeness across all three assays. The four crew members had equivalent coverage; choice was arbitrary among complete cases and documented in `PIPELINE.md` to pre-empt cherry-picking concerns.

---

## Methodology highlights

The full pipeline is documented in [`PIPELINE.md`](./PIPELINE.md). Key methodological commitments:

- **Personal baselines** computed from L-92, L-44, and L-3 timepoints only (n=3 pre-flight)
- **Bootstrap 95% CIs** (1000 resamples) propagated to z-scores for every finding
- **Two-method robustness gate**: every dashboard finding survives BOTH mean+SD and median+MAD methods. Findings that pass only one are excluded.
- **Direction-of-effect concordance** for cohort comparisons (n=4 too small for inferential statistics; we report directional agreement, not p-values)
- **log1p transform** before z-scoring for cytokines and microbial CPM; CBC stays raw scale
- **Recovery classification**: fast (<45 days) / slow (45–194 days) / incomplete (no return to baseline within window)
- **Pre-registered hypothesis test** for Th2 polarization with 6 specified predictions; results reported honestly (2 strictly passed, 3 mixed, 1 not supported → "partially supported")

For the n=3 pre-flight baseline, the formal z-threshold for α=0.05 is approximately 4.3, not 2; the pipeline applies this corrected threshold to all gating decisions. Bootstrap CIs further quantify uncertainty: for IL-6 at R+1, the lower CI bound is +29.88 SD, demonstrating the finding is not a tight-baseline artifact.

---

## Repository structure
i4-personal-risk-profile/
├── analysis/                    # 12-stage Python pipeline
│   ├── load.py                  # OSDR data loading
│   ├── parse.py                 # Schema normalization
│   ├── transform.py             # log1p, z-scoring, scaling
│   ├── baseline.py              # Personal baseline computation
│   ├── deviation.py             # Per-timepoint deviation scoring
│   ├── kinetics.py              # Recovery trajectory classification
│   ├── concordance.py           # Cohort direction-of-effect analysis
│   ├── archetype.py             # Th1/Th2/Th17/regulatory/acute-phase scoring
│   ├── literature_context.py    # Expected-vs-observed direction comparison
│   ├── verify.py                # Two-method robustness gate
│   ├── th2_skew_test.py         # Pre-registered Th2 hypothesis test
│   └── dashboard_export.py      # Final dashboard data preparation
├── data/processed/              # All CSVs the dashboard reads
│   ├── personal_profile_C003.csv
│   ├── recovery_kinetics_C003.csv
│   ├── cohort_concordance.csv
│   ├── archetype_synthesis.csv
│   ├── headline_trajectories.csv
│   ├── th2_skew_verdict.json
│   └── dashboard_findings.csv
├── notebooks/                   # Validation and exploration
├── docs/                        # Live dashboard (GitHub Pages)
│   ├── index.html
│   ├── dashboard.js
│   ├── LITERATURE_CONTEXT.md
│   ├── AUDIT_REPORT.md
│   ├── AUDIT_REPORT_v2.md
│   └── AUDIT_REPORT_v3.md
├── PIPELINE.md                  # Full methodology documentation
└── README.md

---

## How we used AI

This project was built entirely with AI as the implementation partner. Both team members are non-engineers; the role of human judgment was strategic, methodological, and editorial. The role of AI was execution. Documenting this transparently because the project would not exist without it, and because we are competing for the Best Use of AI award.

### Tools used

- **Claude Sonnet 4.6 (web interface, Nicole's account)** — strategic planning, methodology decisions, prompt construction, audit interpretation, copy editing, content critique. Acted as the project's analytical brain throughout.
- **Claude Code (terminal, Lucy's machine)** — pipeline implementation, all Python analysis code, data processing, dashboard implementation in React + Tailwind + Recharts, GitHub Pages deployment, file system operations, and three rounds of self-audit against canonical CSV sources.
- **Claude Design (claude.ai/design)** — visual iteration on the dashboard. Started from a web capture of our live URL and refined typography, layout, color palette, and interactivity through three iterations.

### Division of labor

**Nicole** worked with Claude (web) to make every strategic call: which subject to deep-dive, what statistical thresholds to use, how to frame the type-2 immune findings, which findings deserved hero placement, what brand identity (Stasis) to lock in, and how to interpret the audit reports Lucy's Claude Code returned. Nicole also drove all three Claude Design iterations.

**Lucy** worked with Claude Code to execute every piece of code in this repo: the 12-stage analysis pipeline, the dashboard implementation in React/JS, the deployment configuration, and three rounds of read-only data audits against the live site. Lucy's role was the build engineer; Claude Code was her direct collaborator at every step.

Neither of us wrote production code by hand. Both of us made every methodological and editorial decision.

### Specific patterns we relied on

**Two-Claude-instance verification.** A pattern that emerged organically and turned out to be the project's secret weapon: one Claude instance (web) wrote prompts for another Claude instance (Code) to execute. The web Claude could review what Claude Code returned, catch errors, and write follow-up prompts. This created a check on AI output that a single Claude session would not have caught. Three full audit cycles ran this way; each surfaced material errors that would have been brutal at submission.

**Audit-driven correction cycles.** After the dashboard was built, we ran self-audits via Claude Code. The first audit caught fabricated WBC raw values (5.0 K/μL displayed when the CSV said 7.0), an incorrectly framed IFN-γ "cohort-wide" claim (one of four crew showed the opposite direction), and a wrong author citation on the Nature paper (the original draft cited "Bhatt et al."; the correct lead authors are Overbey EG and Kim JK). The second audit caught propagation gaps where Phase 2 fixes had updated some sections but not all instances. The third audit verified concordance counts on Hgb/Hct/RBC against `cohort_concordance.csv` and found that several "cohort-wide" framings were actually idiosyncratic to C003. Each cycle made the dashboard measurably more honest and more defensible. Audit reports are committed to `docs/AUDIT_REPORT.md`, `AUDIT_REPORT_v2.md`, and `AUDIT_REPORT_v3.md`.

**Methodology-first prompting.** Every prompt to Claude Code began with the methodological commitments: log1p before z-scoring, bootstrap CIs, two-method robustness gates, direction-of-effect concordance for cohort comparisons, n=3 baseline implications. By front-loading these, we reduced the chance of Claude Code making a statistical shortcut we would have to catch later.

**Pre-registration of hypotheses.** Before testing the Th2 polarization hypothesis, we had Claude write down 6 predictions in a JSON file. The test ran against those exact predictions; the verdict (2 strictly passed, partially supported) was reported unchanged from what the code returned. We did not redefine predictions after seeing results.

**Co-iteration on visual design.** Claude Design iterated on the dashboard through three passes: first establishing brand and mission-control aesthetic, second adding interactivity (chart hovers, click-to-reveal methodology panels), third refining the color palette away from neon-on-black toward muted scientific tones. Each iteration was a real-time visual conversation, not a generate-and-pray prompt.

### What we did not delegate to AI

- Selection of subject (C003)
- The decision to drop a basophil finding that failed our own robustness test
- The decision to reframe IFN-γ from "cohort-wide" to "3 of 4, one opposite" after the audit found the error
- The decision to report Th2 as "partially supported" rather than supported
- All copy on the dashboard was written or edited by Nicole; AI drafted, Nicole final-edited
- All audit findings were reviewed and decided on by Nicole; Lucy applied the approved changes

### What we learned about AI-augmented research

A small, methodologically careful team using current AI tools can produce work that previously required a team of bioinformaticians. The bottleneck stops being "can we implement this?" and becomes "can we be rigorous about what we're claiming?" The AI is happy to compute anything; the human's job becomes deciding what to compute, what to display, and how to frame uncertainty. This is a more interesting bottleneck than the implementation one. It is also the bottleneck that determines whether the work is honest.

We believe this workflow generalizes. A non-engineer working with Claude Code can build a research-grade pipeline. A non-designer working with Claude Design can ship a publication-quality dashboard. The combination, with two AI instances cross-checking each other, can produce work that is harder to produce with one engineer alone.

---

## Limitations

- **Single-subject deep dive.** This is an n=1 analysis of C003 with cohort context (n=4). Not generalizable as written; a demonstration of method, not a population claim.
- **Cytokine assay reconciliation.** OSD-575 (Eve panel) and other cytokine panels in the SOMA study use different platforms; we used Eve only, as documented in PIPELINE.md.
- **Type-2 immune classification.** The pattern in C003 is consistent with type-2 activation but the formal hypothesis was only partially supported due to insufficient cohort data after robustness filtering.
- **No causal claims.** All findings are descriptive deviations from personal baseline. Spaceflight is not isolated as the cause of any specific deviation; only the temporal correlation is documented.
- **Microbial z-score capping.** |z| values capped at 50 in the dashboard for interpretability; raw values preserved in `data/processed/personal_profile_C003.csv`.

---

## Team

**Nicole Kargin** — strategy, methodology, audit interpretation, dashboard design direction, copy
**Lucy Taylor** — pipeline implementation, dashboard implementation, deployment, audit execution

Built for the Sovereignty Hackathon, University of Austin, May 6–9, 2026.

---

## Citation

If you reference this work:
Kargin, N. & Taylor, L. (2026). Stasis: Personalized Health Profile of
Inspiration 4 Subject C003. Sovereignty Hackathon, University of Austin.
https://github.com/nicolekargin/i4-personal-risk-profile

---

## License

Code: MIT
Data: NASA OSDR open access (see source datasets)
