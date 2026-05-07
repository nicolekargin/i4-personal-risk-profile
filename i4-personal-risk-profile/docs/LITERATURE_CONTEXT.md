# Literature Context
## Known Spaceflight Findings — Annotation Reference

Used by `literature_context.py` to tag each measurement in the
personal profile as `confirmed`, `novel`, or `contradicted`.

| Measurement | Direction | Source | Note |
|---|---|---|---|
| Fgf Basic | up | Scott et al. 2012 | FGF-2 elevated; fibroblast and angiogenic response to spaceflight stress. |
| Hematocrit | down | Trudel et al. 2020 | Hematocrit reduced consistent with hemolytic space anemia. |
| Hemoglobin | down | Trudel et al. 2020 | Hemoglobin reduced; resolves slowly post-flight (~3 months). |
| Ifn Gamma | up | Crucian et al. 2015; Mehta et al. 2013 | Th1 marker persistently elevated; associated with herpesvirus reactivation risk. |
| Il 10 | up | Crucian et al. 2014 | Anti-inflammatory counter-regulation elevated alongside pro-inflammatory cytokines. |
| Il 1 Beta | up | Crucian et al. 2014 | Elevated early post-flight in multiple ISS crew members. |
| Il 2 | variable | Crucian et al. 2014 | IL-2 responses variable across crew; sometimes reduced (T-cell hyporesponsiveness). |
| Il 4 | up | Crucian et al. 2015 | Th2 shift observed; IL-4 elevation accompanies IFN-γ in some crew. |
| Il 6 | up | Crucian et al. 2014 (J Interferon Cytokine Res); Crucian et al. 2015 | Persistently elevated IL-6 across ISS missions; marker of spaceflight immune dysregulation. |
| Il 8 | up | Crucian et al. 2014 | Neutrophil chemoattractant elevated in-flight and early post-flight. |
| Ip 10 | up | Crucian et al. 2015; Mehta et al. 2013 | CXCL10 / IP-10 elevated in herpesvirus-positive crew; interferon-stimulated gene product. |
| Lymphocyte Percent | down | Crucian et al. 2008 | Relative lymphopenia post-flight as neutrophils dominate re-entry stress response. |
| Mcp 1 | up | Crucian et al. 2014; Makedonas et al. 2019 | Monocyte chemoattractant protein elevated; monocyte dysregulation noted in spaceflight. |
| Mcv | up | Trudel et al. 2020 | MCV elevation consistent with macrocytic shift during erythrocyte regeneration. |
| Mip 1 Alpha | up | Crucian et al. 2014 | Macrophage inflammatory protein elevated post-flight. |
| Mip 1 Beta | up | Crucian et al. 2014 | MIP-1β elevated; associated with innate immune activation. |
| Nasal Microbiome Diversity | down | Voorhies et al. 2019 | Nasal microbiome diversity reduced in-flight; microbial community destabilization. |
| Neutrophil Percent | up | Crucian et al. 2008 | Neutrophilia at landing; mirrors cortisol spike from re-entry physical stress. |
| Oral Microbiome Diversity | down | Voorhies et al. 2019 (NPJ Microgravity) | Alpha diversity reduction in oral microbiome during spaceflight. |
| Red Blood Cell Count | down | Trudel et al. 2020 (Nat Med) — space anemia | RBC destruction accelerated 50× above normal in-flight; hemolytic anemia post-flight. |
| Tnf Alpha | up | Crucian et al. 2014 | Pro-inflammatory cytokine elevated in long-duration spaceflight. |
| Vegf | up | Scott et al. 2012 (vascular adaptation review) | VEGF elevated in microgravity; vascular remodeling response. |
| White Blood Cell Count | up | Crucian et al. 2008 (Aviat Space Environ Med) | WBC commonly elevated early post-landing; stress leukocytosis and gravitational re-adaptation. |

## Status Definitions

| Status | Definition |
|---|---|
| confirmed | Observed direction matches the published spaceflight finding |
| novel | Elevated (|z| ≥ 1) but no matching published finding exists |
| contradicted | Direction opposite to the published finding |
| not_applicable | Baseline timepoint, stable signal (|z| < 1), or no z-score |

## Sources

- Crucian et al. 2014. J Interferon Cytokine Res — 10 ISS crew, cytokine profiles
- Crucian et al. 2015. J Interferon Cytokine Res — Th1/Th2 dysregulation
- Crucian et al. 2008. Aviat Space Environ Med — CBC changes at landing
- Mehta et al. 2013. J Allergy Clin Immunol — herpesvirus & immune dysregulation
- Makedonas et al. 2019. Front Immunol — monocyte/T-cell spaceflight phenotype
- Trudel et al. 2020. Nat Med — space anemia mechanism
- Voorhies et al. 2019. NPJ Microgravity — oral/nasal microbiome ISS
- Scott et al. 2012. vascular adaptation review
