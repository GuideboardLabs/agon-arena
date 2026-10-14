# Calliope C1 — One-Shot Prompt (v2, camera motion built in)

Target environment: **dsh headless** (DeepSeek Harness, clean room: no project context, no skills,
no memory). Tier 0 baseline prompt — raw one-shot capability, nothing else.

Difference from v1: the looping cinematic camera is **requested in the prompt** instead of being
patched in afterwards. v1 produced a static camera that had to be hand-fixed. This version tests
whether a model can build the motion itself, which is the thing the sweep is measuring.

Same `## THE PROMPT` / `---` structure as v1, so the existing run script parses it unchanged.

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
> - Animate continuously: the fire flickers, the smoke drifts upward, and the leaves fall.
> - three.js comes from the CDN as an ES module, e.g.
>   `import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js'`.
>
> **The camera must move by itself.** The page opens already in motion, with no click needed. The
> camera slowly circles the castle while breathing in and out: it drifts closer until the castle
> fills the frame, then eases back out until the clearing and treeline come into view, then closes
> in again. One full circle and one full in-and-out cycle take about half a minute.
>
> The motion must loop **seamlessly**: at the end of the cycle the camera is exactly where it
> started, with the same angle and the same distance, so the loop never jumps. Hold the camera's
> height steady, always keep it aimed at the castle, and keep the speed low and even, drifting
> rather than swinging.
>
> Hard limits on that path. The camera must never pass through the trees or terrain, and must never
> travel so far out that the fog swallows the castle. Both ends of the zoom must leave the castle
> clearly readable, near and far. The far end of the zoom is the one to be careful with: fog hides
> anything past a certain distance, so pick limits that stay inside it.
>
> The viewer must still be able to take over. Dragging orbits and scrolling zooms with a gentle,
> fine-grained zoom rather than a jump. On any drag or scroll the auto camera stops immediately and
> hands over control. After a few seconds of no input it takes the camera back and eases into the
> loop from wherever the viewer left it, without snapping.
>
> **What matters most.** The castle must read instantly as *captured and burning*, not merely
> ruined, and the woodland must read as *snowed-over temperate winter*, not arctic. Depth of
> composition matters: foreground drifts, midground castle, background trees.

---

## Notes

- Change from v1 is confined to the new **"The camera must move by itself"** block. The scene,
  style and construction paragraphs are unchanged so the sweep stays comparable to the v1 result.
- The camera block states **required behaviour and hard limits**, not an implementation. It does not
  name `OrbitControls`, `lookAt`, spherical coordinates, or a timing function, so the model still has
  to figure out how. That is deliberate: it is the thing being measured.
- Three failure modes are called out because they are the ones a model actually hits, and the sweep
  should be able to grade them separately:
  1. **Aiming.** A camera that moves its position without re-aiming at the target orbits while
     facing off into empty space. Half the frames come out as featureless sky.
  2. **Fog.** Travelling past the fog distance dissolves the castle into the sky colour. This is the
     single easiest way to wreck the far end of the zoom.
  3. **The near end.** Pulling in too close puts the camera inside the treeline, and foreground
     voxels crowd the frame.
- "about half a minute" is a real number, not a range, per the writing rules. It is a target; grade
  anything from roughly 20 to 40 seconds as acceptable.
- **Optional vertical variant.** To qualify for X's video carousel the clip must be vertical
  (aspect strictly below 1.0). Swap the opening line for: *Build a single self-contained HTML file
  containing a three.js voxel diorama, laid out for a 9:16 portrait viewport.* Everything else
  stands. Use it only if the run is intended for the carousel; it changes the composition and so
  breaks comparability with v1.

## Baseline for comparison

v1, run on **mistral-large-4** in dsh, produced "The Taking of Thornwick" — 25.8 KB, ~191k output
tokens, ~62 min, graded 7/10 on an independent read. It met every scene requirement and used real
`InstancedMesh`, but shipped a **static** camera; the orbit and zoom were added afterwards by hand.
The known weak points of that render: smoke cubes oversized and clipping through the tower, the
breach not cleanly legible, ambient-heavy lighting making the castle read flat, and no siege
equipment for the "taken" story.
