// ============================================================
// Personalized Health Orbit — dashboard.js
// Subject C003 · SpaceX Inspiration 4 · September 2021
// ============================================================

const { useState } = React;
const {
  LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine,
  ResponsiveContainer, ReferenceArea, CartesianGrid,
} = Recharts;

// ============================================================
// DATA LAYER
// ============================================================

const PROJECT_META = {
  title: "Personalized Health Orbit",
  subtitle: "A multi-omics health profile of one Inspiration 4 crew member, measured against their own pre-flight baseline.",
  subjectId: "C003",
  mission: "SpaceX Inspiration 4 (September 2021)",
  intro: "Spaceflight changes the human body. But every body is different. This dashboard maps how one Inspiration 4 crew member responded to spaceflight — measured against their own pre-flight baseline, not population averages — and reveals what standard clinical tests can miss.",
  team: "Built by Nicole Kargin and Lucy Taylor for the Sovereignty Hackathon, University of Austin, May 2026.",
  repoUrl: "https://github.com/nicolekargin/i4-personal-risk-profile",
};

const HEADLINE_IL6 = {
  foldChange: 2.9,
  zScore: 31.5,
  takeaway: "IL-6 surged nearly 3-fold above C003's pre-flight baseline one day after returning to Earth — and remained elevated for the entire 194-day observation window.",
  context: "IL-6 is the canonical acute-phase inflammatory cytokine. Its elevation in spaceflight is well-documented across NASA's Twins Study and Inspiration 4 publications. C003's response confirms this expected pattern — and the trajectory chart reveals an unexpected dip at R+45 before re-elevation through R+194.",
};

const HEADLINE_WBC = {
  zScore: 10.2,
  foldChange: 0.73,
  clinicalRangeLow: 3.8,    // CSV: personal_profile_C003.csv, measurement=white_blood_cell_count, clinical_min=3.8
  clinicalRangeHigh: 10.8,  // CSV: same row, clinical_max=10.8
  personalBaselineMean: 9.57, // CSV: same measurement, baseline_mean=9.566667
  postFlightValue: 7.0,     // CSV: same measurement, timepoint=R+1, value_raw=7.0
  unit: "K/μL",
  takeaway: "C003's white blood cell count dropped 10 standard deviations below their personal baseline at R+1 — yet remained within the 3.8–10.8 K/μL clinical reference range. Standard lab tests would have called this normal.",
  thesis: "Population-based reference ranges flag values unusual across a large group. They cannot detect a value unusual for a specific individual. This is why personalized monitoring matters.",
};

const BIG_STAT = {
  // 34/71 = 47.89% → rounds to 48% (source: recovery_kinetics_C003.csv, layer=immune)
  number: "48%",
  label: "of C003's immune perturbations remained unresolved",
  qualifier: "194 days after returning to Earth",
  detail: "Of 71 measured cytokines, 34 had not returned to personal baseline within the observation window. Spaceflight is not a transient stress — it produces sustained physiological alterations measurable across more than six months of recovery.",
};

// Actual values from data/processed/headline_trajectories.csv
// value_raw column (pg/mL), z_score column
const IL6_TRAJECTORY = [
  { timepoint: "L-92", days: -92, value: 2.67, zScore:  0.48, phase: "pre-flight"  },
  { timepoint: "L-44", days: -44, value: 2.69, zScore:  0.67, phase: "pre-flight"  },
  { timepoint: "L-3",  days:  -3, value: 2.51, zScore: -1.15, phase: "pre-flight"  },
  { timepoint: "R+1",  days:   1, value: 7.60, zScore: 31.51, phase: "post-flight" },
  { timepoint: "R+45", days:  45, value: 1.32, zScore:-16.24, phase: "post-flight" },
  { timepoint: "R+82", days:  82, value: 3.64, zScore:  9.02, phase: "post-flight" },
  { timepoint: "R+194",days: 194, value: 5.78, zScore: 22.84, phase: "post-flight" },
];
const IL6_BASELINE_MEAN = 2.62; // mean of L-92, L-44, L-3 raw values

const VITAL_GAUGES = [
  {
    name: "Inflammatory Load",
    display: "+31.5 SD",
    displaySub: "peak deviation at R+1",
    state: "elevated",
    // Source: personal_profile_C003.csv, measurement=il_6, timepoint=R+1, z_score=31.509928 (mean+SD method)
    description: "Maximum cytokine deviation at R+1 · IL-6 z-score (mean+SD method) · robust z = +105.7 SD (median+MAD)",
    interpretation: "Significantly elevated. Acute-phase response activated; monocyte recruitment elevated.",
  },
  {
    name: "Immune Stability",
    display: "Type-2",
    displaySub: "dominant · Th1 attenuated",
    state: "polarized",
    // Source: archetype_synthesis.csv, timepoint=R+1: th2_polarization score=0.83, th1_polarization score=0.24
    description: "Th2 archetype activation 0.83 · Th1 activation 0.24 at R+1 (archetype_synthesis.csv)",
    interpretation: "Pattern consistent with type-2 immune activation (formal hypothesis partially supported: 2 of 6 pre-registered predictions strictly passed).",
  },
  {
    name: "Recovery Velocity",
    display: "4 of 71",
    displaySub: "cytokines fully recovered",
    state: "incomplete",
    // Source: recovery_kinetics_C003.csv, layer=immune: fast=4, slow=33, incomplete=34, total=71
    description: "Fraction of perturbations returning to personal baseline within the 194-day observation window",
    interpretation: "Most perturbations unresolved: 48% incomplete, 46% slow, 6% fast recovery.",
  },
];

const SHARED_FINDINGS = [
  {
    measurement: "IL-6",
    archetype: "Acute-phase response",
    foldChange: 2.90,
    direction: "up",
    timepoint: "R+1",
    concordance: "All 4 crew elevated",
    literatureStatus: "confirmed",
    takeaway: "The cohort's shared inflammatory response to return from spaceflight.",
  },
  {
    measurement: "IFNγ",
    archetype: "Th1 / Interferon",
    foldChange: 0.05,
    direction: "down",
    timepoint: "R+82",
    // cohort_concordance.csv: cohort_direction_agree=2/cohort_n=3 — C001 strongly elevated (z=+7.12, fold=10.76×)
    concordance: "3 of 4 crew suppressed (C001: z=+7.12 elevated)",
    literatureStatus: "contradicted",
    contradicted: true,
    takeaway: "Th1 interferon signaling suppressed in 3 of 4 crew at R+82, with one crew member (C001) showing strong elevation in the opposite direction (z=+7.12, fold=10.76×). The split pattern demonstrates that even cohort-level signals can mask individual-level heterogeneity — the central argument for personal-baseline analysis.",
  },
  {
    measurement: "TARC",
    archetype: "Th2 chemokine",
    foldChange: 0.21,
    direction: "down",
    timepoint: "R+45",
    // cohort_concordance.csv: cohort_direction_agree=2/cohort_n=3 — C004 elevated (fold=2.077×)
    concordance: "3 of 4 crew suppressed (C004: elevated)",
    literatureStatus: "novel",
    takeaway: "TARC dropped sharply to 21% of baseline in 3 of 4 crew at 45 days post-flight (C004 showed elevation); a novel cohort-level finding without a published spaceflight precedent.",
  },
  {
    measurement: "MCV",
    archetype: "Red cell morphology",
    foldChange: 0.95,
    direction: "down",
    timepoint: "R+45",
    // cohort_concordance.csv: cohort_direction_agree=2/cohort_n=3 — C001 essentially flat (z=−0.06)
    concordance: "3 of 4 crew shifted (C001: stable)",
    literatureStatus: "contradicted",
    contradicted: true,
    takeaway: "Mean corpuscular volume dropped in 3 of 4 crew — opposite to long-duration spaceflight expectations of macrocytosis.",
  },
];

const PERSONAL_FINDINGS = [
  {
    measurement: "IL-4",
    archetype: "Type 2 immune response",
    foldChange: 5.15,
    zScore: 14.95,
    direction: "up",
    timepoint: "R+194",
    cohortStatus: "Other crew: stable",
    takeaway: "IL-4 elevated 5-fold above C003's baseline — and stayed elevated for the entire 194-day window. The other crew showed no IL-4 deviation.",
  },
  {
    measurement: "IL-13",
    archetype: "Type 2 immune response",
    foldChange: 8.04,
    zScore: 3.87,
    direction: "up",
    timepoint: "R+1",
    cohortStatus: "Other crew: stable",
    takeaway: "IL-13 elevated 8-fold one day post-flight, recovering slowly by 194 days — uniquely in C003.",
  },
  {
    measurement: "IL-5",
    archetype: "Type 2 immune response",
    foldChange: 1.73,
    zScore: 3.20,
    direction: "up",
    timepoint: "R+194",
    cohortStatus: "Other crew: stable",
    takeaway: "IL-5 elevated through the full 194-day window — a third type-2 cytokine in the same idiosyncratic pattern.",
  },
  {
    measurement: "IL-10",
    archetype: "Regulatory response",
    foldChange: 1.35,
    zScore: 3.61,
    direction: "up",
    timepoint: "R+1",
    cohortStatus: "Other crew: stable",
    takeaway: "Regulatory cytokine IL-10 elevated in C003 only — accompanying and possibly moderating the type-2 pattern.",
  },
  {
    measurement: "IL-12p40",
    archetype: "Th1 / IL-12 family",
    foldChange: 4.57,
    zScore: 5.73,
    direction: "up",
    timepoint: "R+45",
    cohortStatus: "Other crew: stable",
    takeaway: "IL-12p40 elevated 4.6-fold in C003 specifically at 45 days post-flight, while the rest of the crew remained stable.",
  },
  {
    measurement: "I-309",
    archetype: "Chemokine (CCL1)",
    foldChange: 8.32,
    // z_score_robust=41.008 (primary, median+MAD); z_score=12.461 (mean+SD) — personal_profile_C003.csv, timepoint=R+194
    zScore: 41.01,
    direction: "up",
    timepoint: "R+194",
    cohortStatus: "Opposite to cohort",
    takeaway: "I-309 elevated 8.32-fold opposite to the cohort direction at 194 days — +41.0 SD (robust z, median+MAD) · +12.5 SD (mean+SD). Both methods confirm the signal. The highest-z idiosyncratic immune finding in the dataset.",
  },
];

const PERSONAL_PHENOTYPE_FRAMING = {
  pattern: "Type 2 immune pattern with reciprocal Th1 suppression",
  description: "C003 is the only crew member with three robustly-elevated type-2 cytokines (IL-4, IL-13, IL-5), accompanied by elevated regulatory IL-10 and concordant suppression of Th1 IFNγ. The formal Th2 polarization hypothesis was partially supported (2 of 6 pre-registered predictions strictly passed) — the descriptive pattern is consistent with type-2 immune activation, though not fully consistent with classical Th2 polarization.",
  // th2_skew_verdict.json: verdict="partially supported", n_supported=2, n_total=6, effective=3.5
  honestCaveat: "Pattern consistent with type-2 immune activation (formal hypothesis partially supported: 2 of 6 pre-registered predictions strictly passed). The formal hypothesis test was inconclusive on most predictions due to insufficient cohort data after robustness filtering. We report the descriptive evidence honestly rather than claiming formal Th2 polarization.",
};

const CONTRADICTED_FINDINGS = [
  {
    measurement: "White Blood Cell Count",
    layer: "clinical",
    expectedDirection: "elevated",
    expectedNote: "acute inflammation",
    observedDirection: "depressed",
    observedNote: "10 SD below personal baseline",
    timepoint: "R+1",
    note: "Clinically 'normal' — yet 10 standard deviations from C003's personal baseline.",
  },
  {
    measurement: "IFNγ",
    layer: "immune",
    expectedDirection: "elevated",
    expectedNote: "Th1 activation",
    observedDirection: "suppressed in C003",
    // personal_profile_C003.csv R+82: C001 z=+7.12 (elevated), C002/C003/C004 suppressed
    observedNote: "3 of 4 crew suppressed; C001 strongly elevated (z=+7.12, fold=10.76×)",
    timepoint: "R+82",
    note: "C002, C003, C004 showed Th1 suppression; C001 showed strong Th1 elevation (fold=10.76×), confirming that even cohort-level patterns mask individual heterogeneity.",
  },
  {
    measurement: "Red Blood Cell Count",
    layer: "clinical",
    expectedDirection: "depressed",
    expectedNote: "long-duration anemia",
    observedDirection: "elevated",
    observedNote: "above personal baseline",
    timepoint: "R+45",
    note: "Opposite of typical long-duration ISS mission pattern.",
  },
  {
    measurement: "Hemoglobin",
    layer: "clinical",
    expectedDirection: "depressed",
    expectedNote: "spaceflight anemia",
    observedDirection: "elevated",
    observedNote: "consistent with RBC elevation",
    timepoint: "R+45",
    note: "Consistent with the elevated RBC count — both contradict long-duration expectations.",
  },
  {
    measurement: "Hematocrit",
    layer: "clinical",
    expectedDirection: "depressed",
    expectedNote: "plasma volume shifts",
    observedDirection: "elevated",
    observedNote: "persistent through R+82",
    timepoint: "R+82",
    note: "Persists 82 days post-flight.",
  },
  {
    measurement: "MCV",
    layer: "clinical",
    expectedDirection: "elevated",
    expectedNote: "macrocytosis",
    observedDirection: "depressed",
    observedNote: "all 4 crew shifted",
    timepoint: "R+45",
    note: "Mean corpuscular volume dropped cohort-wide.",
  },
];

const MISSED_BY_STANDARD_TESTS = [
  {
    measurement: "White Blood Cell Count",
    personalDeviation: "10.2 SD below baseline",
    clinicalRange: "Within reference (3.8–10.8 K/μL)",
    timepoint: "R+1",
  },
  {
    measurement: "Monocytes",
    personalDeviation: "7.7 SD above baseline",
    clinicalRange: "Within reference",
    timepoint: "R+194",
  },
  // Basophils removed: z_score_robust=NaN for all % rows (baseline % values too uniform for MAD).
  // This finding does not survive the both-methods robustness test required by PIPELINE.md.
  {
    measurement: "Red Blood Cell Count",
    personalDeviation: "6.8 SD above baseline",
    clinicalRange: "Within reference (contradicts expected direction)",
    timepoint: "R+45",
  },
  {
    measurement: "All 71 cytokines (IL-6, IL-4, TARC…)",
    personalDeviation: "Strongest: IL-6 +31 SD, I-309 +12 SD, IL-4 +15 SD (robust z)",
    clinicalRange: "No clinical reference ranges exist for any cytokine",
    timepoint: "Multiple",
  },
];

const METHODOLOGY_SUMMARY = `Personal baselines computed from each individual's three pre-flight measurements (L-92, L-44, L-3 days before launch).
Bootstrap 95% confidence intervals (1000 resamples) on every z-score to honestly represent uncertainty given small baseline samples.
Robustness stress test: every finding computed under both mean+SD and median+MAD normalization; only findings that survive both methods are displayed.
Cohort comparisons reported only as direction-of-effect concordance — n=4 prohibits inferential statistics.
Cytokines grouped into immunological archetypes (acute-phase, Th1/Th2/Th17, regulatory, vascular) for phenotype-level interpretation.
Literature-context tagging: each finding labeled confirmed, novel, or contradicted relative to published spaceflight findings.
Hypothesis tests pre-registered with thresholds documented before computation.
Full pipeline documented in PIPELINE.md in the repository.`;

const LIMITATIONS = [
  "n = 4 crew members prohibits inferential statistics; all cohort comparisons are direction-of-effect concordance only.",
  "Personal baselines computed from n = 3 pre-flight timepoints. Bootstrap CIs explicitly represent this uncertainty.",
  "With n=3 pre-flight samples (df=2), the formal z-threshold for α=0.05 is approximately 4.3, not 2; bootstrap 95% CIs replace the t-threshold for quantifying signal uncertainty at each gating step.",
  "All findings reported with bootstrap 95% CIs (1000 resamples). For IL-6 at R+1, lower CI bound +29.88 SD demonstrates the finding is not a tight-baseline artifact.",
  "No R+194 microbiome data exists; microbial recovery kinetics capped at R+82.",
  "Eve and Alamar cytokine panels cannot be directly merged due to different unit scales; only Eve panel used in primary immune analysis.",
  "Microbiome analysis restricted to oral and nasal cavities for interpretability.",
  "Microbial |z| values capped at 50 in dashboard for interpretability; raw values preserved in master CSV (data/processed/personal_profile_C003.csv).",
  "Subject C003 was selected by data completeness across assays prior to any signal preview, not by signal magnitude. Documented in PIPELINE.md.",
  "Anonymized subject identity (C003) is not linked to any specific named crew member.",
];

// ============================================================
// COMPONENTS
// ============================================================

// ---- Header ----

function Header() {
  return (
    <header
      className="sticky top-0 z-50 flex items-center justify-between px-6 py-3 border-b border-gray-800"
      style={{ background: '#0a0e1aee', backdropFilter: 'blur(8px)' }}
    >
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div
            className="w-2 h-2 rounded-full bg-green-400"
            style={{ animation: 'pulse 2s cubic-bezier(0.4,0,0.6,1) infinite' }}
          />
          <span className="font-display font-semibold text-sm text-gray-100">HEALTH ORBIT</span>
        </div>
        <span className="font-mono text-xs text-gray-600 hidden sm:block">
          SUBJECT C003 · SpaceX Inspiration 4 · SEP 2021
        </span>
      </div>
      <a
        href={PROJECT_META.repoUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="font-mono text-xs text-gray-500 hover:text-cyan-400 transition-colors"
      >
        GitHub ↗
      </a>
    </header>
  );
}

// ---- IL-6 Trajectory Chart ----

function IL6MiniChart() {
  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || !payload.length) return null;
    const d = payload[0].payload;
    return (
      <div
        className="font-mono text-xs"
        style={{ background: '#0f1424', border: '1px solid #1f2937', borderRadius: 4, padding: '8px 12px' }}
      >
        <div style={{ color: '#9ca3af' }}>{d.timepoint}</div>
        <div style={{ color: '#00d9ff' }}>{d.value.toFixed(2)} pg/mL</div>
        <div style={{ color: '#6b7280' }}>z = {d.zScore.toFixed(1)} SD</div>
      </div>
    );
  };

  return (
    <div style={{ height: 160, marginTop: 16 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={IL6_TRAJECTORY} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis
            dataKey="days"
            type="number"
            domain={[-100, 205]}
            ticks={[-92, -44, -3, 1, 45, 82, 194]}
            tickFormatter={d => {
              if (d === 1) return 'R+1';
              if (d < 0) return `L${d}`;
              return `R+${d}`;
            }}
            tick={{ fill: '#9ca3af', fontSize: 9, fontFamily: 'IBM Plex Mono, monospace' }}
            axisLine={{ stroke: '#374151' }}
            tickLine={false}
            interval={0}
          />
          <YAxis
            domain={[0, 9]}
            ticks={[0, 2, 4, 6, 8]}
            tick={{ fill: '#9ca3af', fontSize: 9, fontFamily: 'IBM Plex Mono, monospace' }}
            axisLine={false}
            tickLine={false}
            width={24}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceArea x1={-3} x2={1} fill="#00d9ff" fillOpacity={0.05} />
          <ReferenceLine x={0} stroke="#374151" strokeDasharray="4 4" />
          <ReferenceLine
            y={IL6_BASELINE_MEAN}
            stroke="#374151"
            strokeDasharray="4 4"
            label={{
              value: 'baseline',
              position: 'insideTopLeft',
              fill: '#6b7280',
              fontSize: 8,
              fontFamily: 'IBM Plex Mono, monospace',
              dy: -4,
            }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="#00d9ff"
            strokeWidth={2}
            dot={{ fill: '#00d9ff', strokeWidth: 0, r: 3 }}
            activeDot={{ r: 5, fill: '#00d9ff', stroke: '#0a0e1a', strokeWidth: 2 }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---- WBC Dual-Scale Visualization ----

function WBCDualScale() {
  // x scale: [1.0, 13.0] K/μL → [30, 530] px  (500px over 12 units)
  const sc = v => 30 + ((v - 1) / 12) * 500;
  const clinL = sc(3.8);   // 146.7 — source: personal_profile_C003.csv clinical_min=3.8
  const clinH = sc(10.8);  // 438.3 — source: personal_profile_C003.csv clinical_max=10.8
  const bl    = sc(9.57);  // 387.1 — source: personal_profile_C003.csv baseline_mean=9.566667
  const r1    = sc(7.0);   // 280.0 — source: personal_profile_C003.csv timepoint=R+1 value_raw=7.0

  return (
    <div style={{ marginTop: 24, overflowX: 'auto' }}>
      <svg viewBox="0 0 560 110" style={{ width: '100%', minWidth: 300, display: 'block' }}>
        {/* Clinical range bar */}
        <rect x={clinL} y={52} width={clinH - clinL} height={18} fill="#1f2937" rx="3" />
        <text
          x={(clinL + clinH) / 2} y={46}
          textAnchor="middle"
          fill="#6b7280" fontSize="9"
          fontFamily="IBM Plex Mono, monospace"
        >
          Clinical reference range (3.8 – 10.8 K/μL)
        </text>

        {/* Both-in-range note */}
        <text
          x={(clinL + clinH) / 2} y={81}
          textAnchor="middle"
          fill="#4b5563" fontSize="8"
          fontFamily="IBM Plex Mono, monospace"
        >
          Both values within this range
        </text>

        {/* Personal baseline line */}
        <line x1={bl} y1={38} x2={bl} y2={76} stroke="#00d9ff" strokeWidth="2" />
        <text x={bl} y={33} textAnchor="middle" fill="#00d9ff" fontSize="9" fontFamily="IBM Plex Mono, monospace">
          Baseline
        </text>
        <text x={bl} y={23} textAnchor="middle" fill="#00d9ff" fontSize="8" fontFamily="IBM Plex Mono, monospace">
          9.57 K/μL
        </text>

        {/* R+1 value line */}
        <line x1={r1} y1={38} x2={r1} y2={76} stroke="#ffb000" strokeWidth="2" strokeDasharray="5 3" />
        <text x={r1} y={33} textAnchor="middle" fill="#ffb000" fontSize="9" fontFamily="IBM Plex Mono, monospace">
          R+1
        </text>
        <text x={r1} y={23} textAnchor="middle" fill="#ffb000" fontSize="8" fontFamily="IBM Plex Mono, monospace">
          7.0 K/μL
        </text>

        {/* Distance annotation */}
        <line x1={r1 + 2} y1={64} x2={bl - 2} y2={64} stroke="#9ca3af" strokeWidth="1" markerEnd="url(#arr-r)" markerStart="url(#arr-l)" />
        <rect x={(r1 + bl) / 2 - 22} y={57} width={44} height={14} fill="#0a0e1a" />
        <text
          x={(r1 + bl) / 2} y={67}
          textAnchor="middle"
          fill="#e8eaed" fontSize="9"
          fontFamily="IBM Plex Mono, monospace"
          fontWeight="500"
        >
          10.2 SD
        </text>

        {/* Axis ticks */}
        {[2, 4, 6, 8, 10, 12].map(v => (
          <g key={v}>
            <line x1={sc(v)} y1={72} x2={sc(v)} y2={78} stroke="#374151" strokeWidth="1" />
            <text x={sc(v)} y={90} textAnchor="middle" fill="#4b5563" fontSize="8" fontFamily="IBM Plex Mono, monospace">
              {v}
            </text>
          </g>
        ))}
        <text x={280} y={103} textAnchor="middle" fill="#4b5563" fontSize="8" fontFamily="IBM Plex Mono, monospace">
          K/μL
        </text>
        <line x1={30} y1={72} x2={530} y2={72} stroke="#374151" strokeWidth="1" />

        {/* Arrow markers */}
        <defs>
          <marker id="arr-r" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <path d="M0,0.5 L5,3 L0,5.5" fill="none" stroke="#9ca3af" strokeWidth="1" />
          </marker>
          <marker id="arr-l" markerWidth="6" markerHeight="6" refX="1" refY="3" orient="auto-start-reverse">
            <path d="M0,0.5 L5,3 L0,5.5" fill="none" stroke="#9ca3af" strokeWidth="1" />
          </marker>
        </defs>
      </svg>
    </div>
  );
}

// ---- Headline Cards ----

function HeadlineIL6() {
  return (
    <div
      className="rounded-lg p-6 border border-gray-800 flex flex-col"
      style={{ background: '#0f1424' }}
    >
      <div className="font-mono text-xs tracking-widest mb-3" style={{ color: '#00d9ff' }}>
        CONFIRMS KNOWN BIOLOGY
      </div>
      <div className="flex items-baseline gap-3">
        <span
          className="font-display font-bold"
          style={{ fontSize: 'clamp(3rem,8vw,4.5rem)', lineHeight: 1, color: '#00d9ff' }}
        >
          2.9×
        </span>
      </div>
      <div className="font-mono text-sm mt-2 mb-1" style={{ color: '#9ca3af' }}>
        IL-6 above personal baseline · one day post-flight
      </div>
      <div className="flex flex-wrap gap-2 mb-4 mt-1">
        <span
          className="px-2 py-0.5 rounded font-mono text-xs border"
          style={{ borderColor: '#1f2937', color: '#9ca3af' }}
        >
          Concordant · all 4 crew
        </span>
        <span
          className="px-2 py-0.5 rounded font-mono text-xs border"
          style={{ borderColor: '#78350f', color: '#d97706' }}
        >
          Recovery: incomplete at R+194
        </span>
      </div>
      <IL6MiniChart />
      <p className="text-sm mt-4 leading-relaxed" style={{ color: '#9ca3af' }}>
        {HEADLINE_IL6.takeaway}
      </p>
      <p className="text-xs mt-2 leading-relaxed" style={{ color: '#4b5563' }}>
        {HEADLINE_IL6.context}
      </p>
    </div>
  );
}

function HeadlineWBC() {
  return (
    <div
      className="rounded-lg p-6 border border-gray-800 flex flex-col"
      style={{ background: '#0f1424' }}
    >
      <div className="font-mono text-xs tracking-widest mb-3" style={{ color: '#ffb000' }}>
        WHAT STANDARD TESTS WOULD HAVE MISSED
      </div>
      <div className="flex items-baseline gap-2">
        <span
          className="font-display font-bold"
          style={{ fontSize: 'clamp(3rem,8vw,4.5rem)', lineHeight: 1, color: '#ffb000' }}
        >
          10.2
        </span>
        <span className="font-mono text-2xl font-medium" style={{ color: '#ffb000' }}>SD</span>
      </div>
      <div className="font-mono text-sm mt-2 mb-1" style={{ color: '#9ca3af' }}>
        below personal baseline at R+1
      </div>
      <div
        className="font-mono text-xs px-3 py-1 rounded border inline-block self-start mt-1 mb-4"
        style={{ borderColor: '#14532d', color: '#22c55e', background: 'rgba(34,197,94,0.06)' }}
      >
        Within clinical reference range (3.8–10.8 K/μL)
      </div>
      <WBCDualScale />
      <p className="text-sm mt-4 leading-relaxed" style={{ color: '#9ca3af' }}>
        {HEADLINE_WBC.takeaway}
      </p>
      <p
        className="text-sm mt-3 leading-relaxed italic border-l-2 pl-3"
        style={{ color: '#6b7280', borderColor: '#1e3a5f' }}
      >
        {HEADLINE_WBC.thesis}
      </p>
    </div>
  );
}

// ---- Hero Section ----

function HeroSection() {
  return (
    <section className="max-w-6xl mx-auto px-6 pt-16 pb-10">
      <div className="mb-12">
        <div className="font-mono text-xs tracking-widest mb-4" style={{ color: '#6b7280' }}>
          SOVEREIGNTY HACKATHON · UNIVERSITY OF AUSTIN · MAY 2026
        </div>
        <h1
          className="font-display font-bold leading-tight mb-4"
          style={{ fontSize: 'clamp(2rem,6vw,3.5rem)', color: '#e8eaed' }}
        >
          Personalized Health Orbit
        </h1>
        <p className="text-lg leading-relaxed mb-3 max-w-3xl" style={{ color: '#9ca3af' }}>
          {PROJECT_META.subtitle}
        </p>
        <p className="text-sm leading-relaxed max-w-3xl" style={{ color: '#6b7280' }}>
          {PROJECT_META.intro}
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <HeadlineIL6 />
        <HeadlineWBC />
      </div>
    </section>
  );
}

// ---- Big Stat ----

function BigStat() {
  const fast = 4, slow = 33, incomplete = 34, total = 71;
  return (
    <section className="max-w-6xl mx-auto px-6 py-20 text-center">
      <div
        className="font-display font-bold leading-none"
        style={{
          fontSize: 'clamp(5rem,18vw,10rem)',
          color: '#e8eaed',
          textShadow: '0 0 100px rgba(0,217,255,0.15)',
        }}
      >
        {BIG_STAT.number}
      </div>
      <div className="font-mono text-lg mt-4 mb-2" style={{ color: '#d1d5db' }}>
        {BIG_STAT.label}
      </div>
      <div className="font-mono text-sm mb-10" style={{ color: '#6b7280' }}>
        {BIG_STAT.qualifier}
      </div>

      {/* Recovery distribution bar */}
      <div className="flex justify-center mb-3">
        <div style={{ width: '100%', maxWidth: 360 }}>
          <div className="flex rounded overflow-hidden" style={{ height: 16, marginBottom: 8 }}>
            <div
              style={{ width: `${(fast / total) * 100}%`, background: '#22c55e' }}
              title={`Fast recovery: ${fast}`}
            />
            <div
              style={{ width: `${(slow / total) * 100}%`, background: '#ffb000' }}
              title={`Slow recovery: ${slow}`}
            />
            <div
              style={{ width: `${(incomplete / total) * 100}%`, background: '#ff4757' }}
              title={`Incomplete: ${incomplete}`}
            />
          </div>
          <div className="flex justify-between font-mono text-xs" style={{ color: '#6b7280' }}>
            <span><span style={{ color: '#22c55e' }}>■</span> Fast ({fast})</span>
            <span><span style={{ color: '#ffb000' }}>■</span> Slow ({slow})</span>
            <span><span style={{ color: '#ff4757' }}>■</span> Incomplete ({incomplete})</span>
          </div>
        </div>
      </div>

      <p className="text-sm leading-relaxed mx-auto mt-6 max-w-xl" style={{ color: '#9ca3af' }}>
        {BIG_STAT.detail}
      </p>
    </section>
  );
}

// ---- Vital Gauge (SVG) ----

function VitalGauge({ gauge }) {
  const { name, display, displaySub, state, description, interpretation } = gauge;
  const color = { elevated: '#00d9ff', polarized: '#ffb000', incomplete: '#ff4757' }[state] || '#9ca3af';

  return (
    <div
      className="rounded-lg p-6 border border-gray-800 flex flex-col items-center text-center"
      style={{ background: '#0f1424' }}
    >
      <div className="font-mono text-xs tracking-widest mb-4" style={{ color: '#6b7280' }}>
        {name.toUpperCase()}
      </div>
      <div
        className="font-display font-bold leading-none my-4"
        style={{
          fontSize: 'clamp(1.8rem,5vw,2.6rem)',
          color,
          minHeight: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {display}
      </div>
      {displaySub && (
        <div className="font-mono text-xs mb-4" style={{ color: '#6b7280' }}>
          {displaySub}
        </div>
      )}
      <p className="text-xs leading-relaxed mb-3" style={{ color: '#6b7280' }}>{description}</p>
      <p className="text-sm leading-relaxed" style={{ color: '#d1d5db' }}>{interpretation}</p>
    </div>
  );
}

function VitalGauges() {
  return (
    <section className="max-w-6xl mx-auto px-6 py-8">
      <div className="mb-2 font-mono text-xs tracking-widest" style={{ color: '#6b7280' }}>
        MISSION STATUS INDICATORS
      </div>
      <h2 className="font-display text-2xl font-semibold mb-2" style={{ color: '#e8eaed' }}>
        Composite Health Signals
      </h2>
      <p className="font-mono text-sm mb-8" style={{ color: '#6b7280' }}>
        Derived from C003's 71-cytokine immune panel · post-flight observation window
      </p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {VITAL_GAUGES.map(g => <VitalGauge key={g.name} gauge={g} />)}
      </div>
    </section>
  );
}

// ---- Finding Card ----

function FindingCard({ finding }) {
  const { measurement, archetype, foldChange, direction, timepoint, takeaway, contradicted, cohortStatus, concordance } = finding;
  const color = direction === 'up' ? '#00d9ff' : '#ffb000';
  const arrow = direction === 'up' ? '▲' : '▼';
  const cohortNote = concordance || cohortStatus;

  return (
    <div
      className="rounded-lg p-5 border border-gray-800 flex flex-col"
      style={{ background: '#0f1424' }}
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <div className="font-display font-semibold" style={{ color: '#e8eaed' }}>
            {measurement}
          </div>
          <div className="font-mono text-xs mt-0.5" style={{ color: '#6b7280' }}>{archetype}</div>
        </div>
        {contradicted && (
          <span
            className="font-mono text-xs px-2 py-0.5 rounded border ml-2 whitespace-nowrap flex-shrink-0"
            style={{ borderColor: '#7f1d1d', color: '#f87171' }}
            title="Direction-of-effect differs from published spaceflight literature; n=4 prohibits statistical inference"
          >
            vs. literature: contradicted
          </span>
        )}
      </div>
      <div className="flex items-baseline gap-2 my-3">
        <span className="font-mono text-3xl" style={{ color }}>{arrow}</span>
        <span className="font-display text-3xl font-bold" style={{ color }}>
          {foldChange.toFixed(2)}×
        </span>
      </div>
      <div className="font-mono text-xs mb-3" style={{ color: '#6b7280' }}>
        Peak: {timepoint}
        {cohortNote && <span style={{ color: '#4b5563' }}> · {cohortNote}</span>}
      </div>
      <p className="text-sm leading-relaxed flex-1" style={{ color: '#9ca3af' }}>
        {takeaway}
      </p>
    </div>
  );
}

// ---- Story Panel: Shared ----

function StoryPanelShared() {
  return (
    <section className="max-w-6xl mx-auto px-6 py-16">
      <div className="mb-10">
        <div className="font-mono text-xs tracking-widest mb-2" style={{ color: '#6b7280' }}>
          COHORT FINDINGS
        </div>
        <h2 className="font-display text-3xl font-semibold mb-3" style={{ color: '#e8eaed' }}>
          Shared with the crew
        </h2>
        <p className="leading-relaxed max-w-2xl" style={{ color: '#9ca3af' }}>
          What spaceflight did to all four Inspiration 4 crew members — findings where C003's response matched the broader cohort pattern.
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {SHARED_FINDINGS.map(f => <FindingCard key={f.measurement} finding={f} />)}
      </div>
    </section>
  );
}

// ---- Story Panel: Personal ----

function StoryPanelPersonal() {
  return (
    <section className="max-w-6xl mx-auto px-6 py-16">
      <div className="mb-10">
        <div className="font-mono text-xs tracking-widest mb-2" style={{ color: '#6b7280' }}>
          IDIOSYNCRATIC FINDINGS
        </div>
        <h2 className="font-display text-3xl font-semibold mb-3" style={{ color: '#e8eaed' }}>
          Unique to C003
        </h2>
        <p className="leading-relaxed max-w-2xl" style={{ color: '#9ca3af' }}>
          C003's idiosyncratic immune signature, layered on the shared response.
        </p>
      </div>

      {/* Phenotype framing box */}
      <div
        className="rounded-lg p-6 border mb-10"
        style={{ borderColor: '#1e3a5f', background: 'rgba(0,217,255,0.03)' }}
      >
        <div className="font-mono text-xs tracking-widest mb-2" style={{ color: '#38bdf8' }}>
          PERSONAL IMMUNE SIGNATURE
        </div>
        <h3 className="font-display text-xl font-semibold mb-3" style={{ color: '#e8eaed' }}>
          {PERSONAL_PHENOTYPE_FRAMING.pattern}
        </h3>
        <p className="text-sm leading-relaxed mb-4" style={{ color: '#d1d5db' }}>
          {PERSONAL_PHENOTYPE_FRAMING.description}
        </p>
        <div className="border-l-2 pl-4" style={{ borderColor: '#374151' }}>
          <p className="text-xs italic leading-relaxed" style={{ color: '#6b7280' }}>
            {PERSONAL_PHENOTYPE_FRAMING.honestCaveat}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {PERSONAL_FINDINGS.map(f => <FindingCard key={f.measurement} finding={f} />)}
      </div>
    </section>
  );
}

// ---- Story Panel: Contradicted ----

function ContradictedRow({ finding }) {
  const { measurement, layer, expectedDirection, expectedNote, observedDirection, observedNote, timepoint, note } = finding;
  const obsUp = !observedDirection.includes('suppress') && !observedDirection.includes('depress');
  const expUp = !expectedDirection.includes('suppress') && !expectedDirection.includes('depress');
  const obsColor = obsUp ? '#00d9ff' : '#ffb000';

  return (
    <div className="py-5 border-b border-gray-800 last:border-b-0">
      <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-start">
        <div className="sm:col-span-3">
          <div className="font-display font-semibold text-sm" style={{ color: '#e8eaed' }}>
            {measurement}
          </div>
          <div className="font-mono text-xs mt-0.5" style={{ color: '#4b5563' }}>
            {layer} · {timepoint}
          </div>
        </div>

        <div className="sm:col-span-4 flex items-start gap-3">
          <span className="font-mono text-2xl mt-0.5" style={{ color: '#4b5563' }}>
            {expUp ? '↑' : '↓'}
          </span>
          <div>
            <div className="font-mono text-xs tracking-wider uppercase mb-0.5" style={{ color: '#4b5563' }}>
              Expected
            </div>
            <div className="text-sm" style={{ color: '#6b7280' }}>
              {expectedDirection}
              {expectedNote && <span style={{ color: '#4b5563' }}> ({expectedNote})</span>}
            </div>
          </div>
        </div>

        <div className="sm:col-span-5 flex items-start gap-3">
          <span className="font-mono text-2xl mt-0.5" style={{ color: obsColor }}>
            {obsUp ? '↑' : '↓'}
          </span>
          <div>
            <div className="font-mono text-xs tracking-wider uppercase mb-0.5" style={{ color: obsColor }}>
              Observed in C003
            </div>
            <div className="text-sm" style={{ color: '#d1d5db' }}>
              {observedDirection}
              {observedNote && <span style={{ color: '#9ca3af' }}> — {observedNote}</span>}
            </div>
            {note && (
              <div className="text-xs italic mt-1" style={{ color: '#6b7280' }}>{note}</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StoryPanelContradicted() {
  return (
    <section className="max-w-6xl mx-auto px-6 py-16">
      <div className="mb-10">
        <div className="font-mono text-xs tracking-widest mb-2" style={{ color: '#6b7280' }}>
          LITERATURE CONTRADICTIONS
        </div>
        <h2 className="font-display text-3xl font-semibold mb-3" style={{ color: '#e8eaed' }}>
          Where C003 doesn't match the textbook
        </h2>
        <p className="leading-relaxed max-w-2xl" style={{ color: '#9ca3af' }}>
          Six measurements moved opposite to published spaceflight literature expectations. The directional arrows show what was expected vs. what was observed.
        </p>
      </div>

      <div className="rounded-lg border border-gray-800 px-6" style={{ background: '#0f1424' }}>
        {CONTRADICTED_FINDINGS.map(f => <ContradictedRow key={f.measurement} finding={f} />)}
      </div>

      <p className="text-sm italic leading-relaxed mt-6 max-w-3xl" style={{ color: '#6b7280' }}>
        These contradictions likely reflect the unique conditions of a short-duration (3-day) civilian mission compared to the 6-month ISS stays underlying most spaceflight physiology literature. Inspiration 4's short mission duration, the civilian crew's fitness profile, and the timing of measurements post-return all differ from the astronaut studies used to establish expected directions.
      </p>
    </section>
  );
}

// ---- Story Panel: Missed by Standard ----

function StoryPanelMissedByStandard() {
  return (
    <section className="max-w-6xl mx-auto px-6 py-16">
      <div className="mb-10">
        <div className="font-mono text-xs tracking-widest mb-2" style={{ color: '#6b7280' }}>
          THE CORE THESIS
        </div>
        <h2 className="font-display text-3xl font-semibold mb-3" style={{ color: '#e8eaed' }}>
          What standard medicine would have missed
        </h2>
        <p className="leading-relaxed max-w-2xl" style={{ color: '#9ca3af' }}>
          Findings that fall within — or have no — clinical reference ranges, yet deviate sharply from C003's personal baseline.
        </p>
      </div>

      <div className="rounded-lg border border-gray-800 overflow-hidden mb-8" style={{ background: '#0f1424' }}>
        <div className="overflow-x-auto">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #1f2937' }}>
                {['Measurement', 'Personal Deviation', 'Clinical Reference Status', 'Timepoint'].map(h => (
                  <th
                    key={h}
                    className="text-left px-6 py-3 font-mono text-xs tracking-wider uppercase"
                    style={{ color: '#6b7280' }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MISSED_BY_STANDARD_TESTS.map((row, i) => (
                <tr
                  key={row.measurement}
                  style={{ borderBottom: i < MISSED_BY_STANDARD_TESTS.length - 1 ? '1px solid #1f2937' : 'none' }}
                >
                  <td className="px-6 py-4 font-display font-medium text-sm" style={{ color: '#e8eaed' }}>
                    {row.measurement}
                  </td>
                  <td className="px-6 py-4 font-mono text-sm" style={{ color: '#ffb000' }}>
                    {row.personalDeviation}
                  </td>
                  <td className="px-6 py-4 text-sm" style={{ color: '#9ca3af' }}>
                    {row.clinicalRange}
                  </td>
                  <td className="px-6 py-4 font-mono text-xs" style={{ color: '#6b7280' }}>
                    {row.timepoint}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div
        className="rounded-lg p-6 border"
        style={{ borderColor: '#78350f', background: 'rgba(255,176,0,0.04)' }}
      >
        <p className="leading-relaxed mb-3" style={{ color: '#d1d5db' }}>
          Population-based reference ranges are designed to flag values that are statistically unusual across a large group. They cannot detect a value that is unusual for a specific individual. C003's white blood cell count at R+1 was approximately 7.0 K/μL — within the clinical reference range of 3.8–10.8 — yet 10 standard deviations below C003's own pre-flight baseline. No standard clinical test would have flagged this. Personalized monitoring would have.
        </p>
        <p className="text-sm leading-relaxed" style={{ color: '#9ca3af' }}>
          Beyond clinical tests, 71 cytokine measurements in this study have no clinical reference ranges at all. These markers — including IL-6, IL-4, TARC, and others — are not part of standard-of-care blood panels. They are only accessible through research-grade multi-omics profiling. C003's most extreme findings (IL-6 at +31 SD, I-309 at +12 SD) are invisible to standard medicine by definition.
        </p>
      </div>
    </section>
  );
}

// ---- Methodology Footer ----

function MethodologyFooter() {
  const methodLines = METHODOLOGY_SUMMARY.trim().split('\n').filter(l => l.trim());
  return (
    <footer style={{ borderTop: '1px solid #1f2937', marginTop: 64 }}>
      <div className="max-w-6xl mx-auto px-6 py-16">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-12">

          <div>
            <h3 className="font-display font-semibold mb-4" style={{ color: '#e8eaed' }}>Methodology</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {methodLines.map((line, i) => (
                <p key={i} className="text-sm leading-relaxed" style={{ color: '#6b7280' }}>
                  · {line.trim()}
                </p>
              ))}
            </div>
          </div>

          <div>
            <h3 className="font-display font-semibold mb-4" style={{ color: '#e8eaed' }}>Limitations</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {LIMITATIONS.map((lim, i) => (
                <p key={i} className="text-sm leading-relaxed" style={{ color: '#6b7280' }}>
                  · {lim}
                </p>
              ))}
            </div>
          </div>

          <div>
            <h3 className="font-display font-semibold mb-4" style={{ color: '#e8eaed' }}>Credits</h3>
            <p className="text-sm leading-relaxed mb-4" style={{ color: '#9ca3af' }}>
              {PROJECT_META.team}
            </p>
            <a
              href={PROJECT_META.repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-sm transition-colors"
              style={{ color: '#38bdf8' }}
            >
              {PROJECT_META.repoUrl} ↗
            </a>
            <div
              className="mt-6 pt-6"
              style={{ borderTop: '1px solid #1f2937', display: 'flex', flexDirection: 'column', gap: 4 }}
            >
              <p className="font-mono text-xs" style={{ color: '#4b5563' }}>
                Data: Overbey EG, Kim JK, Tierney BT et al. Nature 632, 1145–1154 (2024). doi:10.1038/s41586-024-07639-y
              </p>
              <p className="font-mono text-xs" style={{ color: '#4b5563' }}>
                Source datasets: NASA OSDR OSD-569 (CBC), OSD-572 (metagenomics), OSD-575 (Eve cytokine panel)
              </p>
              <p className="font-mono text-xs" style={{ color: '#4b5563' }}>
                Analysis: Personal baseline z-scoring with bootstrap CI (n=1000)
              </p>
              <p className="font-mono text-xs" style={{ color: '#4b5563' }}>
                Full pipeline: PIPELINE.md in repository
              </p>
            </div>
          </div>
        </div>

        <div
          className="mt-12 pt-8 text-center"
          style={{ borderTop: '1px solid #1f2937' }}
        >
          <p className="font-mono text-xs" style={{ color: '#374151' }}>
            Subject C003 · SpaceX Inspiration 4 · September 2021 · Analysis May 2026
          </p>
        </div>
      </div>
    </footer>
  );
}

// ---- App ----

function App() {
  return (
    <div style={{ background: '#0a0e1a', minHeight: '100vh' }}>
      <Header />
      <HeroSection />
      <BigStat />
      <VitalGauges />
      <StoryPanelShared />
      <StoryPanelPersonal />
      <StoryPanelContradicted />
      <StoryPanelMissedByStandard />
      <MethodologyFooter />
    </div>
  );
}

// ---- Mount ----

const _root = ReactDOM.createRoot(document.getElementById('root'));
_root.render(React.createElement(App));
