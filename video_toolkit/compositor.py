"""Blender compositor node coverage used by the add-on and tests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompositorNodeTool:
    """A Blender compositor node that is relevant to video finishing."""

    node_type: str
    label: str
    category: str
    description: str


COMPOSITOR_COLOR_NODES: tuple[CompositorNodeTool, ...] = (
    CompositorNodeTool("CompositorNodeMovieClip", "Movie Clip", "Input", "Loads the selected movie strip as a compositor source."),
    CompositorNodeTool("CompositorNodeConvertColorSpace", "Convert Color Space", "Color", "Native color-space conversion."),
    CompositorNodeTool("CompositorNodeConvertToDisplay", "Convert to Display", "Color", "Maps scene-linear imagery to display color."),
    CompositorNodeTool("CompositorNodeExposure", "Exposure", "Color", "Native exposure adjustment."),
    CompositorNodeTool("CompositorNodeBrightContrast", "Brightness/Contrast", "Color", "Native brightness and contrast adjustment."),
    CompositorNodeTool("CompositorNodeColorBalance", "Color Balance", "Color", "Lift, gamma, gain, offset, power, slope, temperature, and tint."),
    CompositorNodeTool("CompositorNodeColorCorrection", "Color Correction", "Color", "Master, shadows, midtones, and highlights controls."),
    CompositorNodeTool("CompositorNodeCurveRGB", "RGB Curves", "Color", "RGB curve shaping."),
    CompositorNodeTool("CompositorNodeHueSat", "Hue/Saturation/Value", "Color", "HSV hue, saturation, and value adjustment."),
    CompositorNodeTool("CompositorNodeHueCorrect", "Hue Correct", "Color", "Hue-zone curve correction."),
    CompositorNodeTool("CompositorNodeTonemap", "Tone Map", "Color", "Photoreceptor and simple tone mapping."),
    CompositorNodeTool("CompositorNodeLevels", "Levels", "Analysis", "Mean, standard deviation, minimum, and maximum outputs."),
    CompositorNodeTool("CompositorNodeSeparateColor", "Separate Color", "Color Channels", "Splits color channels."),
    CompositorNodeTool("CompositorNodeCombineColor", "Combine Color", "Color Channels", "Combines color channels."),
    CompositorNodeTool("CompositorNodeRGBToBW", "RGB to BW", "Color Channels", "Converts image color to luminance."),
    CompositorNodeTool("CompositorNodeInvert", "Invert", "Color", "Inverts color and alpha."),
    CompositorNodeTool("CompositorNodeNormalize", "Normalize", "Color", "Normalizes value ranges."),
    CompositorNodeTool("CompositorNodePosterize", "Posterize", "Color", "Reduces tonal steps."),
    CompositorNodeTool("CompositorNodePremulKey", "Premul Key", "Alpha", "Converts alpha premultiplication state."),
    CompositorNodeTool("CompositorNodeSetAlpha", "Set Alpha", "Alpha", "Sets or applies alpha."),
    CompositorNodeTool("CompositorNodeAlphaOver", "Alpha Over", "Alpha", "Composites foreground over background."),
)


COMPOSITOR_RESTORATION_NODES: tuple[CompositorNodeTool, ...] = (
    CompositorNodeTool("CompositorNodeAntiAliasing", "Anti-Aliasing", "Restoration", "Smooths aliased edges."),
    CompositorNodeTool("CompositorNodeBilateralblur", "Bilateral Blur", "Restoration", "Edge-aware blur."),
    CompositorNodeTool("CompositorNodeBlur", "Blur", "Restoration", "General-purpose blur."),
    CompositorNodeTool("CompositorNodeBokehBlur", "Bokeh Blur", "Restoration", "Bokeh-style blur."),
    CompositorNodeTool("CompositorNodeDefocus", "Defocus", "Restoration", "Depth-aware defocus."),
    CompositorNodeTool("CompositorNodeDenoise", "Denoise", "Restoration", "Blender compositor denoise."),
    CompositorNodeTool("CompositorNodeDespeckle", "Despeckle", "Restoration", "Removes small speckles."),
    CompositorNodeTool("CompositorNodeFilter", "Filter", "Restoration", "Filter kernel presets."),
    CompositorNodeTool("CompositorNodeGlare", "Glare", "Restoration", "Highlight glare treatment."),
    CompositorNodeTool("CompositorNodeInpaint", "Inpaint", "Restoration", "Fills transparent or missing pixels."),
    CompositorNodeTool("CompositorNodeKuwahara", "Kuwahara", "Restoration", "Stylized edge-preserving smoothing."),
    CompositorNodeTool("CompositorNodeLensdist", "Lens Distortion", "Restoration", "Lens distortion and dispersion."),
    CompositorNodeTool("CompositorNodeMovieDistortion", "Movie Distortion", "Restoration", "Movie-clip distortion correction."),
    CompositorNodeTool("CompositorNodePixelate", "Pixelate", "Restoration", "Pixelation utility."),
    CompositorNodeTool("CompositorNodeStabilize", "Stabilize", "Restoration", "Movie-clip stabilization node."),
    CompositorNodeTool("CompositorNodeVecBlur", "Vector Blur", "Restoration", "Motion-vector blur."),
)


COMPOSITOR_TRANSFORM_NODES: tuple[CompositorNodeTool, ...] = (
    CompositorNodeTool("CompositorNodeCornerPin", "Corner Pin", "Transform", "Pins footage to a quadrilateral."),
    CompositorNodeTool("CompositorNodeCrop", "Crop", "Transform", "Crops image bounds."),
    CompositorNodeTool("CompositorNodeDisplace", "Displace", "Transform", "Displaces image pixels."),
    CompositorNodeTool("CompositorNodeFlip", "Flip", "Transform", "Flips image axes."),
    CompositorNodeTool("CompositorNodeMapUV", "Map UV", "Transform", "Maps image through UV coordinates."),
    CompositorNodeTool("CompositorNodePlaneTrackDeform", "Plane Track Deform", "Transform", "Deforms through a tracked plane."),
    CompositorNodeTool("CompositorNodeRelativeToPixel", "Relative to Pixel", "Transform", "Converts relative values to pixels."),
    CompositorNodeTool("CompositorNodeRotate", "Rotate", "Transform", "Rotates an image."),
    CompositorNodeTool("CompositorNodeScale", "Scale", "Transform", "Scales an image."),
    CompositorNodeTool("CompositorNodeTransform", "Transform", "Transform", "Translate, rotate, and scale."),
    CompositorNodeTool("CompositorNodeTranslate", "Translate", "Transform", "Translates an image."),
)


COMPOSITOR_MATTE_NODES: tuple[CompositorNodeTool, ...] = (
    CompositorNodeTool("CompositorNodeBoxMask", "Box Mask", "Matte", "Box-shaped mask."),
    CompositorNodeTool("CompositorNodeChannelMatte", "Channel Matte", "Matte", "Channel-key matte."),
    CompositorNodeTool("CompositorNodeChromaMatte", "Chroma Matte", "Matte", "Chroma-key matte."),
    CompositorNodeTool("CompositorNodeColorMatte", "Color Matte", "Matte", "Color-key matte."),
    CompositorNodeTool("CompositorNodeColorSpill", "Color Spill", "Matte", "Spill suppression."),
    CompositorNodeTool("CompositorNodeCryptomatte", "Cryptomatte", "Matte", "Cryptomatte extraction."),
    CompositorNodeTool("CompositorNodeCryptomatteV2", "Cryptomatte V2", "Matte", "Cryptomatte extraction."),
    CompositorNodeTool("CompositorNodeDiffMatte", "Difference Matte", "Matte", "Difference-key matte."),
    CompositorNodeTool("CompositorNodeDilateErode", "Dilate/Erode", "Matte", "Expands or contracts masks."),
    CompositorNodeTool("CompositorNodeDistanceMatte", "Distance Matte", "Matte", "Distance-key matte."),
    CompositorNodeTool("CompositorNodeDoubleEdgeMask", "Double Edge Mask", "Matte", "Two-edge mask refinement."),
    CompositorNodeTool("CompositorNodeEllipseMask", "Ellipse Mask", "Matte", "Ellipse-shaped mask."),
    CompositorNodeTool("CompositorNodeIDMask", "ID Mask", "Matte", "Object/material ID mask."),
    CompositorNodeTool("CompositorNodeKeying", "Keying", "Matte", "Full keying node."),
    CompositorNodeTool("CompositorNodeKeyingScreen", "Keying Screen", "Matte", "Keying screen generator."),
    CompositorNodeTool("CompositorNodeLumaMatte", "Luma Matte", "Matte", "Luminance-key matte."),
    CompositorNodeTool("CompositorNodeMask", "Mask", "Matte", "Blender mask source."),
    CompositorNodeTool("CompositorNodeMaskToSDF", "Mask to SDF", "Matte", "Converts masks to signed distance fields."),
)


COMPOSITOR_INPUT_OUTPUT_NODES: tuple[CompositorNodeTool, ...] = (
    CompositorNodeTool("CompositorNodeBlankImage", "Blank Image", "Input", "Generated blank image input."),
    CompositorNodeTool("CompositorNodeBokehImage", "Bokeh Image", "Input", "Generated bokeh image input."),
    CompositorNodeTool("CompositorNodeImage", "Image", "Input", "Still-image input."),
    CompositorNodeTool("CompositorNodeImageCoordinates", "Image Coordinates", "Input", "Image coordinate outputs."),
    CompositorNodeTool("CompositorNodeImageInfo", "Image Info", "Input", "Image dimensions, transform, and resolution."),
    CompositorNodeTool("CompositorNodeNormal", "Normal", "Input", "Normal-vector input."),
    CompositorNodeTool("CompositorNodeRGB", "RGB", "Input", "Constant RGB color source."),
    CompositorNodeTool("CompositorNodeRLayers", "Render Layers", "Input", "Render layer input."),
    CompositorNodeTool("CompositorNodeSceneTime", "Scene Time", "Input", "Scene time outputs."),
    CompositorNodeTool("CompositorNodeSequencerStripInfo", "Sequencer Strip Info", "Input", "Sequencer strip transform data."),
    CompositorNodeTool("CompositorNodeTime", "Time", "Input", "Time-factor output."),
    CompositorNodeTool("CompositorNodeOutputFile", "Output File", "Output", "Writes compositor output files."),
    CompositorNodeTool("CompositorNodeViewer", "Viewer", "Output", "Viewer output for compositor preview."),
)


COMPOSITOR_UTILITY_NODES: tuple[CompositorNodeTool, ...] = (
    CompositorNodeTool("CompositorNodeConvolve", "Convolve", "Utility", "Custom convolution kernels."),
    CompositorNodeTool("CompositorNodeCryptomatteV2", "Cryptomatte V2", "Utility", "Modern cryptomatte node."),
    CompositorNodeTool("CompositorNodeSplit", "Split", "Utility", "Compares two images in one output."),
    CompositorNodeTool("CompositorNodeStringToImage", "String to Image", "Utility", "Renders text to an image."),
    CompositorNodeTool("CompositorNodeSwitch", "Switch", "Utility", "Switches between inputs."),
    CompositorNodeTool("CompositorNodeSwitchView", "Switch View", "Utility", "Stereo view switch."),
    CompositorNodeTool("CompositorNodeTrackPos", "Track Position", "Utility", "Movie tracking position outputs."),
    CompositorNodeTool("CompositorNodeZcombine", "Z Combine", "Utility", "Depth-based compositing."),
)


COLOR_WORKSPACE_STACK_NODE_TYPES: tuple[str, ...] = (
    "CompositorNodeMovieClip",
    "CompositorNodeConvertColorSpace",
    "CompositorNodeExposure",
    "CompositorNodeBrightContrast",
    "CompositorNodeColorBalance",
    "CompositorNodeColorCorrection",
    "CompositorNodeCurveRGB",
    "CompositorNodeHueSat",
    "CompositorNodeHueCorrect",
    "CompositorNodeTonemap",
    "CompositorNodeSeparateColor",
    "CompositorNodeCombineColor",
    "CompositorNodeLevels",
    "CompositorNodeViewer",
    "CompositorNodeOutputFile",
)


RESTORATION_WORKSPACE_STACK_NODE_TYPES: tuple[str, ...] = (
    "CompositorNodeMovieClip",
    "CompositorNodeStabilize",
    "CompositorNodeMovieDistortion",
    "CompositorNodeDenoise",
    "CompositorNodeDespeckle",
    "CompositorNodeBilateralblur",
    "CompositorNodeAntiAliasing",
    "CompositorNodeViewer",
    "CompositorNodeOutputFile",
)


def compositor_node_tools() -> tuple[CompositorNodeTool, ...]:
    """Return compositor nodes Video Toolkit tracks for Blender-native video work."""

    tools = (
        COMPOSITOR_COLOR_NODES
        + COMPOSITOR_RESTORATION_NODES
        + COMPOSITOR_TRANSFORM_NODES
        + COMPOSITOR_MATTE_NODES
        + COMPOSITOR_INPUT_OUTPUT_NODES
        + COMPOSITOR_UTILITY_NODES
    )
    seen: set[str] = set()
    unique: list[CompositorNodeTool] = []
    for tool in tools:
        if tool.node_type in seen:
            continue
        unique.append(tool)
        seen.add(tool.node_type)
    return tuple(unique)


def compositor_node_types() -> tuple[str, ...]:
    """Return unique Blender compositor node type identifiers tracked by the add-on."""

    return tuple(tool.node_type for tool in compositor_node_tools())
