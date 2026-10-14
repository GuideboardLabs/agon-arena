# Calliope — Event 1 Prompts

Calliope is Agon Mousai's monumental-scene event: the voxel-diorama lineage the Pagoda garden
prompt belongs to. Three tasks per model, each producing one self-contained HTML page.

**Provenance note.** I could not retrieve the canonical "Pagoda garden" prompt text (searched, no
findable original). The prompts below are therefore *original work in that lineage*, not a
modification of a specific known prompt. Stated here so nobody later claims it is "the pagoda
prompt, edited".

**Scaffold note.** What follows is the **Tier 0 creative brief** — the bare task prompt. Only
Tier 2 wraps it with the structure contract (classic `<script>`, global `THREE`, `window.__probe()`)
and the craft block (checklists and API facts, never working code). Do not paste the brief alone
into a small model and call it the harness.

---

## C1 — Voxel Windmill on the Canal Bank  ★ RECOMMENDED

> Build a voxel diorama, in three.js, of a Dutch windmill standing on the bank of a canal in early
> morning light.
>
> **The place.** A tapered brick windmill: a wide octagonal base narrowing toward a cap, with a
> wooden gallery running around the second storey, a small arched door at the base, and a thatched
> cap. Four sails are mounted on the hub at the front of the cap — each sail a lattice of wooden
> slats on a spar, set at an angle to the tower and arranged in a cross, not pressed flat against
> the masonry. The mill stands on a grass bank. A canal runs past on the far side behind a low
> brick retaining wall, with reeds along the waterline, a moored rowboat, and a small brick
> outbuilding with a thatched roof.
>
> **Style.** Everything is built from cubes on one consistent voxel grid. No smooth primitives, no
> imported models, no textures, no image maps — flat color only. Choose a restrained palette of at
> most 12 colors drawn from: brick red-brown, cream, dark timber, reed green, ochre, canal
> grey-green, and a pale morning sky.
>
> **What matters most.**
> - Every repeated element — reeds, slats, grass tufts, roof tiles — must be drawn with a **single
>   `THREE.InstancedMesh` per element type**, positioned through per-instance matrices. One `Mesh`
>   per cube is the wrong answer even when it happens to look right.
> - The sails must be placed with **real transforms**: each sail is a lattice of instances rotated
>   about the hub axis *and* inclined relative to the tower. Sails lying flat against the masonry
>   do not count as sails.
> - There must be a visible ground plane, and the whole mill must read as a windmill in silhouette
>   from the starting camera.
> - Work procedurally inside the volume: the 64 × 64 × 48 voxel budget is far larger than anything
>   you should write out one coordinate at a time.

**What it tests.** Non-axis-aligned instance transforms under a composed rotation (the sails) —
the single sharpest discriminator between a model that reasons about matrices and one that places
boxes in a grid. The pagoda's upswept eaves test the same faculty; the windmill tests it without
depending on one specific building, and adds a reflective water plane and a silhouetted read for
the light and framing batteries to bite on.

**Alternatives, if the subject is wrong:**

- **C1-alt-A — Pagoda, relocated.** Keep the pagoda but move it: a moss-covered pagoda on a misty
  mountain ledge at dawn, stone lanterns, a raked gravel courtyard, pine. Closest to the original
  genre and the easiest apples-to-apples against the well-known prompt. Tests the upswept-eave
  transform directly.
- **C1-alt-B — Lighthouse on a basalt shore.** Tapered tower, banded paint, gallery railing, lantern
  room with a glowing lamp, rocks and surf below. Cleanest silhouette, strongest light story, weakest
  transform story (a taper is per-instance scale, not rotation).
- **C1-alt-C — Step pyramid in a jungle clearing.** Stacked tiers and a central stair, foliage
  encroaching on the stone, a cenote at the base. Structurally the pagoda's sibling; the risk is
  that it reads as too close to "pagoda in a garden" to be a genuinely different test.

---

## C2 — Atmosphere and light battery

Not a separate artifact. C2 grades the page C1 produced, on its lighting and depth.

Assertions: a `DirectionalLight` with `castShadow` set, **and** `renderer.shadowMap.enabled` true,
**and** at least one mesh with `receiveShadow` — all three, since any one alone renders nothing. A
`Fog` or `FogExp2` attached to the scene. At least one emissive material. A sky that is a gradient
or a distinct color, not the default black. Then a pixel pass: mean luminance in a declared range,
a non-flat luminance histogram, and a shadow region measurably darker than the lit region.

## C3 — Deterministic camera framing battery

Also grades C1. The camera is placed so the subject fills a target fraction of the frame.

Assertions: the subject's projected bounding box (computed from the scene graph, not by eye)
occupies between 45% and 80% of frame height and its center sits within 8% of frame center. The
horizon sits in the upper or lower third, not dead center. All measured at step 0, so it is
reproducible.

---

## Why these three batteries and not three prompts

Each artifact is interrogated repeatedly and cheaply. Probing costs no model tokens, so depth comes
from interrogation rather than from more generations — which matters because one Agon code event
already averages over 100 minutes per run. One page, three batteries, one bill.
