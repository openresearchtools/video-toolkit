# Open Research Video Toolkit

Blender Video Sequencer add-on for one-click video enhancement, live color tools, and restoration filters. It adds a **Video Effects** sidecar tab in the Video Sequencer with mini tabs for tools, analysis, color management, compositor nodes, strip controls, modifiers, and rendered restoration, plus a secondary header menu. The sidecar follows the sister Audio Toolkit layout: selected strip status, group/tool selectors, direct supported-tool buttons, Apply/Nodes actions, and editable live modifier controls in the docked sidebar.

The add-on has three tool classes:

- **Live Blender tools**: frame analysis, color matching, color management, transform/crop/opacity, and Blender VSE modifiers. These update the selected strip and preview live in the Sequencer.
- **Native compositor node stacks**: one-click static, catalog color-recipe, connected native color-room, sampled Color Management, sampled grade, diagnostic, palette-identity, reference-matched, reference color-board, animated timeline-matched, FFmpeg-translated, and keyframed lighting-normalizer color/restoration graphs plus a full native video-finishing node library created from the active movie strip using Blender's compositor nodes.
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
python scripts/end_user_full_ui_operator_matrix.py
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
4. Open the Video Sequencer and use the sidebar **Video Effects** tab.

The tools operate on the active Video Sequencer strip. Add or open a movie in the
Video Sequencer, click the strip so it is selected, then open the sidebar with
**N** and use the **Video Effects** tab. The sidecar contains mini tabs for the
tool browser, one-click enhancement buttons, frame analysis, Color Management,
compositor nodes, live tools, strip controls, modifiers, and rendered restoration.

The Sequencer header menu exposes **Video Effects** as a secondary shortcut,
while the buttons themselves stay inside the docked sidecar.

Live Blender color tools update the selected strip immediately in the Sequencer
preview. The **Native Color Chain Translation** field accepts supported
FFmpeg-style color chains such as `eq`, `colorbalance`, `colorlevels`, `curves`,
`normalize`, `colorcorrect`, `colorcontrast`, `selectivecolor`, `vibrance`, `exposure`,
`colortemperature`, `limiter`, `tonemap`, `histeq`, `colorspace`, `colormatrix`,
`setparams`, and `setrange`, then adds editable native Blender VSE modifiers
and Blender color-management settings instead of rendering a new file.

## CLI Usage

The same processing catalog is available without Blender:

```bash
video-toolkit list
video-toolkit apply auto_enhance input.mp4 output.mp4
video-toolkit apply stabilize input.mp4 output.mp4
```

FFmpeg must be installed and visible on `PATH`.

## Included Tool Groups

- Live frame analysis: auto balance selected footage, run a one-click **Pro Color Workflow** that samples once and applies Color Management, ranked live modifiers, recommendation reports, and compositor graphs together, run a one-click **FFmpeg Color Workflow** that translates supported FFmpeg color intent into live Blender modifiers, Blender Color Management, and compositor nodes, sample real frames for native scene Color Management, white balance/color-cast neutralization, levels/gamma normalization, hue/chroma balancing, a combined sampled pro-grade stack, a dynamic **Sampled Color Board** primary/secondary stack, and a **Reference Color Board** that matches the active strip to another selected reference strip with editable live Blender color-board controls, match the active movie strip to another selected reference strip, identify dominant colors, build a palette-aware live grade, write a color diagnostics report, rank Blender-native color recipes against sampled luma/chroma/warm-cool/skin/palette math, apply a ranked recipe mix, and apply a diagnostic grade from the suggested native Blender tools.
- Live lighting and color timeline matching: samples luma and RGB through time, creates keyframed Blender Brightness/Contrast correction to reduce flicker, matches the active strip's lighting timeline to another selected reference strip, or keyframes Color Balance gamma/gain to follow a reference clip's color timeline without rendering a new file.
- Zone-aware matching: frame samples are split into shadows, midtones, and highlights, then mapped to Blender White Balance, Lift/Gamma/Gain, sampled black/mid/white RGB Curves, Brightness/Contrast, Tone Map, and Hue Correct.
- Palette math: sampled frames report dominant swatches, warm/cool balance, skin-tone-like pixel ratio, average saturation, and chroma, then map that identity into White Balance, Lift/Gamma/Gain, black/mid/white Curves, Hue Correct hue-zone curves, Tone Map, the one-click Sampled Pro Grade, a **Recipe Recommendations** text report, an **Apply Recommended Recipe Mix** action that combines the top-ranked live Blender color tools in the sidecar, a **Recommended Recipe Mix Nodes** action that builds the same sampled mix as one connected Blender compositor graph, and the one-click **Pro Color Workflow** that combines those pieces with sampled scene Color Management.
- Live Blender color room: one-click Color Management looks, sampled scene/view Color Management from real frames, display device/emulation, Sequencer input color space, view transform/look, exposure, gamma, white balance temperature/tint/whitepoint, view curve mapping, strip transform/crop/opacity, and editable live modifier stack.
- Apply targets: live tools can be applied to the active strip, every selected strip, or a new native VSE adjustment layer above the selected range.
- Live one-click Blender stacks: Pro Color Stack, Gamma Grade, Shadow Recovery, Contrast Pop, Warm Grade, Cool Grade, primary color board, log-zone board, ASC CDL finish board, six-vector hue board, secondary skin vector, palette separation board, broadcast-safe finish, match-prep neutralizer, saturation boost/reduce, monochrome, faded film, contrast curves, levels, black/white point correction, luma S-curves, per-channel RGB gamma trims, green/magenta tint repair, shadow/highlight tinting, skin-tone isolation, shadow/highlight balance, vibrance, exposure protection, temperature correction, legal-range clamp, and HDR tone compression.
- Native Blender primitives: Brightness/Contrast, Lift/Gamma/Gain, ASC CDL Offset/Power/Slope, R/D Photoreceptor Tone Map, Rh Simple Tone Map, Curves, Hue Correct, White Balance, Mask.
- Blender VSE modifiers: Brightness/Contrast, Color Balance, Curves, Hue Correct, Mask, Tone Map, White Balance.
- Blender compositor nodes: active-strip Movie Clip source, the **Video Effects** sidebar browser `Nodes` action plus the **Compositor Color Recipes** menu for every supported Blender-native catalog color recipe, sampled **Recommended Recipe Mix Nodes**, one-click **Pro Color Workflow** recipe and Color Management graphs, one-click **FFmpeg Color Workflow** translated color graphs, sampled dynamic **Color Board** graphs, reference **Color Board** graphs, a one-click **All Recipe Nodes** action that generates every supported catalog recipe graph, a **Catalog Coverage Report** text datablock that lists native/compositor/rendered fallback coverage plus FFmpeg-to-Blender translation coverage, connected native color-room graph, sampled Color Management graph for exposure/gamma/white balance/view curves/display conversion, sampled real-frame color graph, diagnostic recommendation graph, palette-identity color graph, reference-matched color graph, animated color-timeline match graph, FFmpeg-translated color graph, keyframed lighting-normalizer graph, Color Space, Exposure, Brightness/Contrast, Color Balance, Color Correction, RGB Curves, Hue/Saturation/Value, Hue Correct, Tone Map, display conversion, channel split/combine, luma/normalize monitor nodes, Directional Blur, reusable node groups, Levels, Viewer, Output File, and a full native node library organized by color, restoration, transform, matte, input/output, and utility groups.
- Native restoration nodes: Stabilize, Movie Distortion, Denoise, Despeckle, Bilateral Blur, Anti-Aliasing, plus broader coverage for Blender matte, transform, alpha, and utility compositor nodes where they are applicable to video finishing.
- Blender-native color recipes: auto enhance, neutral grade, punchy color, soft contrast, exposure lift, gamma up/down, warm/cool balance.
- Blender-native Color Management tools: sampled real-frame scene profile plus AgX balanced, AgX punch, Filmic soft, Standard video, warm review, and view-curve contrast presets.
- FFmpeg-to-Blender translation: supported FFmpeg color intent (`eq`, `hue`, `huesaturation`, `colorchannelmixer`, `curves`, `colorlevels`, `colorbalance`, `normalize`, `colorcorrect`, `colorcontrast`, `selectivecolor`, `monochrome`, `colorize`, `grayworld`, `negate`, `chromahold`, `colorhold`, `hsvhold`, simple `lut`/`lutrgb`/`lutyuv`, `histeq`, `vibrance`, `exposure`, `colortemperature`, `limiter`, `tonemap`, `colorspace`, `colormatrix`, `setparams`, `setrange`) is converted into native live Blender VSE modifier stacks, Blender color-management settings, and compositor color nodes from the **Native Color Chain Translation**, **FFmpeg Color Workflow**, and **Translated** compositor controls; non-native temporal filters stay in rendered restoration.
- Restoration: deflicker, lighting normalizer, denoise, sharpen restoration, deinterlace, quick deshake, two-pass vidstab stabilization.
- Motion and output: 2x Lanczos upscale, 1080p normalize scale, 60 fps interpolation, temporal smoothing.

Generated videos are written to `video_toolkit_outputs/` by default and are ignored by Git.

## End-User Verification

`scripts/end_user_blender_preview_test.py` opens a real MP4 in Blender's Video Sequencer, selects the movie strip, applies live Blender color tools through the same operators the UI buttons use, translates an FFmpeg-style color chain into native Blender modifiers, runs the one-click FFmpeg Color Workflow, applies a native Color Management preset, applies sampled real-frame Color Management, writes a color diagnostics report, applies the diagnostic grade recommendations, applies sampled native white balance/color-cast correction, sampled levels/gamma normalization, sampled hue/chroma balancing, the combined sampled pro grade, the sidecar Primary Color Board, the dynamic Sampled Color Board, and the reference-matched Color Board, edits the resulting live modifier properties, renders before/after Sequencer preview frames to PNG, and fails if the pixels do not change. It also creates Blender-native static, sampled recommended recipe mix, one-click professional workflow, FFmpeg workflow, sidebar-selected catalog recipe, professional color-board recipe, individual catalog color-recipe, all catalog color-recipe, connected native color-room, sampled Color Management, sampled dynamic color-board, reference color-board, sampled grade, diagnostic, palette-identity, keyframed lighting-normalizer, animated color-timeline match, reference-matched, and FFmpeg-translated compositor color graphs, writes the catalog coverage report, creates a restoration graph, and builds the full native node library from that selected strip.

`scripts/end_user_full_ui_operator_matrix.py` is the exhaustive real-video UI matrix. It opens a real MP4 and reference strip in Blender, then invokes every catalog Apply button, every compositor-compatible catalog Nodes action, every sidecar section/group selector, the sidecar Apply/Nodes buttons, strip and modifier controls, all Color Management presets, sampled analysis tools, color/reference matching, lighting normalization, FFmpeg color-chain translation, every compositor stack, rendered restoration/output tools, and preview pixel proof. It writes `tests/output/full_ui_matrix/report.json` with exact pass/fail evidence for every item and `tests/output/full_ui_matrix/report.md` with a readable end-user summary of the UI coverage, native Color Management values, FFmpeg-to-Blender translation, rendered outputs, and before/after preview pixel proof.

`scripts/blender_native_coverage.py` audits the installed Blender build directly. It verifies every VSE color modifier used by the add-on, every tracked Blender compositor video node can be created in Blender 5.2, and no creatable Blender 5.2 compositor node is missing from the native node library classification.

`scripts/capture_blender_ui.py` opens Blender's Sequencer with a selected movie strip and captures the **Video Effects** sidecar mini-tab UI to `tests/output/blender_ui/video_filters_panel_open.png`.

`scripts/open_blender_video_filters.py` opens Blender for manual checking, registers the add-on from this checkout, selects a real video strip and reference strip in the Sequencer, applies diagnostic grade plus the one-click professional workflow, FFmpeg Color Workflow, Primary Color Board, Six-Vector Hue Board, Broadcast-Safe Finish, sampled Color Management, white-balance, levels/gamma, hue/chroma, pro-grade tools, Sampled Color Board, Reference Color Board, connected native color-room nodes, sampled recommended recipe mix nodes, color-board compositor recipe nodes, catalog color-recipe compositor nodes, sampled Color Management compositor nodes, sampled dynamic Color Board nodes, reference Color Board nodes, sampled compositor color nodes, diagnostic compositor grade nodes, palette-identity compositor color nodes, reference-matched compositor color nodes, animated color-timeline match compositor nodes, FFmpeg-translated compositor color nodes, and keyframed lighting-normalizer compositor nodes, and leaves the Sequencer **Video Effects** sidebar tab available instead of opening a detached panel.
