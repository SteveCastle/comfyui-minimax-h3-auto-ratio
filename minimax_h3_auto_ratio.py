"""MiniMax H3 Auto Ratio: pick the supported aspect ratio closest to the input
image and fit the image to the model's native canvas for it.

H3 supports square, 4:3 and 16:9 in both orientations. Canvases follow the
model's own sizing rules (short edge 768, area capped at 768*1344, per-axis
round to 32), so at the default short edge the five candidates are:
    1:1 -> 768x768    4:3 -> 1024x768   3:4 -> 768x1024
    16:9 -> 1344x768  9:16 -> 768x1344
The ratio is chosen by minimal log-distance from the input aspect, i.e. the
one needing the least padding/cropping/stretching.
"""

import math

import torch

import nodes
import comfy.utils
from comfy_api.latest import ComfyExtension, io
from server import PromptServer

CANVAS_MULTIPLE = 32
BASE_SHORT_EDGE = 768
BASE_MAX_PIXELS = 768 * 1344

# (label, w/h ratio) - square, 4:3 and 16:9 in both orientations
SUPPORTED_RATIOS = [
    ("1:1", 1.0),
    ("4:3", 4 / 3),
    ("3:4", 3 / 4),
    ("16:9", 16 / 9),
    ("9:16", 9 / 16),
]


def canvas_for_ratio(ratio, short_edge):
    """Same sizing rules as nodes_minimax_h3.adapt_canvas, with a scalable short edge."""
    max_pixels = BASE_MAX_PIXELS * (short_edge / BASE_SHORT_EDGE) ** 2
    if ratio >= 1.0:
        nom_w, nom_h = short_edge * ratio, short_edge
    else:
        nom_w, nom_h = short_edge, short_edge / ratio
    if nom_w * nom_h > max_pixels:
        s = math.sqrt(max_pixels / (nom_w * nom_h))
        nom_w, nom_h = nom_w * s, nom_h * s
    return (max(CANVAS_MULTIPLE, round(nom_w / CANVAS_MULTIPLE) * CANVAS_MULTIPLE),
            max(CANVAS_MULTIPLE, round(nom_h / CANVAS_MULTIPLE) * CANVAS_MULTIPLE))


def best_ratio(width, height):
    aspect = width / height
    return min(SUPPORTED_RATIOS, key=lambda r: abs(math.log(aspect / r[1])))


class MiniMaxH3AutoRatio(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MiniMaxH3AutoRatio",
            display_name="MiniMax H3 Auto Ratio",
            search_aliases=["auto aspect", "fit to ratio"],
            category="image/transform",
            description="Picks the MiniMax H3 aspect ratio (1:1, 4:3, 3:4, 16:9, 9:16) closest to the "
                        "input image and fits it to the model-native canvas by padding, cropping or stretching. "
                        "Feed the image to first_frame and width/height to the H3 node.",
            inputs=[
                io.Image.Input("image"),
                io.Combo.Input("fit", options=["pad", "crop", "stretch"], default="pad",
                    tooltip="pad: keep whole image, fill borders. crop: center-crop to fill. stretch: distort to fill."),
                io.Combo.Input("padding_color", options=["black", "white"], advanced=True),
                io.Combo.Input("interpolation", options=["lanczos", "area", "bicubic", "bilinear", "nearest-exact"], advanced=True),
                io.Int.Input("short_edge", default=BASE_SHORT_EDGE, min=CANVAS_MULTIPLE, max=nodes.MAX_RESOLUTION,
                    step=CANVAS_MULTIPLE, advanced=True,
                    tooltip="Short edge of the output canvas. 768 is MiniMax H3's native resolution."),
            ],
            outputs=[
                io.Image.Output(),
                io.Int.Output(display_name="width"),
                io.Int.Output(display_name="height"),
                io.String.Output(display_name="ratio"),
            ],
            hidden=[io.Hidden.unique_id],
        )

    @classmethod
    def execute(cls, image, fit, padding_color, interpolation, short_edge) -> io.NodeOutput:
        batch_size, orig_height, orig_width, channels = image.shape

        label, ratio = best_ratio(orig_width, orig_height)
        target_width, target_height = canvas_for_ratio(ratio, short_edge)

        samples = image.movedim(-1, 1)
        if fit == "pad":
            scale = min(target_width / orig_width, target_height / orig_height)
            new_width = max(1, round(orig_width * scale))
            new_height = max(1, round(orig_height * scale))
            resized = comfy.utils.common_upscale(samples, new_width, new_height, interpolation, "disabled")
            pad_value = 0.0 if padding_color == "black" else 1.0
            output = torch.full((batch_size, channels, target_height, target_width), pad_value,
                                dtype=image.dtype, device=image.device)
            y = (target_height - new_height) // 2
            x = (target_width - new_width) // 2
            output[:, :, y:y + new_height, x:x + new_width] = resized
        else:
            crop = "center" if fit == "crop" else "disabled"
            output = comfy.utils.common_upscale(samples, target_width, target_height, interpolation, crop)
        output = output.movedim(1, -1)

        if cls.hidden.unique_id:
            PromptServer.instance.send_progress_text(
                f"{orig_width}x{orig_height} → {label} ({fit}): {target_width}x{target_height}",
                cls.hidden.unique_id)

        return io.NodeOutput(output, target_width, target_height, label)


class MiniMaxH3AutoRatioExtension(ComfyExtension):
    async def get_node_list(self):
        return [MiniMaxH3AutoRatio]


async def comfy_entrypoint() -> MiniMaxH3AutoRatioExtension:
    return MiniMaxH3AutoRatioExtension()
