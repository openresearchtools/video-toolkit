# Open Research Video Toolkit

Blender Video Sequencer add-on for one-click video enhancement, live color tools, and restoration filters. It adds a **Tools** menu inside the Video Sequencer plus a **Video Filters** sidebar panel.

The add-on has two tool classes:

- **Live Blender tools**: frame analysis, color matching, color management, transform/crop/opacity, and Blender VSE modifiers. These update the selected strip and preview live in the Sequencer.
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

## CLI Usage

The same processing catalog is available without Blender:

```bash
video-toolkit list
video-toolkit apply auto_enhance input.mp4 output.mp4
video-toolkit apply stabilize input.mp4 output.mp4
```

FFmpeg must be installed and visible on `PATH`.

## Included Tool Groups

- Live frame analysis: auto balance selected footage, or match the active movie strip to another selected reference strip.
- Zone-aware matching: frame samples are split into shadows, midtones, and highlights, then mapped to Blender Lift/Gamma/Gain, Tone Map, RGB Curves, and Hue Correct.
- Live Blender color room: Color Management, Sequencer input color space, exposure, gamma, white balance, strip transform/crop/opacity, and editable live modifier stack.
- Apply targets: live tools can be applied to the active strip, every selected strip, or a new native VSE adjustment layer above the selected range.
- Live one-click Blender stacks: Pro Color Stack, Gamma Grade, Shadow Recovery, Contrast Pop, Warm Grade, Cool Grade, saturation boost/reduce, monochrome, faded film, and contrast curves.
- Native Blender primitives: Brightness/Contrast, Lift/Gamma/Gain, ASC CDL Offset/Power/Slope, R/D Photoreceptor Tone Map, Rh Simple Tone Map, Curves, Hue Correct, White Balance, Mask.
- Blender VSE modifiers: Brightness/Contrast, Color Balance, Curves, Hue Correct, Mask, Tone Map, White Balance.
- Blender-native color recipes: auto enhance, neutral grade, punchy color, soft contrast, exposure lift, gamma up/down, warm/cool balance.
- FFmpeg-to-Blender translation: supported FFmpeg color intent (`eq`, `hue`, `huesaturation`, `colorchannelmixer`, `curves`) is converted into native live Blender VSE modifier stacks; non-native temporal filters stay in rendered restoration.
- Restoration: deflicker, lighting normalizer, denoise, sharpen restoration, deinterlace, quick deshake, two-pass vidstab stabilization.
- Motion and output: 2x Lanczos upscale, 1080p normalize scale, 60 fps interpolation, temporal smoothing.

Generated videos are written to `video_toolkit_outputs/` by default and are ignored by Git.

## End-User Verification

`scripts/end_user_blender_preview_test.py` opens a real MP4 in Blender's Video Sequencer, selects the movie strip, applies live Blender color tools through the same operators the UI buttons use, edits the resulting live modifier properties, renders before/after Sequencer preview frames to PNG, and fails if the pixels do not change.
