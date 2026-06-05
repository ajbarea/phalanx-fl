# RIT Capstone 2025 — IntelliFL

**Title:** Enhancing the IntelliFL Federated Learning Framework

**Author:** AJ Barea, Rochester Institute of Technology (`ajb6289@rit.edu`)

**Venue:** Fall 2025 Graduate Capstone Poster Session (MS/SE & MS/DS), RIT Golisano College of Computing and Information Sciences

**Date:** Wednesday, December 10, 2025 · 10:00 AM – 12:00 PM

**Location:** Student Innovation Hall 1600 Atrium, RIT, Rochester, NY

**Downloads:**

- [Poster (PDF)](intellifl-poster.pdf): the final version presented on Dec 10
- [Final Report (PDF)](intellifl-report.pdf)
- [Poster, all 3 iterations (PDF)](intellifl-poster-iterations.pdf): design-journey artifact, see note below

<img src="intellifl-poster.jpg" class="research-poster" alt="IntelliFL capstone poster">

## Summary

Capstone contribution to **IntelliFL**, a federated learning execution and
research framework built on Flower. Focus areas: stabilizing Ray-backed
simulation on Windows, tightening the strategy / attack / defense layer for
experimentation, and shaping the dataset and partitioning surface so
researchers can iterate on FL experiments without fighting the tooling.

## Poster iterations

The [three-iteration PDF](intellifl-poster-iterations.pdf) captures the full
design journey in order, one version per page:

1. **Text-heavy draft (page 1):** leaned on prose for technical depth;
   sacrificed visual hierarchy.
2. **Picture-heavy draft (page 2):** swung the other way with dense imagery;
   lost narrative thread.
3. **Final (page 3):** balanced version presented on Dec 10. Also available
   as a standalone clean download [above](intellifl-poster.pdf) and used as
   the preview image on this page.

Kept all three bundled for posterity; the progression illustrates the
text-vs-visual tradeoff of single-page research posters.

## Project lineage

This capstone was a team project that went through three names:

1. **IntelliFL:** the original name under which the project was built and
   the poster/report above were produced.
2. **InteFL:** a late-stage rename after another research group was found
   to have already published under the "IntelliFL" name. The rebrand
   happened too close to the capstone deadline to reflow the submitted
   poster and report, which is why both artifacts here still read IntelliFL.
3. **Phalanx-FL:** the post-capstone solo continuation. A ground-up rewrite
   targeting Flower 1.28+ that replaces the accumulated Flower-1.9-era
   workarounds (Ray instability on Windows, bespoke partitioning, deprecated
   strategy shims) with current upstream primitives from Flower Labs
   (`flwr-datasets`, first-class partitioning, updated `ServerApp` /
   `ClientApp` layout).

See the [Phalanx-FL overview](../../index.md) for the current project state.
