# ComfyUI — MiniMax H3 Auto Ratio

Derive the generation size from the reference image: one node that picks the
MiniMax H3 aspect ratio closest to your input image and fits the image to the
model's native canvas, so the H3 node never sees a resolution it wasn't trained on.

One node, category `image/transform`:

| Node | Use |
| --- | --- |
| **MiniMax H3 Auto Ratio** (`MiniMaxH3AutoRatio`) | fit an image to the nearest H3-supported canvas and emit the matching width/height |

## Why

MiniMax H3 supports square, 4:3 and 16:9 in both orientations, and sizes its
canvas by its own rules (short edge 768, area capped at 768×1344, each axis
rounded to a multiple of 32). Reference images almost never arrive at exactly
those dimensions, so picking a ratio and resizing by hand is busywork you redo
for every input — and getting it wrong wastes a generation.

This node does the whole step: it measures the input's aspect, chooses the
supported ratio with the smallest log-distance from it (i.e. the one needing the
least padding/cropping/stretching), and outputs both the fitted image and the
exact width/height to drive the H3 node.

At the default short edge the five candidate canvases are:

| Ratio | Canvas |
| --- | --- |
| 1:1 | 768×768 |
| 4:3 | 1024×768 |
| 3:4 | 768×1024 |
| 16:9 | 1344×768 |
| 9:16 | 768×1344 |

## Inputs

| Input | Meaning |
| --- | --- |
| `image` | the reference image (batch supported) |
| `fit` | how the image meets the canvas — see below (default `pad`) |
| `padding_color` | `black` / `white` borders when padding (advanced) |
| `interpolation` | resampling filter: `lanczos` (default), `area`, `bicubic`, `bilinear`, `nearest-exact` (advanced) |
| `short_edge` | short edge of the output canvas, in steps of 32 (advanced). 768 is H3's native resolution; the area cap scales with it |

### `fit`

- **`pad`** — scale to fit entirely inside the canvas, fill the borders with
  `padding_color`. Nothing is lost or distorted; the model sees letterboxing.
- **`crop`** — scale to cover the canvas and center-crop the overflow. Fills the
  frame; edges of the input are lost.
- **`stretch`** — resize to the canvas exactly, distorting the aspect. Fills the
  frame with the whole image; geometry shifts slightly.

Because the chosen ratio is already the closest supported one, whichever mode you
pick is operating on the smallest possible mismatch.

## Outputs

| Output | Type | |
| --- | --- | --- |
| `image` | IMAGE | the fitted image at exactly the canvas size |
| `width` | INT | canvas width — wire into the H3 node |
| `height` | INT | canvas height — wire into the H3 node |
| `ratio` | STRING | the chosen ratio label, e.g. `16:9` |

The node also reports its decision live on the node body, e.g.
`1920x1080 → 16:9 (pad): 1344x768`.

## Wiring

```
Load Image ──image──► MiniMax H3 Auto Ratio ──image───► H3 first_frame
                                            ├─width───► H3 width
                                            └─height──► H3 height
```

## Installation

Clone into your ComfyUI `custom_nodes` folder and restart:

```
cd ComfyUI/custom_nodes
git clone https://github.com/SteveCastle/comfyui-minimax-h3-auto-ratio
```

No dependencies beyond ComfyUI itself. Uses the modern `ComfyExtension` /
`comfy_entrypoint` API, so it needs a reasonably current ComfyUI.

## Companion nodes

Part of a set of nodes for driving MiniMax H3 workflows:

- [comfyui-video-slicer](https://github.com/SteveCastle/comfyui-video-slicer) — sliding-window video slicing for `ref_video` inputs
- [comfyui-audio-slicer](https://github.com/SteveCastle/comfyui-audio-slicer) — sliding-window audio slicing, one generation per slice
- [comfyui-frame-carry](https://github.com/SteveCastle/comfyui-frame-carry) — carry the last frame of one generation into the next
