# Open Research Video Toolkit

Blender Video Sequencer add-on for one-click video enhancement, live color tools, and restoration filters. It adds a **Tools** menu inside the Video Sequencer plus a **Video Filters** sidebar panel.

The add-on has two tool classes:

- **Live Blender tools**: frame analysis, color matching, color management, transform/crop/opacity, and Blender VSE modifiers. These update the selected strip and preview live in the Sequencer.
- **Native compositor node stacks**: one-click color/restoration graphs and a full native video-finishing node library created from the active movie strip using Blender's compositor nodes.
- **Rendered restoration tools**: FFmpeg-backed jobs for deflicker, lighting normalization, denoise, stabilization, deinterlace, upscale, and motion interpolation. These render a new MP4 and add it above the source strip.

## Quick Start

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e . pytest
python scripts/download_blender.py
pytest
python scripts/end_user_blender_preview_test.py
python scripts/blender_native_coverage.py
```

The Blender download script stores builds under `.local/blender/`, which is ignored by Git.

## Blender Install

Install the add-on from this repository folder or package it as a zip:

```bash
python scripts/package_addon.py
```

In Blender:

1. Open **Edit > Preferences > Add-ons**.
2. Install the generated zip from `dist/`.
3. Enable **Open Research Video Toolkit**.
4. Open the Video Sequencer and use **Tools > Video Filters** or the sidebar **Video Filters** panel.

The tools operate on the active Video Sequencer strip. Add or open a movie in the
Video Sequencer, click the strip so it is selected, then use either:

- The Sequencer header **Tools > Video Filters** menu.
- The Sequencer sidebar opened with **N**, tab **Video Filters**.

Live Blender color tools update the selected strip immediately in the Sequencer
preview. The **Native Color Chain Translation** field accepts supported
FFmpeg-style color chains such as `eq`, `colorbalance`, `colorlevels`, `curves`,
`normalize`, `colorcorrect`, `colorcontrast`, `vibrance`, `exposure`,
`colortemperature`, `limiter`, `tonemap`, and `histeq`, then adds editable
native Blender VSE modifiers instead of rendering a new file.

## CLI Usage

The same processing catalog is available without Blender:

```bash
video-toolkit list
video-toolkit apply auto_enhance input.mp4 output.mp4
video-toolkit apply stabilize input.mp4 output.mp4
```

FFmpeg must be installed and visible on `PATH`.

## Included Tool Groups

- Live frame analysis: auto balance selected footage, match the active movie strip to another selected reference strip, identify dominant colors, build a palette-aware live grade, write a color diagnostics report, and apply a diagnostic grade from the suggested native Blender tools.
- Live lighting and color timeline matching: samples luma and RGB through time, creates keyframed Blender Brightness/Contrast correction to reduce flicker, matches the active strip's lighting timeline to another selected reference strip, or keyframes Color Balance gamma/gain to follow a reference clip's color timeline without rendering a new file.
- Zone-aware matching: frame samples are split into shadows, midtones, and highlights, then mapped to Blender Lift/Gamma/Gain, Tone Map, RGB Curves, and Hue Correct.
- Palette math: sampled frames report dominant swatches, warm/cool balance, skin-tone-like pixel ratio, average saturation, and chroma, then map that identity into White Balance, Color Balance, Curves, Hue Correct, and Tone Map.
- Live Blender color room: one-click Color Management looks, Sequencer input color space, exposure, gamma, white balance, view curve mapping, strip transform/crop/opacity, and editable live modifier stack.
- Apply targets: live tools can be applied to the active strip, every selected strip, or a new native VSE adjustment layer above the selected range.
- Live one-click Blender stacks: Pro Color Stack, Gamma Grade, Shadow Recovery, Contrast Pop, Warm Grade, Cool Grade, saturation boost/reduce, monochrome, faded film, contrast curves, levels, black/white point correction, luma S-curves, per-channel RGB gamma trims, green/magenta tint repair, shadow/highlight tinting, skin-tone isolation, shadow/highlight balance, vibrance, exposure protection, temperature correction, legal-range clamp, and HDR tone compression.
- Native Blender primitives: Brightness/Contrast, Lift/Gamma/Gain, ASC CDL Offset/Power/Slope, R/D Photoreceptor Tone Map, Rh Simple Tone Map, Curves, Hue Correct, White Balance, Mask.
- Blender VSE modifiers: Brightness/Contrast, Color Balance, Curves, Hue Correct, Mask, Tone Map, White Balance.
- Blender compositor nodes: active-strip Movie Clip source, Color Space, Exposure, Brightness/Contrast, Color Balance, Color Correction, RGB Curves, Hue/Saturation/Value, Hue Correct, Tone Map, channel split/combine, Levels, Viewer, Output File, and a full native node library organized by color, restoration, transform, matte, input/output, and utility groups.
- Native restoration nodes: Stabilize, Movie Distortion, Denoise, Despeckle, Bilateral Blur, Anti-Aliasing, plus broader coverage for Blender matte, transform, alpha, and utility compositor nodes where they are applicable to video finishing.
- Blender-native color recipes: auto enhance, neutral grade, punchy color, soft contrast, exposure lift, gamma up/down, warm/cool balance.
- Blender-native Color Management presets: AgX balanced, AgX punch, Filmic soft, Standard video, warm review, and view-curve contrast.
- FFmpeg-to-Blender translation: supported FFmpeg color intent (`eq`, `hue`, `huesaturation`, `colorchannelmixer`, `curves`, `colorlevels`, `colorbalance`, `normalize`, `colorcorrect`, `colorcontrast`, `monochrome`, `colorize`, `histeq`, `vibrance`, `exposure`, `colortemperature`, `limiter`, `tonemap`) is converted into native live Blender VSE modifier stacks from the **Native Color Chain Translation** control; non-native temporal filters stay in rendered restoration.
- Restoration: deflicker, lighting normalizer, denoise, sharpen restoration, deinterlace, quick deshake, two-pass vidstab stabilization.
- Motion and output: 2x Lanczos upscale, 1080p normalize scale, 60 fps interpolation, temporal smoothing.

Generated videos are written to `video_toolkit_outputs/` by default and are ignored by Git.

## End-User Verification

`scripts/end_user_blender_preview_test.py` opens a real MP4 in Blender's Video Sequencer, selects the movie strip, applies live Blender color tools through the same operators the UI buttons use, translates an FFmpeg-style color chain into native Blender modifiers, applies a native Color Management preset, writes a color diagnostics report, applies the diagnostic grade recommendations, edits the resulting live modifier properties, renders before/after Sequencer preview frames to PNG, and fails if the pixels do not change. It also creates Blender-native compositor color/restoration graphs and the full native node library from that selected strip.

`scripts/blender_native_coverage.py` audits the installed Blender build directly. It verifies every VSE color modifier used by the add-on and every tracked Blender compositor video node can be created in Blender 5.2.

`scripts/capture_blender_ui.py` opens Blender's Sequencer with a selected movie strip and captures the **Video Filters** panel to `tests/output/blender_ui/video_filters_panel_open.png`.

`scripts/open_blender_video_filters.py` opens Blender for manual checking, registers the add-on from this checkout, selects a real video strip in the Sequencer, applies the diagnostic grade tools, and leaves the **Video Filters** panel open.
