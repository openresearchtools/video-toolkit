# Open Research Video Toolkit

Blender Video Sequencer add-on for one-click video enhancement, color tools, and restoration filters. It adds a **Tools** menu inside the Video Sequencer plus a **Video Filters** sidebar panel. Processing is backed by Blender's built-in VSE modifiers where they fit, and FFmpeg for rendered restoration jobs such as deflicker, lighting normalization, denoise, stabilization, deinterlace, upscale, and motion interpolation.

## Quick Start

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e . pytest
python scripts/download_blender.py
pytest
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

- Blender VSE modifiers: Brightness/Contrast, Color Balance, Curves, Hue Correct, Mask, Tone Map, White Balance.
- Color and gamma tools: auto enhance, neutral grade, punchy color, exposure lift, gamma up/down, warm/cool balance.
- Restoration: deflicker, lighting normalizer, denoise, sharpen restoration, deinterlace, quick deshake, two-pass vidstab stabilization.
- Motion and output: 2x Lanczos upscale, 1080p normalize scale, 60 fps interpolation, temporal smoothing.

Generated videos are written to `video_toolkit_outputs/` by default and are ignored by Git.
