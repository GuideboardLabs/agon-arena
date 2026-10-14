# Calliope C1 — One-Shot Prompt (v1)

Target environment: **dsh headless** (DeepSeek Harness, clean room: no project context, no skills,
no memory). This is the Tier 0 baseline prompt — raw one-shot capability, nothing else.

Style reference: the "voxel_shinto / Skyreach Shrine" artifact by @mr_r0b0t (Ox Alpha, 2026-08-23).
Same genre and presentation, different subject.

---

## THE PROMPT

> Build a single self-contained HTML file containing a three.js voxel diorama: a conquered castle
> in a snowed-over woodland clearing.
>
> **The scene.** A stone castle stands on a low hill in the middle of a snowy clearing, and it has
> been taken. Its curtain wall is breached on one side, tumbled blocks spilling down the slope. Two
> of the four towers still stand; one has lost its conical roof and its upper stonework; the
> gatehouse has been smashed open. From the broken roofs and the keep, heavy smoke rises, and
> orange fire glows through the shattered windows and along the collapsed roof beams. A torn banner
> hangs from the gatehouse, and scattered broken siege equipment and fallen blocks lie on the snow
> below. Snow has settled on the surviving battlements and the unbroken roofs.
>
> **The woodland.** Around the clearing stand white-barked trees, tall and slender, their bark pale
> with dark horizontal flecks. Their canopies are made of red, orange and deep-russet leaf blocks,
> with some bare branches showing through. Their leaves have begun to fall, so drifting red and
> orange leaf blocks move slowly through the air. The ground is snow with **green grass breaking
> through it** in patches: this is a temperate place in early winter, not an arctic waste, so the
> snow is partial and the landscape still reads as alive. Fallen leaves rest on the snow, and a few
> grey rocks and low bushes poke through the drifts.
>
> **Style and construction.** Everything is built from cubes on a consistent voxel grid. No smooth
> primitives, no imported models, no textures, no image maps, and no external asset files: flat
> mesh colour only. Use a restrained palette drawn from warm stone greys, pale birch white, snow
> blue-white, ember orange, ember yellow, deep red and russet, smoke charcoal, and grass green.
>
> **How it must be built.**
> - Every repeated element (voxels, trees, leaves, falling leaves, snow, rocks, grass tufts,
>   fire particles, smoke) must be drawn with `THREE.InstancedMesh`, positioned through per-instance
>   matrices, with `instanceMatrix.needsUpdate = true` after writing them.
> - Light the scene with a low sun that casts shadows (`renderer.shadowMap.enabled = true`, a
>   directional light with `castShadow`, and meshes with `castShadow`/`receiveShadow` set).
> - Add fog and a gradient sky, and let the fire read as a real light source in the scene.
> - Give the page `OrbitControls` so the diorama can be dragged to orbit and scrolled to zoom, and
>   start the camera at an angle that shows the breach, the standing towers and the treeline at once.
> - Animate continuously: the fire flickers, the smoke drifts upward, and the leaves fall. The
>   whole scene should loop forever and look good at any moment.
> - three.js comes from the CDN as an ES module, e.g.
>   `import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js'`.
>
> **What matters most.** The castle must read instantly as *captured and burning*, not merely
> ruined, and the woodland must read as *snowed-over temperate winter*, not arctic. Depth of
> composition matters: foreground drifts, midground castle, background trees.

---

## Notes

- Deliberately one paragraph of scene, one of style, one of construction, matching how the
  reference artifact's genre is normally prompted.
- The grass-through-snow and red/orange-leaf phrasing is explicit because the default drift is
  toward bare tundra and evergreens.
- "Conquered" needs the banner, the breach, and the siege debris; without them the model tends to
  produce an intact castle or a generic ruin.
