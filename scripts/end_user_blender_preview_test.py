#!/usr/bin/env python3
"""Exercise the add-on like an end user inside Blender on a real MP4.

The test opens real footage in the Video Sequencer, selects the movie strip,
invokes the same Blender operators the UI buttons call, edits live Blender
modifier values, renders before/after preview frames, and fails if the rendered
preview pixels do not change.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(os.environ.get("BLENDER", ROOT / ".local" / "blender" / "blender"))
DEFAULT_VIDEO = ROOT / "tests" / "fixtures" / "real_user_video.mp4"
DEFAULT_OUTPUT = ROOT / "tests" / "output" / "end_user_preview"
SAMPLE_URLS = (
    "https://filesamples.com/samples/video/mp4/sample_640x360.mp4",
    "https://samplelib.com/lib/preview/mp4/sample-5s.mp4",
    "https://media.w3.org/2010/05/sintel/trailer.mp4",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, default=Path(os.environ.get("VIDEO_TOOLKIT_REAL_VIDEO", DEFAULT_VIDEO)))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    if not BLENDER.exists():
        raise SystemExit(f"Blender not found: {BLENDER}. Run scripts/download_blender.py first.")
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg and ffprobe are required for the end-user preview test")

    video = _ensure_real_video(args.video)
    _probe(video)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    reference_video = _make_reference_video(video, output_dir / "reference_lighting_match.mp4")

    script = _blender_script(video, reference_video, output_dir)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        script_path = Path(handle.name)
    try:
        result = subprocess.run(
            [str(BLENDER), "--background", "--factory-startup", "--python", str(script_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        blender_output = result.stdout + result.stderr
        if result.returncode != 0 or "Traceback (most recent call last):" in blender_output or "AssertionError" in blender_output:
            return result.returncode or 1
    finally:
        script_path.unlink(missing_ok=True)
    print(output_dir / "report.json")
    return 0


def _ensure_real_video(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for url in SAMPLE_URLS:
        try:
            print(f"Downloading real MP4 sample: {url}")
            with urllib.request.urlopen(url, timeout=45) as response, path.open("wb") as handle:
                shutil.copyfileobj(response, handle)
            if path.stat().st_size > 0:
                return path
        except Exception as exc:  # pragma: no cover - network fallback path
            last_error = exc
            path.unlink(missing_ok=True)
    raise SystemExit(f"Could not download a real MP4 sample: {last_error}")


def _probe(path: Path) -> None:
    subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,codec_name",
            "-of",
            "default=nw=1",
            str(path),
        ],
        check=True,
    )


def _make_reference_video(source: Path, output: Path) -> Path:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i",
            str(source),
            "-an",
            "-vf",
            "colorchannelmixer=rr=1.08:gg=1.00:bb=0.90,eq=brightness=0.10:contrast=1.05:saturation=1.02",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            str(output),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return output


def _blender_script(video: Path, reference_video: Path, output_dir: Path) -> str:
    before = output_dir / "before_live_edit.png"
    after = output_dir / "after_live_edit.png"
    translated = output_dir / "after_native_color_chain.png"
    translated_workflow = output_dir / "after_ffmpeg_color_workflow.png"
    color_managed = output_dir / "after_color_management_preset.png"
    sampled_color_management = output_dir / "after_sampled_color_management.png"
    recommended_recipe_mix = output_dir / "after_recommended_recipe_mix.png"
    professional_workflow = output_dir / "after_professional_color_workflow.png"
    diagnostic_grade = output_dir / "after_diagnostic_grade.png"
    sampled_white_balance_base = output_dir / "before_sampled_white_balance.png"
    sampled_white_balance = output_dir / "after_sampled_white_balance.png"
    sampled_levels_gamma_base = output_dir / "before_sampled_levels_gamma.png"
    sampled_levels_gamma = output_dir / "after_sampled_levels_gamma.png"
    sampled_hue_chroma_base = output_dir / "before_sampled_hue_chroma.png"
    sampled_hue_chroma = output_dir / "after_sampled_hue_chroma.png"
    sampled_pro_grade_base = output_dir / "before_sampled_pro_grade.png"
    sampled_pro_grade = output_dir / "after_sampled_pro_grade.png"
    master_color_wheels = output_dir / "after_master_color_wheels.png"
    primary_color_board = output_dir / "after_primary_color_board.png"
    sampled_color_board = output_dir / "after_sampled_color_board.png"
    reference_color_board_base = output_dir / "before_reference_color_board.png"
    reference_color_board = output_dir / "after_reference_color_board.png"
    blend = output_dir / "end_user_preview.blend"
    report = output_dir / "report.json"
    return f"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, {str(ROOT)!r})
import bpy
import video_toolkit
from video_toolkit.compositor import compositor_node_types
from video_toolkit.ffmpeg_native import NATIVE_FFMPEG_COMPOSITOR_FILTERS, NATIVE_FFMPEG_FILTERS

video_toolkit.register()
scene = bpy.context.scene
scene.sequence_editor_create()
editor = scene.sequence_editor
strip = editor.strips.new_movie(
    name='END USER SELECTED REAL VIDEO',
    filepath={str(video)!r},
    channel=1,
    frame_start=1,
)
reference_strip = editor.strips.new_movie(
    name='END USER REFERENCE LIGHTING VIDEO',
    filepath={str(reference_video)!r},
    channel=2,
    frame_start=1,
)
reference_strip.mute = True
for candidate in editor.strips_all:
    candidate.select = False
strip.select = True
editor.active_strip = strip

scene.frame_current = min(strip.frame_final_start + 24, strip.frame_final_end - 1)
scene.frame_start = strip.frame_final_start
scene.frame_end = strip.frame_final_end
scene.render.use_sequencer = True
scene.render.resolution_x = 320
scene.render.resolution_y = 180
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'

def render_preview(path):
    if hasattr(scene.render, "use_compositing"):
        scene.render.use_compositing = False
    try:
        bpy.ops.sequencer.refresh_all()
    except Exception:
        pass
    scene.frame_set(scene.frame_current)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(path), check_existing=False)
    pixels = list(image.pixels)
    channels = len(pixels) // 4
    stats = {{
        'r': sum(pixels[0::4]) / channels,
        'g': sum(pixels[1::4]) / channels,
        'b': sum(pixels[2::4]) / channels,
        'luma': sum(0.2126 * pixels[i] + 0.7152 * pixels[i + 1] + 0.0722 * pixels[i + 2] for i in range(0, len(pixels), 4)) / channels,
        'pixels': channels,
    }}
    bpy.data.images.remove(image)
    return stats

before_stats = render_preview({str(before)!r})

for candidate in editor.strips_all:
    candidate.select = False
strip.select = True
reference_strip.select = True
editor.active_strip = strip
reference_color_board_base_stats = render_preview({str(reference_color_board_base)!r})

result = bpy.ops.video_toolkit.apply_reference_color_board()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_reference_color_board.startswith('reference color board to')
reference_color_board_summary = scene.video_toolkit_last_reference_color_board
reference_color_board_modifier_types = [
    modifier.type for modifier in strip.modifiers if modifier.name.startswith('VTK Reference Color Board')
]
assert reference_color_board_modifier_types == [
    'WHITE_BALANCE',
    'BRIGHT_CONTRAST',
    'COLOR_BALANCE',
    'COLOR_BALANCE',
    'CURVES',
    'HUE_CORRECT',
    'TONEMAP',
    'CURVES',
    'HUE_CORRECT',
], reference_color_board_modifier_types
reference_color_board_node_count = scene.get('video_toolkit_last_reference_color_board_node_count', 0)
assert reference_color_board_node_count >= 10, reference_color_board_node_count
reference_color_board_node_types = [
    node.bl_idname
    for node in (scene.compositing_node_group if hasattr(scene, 'compositing_node_group') else scene.node_tree).nodes
    if node.name.startswith('VTK Reference Color Board ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueCorrect',
    'CompositorNodeTonemap',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in reference_color_board_node_types, required
reference_color_board_stats = render_preview({str(reference_color_board)!r})
reference_color_board_diff = (
    abs(reference_color_board_stats['r'] - reference_color_board_base_stats['r'])
    + abs(reference_color_board_stats['g'] - reference_color_board_base_stats['g'])
    + abs(reference_color_board_stats['b'] - reference_color_board_base_stats['b'])
)
assert reference_color_board_diff > 0.001, f'Reference Color Board did not visibly change preview pixels: {{reference_color_board_diff}}'
result = bpy.ops.video_toolkit.clear_live_modifiers()
assert result == {{'FINISHED'}}, result
for candidate in editor.strips_all:
    candidate.select = False
strip.select = True
editor.active_strip = strip

result = bpy.ops.video_toolkit.apply_filter(filter_id='auto_enhance')
assert result == {{'FINISHED'}}, result
assert editor.active_strip == strip
assert strip.select

edited = []
for modifier in strip.modifiers:
    if modifier.name.startswith('VTK Auto Enhance') and modifier.type == 'BRIGHT_CONTRAST':
        modifier.bright = 0.08
        modifier.contrast = 18.0
        edited.append(modifier.name)
    elif modifier.name.startswith('VTK Auto Enhance') and modifier.type == 'COLOR_BALANCE':
        modifier.color_balance.gamma = (1.14, 1.10, 1.06)
        modifier.color_balance.gain = (1.10, 1.08, 1.04)
        modifier.color_multiply = 1.06
        edited.append(modifier.name)
assert edited, 'No live modifiers were edited'

after_stats = render_preview({str(after)!r})
diff = abs(after_stats['r'] - before_stats['r']) + abs(after_stats['g'] - before_stats['g']) + abs(after_stats['b'] - before_stats['b'])
assert diff > 0.015, f'Live edit did not visibly change preview pixels: {{diff}}'

result = bpy.ops.video_toolkit.apply_filter(filter_id='native_all_color_tools')
assert result == {{'FINISHED'}}, result
types = [modifier.type for modifier in strip.modifiers if modifier.name.startswith('VTK ')]
for required in ['BRIGHT_CONTRAST', 'COLOR_BALANCE', 'TONEMAP', 'WHITE_BALANCE', 'CURVES', 'HUE_CORRECT', 'MASK']:
    assert required in types, required
for filter_id in ['luma_s_curve', 'green_cast_repair', 'red_gamma_trim']:
    result = bpy.ops.video_toolkit.apply_filter(filter_id=filter_id)
    assert result == {{'FINISHED'}}, result
primary_correction_types = [
    modifier.type
    for modifier in strip.modifiers
    if (
        modifier.name.startswith('VTK Luma S-Curve')
        or modifier.name.startswith('VTK Green Cast Repair')
        or modifier.name.startswith('VTK Red Gamma Trim')
    )
]
assert {{'CURVES', 'COLOR_BALANCE', 'WHITE_BALANCE'}}.issubset(set(primary_correction_types))

scene.video_toolkit_ffmpeg_chain = (
    'colorspace=iall=bt709:all=bt709:irange=tv:range=pc,'
    'colorspace_cuda=range=pc,'
    'normalize=smoothing=24:independence=0.7:strength=0.55,'
    'eq=contrast=1.12:saturation=1.08:gamma=1.02,'
    'colorbalance=rs=0.05:bm=0.03:bh=-0.04:pl=1,'
    'colorcorrect=rl=0.05:bl=-0.03:rh=0.02:bh=-0.02:saturation=1.05,'
    'colorcontrast=rc=0.12:gm=-0.04:by=0.08:rcw=0.5:gmw=0.35:byw=0.45:pl=1,'
    'selectivecolor=reds=0.08 -0.03 -0.02 0.00:blues=-0.03 0.01 0.08 0.02:whites=0.01 0.00 -0.06 0.01,'
    'colortemperature=temperature=5600:mix=0.55,'
    'greyedge=difford=2:minknorm=5:sigma=2,'
    'procamp_vaapi=brightness=8:contrast=1.18:saturation=1.14:hue=4,'
    'tonemap_opencl=tonemap=mobius:param=0.35:desat=0.45:peak=600:transfer=bt709:matrix=bt709:primaries=bt709:range=pc,'
    'tonemap_vaapi=transfer=bt709:matrix=bt709:primaries=bt709:range=pc,'
    'lut1d=file=warm_print.spi1d:interp=cubic,'
    'lut3d=file=teal_orange.cube:interp=tetrahedral,'
    'haldclut=interp=tetrahedral:clut=all,'
    'colormap=patch_size=64x64:nb_patches=32:type=absolute:kernel=weuclidean,'
    'chromakey=color=green:similarity=0.12:blend=0.04,'
    'chromakey_cuda=color=green:similarity=0.12:blend=0.04,'
    'colorkey=color=blue:similarity=0.10:blend=0.03,'
    'colorkey_opencl=color=blue:similarity=0.10:blend=0.03,'
    'hsvkey=hue=210:sat=0.75:val=0.85:similarity=0.10:blend=0.02,'
    'lumakey=threshold=0.20:tolerance=0.08:softness=0.02,'
    'despill=type=green:mix=0.65:expand=0.12:green=-1.0,'
    'backgroundkey=threshold=0.08:similarity=0.12:blend=0.04,'
    'threshold=planes=7,'
    'maskedthreshold=threshold=2048:planes=7:mode=abs,'
    "blend=all_mode=overlay:all_opacity=0.35,"
    "blend_vulkan=all_mode=multiply:all_opacity=0.42,"
    "tblend=all_mode=average:all_opacity=0.45,"
    "lut2=c0='(x+y)/2':c1='(x+y)/2':c2='(x+y)/2':c3=x,"
    "tlut2=c0='(x+y)/2':c1='(x+y)/2':c2='(x+y)/2':c3=x,"
    "maskedmerge=planes=15,"
    "mergeplanes=map0p=2:map1p=1:map2p=0:map3p=3,"
    'rgbashift=rh=4:rv=-2:bh=-3:bv=2,'
    'chromashift=cbh=2:cbv=-1:crh=-2:crv=1,'
    'chromaber_vulkan=dist_x=2.0:dist_y=-1.0,'
    'alphaextract,'
    'alphamerge,'
    'extractplanes=planes=y,'
    'premultiply,'
    'unpremultiply,'
    'shuffleplanes=map0=2:map1=1:map2=0:map3=3,'
    'elbg=l=64:n=2:seed=17,'
    'unsharp=5:5:0.45:3:3:0.20,'
    'sobel=scale=1.2:delta=0.02,'
    'prewitt=scale=0.9:delta=0.01,'
    'kirsch=scale=0.8,'
    'edgedetect=high=0.20:low=0.08:mode=wires,'
    'erosion=coordinates=255:threshold0=64000:threshold1=64000:threshold2=64000,'
    'dilation=coordinates=255:threshold0=64000:threshold1=64000:threshold2=64000,'
    'convolution=0m="0 -1 0 -1 5 -1 0 -1 0":0rdiv=1:0bias=0,'
    'convolution_opencl=0m="0 -1 0 -1 5 -1 0 -1 0":0rdiv=1:0bias=0,'
    'avgblur=sizeX=4:sizeY=6,'
    'boxblur=lr=3:lp=2,'
    'gblur=sigma=1.2:steps=2:sigmaV=0.8,'
    'smartblur=lr=2:ls=0.8:lt=8,'
    'sab=lr=2:lpfr=1:ls=12,'
    'yaepblur=r=4:s=192,'
    'dblur=angle=30:radius=12,'
    'scale=960:540,'
    'crop=w=1280:h=720:x=320:y=180,'
    'rotate=angle=PI/6,'
    'transpose=clock,'
    'hflip,'
    'vflip,'
    'lenscorrection=k1=-0.12:k2=0.04:cx=0.45:cy=0.55,'
    'hqdn3d=1.5:1.5:6:6,'
    'nlmeans=s=2.5:p=7:r=9,'
    'bm3d=sigma=3:group=8:range=12,'
    'owdenoise=ls=2:cs=1.5,'
    'vaguedenoiser=threshold=2.5:percent=80,'
    'atadenoise=s=9,'
    'median=radius=3:radiusV=5:percentile=0.55,'
    'dedot=lt=0.08:tl=0.09:tc=0.06:ct=0.02,'
    'deband=1thr=0.03:2thr=0.025:3thr=0.02:range=20,'
    'deblock=block=16:alpha=0.12:beta=0.08,'
    'deflicker=s=12:m=median,'
    'bwdif=mode=send_frame:parity=auto:deint=all,'
    'yadif=mode=send_frame:parity=auto:deint=all,'
    'deshake=rx=16:ry=16,'
    'vidstabdetect=shakiness=5:accuracy=15:result=motion.trf,'
    'vidstabtransform=input=motion.trf:smoothing=30:zoom=2,'
    "tmix=frames=3:weights='1 2 1',"
    'fps=fps=30:round=near,'
    'framerate=fps=60,'
    'minterpolate=fps=60:mi_mode=mci,'
    'blackdetect=d=1.0:pic_th=0.96:pix_th=0.08,'
    'blackdetect_vulkan=d=1.0:pic_th=0.96:pix_th=0.08,'
    'blackframe=amount=96:threshold=28,'
    'blockdetect=period_min=3:period_max=24:planes=1,'
    'blurdetect=high=0.12:low=0.06:radius=40:block_pct=80:planes=1,'
    'cropdetect=limit=0.094:round=16:reset=30:skip=2,'
    'bbox=min_val=16,'
    'bitplanenoise=bitplane=1:filter=1,'
    'freezedetect=n=0.001:d=2,'
    'scdet=threshold=10:sc_pass=0,'
    'scdet_vulkan=threshold=10:sc_pass=0,'
    'vfrdet,'
    'idet=intl_thres=1.04:prog_thres=1.5:rep_thres=3,'
    'identity=eof_action=repeat:repeatlast=1:ts_sync_mode=nearest,'
    'ssim=stats_file=vtk_ssim.log:eof_action=repeat:repeatlast=1:ts_sync_mode=nearest,'
    'psnr=stats_file=vtk_psnr.log:stats_version=2:output_max=1:eof_action=repeat,'
    'xpsnr=stats_file=vtk_xpsnr.log:eof_action=repeat,'
    'corr=eof_action=repeat:repeatlast=1,'
    'msad=eof_action=repeat:repeatlast=1,'
    'xcorrelate=planes=7:secondary=all:eof_action=repeat,'
    'pseudocolor=preset=viridis:opacity=0.75:index=1,'
    'histeq=strength=0.22:intensity=0.20:antibanding=1,'
    'zscale=primariesin=bt709:transferin=bt709:matrixin=bt709:rangein=limited:primaries=bt2020:transfer=bt2020-10:matrix=bt2020nc:range=full'
)
result = bpy.ops.video_toolkit.translate_ffmpeg_chain()
assert result == {{'FINISHED'}}, result
for required_filter in [
    'colorspace',
    'normalize',
    'eq',
    'colorbalance',
    'chromakey',
    'despill',
    'colorspace_cuda',
    'procamp_vaapi',
    'tonemap_opencl',
    'tonemap_vaapi',
    'backgroundkey',
    'threshold',
    'blend',
    'blend_vulkan',
    'tblend',
    'lut2',
    'tlut2',
    'maskedmerge',
    'mergeplanes',
    'rgbashift',
    'chromaber_vulkan',
    'chromakey_cuda',
    'colorkey_opencl',
    'convolution_opencl',
    'alphamerge',
    'blackdetect',
    'blackframe',
    'blockdetect',
    'blurdetect',
    'cropdetect',
    'bbox',
    'bitplanenoise',
    'freezedetect',
    'scdet',
    'vfrdet',
    'idet',
    'deflicker',
    'bwdif',
    'yadif',
    'deshake',
    'vidstabdetect',
    'vidstabtransform',
    'tmix',
    'fps',
    'framerate',
    'minterpolate',
    'identity',
    'ssim',
    'psnr',
    'xpsnr',
    'corr',
    'msad',
    'xcorrelate',
    'unsharp',
    'hqdn3d',
    'pseudocolor',
    'zscale',
]:
    assert required_filter in scene.video_toolkit_last_translation, required_filter
compositor_node_count = int(
    scene.video_toolkit_last_translation.split('compositor-native node(s): ', 1)[1].split(';', 1)[0]
)
assert compositor_node_count >= 67, scene.video_toolkit_last_translation
assert 'color management:' in scene.video_toolkit_last_translation
translated_types = [modifier.type for modifier in strip.modifiers if modifier.name.startswith('VTK Translated Color Chain')]
for required in ['BRIGHT_CONTRAST', 'COLOR_BALANCE', 'HUE_CORRECT', 'TONEMAP', 'WHITE_BALANCE']:
    assert required in translated_types, required
translated_stats = render_preview({str(translated)!r})
translated_diff = (
    abs(translated_stats['r'] - before_stats['r'])
    + abs(translated_stats['g'] - before_stats['g'])
    + abs(translated_stats['b'] - before_stats['b'])
)
assert translated_diff > 0.015, f'Translated live color chain did not visibly change preview pixels: {{translated_diff}}'
result = bpy.ops.video_toolkit.apply_translated_color_workflow()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_translated_workflow.startswith('translated color workflow')
translated_workflow_summary = scene.video_toolkit_last_translated_workflow
translated_workflow_supported = scene.get('video_toolkit_last_translated_workflow_supported_filters', '').split(',')
translated_workflow_node_count = scene.get('video_toolkit_last_translated_workflow_node_count', 0)
assert translated_workflow_node_count >= 10
assert 'colorspace' in translated_workflow_supported
assert 'colorspace_cuda' in translated_workflow_supported
assert 'procamp_vaapi' in translated_workflow_supported
assert 'tonemap_opencl' in translated_workflow_supported
assert 'tonemap_vaapi' in translated_workflow_supported
assert 'histeq' in translated_workflow_supported
assert 'greyedge' in translated_workflow_supported
assert 'chromakey' in translated_workflow_supported
assert 'chromakey_cuda' in translated_workflow_supported
assert 'colorkey' in translated_workflow_supported
assert 'colorkey_opencl' in translated_workflow_supported
assert 'hsvkey' in translated_workflow_supported
assert 'lumakey' in translated_workflow_supported
assert 'backgroundkey' in translated_workflow_supported
assert 'blend_vulkan' in translated_workflow_supported
assert 'rgbashift' in translated_workflow_supported
assert 'chromashift' in translated_workflow_supported
assert 'chromaber_vulkan' in translated_workflow_supported
assert 'alphaextract' in translated_workflow_supported
assert 'alphamerge' in translated_workflow_supported
assert 'extractplanes' in translated_workflow_supported
assert 'identity' in translated_workflow_supported
assert 'ssim' in translated_workflow_supported
assert 'psnr' in translated_workflow_supported
assert 'xpsnr' in translated_workflow_supported
assert 'corr' in translated_workflow_supported
assert 'msad' in translated_workflow_supported
assert 'xcorrelate' in translated_workflow_supported
assert 'premultiply' in translated_workflow_supported
assert 'unpremultiply' in translated_workflow_supported
assert 'shuffleplanes' in translated_workflow_supported
assert 'elbg' in translated_workflow_supported
assert 'unsharp' in translated_workflow_supported
assert 'sobel' in translated_workflow_supported
assert 'prewitt' in translated_workflow_supported
assert 'kirsch' in translated_workflow_supported
assert 'edgedetect' in translated_workflow_supported
assert 'erosion' in translated_workflow_supported
assert 'dilation' in translated_workflow_supported
assert 'convolution_opencl' in translated_workflow_supported
assert 'blackdetect' in translated_workflow_supported
assert 'blackframe' in translated_workflow_supported
assert 'blockdetect' in translated_workflow_supported
assert 'blurdetect' in translated_workflow_supported
assert 'cropdetect' in translated_workflow_supported
assert 'bbox' in translated_workflow_supported
assert 'bitplanenoise' in translated_workflow_supported
assert 'freezedetect' in translated_workflow_supported
assert 'scdet' in translated_workflow_supported
assert 'vfrdet' in translated_workflow_supported
assert 'idet' in translated_workflow_supported
assert 'deflicker' in translated_workflow_supported
assert 'bwdif' in translated_workflow_supported
assert 'yadif' in translated_workflow_supported
assert 'deshake' in translated_workflow_supported
assert 'vidstabdetect' in translated_workflow_supported
assert 'vidstabtransform' in translated_workflow_supported
assert 'tmix' in translated_workflow_supported
assert 'fps' in translated_workflow_supported
assert 'framerate' in translated_workflow_supported
assert 'minterpolate' in translated_workflow_supported
assert 'pseudocolor' in translated_workflow_supported
assert 'zscale' in translated_workflow_supported
translated_workflow_modifier_types = [
    modifier.type
    for modifier in strip.modifiers
    if modifier.name.startswith('VTK Translated Color Workflow')
]
for required in ['BRIGHT_CONTRAST', 'COLOR_BALANCE', 'HUE_CORRECT', 'TONEMAP', 'WHITE_BALANCE']:
    assert required in translated_workflow_modifier_types, required
translated_workflow_tree = scene.compositing_node_group if hasattr(scene, 'compositing_node_group') else scene.node_tree
translated_workflow_node_types = [
    node.bl_idname
    for node in translated_workflow_tree.nodes
    if node.name.startswith('VTK Translated Color Workflow ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueCorrect',
    'CompositorNodeColorCorrection',
    'CompositorNodeChromaMatte',
    'CompositorNodeColorMatte',
    'CompositorNodeDiffMatte',
    'CompositorNodeFilter',
    'CompositorNodeLumaMatte',
    'CompositorNodeRGB',
    'CompositorNodeSeparateColor',
    'CompositorNodeTranslate',
    'CompositorNodeCombineColor',
    'CompositorNodeRGBToBW',
    'CompositorNodePremulKey',
    'CompositorNodeTonemap',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in translated_workflow_node_types, required
translated_workflow_stats = render_preview({str(translated_workflow)!r})
translated_workflow_diff = (
    abs(translated_workflow_stats['r'] - translated_stats['r'])
    + abs(translated_workflow_stats['g'] - translated_stats['g'])
    + abs(translated_workflow_stats['b'] - translated_stats['b'])
)
assert translated_workflow_diff > 0.001, f'FFmpeg color workflow did not visibly change preview pixels: {{translated_workflow_diff}}'

result = bpy.ops.video_toolkit.apply_color_management_preset(preset_id='VIEW_CURVE_CONTRAST')
assert result == {{'FINISHED'}}, result
assert scene.view_settings.use_curve_mapping
assert 'View Curve Contrast' in scene.video_toolkit_last_color_management
color_management_summary = scene.video_toolkit_last_color_management
color_managed_stats = render_preview({str(color_managed)!r})
color_management_diff = (
    abs(color_managed_stats['r'] - translated_stats['r'])
    + abs(color_managed_stats['g'] - translated_stats['g'])
    + abs(color_managed_stats['b'] - translated_stats['b'])
)
assert color_management_diff > 0.001, f'Color Management preset did not visibly change preview pixels: {{color_management_diff}}'

result = bpy.ops.video_toolkit.apply_sampled_color_management()
assert result == {{'FINISHED'}}, result
assert scene.view_settings.use_curve_mapping
assert scene.video_toolkit_last_sampled_color_management.startswith('sampled color management')
sampled_color_management_summary = scene.video_toolkit_last_sampled_color_management
sampled_color_management_stats = render_preview({str(sampled_color_management)!r})
sampled_color_management_diff = (
    abs(sampled_color_management_stats['r'] - color_managed_stats['r'])
    + abs(sampled_color_management_stats['g'] - color_managed_stats['g'])
    + abs(sampled_color_management_stats['b'] - color_managed_stats['b'])
)
assert sampled_color_management_diff > 0.001, f'Sampled Color Management did not visibly change preview pixels: {{sampled_color_management_diff}}'

result = bpy.ops.video_toolkit.analyze_color(mode='PALETTE')
assert result == {{'FINISHED'}}, result
palette_types = [modifier.type for modifier in strip.modifiers if modifier.name.startswith('VTK Frame Color Identity')]
assert palette_types == ['WHITE_BALANCE', 'COLOR_BALANCE', 'CURVES', 'HUE_CORRECT', 'TONEMAP'], palette_types
assert 'palette #' in scene.video_toolkit_last_analysis
palette_summary = scene.video_toolkit_last_analysis
result = bpy.ops.video_toolkit.color_diagnostics()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_diagnostics.startswith('diagnosis')
diagnostics_text_name = scene.video_toolkit_last_diagnostics_text
assert diagnostics_text_name in bpy.data.texts
diagnostics_report = bpy.data.texts[diagnostics_text_name].as_string()
assert 'Video Toolkit Color Diagnostics' in diagnostics_report
assert 'Suggested native Blender tools' in diagnostics_report
result = bpy.ops.video_toolkit.recommend_catalog_recipes()
assert result == {{'FINISHED'}}, result
recipe_recommendations_name = scene.video_toolkit_last_recipe_recommendations
assert recipe_recommendations_name.startswith('VTK Recipe Recommendations')
assert recipe_recommendations_name in bpy.data.texts
recipe_recommendations_report = bpy.data.texts[recipe_recommendations_name].as_string()
assert 'Open Research Video Toolkit Recipe Recommendations' in recipe_recommendations_report
assert 'Top Blender-native recipes:' in recipe_recommendations_report
assert 'Frame stats:' in recipe_recommendations_report
recommended_recipe_ids = scene.get('video_toolkit_last_recommended_recipe_ids', '').split(',')
assert scene.video_toolkit_sidecar_tool in recommended_recipe_ids
assert any(recipe_id in recommended_recipe_ids for recipe_id in ('exposure_protect', 'hdr_tone_compress', 'levels_expand', 'live_contrast_pop'))
result = bpy.ops.video_toolkit.apply_recommended_recipe_mix()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_recommended_recipe_mix.startswith('recommended recipe mix')
recipe_mix_ids = scene.get('video_toolkit_last_recommended_recipe_mix_ids', '').split(',')
assert recipe_mix_ids
assert recipe_mix_ids[0] in recommended_recipe_ids
recipe_mix_types = [modifier.type for modifier in strip.modifiers if modifier.name.startswith('VTK Recommended Recipe Mix')]
assert recipe_mix_types, 'No recommended recipe mix modifiers were added'
result = bpy.ops.video_toolkit.create_recommended_recipe_mix_nodes()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_compositor_nodes.startswith('recommended recipe mix nodes')
recommended_recipe_mix_node_summary = scene.video_toolkit_last_compositor_nodes
recipe_mix_node_ids = scene.get('video_toolkit_last_recommended_recipe_mix_node_ids', '').split(',')
assert recipe_mix_node_ids == recipe_mix_ids
tree = scene.compositing_node_group if hasattr(scene, 'compositing_node_group') else scene.node_tree
recommended_recipe_mix_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Recommended Recipe Mix ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeBrightContrast',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in recommended_recipe_mix_node_types, required
assert any(
    required in recommended_recipe_mix_node_types
    for required in ('CompositorNodeColorBalance', 'CompositorNodeCurveRGB', 'CompositorNodeHueCorrect', 'CompositorNodeTonemap')
), recommended_recipe_mix_node_types
recommended_recipe_mix_stats = render_preview({str(recommended_recipe_mix)!r})
recommended_recipe_mix_diff = (
    abs(recommended_recipe_mix_stats['r'] - sampled_color_management_stats['r'])
    + abs(recommended_recipe_mix_stats['g'] - sampled_color_management_stats['g'])
    + abs(recommended_recipe_mix_stats['b'] - sampled_color_management_stats['b'])
)
assert recommended_recipe_mix_diff > 0.001, f'Recommended recipe mix did not visibly change preview pixels: {{recommended_recipe_mix_diff}}'
result = bpy.ops.video_toolkit.apply_professional_color_workflow()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_professional_workflow.startswith('professional color workflow')
professional_workflow_summary = scene.video_toolkit_last_professional_workflow
professional_workflow_recipe_ids = scene.get('video_toolkit_last_professional_workflow_recipe_ids', '').split(',')
assert professional_workflow_recipe_ids == recipe_mix_ids
professional_workflow_node_count = scene.get('video_toolkit_last_professional_workflow_node_count', 0)
assert professional_workflow_node_count >= 20
professional_workflow_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Professional Color Workflow ')
]
professional_color_management_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Professional Color Management ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeBrightContrast',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in professional_workflow_node_types, required
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeExposure',
    'CompositorNodeColorBalance',
    'CompositorNodeCurveRGB',
    'CompositorNodeConvertToDisplay',
    'CompositorNodeOutputFile',
]:
    assert required in professional_color_management_node_types, required
professional_workflow_stats = render_preview({str(professional_workflow)!r})
professional_workflow_diff = (
    abs(professional_workflow_stats['r'] - recommended_recipe_mix_stats['r'])
    + abs(professional_workflow_stats['g'] - recommended_recipe_mix_stats['g'])
    + abs(professional_workflow_stats['b'] - recommended_recipe_mix_stats['b'])
)
assert professional_workflow_diff > 0.001, f'Professional workflow did not visibly change preview pixels: {{professional_workflow_diff}}'
result = bpy.ops.video_toolkit.apply_diagnostic_grade()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_diagnostic_grade.startswith('diagnostic grade')
diagnostic_grade_types = [modifier.type for modifier in strip.modifiers if modifier.name.startswith('VTK Diagnostic Grade')]
assert diagnostic_grade_types, 'No diagnostic grade modifiers were added'
diagnostic_grade_stats = render_preview({str(diagnostic_grade)!r})
diagnostic_grade_diff = (
    abs(diagnostic_grade_stats['r'] - sampled_color_management_stats['r'])
    + abs(diagnostic_grade_stats['g'] - sampled_color_management_stats['g'])
    + abs(diagnostic_grade_stats['b'] - sampled_color_management_stats['b'])
)
assert diagnostic_grade_diff > 0.001, f'Diagnostic grade did not visibly change preview pixels: {{diagnostic_grade_diff}}'

result = bpy.ops.video_toolkit.clear_live_modifiers()
assert result == {{'FINISHED'}}, result
for candidate in editor.strips_all:
    candidate.select = False
strip.select = True
editor.active_strip = strip
sampled_white_balance_base_stats = render_preview({str(sampled_white_balance_base)!r})
result = bpy.ops.video_toolkit.apply_sampled_white_balance()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_sampled_white_balance.startswith('sampled white balance')
sampled_white_balance_types = [
    modifier.type for modifier in strip.modifiers if modifier.name.startswith('VTK Sampled White Balance')
]
assert sampled_white_balance_types == ['WHITE_BALANCE', 'COLOR_BALANCE', 'BRIGHT_CONTRAST', 'CURVES', 'HUE_CORRECT'], sampled_white_balance_types
sampled_white_balance_stats = render_preview({str(sampled_white_balance)!r})
sampled_white_balance_diff = (
    abs(sampled_white_balance_stats['r'] - sampled_white_balance_base_stats['r'])
    + abs(sampled_white_balance_stats['g'] - sampled_white_balance_base_stats['g'])
    + abs(sampled_white_balance_stats['b'] - sampled_white_balance_base_stats['b'])
)
assert sampled_white_balance_diff > 0.001, f'Sampled white balance did not visibly change preview pixels: {{sampled_white_balance_diff}}'

result = bpy.ops.video_toolkit.clear_live_modifiers()
assert result == {{'FINISHED'}}, result
for candidate in editor.strips_all:
    candidate.select = False
strip.select = True
editor.active_strip = strip
sampled_levels_gamma_base_stats = render_preview({str(sampled_levels_gamma_base)!r})
result = bpy.ops.video_toolkit.apply_sampled_levels_gamma()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_sampled_levels_gamma.startswith('sampled levels/gamma')
sampled_levels_gamma_types = [
    modifier.type for modifier in strip.modifiers if modifier.name.startswith('VTK Sampled Levels Gamma')
]
assert sampled_levels_gamma_types == ['CURVES', 'COLOR_BALANCE', 'BRIGHT_CONTRAST', 'TONEMAP', 'HUE_CORRECT'], sampled_levels_gamma_types
sampled_levels_gamma_stats = render_preview({str(sampled_levels_gamma)!r})
sampled_levels_gamma_diff = (
    abs(sampled_levels_gamma_stats['r'] - sampled_levels_gamma_base_stats['r'])
    + abs(sampled_levels_gamma_stats['g'] - sampled_levels_gamma_base_stats['g'])
    + abs(sampled_levels_gamma_stats['b'] - sampled_levels_gamma_base_stats['b'])
)
assert sampled_levels_gamma_diff > 0.001, f'Sampled levels/gamma did not visibly change preview pixels: {{sampled_levels_gamma_diff}}'

result = bpy.ops.video_toolkit.clear_live_modifiers()
assert result == {{'FINISHED'}}, result
for candidate in editor.strips_all:
    candidate.select = False
strip.select = True
editor.active_strip = strip
sampled_hue_chroma_base_stats = render_preview({str(sampled_hue_chroma_base)!r})
result = bpy.ops.video_toolkit.apply_sampled_hue_chroma()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_sampled_hue_chroma.startswith('sampled hue/chroma')
sampled_hue_chroma_types = [
    modifier.type for modifier in strip.modifiers if modifier.name.startswith('VTK Sampled Hue Chroma')
]
assert sampled_hue_chroma_types == ['HUE_CORRECT', 'COLOR_BALANCE', 'CURVES'], sampled_hue_chroma_types
sampled_hue_chroma_stats = render_preview({str(sampled_hue_chroma)!r})
sampled_hue_chroma_diff = (
    abs(sampled_hue_chroma_stats['r'] - sampled_hue_chroma_base_stats['r'])
    + abs(sampled_hue_chroma_stats['g'] - sampled_hue_chroma_base_stats['g'])
    + abs(sampled_hue_chroma_stats['b'] - sampled_hue_chroma_base_stats['b'])
)
assert sampled_hue_chroma_diff > 0.001, f'Sampled hue/chroma did not visibly change preview pixels: {{sampled_hue_chroma_diff}}'

pro_grade_strip = editor.strips.new_movie(
    name='END USER SAMPLED PRO GRADE REAL VIDEO',
    filepath={str(video)!r},
    channel=5,
    frame_start=1,
)
for candidate in editor.strips_all:
    candidate.select = False
pro_grade_strip.select = True
editor.active_strip = pro_grade_strip
sampled_pro_grade_base_stats = render_preview({str(sampled_pro_grade_base)!r})

result = bpy.ops.video_toolkit.apply_sampled_pro_grade()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_sampled_pro_grade.startswith('sampled pro grade')
sampled_pro_grade_types = [
    modifier.type for modifier in pro_grade_strip.modifiers if modifier.name.startswith('VTK Sampled Pro Grade')
]
assert sampled_pro_grade_types == [
    'WHITE_BALANCE', 'COLOR_BALANCE', 'CURVES', 'COLOR_BALANCE', 'BRIGHT_CONTRAST',
    'TONEMAP', 'HUE_CORRECT', 'COLOR_BALANCE', 'CURVES', 'HUE_CORRECT'
], sampled_pro_grade_types
sampled_pro_grade_stats = render_preview({str(sampled_pro_grade)!r})
sampled_pro_grade_diff = (
    abs(sampled_pro_grade_stats['r'] - sampled_pro_grade_base_stats['r'])
    + abs(sampled_pro_grade_stats['g'] - sampled_pro_grade_base_stats['g'])
    + abs(sampled_pro_grade_stats['b'] - sampled_pro_grade_base_stats['b'])
)
assert sampled_pro_grade_diff > 0.001, f'Sampled pro grade did not visibly change preview pixels: {{sampled_pro_grade_diff}}'
scene.video_toolkit_sidecar_group = 'LIVE_BLENDER_COLOR'
scene.video_toolkit_sidecar_tool = 'master_color_wheels'
result = bpy.ops.video_toolkit.apply_sidecar_tool()
assert result == {{'FINISHED'}}, result
master_color_wheels_modifier_types = [
    modifier.type
    for modifier in pro_grade_strip.modifiers
    if modifier.name.startswith('VTK Master Color Wheels')
]
assert master_color_wheels_modifier_types == [
    'BRIGHT_CONTRAST', 'COLOR_BALANCE', 'COLOR_BALANCE', 'WHITE_BALANCE', 'CURVES', 'TONEMAP', 'HUE_CORRECT'
], master_color_wheels_modifier_types
master_color_wheels_modifier_names = [
    modifier.name
    for modifier in pro_grade_strip.modifiers
    if modifier.name.startswith('VTK Master Color Wheels')
]
master_color_wheels_modifier_roles = [
    modifier.name.rsplit(' - ', 1)[-1]
    for modifier in pro_grade_strip.modifiers
    if modifier.name.startswith('VTK Master Color Wheels')
]
assert master_color_wheels_modifier_roles == [
    'Brightness Contrast',
    'Lift Gamma Gain',
    'ASC CDL Offset Power Slope',
    'White Balance',
    'RGB Curves',
    'Tone Map',
    'Hue Correct',
], master_color_wheels_modifier_roles
assert any(name.endswith('Lift Gamma Gain') for name in master_color_wheels_modifier_names)
assert any(name.endswith('ASC CDL Offset Power Slope') for name in master_color_wheels_modifier_names)
master_color_wheels_stats = render_preview({str(master_color_wheels)!r})
master_color_wheels_diff = (
    abs(master_color_wheels_stats['r'] - sampled_pro_grade_stats['r'])
    + abs(master_color_wheels_stats['g'] - sampled_pro_grade_stats['g'])
    + abs(master_color_wheels_stats['b'] - sampled_pro_grade_stats['b'])
)
assert master_color_wheels_diff > 0.001, f'Master Color Wheels did not visibly change preview pixels: {{master_color_wheels_diff}}'
result = bpy.ops.video_toolkit.create_sidecar_compositor_nodes()
assert result == {{'FINISHED'}}, result
master_color_wheels_compositor_summary = scene.video_toolkit_last_compositor_nodes
assert master_color_wheels_compositor_summary.startswith('tool compositor Master Color Wheels')
master_color_wheels_node_types = [
    node.bl_idname
    for node in (scene.compositing_node_group if hasattr(scene, 'compositing_node_group') else scene.node_tree).nodes
    if node.name.startswith('VTK Tool Master Color Wheels ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueCorrect',
    'CompositorNodeTonemap',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in master_color_wheels_node_types, required
scene.video_toolkit_sidecar_tool = 'primary_color_board'
result = bpy.ops.video_toolkit.apply_sidecar_tool()
assert result == {{'FINISHED'}}, result
primary_color_board_modifier_types = [
    modifier.type
    for modifier in pro_grade_strip.modifiers
    if modifier.name.startswith('VTK Primary Color Board')
]
for required in ['BRIGHT_CONTRAST', 'COLOR_BALANCE', 'CURVES', 'HUE_CORRECT', 'TONEMAP']:
    assert required in primary_color_board_modifier_types, required
primary_color_board_stats = render_preview({str(primary_color_board)!r})
primary_color_board_diff = (
    abs(primary_color_board_stats['r'] - sampled_pro_grade_stats['r'])
    + abs(primary_color_board_stats['g'] - sampled_pro_grade_stats['g'])
    + abs(primary_color_board_stats['b'] - sampled_pro_grade_stats['b'])
)
assert primary_color_board_diff > 0.001, f'Primary Color Board did not visibly change preview pixels: {{primary_color_board_diff}}'
result = bpy.ops.video_toolkit.create_sidecar_compositor_nodes()
assert result == {{'FINISHED'}}, result
primary_color_board_compositor_summary = scene.video_toolkit_last_compositor_nodes
assert primary_color_board_compositor_summary.startswith('tool compositor Primary Color Board')
primary_color_board_node_types = [
    node.bl_idname
    for node in (scene.compositing_node_group if hasattr(scene, 'compositing_node_group') else scene.node_tree).nodes
    if node.name.startswith('VTK Tool Primary Color Board ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueCorrect',
    'CompositorNodeTonemap',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in primary_color_board_node_types, required
result = bpy.ops.video_toolkit.apply_sampled_color_board()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_sampled_color_board.startswith('sampled color board')
sampled_color_board_summary = scene.video_toolkit_last_sampled_color_board
sampled_color_board_modifier_types = [
    modifier.type
    for modifier in pro_grade_strip.modifiers
    if modifier.name.startswith('VTK Sampled Color Board')
]
assert sampled_color_board_modifier_types == [
    'WHITE_BALANCE',
    'BRIGHT_CONTRAST',
    'COLOR_BALANCE',
    'COLOR_BALANCE',
    'CURVES',
    'HUE_CORRECT',
    'TONEMAP',
    'CURVES',
    'HUE_CORRECT',
], sampled_color_board_modifier_types
sampled_color_board_node_count = scene.get('video_toolkit_last_sampled_color_board_node_count', 0)
assert sampled_color_board_node_count >= 10, sampled_color_board_node_count
sampled_color_board_node_types = [
    node.bl_idname
    for node in (scene.compositing_node_group if hasattr(scene, 'compositing_node_group') else scene.node_tree).nodes
    if node.name.startswith('VTK Sampled Color Board ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueCorrect',
    'CompositorNodeTonemap',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in sampled_color_board_node_types, required
sampled_color_board_stats = render_preview({str(sampled_color_board)!r})
sampled_color_board_diff = (
    abs(sampled_color_board_stats['r'] - primary_color_board_stats['r'])
    + abs(sampled_color_board_stats['g'] - primary_color_board_stats['g'])
    + abs(sampled_color_board_stats['b'] - primary_color_board_stats['b'])
)
assert sampled_color_board_diff > 0.001, f'Sampled Color Board did not visibly change preview pixels: {{sampled_color_board_diff}}'
for candidate in editor.strips_all:
    candidate.select = False
strip.select = True
editor.active_strip = strip

result = bpy.ops.video_toolkit.normalize_lighting()
assert result == {{'FINISHED'}}, result
normalizer = next(modifier for modifier in strip.modifiers if modifier.name.startswith('VTK Live Flicker Normalizer'))
def action_keyframe_count(action, data_path):
    if hasattr(action, 'fcurves'):
        return sum(len(fcurve.keyframe_points) for fcurve in action.fcurves if fcurve.data_path == data_path)
    total = 0
    for layer in action.layers:
        for action_strip in layer.strips:
            for channelbag in action_strip.channelbags:
                total += sum(len(fcurve.keyframe_points) for fcurve in channelbag.fcurves if fcurve.data_path == data_path)
    return total
assert scene.animation_data is not None
assert scene.animation_data.action is not None
normalizer_keyframes = action_keyframe_count(scene.animation_data.action, normalizer.path_from_id('bright'))
assert normalizer_keyframes >= 2, normalizer_keyframes

for candidate in editor.strips_all:
    candidate.select = False
strip.select = True
reference_strip.select = True
editor.active_strip = strip
result = bpy.ops.video_toolkit.match_lighting_timeline()
assert result == {{'FINISHED'}}, result
timeline_match = next(modifier for modifier in strip.modifiers if modifier.name.startswith('VTK Live Timeline Match'))
timeline_match_keyframes = action_keyframe_count(scene.animation_data.action, timeline_match.path_from_id('bright'))
assert timeline_match_keyframes >= 2, timeline_match_keyframes

result = bpy.ops.video_toolkit.match_color_timeline()
assert result == {{'FINISHED'}}, result
color_timeline_match = next(modifier for modifier in strip.modifiers if modifier.name.startswith('VTK Live Color Timeline Match'))
color_timeline_gamma_keyframes = action_keyframe_count(scene.animation_data.action, color_timeline_match.color_balance.path_from_id('gamma'))
color_timeline_gain_keyframes = action_keyframe_count(scene.animation_data.action, color_timeline_match.color_balance.path_from_id('gain'))
assert color_timeline_gamma_keyframes >= 6, color_timeline_gamma_keyframes
assert color_timeline_gain_keyframes >= 6, color_timeline_gain_keyframes

result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type='COLOR')
assert result == {{'FINISHED'}}, result
if hasattr(scene, 'compositing_node_group'):
    tree = scene.compositing_node_group
else:
    tree = scene.node_tree
assert tree is not None, 'No compositor node tree was created'
color_node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK ')]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeExposure',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeColorCorrection',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueSat',
    'CompositorNodeHueCorrect',
    'CompositorNodeTonemap',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in color_node_types, required
assert any(node.bl_idname == 'CompositorNodeColorCorrection' and node.name == 'VTK Gamma Control' for node in tree.nodes), 'VTK Gamma Control'
assert len(tree.links) >= 12, f'Expected linked compositor color graph, got {{len(tree.links)}} links'

result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type='NATIVE_COLOR_ROOM')
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_compositor_nodes.startswith('native color room graph')
native_room_summary = scene.video_toolkit_last_compositor_nodes
native_room_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Native Color Room ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeExposure',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeColorCorrection',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueSat',
    'CompositorNodeHueCorrect',
    'CompositorNodeTonemap',
    'CompositorNodeConvertToDisplay',
    'CompositorNodeSeparateColor',
    'CompositorNodeCombineColor',
    'CompositorNodeRGBToBW',
    'CompositorNodeNormalize',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in native_room_node_types, required
assert any(node.bl_idname == 'CompositorNodeColorCorrection' and node.name == 'VTK Native Color Room Gamma' for node in tree.nodes), 'VTK Native Color Room Gamma'
native_room_links = len([link for link in tree.links if link.from_node.name.startswith('VTK Native Color Room ')])
assert native_room_links >= 16, native_room_links

scene.video_toolkit_sidecar_group = 'LIVE_BLENDER_COLOR'
scene.video_toolkit_sidecar_tool = 'live_gamma_grade'
result = bpy.ops.video_toolkit.create_sidecar_compositor_nodes()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_compositor_nodes.startswith('tool compositor Live Gamma Grade')
sidecar_recipe_summary = scene.video_toolkit_last_compositor_nodes
sidecar_recipe_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Tool Live Gamma Grade ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in sidecar_recipe_node_types, required

result = bpy.ops.video_toolkit.create_tool_compositor_nodes(filter_id='live_pro_color_stack')
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_compositor_nodes.startswith('tool compositor Live Pro Color Stack')
tool_recipe_summary = scene.video_toolkit_last_compositor_nodes
tool_recipe_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Tool Live Pro Color Stack ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeTonemap',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueCorrect',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in tool_recipe_node_types, required
tool_recipe_filter_ids = [
    node['video_toolkit_filter_id']
    for node in tree.nodes
    if node.name.startswith('VTK Tool Live Pro Color Stack ')
]
assert set(tool_recipe_filter_ids) == {{'live_pro_color_stack'}}, tool_recipe_filter_ids

result = bpy.ops.video_toolkit.create_tool_compositor_nodes(filter_id='channel_mixer_balance')
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_compositor_nodes.startswith('tool compositor Channel Mixer Balance')
channel_mixer_summary = scene.video_toolkit_last_compositor_nodes
channel_mixer_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Tool Channel Mixer Balance ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeSeparateColor',
    'ShaderNodeMath',
    'CompositorNodeCombineColor',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in channel_mixer_node_types, required
channel_mixer_matrix_nodes = [
    node for node in tree.nodes
    if node.name.startswith('VTK Tool Channel Mixer Balance Color Channel Mixer Matrix')
    and node.bl_idname == 'ShaderNodeMath'
]
assert len(channel_mixer_matrix_nodes) >= 15, len(channel_mixer_matrix_nodes)
channel_mixer_matrix_values = [
    node.get('video_toolkit_rgb_matrix', '')
    for node in channel_mixer_matrix_nodes
]
assert any('1.06,-0.02,-0.01' in matrix for matrix in channel_mixer_matrix_values), channel_mixer_matrix_values[:1]

result = bpy.ops.video_toolkit.create_tool_compositor_nodes(filter_id='native_colormatrix_601_to_709_pipeline')
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_compositor_nodes.startswith('tool compositor Matrix 601 to 709')
colormatrix_summary = scene.video_toolkit_last_compositor_nodes
colormatrix_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Tool Matrix 601 to 709 ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeSeparateColor',
    'ShaderNodeMath',
    'CompositorNodeCombineColor',
    'CompositorNodeConvertToDisplay',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in colormatrix_node_types, required
colormatrix_matrix_nodes = [
    node for node in tree.nodes
    if node.name.startswith('VTK Tool Matrix 601 to 709 Color Matrix smpte170m to bt709')
    and node.bl_idname == 'ShaderNodeMath'
]
assert len(colormatrix_matrix_nodes) >= 15, len(colormatrix_matrix_nodes)
colormatrix_matrix_values = [
    node.get('video_toolkit_rgb_matrix', '')
    for node in colormatrix_matrix_nodes
]
assert any('1.0864,-0.072349' in matrix for matrix in colormatrix_matrix_values), colormatrix_matrix_values[:1]

from video_toolkit.addon import _tool_has_compositor_stack
from video_toolkit.catalog import all_tools
expected_all_recipe_ids = [tool.id for tool in all_tools() if _tool_has_compositor_stack(tool)]
result = bpy.ops.video_toolkit.create_all_tool_compositor_nodes()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_compositor_nodes.startswith('all tool compositor recipes:')
assert f'{{len(expected_all_recipe_ids)}} tools' in scene.video_toolkit_last_compositor_nodes
all_recipe_summary = scene.video_toolkit_last_compositor_nodes
all_recipe_ids = scene.get('video_toolkit_last_compositor_recipe_ids', '').split(',')
assert all_recipe_ids == expected_all_recipe_ids, (len(all_recipe_ids), len(expected_all_recipe_ids))
assert 'live_pro_color_stack' in all_recipe_ids
assert 'native_white_balance_editor' in all_recipe_ids
assert 'native_mask_slot' not in all_recipe_ids
result = bpy.ops.video_toolkit.write_catalog_coverage_report()
assert result == {{'FINISHED'}}, result
catalog_report_name = scene.video_toolkit_last_catalog_report
assert catalog_report_name == 'VTK Video Effects Catalog Coverage'
assert catalog_report_name in bpy.data.texts
catalog_coverage_report = bpy.data.texts[catalog_report_name].as_string()
assert f'Compositor-compatible catalog recipes: {{len(expected_all_recipe_ids)}}' in catalog_coverage_report
assert 'VSE-only native tools:' in catalog_coverage_report
assert 'native_mask_slot: Mask Slot' in catalog_coverage_report
assert 'Rendered fallback tools:' in catalog_coverage_report
assert f'Native-translated FFmpeg filters: {{len(NATIVE_FFMPEG_FILTERS)}}' in catalog_coverage_report
assert 'Installed FFmpeg video filters: ' in catalog_coverage_report
assert 'Missing installed FFmpeg video filters: None' in catalog_coverage_report
assert 'Native compositor-only FFmpeg filters: ' + ', '.join(NATIVE_FFMPEG_COMPOSITOR_FILTERS) in catalog_coverage_report
assert 'Native Color Management metadata filters: colorspace, colorspace_cuda, colormatrix, setparams, setrange, zscale' in catalog_coverage_report
assert 'Rendered-only FFmpeg filters:' in catalog_coverage_report
assert 'deflicker' in catalog_coverage_report
assert 'vidstabdetect' in catalog_coverage_report
assert 'Live approximation plus rendered fallback filters: bwdif, deflicker, deshake, hqdn3d, minterpolate, nlmeans, normalize, scale, tmix, unsharp, vidstabdetect, vidstabtransform' in catalog_coverage_report
assert 'Representative FFmpeg color-chain translation:' in catalog_coverage_report

result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type='SAMPLED_COLOR_MANAGEMENT')
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_compositor_nodes.startswith('sampled color management')
sampled_cm_compositor_summary = scene.video_toolkit_last_compositor_nodes
sampled_cm_compositor_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Sampled Color Management ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeExposure',
    'CompositorNodeColorBalance',
    'CompositorNodeColorCorrection',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueSat',
    'CompositorNodeTonemap',
    'CompositorNodeConvertToDisplay',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in sampled_cm_compositor_node_types, required
sampled_cm_exposure_node = next(node for node in tree.nodes if node.name == 'VTK Sampled Color Management Exposure')
sampled_cm_exposure_socket = next(socket for socket in sampled_cm_exposure_node.inputs if socket.name == 'Exposure')
assert abs(sampled_cm_exposure_socket.default_value) > 0.001
sampled_cm_display_node = next(node for node in tree.nodes if node.name == 'VTK Sampled Color Management Display Convert')
assert sampled_cm_display_node['video_toolkit_view_transform']
assert sampled_cm_display_node['video_toolkit_sequencer_input'] == 'bt709'

result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type='SAMPLED_COLOR')
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_compositor_nodes.startswith('sampled compositor grade')
sampled_compositor_summary = scene.video_toolkit_last_compositor_nodes
sampled_compositor_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Sampled ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeExposure',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeColorCorrection',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueSat',
    'CompositorNodeHueCorrect',
    'CompositorNodeTonemap',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in sampled_compositor_node_types, required
sampled_exposure_node = next(node for node in tree.nodes if node.name == 'VTK Sampled Exposure')
sampled_exposure_socket = next(socket for socket in sampled_exposure_node.inputs if socket.name == 'Exposure')
assert abs(sampled_exposure_socket.default_value) > 0.001
sampled_curve_node = next(node for node in tree.nodes if node.name == 'VTK Sampled RGB Curves')
assert len(sampled_curve_node.mapping.curves[0].points) >= 5

result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type='IDENTITY_COLOR')
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_compositor_nodes.startswith('palette compositor')
assert 'palette #' in scene.video_toolkit_last_compositor_nodes
identity_compositor_summary = scene.video_toolkit_last_compositor_nodes
identity_compositor_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Palette Identity ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeColorBalance',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueCorrect',
    'CompositorNodeTonemap',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in identity_compositor_node_types, required
identity_curve_node = next(node for node in tree.nodes if node.name == 'VTK Palette Identity Curves')
assert len(identity_curve_node.mapping.curves[0].points) >= 5

result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type='DIAGNOSTIC_COLOR')
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_compositor_nodes.startswith('diagnostic compositor grade')
diagnostic_compositor_summary = scene.video_toolkit_last_compositor_nodes
diagnostic_compositor_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Diagnostic Grade ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in diagnostic_compositor_node_types, required
assert any(
    node_type in diagnostic_compositor_node_types
    for node_type in (
        'CompositorNodeBrightContrast',
        'CompositorNodeColorBalance',
        'CompositorNodeCurveRGB',
        'CompositorNodeHueCorrect',
        'CompositorNodeTonemap',
    )
), diagnostic_compositor_node_types
assert scene.video_toolkit_last_diagnostics_text in bpy.data.texts
diagnostic_compositor_report = bpy.data.texts[scene.video_toolkit_last_diagnostics_text].as_string()
assert 'Suggested native Blender tools' in diagnostic_compositor_report

result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type='LIGHTING_NORMALIZE')
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_compositor_nodes.startswith('compositor lighting normalizer')
lighting_compositor_summary = scene.video_toolkit_last_compositor_nodes
lighting_compositor_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Lighting Normalizer ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeBrightContrast',
    'CompositorNodeTonemap',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in lighting_compositor_node_types, required
lighting_bright_node = next(node for node in tree.nodes if node.name == 'VTK Lighting Normalizer Brightness')
lighting_brightness_socket = next(
    socket for socket in lighting_bright_node.inputs if socket.name in ('Brightness', 'Bright')
)
assert tree.animation_data is not None
assert tree.animation_data.action is not None
lighting_compositor_keyframes = action_keyframe_count(
    tree.animation_data.action,
    lighting_brightness_socket.path_from_id('default_value'),
)
assert lighting_compositor_keyframes >= 2, lighting_compositor_keyframes

result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type='COLOR_TIMELINE_MATCH')
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_compositor_nodes.startswith('compositor color timeline match to')
timeline_compositor_summary = scene.video_toolkit_last_compositor_nodes
timeline_compositor_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Color Timeline Match ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeColorBalance',
    'CompositorNodeTonemap',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in timeline_compositor_node_types, required
timeline_balance_node = next(node for node in tree.nodes if node.name == 'VTK Color Timeline Match Balance')
timeline_compositor_gamma_keyframes = action_keyframe_count(
    tree.animation_data.action,
    timeline_balance_node['video_toolkit_gamma_socket_path'],
)
timeline_compositor_gain_keyframes = action_keyframe_count(
    tree.animation_data.action,
    timeline_balance_node['video_toolkit_gain_socket_path'],
)
assert timeline_compositor_gamma_keyframes >= 2, timeline_compositor_gamma_keyframes
assert timeline_compositor_gain_keyframes >= 2, timeline_compositor_gain_keyframes

result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type='MATCHED_COLOR')
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_compositor_nodes.startswith('matched compositor to')
matched_compositor_summary = scene.video_toolkit_last_compositor_nodes
matched_compositor_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Matched to ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueCorrect',
    'CompositorNodeTonemap',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in matched_compositor_node_types, required
matched_curve_node = next(
    node for node in tree.nodes if node.name.startswith('VTK Matched to ') and node.bl_idname == 'CompositorNodeCurveRGB'
)
assert len(matched_curve_node.mapping.curves[0].points) >= 5

result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type='REFERENCE_COLOR_BOARD')
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_compositor_nodes.startswith('reference color board compositor to')
reference_board_compositor_summary = scene.video_toolkit_last_compositor_nodes
reference_board_compositor_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Reference Color Board to ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueCorrect',
    'CompositorNodeTonemap',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in reference_board_compositor_node_types, required

result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type='TRANSLATED_COLOR')
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_compositor_nodes.startswith('translated compositor')
assert 'color management:' in scene.video_toolkit_last_compositor_nodes
assert 'blackdetect' in scene.video_toolkit_last_compositor_nodes
assert 'blurdetect' in scene.video_toolkit_last_compositor_nodes
assert 'idet' in scene.video_toolkit_last_compositor_nodes
assert 'deflicker' in scene.video_toolkit_last_compositor_nodes
assert 'vidstabtransform' in scene.video_toolkit_last_compositor_nodes
assert 'minterpolate' in scene.video_toolkit_last_compositor_nodes
translated_compositor_filter_count = int(
    scene.video_toolkit_last_compositor_nodes.split('compositor-native filter node(s): ', 1)[1].split(';', 1)[0]
)
assert translated_compositor_filter_count >= 99, scene.video_toolkit_last_compositor_nodes
translated_compositor_summary = scene.video_toolkit_last_compositor_nodes
translated_compositor_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Translated ')
]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueCorrect',
    'CompositorNodeColorCorrection',
    'CompositorNodeChromaMatte',
    'CompositorNodeColorMatte',
    'CompositorNodeLumaMatte',
    'CompositorNodeSeparateColor',
    'CompositorNodeTranslate',
    'CompositorNodeCombineColor',
    'CompositorNodeRGBToBW',
    'CompositorNodePremulKey',
    'CompositorNodePosterize',
    'CompositorNodeFilter',
    'CompositorNodeDilateErode',
    'CompositorNodeConvolve',
    'CompositorNodeBlur',
    'CompositorNodeBilateralblur',
    'CompositorNodeDBlur',
    'CompositorNodeScale',
    'CompositorNodeCrop',
    'CompositorNodeRotate',
    'CompositorNodeFlip',
    'CompositorNodeLensdist',
    'CompositorNodeDenoise',
    'CompositorNodeDespeckle',
    'CompositorNodeAntiAliasing',
    'CompositorNodeTonemap',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in translated_compositor_node_types, required
translated_convolve_node = next(node for node in tree.nodes if node.name == 'VTK Translated Convolve')
translated_convolve_kernel_socket = next(
    socket
    for socket in translated_convolve_node.inputs
    if getattr(socket, 'identifier', '') == 'Color Kernel'
)
assert translated_convolve_kernel_socket.is_linked
translated_convolve_kernel_node = next(node for node in tree.nodes if node.name == 'VTK Translated Convolve Kernel')
assert tuple(translated_convolve_kernel_node.image.size[:]) == (3, 3)
translated_convolve_kernel_pixels = list(translated_convolve_kernel_node.image.pixels[:20])
assert translated_convolve_kernel_pixels[4] < 0.0
assert translated_convolve_kernel_pixels[16] > 4.0
translated_gaussian_blur_node = next(node for node in tree.nodes if node.name == 'VTK Translated Gaussian Blur')
translated_gaussian_blur_size = next(socket for socket in translated_gaussian_blur_node.inputs if socket.name == 'Size').default_value
assert translated_gaussian_blur_size[0] > translated_gaussian_blur_size[1]
translated_smart_blur_node = next(node for node in tree.nodes if node.name == 'VTK Translated Smart Blur')
translated_smart_blur_threshold = next(socket for socket in translated_smart_blur_node.inputs if socket.name == 'Threshold')
assert translated_smart_blur_threshold.default_value > 0.05
translated_directional_blur_node = next(node for node in tree.nodes if node.name == 'VTK Translated Directional Blur')
translated_direction_socket = next(socket for socket in translated_directional_blur_node.inputs if socket.name == 'Direction')
translated_amount_socket = next(socket for socket in translated_directional_blur_node.inputs if socket.name == 'Amount')
assert 0.52 < translated_direction_socket.default_value < 0.53
assert translated_amount_socket.default_value > 0.10
translated_denoise_node = next(node for node in tree.nodes if node.name == 'VTK Translated High Quality Denoise')
translated_denoise_quality = next(socket for socket in translated_denoise_node.inputs if socket.name == 'Quality')
assert translated_denoise_quality.default_value == 'High'
assert translated_denoise_node['video_toolkit_ffmpeg_filter'] == 'hqdn3d'
translated_despeckle_node = next(node for node in tree.nodes if node.name == 'VTK Translated Median Despeckle')
translated_despeckle_neighbor = next(socket for socket in translated_despeckle_node.inputs if socket.name == 'Neighbor Threshold')
translated_despeckle_color = next(socket for socket in translated_despeckle_node.inputs if socket.name == 'Color Threshold')
assert translated_despeckle_neighbor.default_value > translated_despeckle_color.default_value
translated_deblock_node = next(node for node in tree.nodes if node.name == 'VTK Translated Deblock Smoothing')
translated_deblock_contrast = next(socket for socket in translated_deblock_node.inputs if socket.name == 'Contrast Limit')
assert translated_deblock_contrast.default_value > 2.0
translated_bright_node = next(node for node in tree.nodes if node.name == 'VTK Translated Bright Contrast')
translated_contrast_socket = next(socket for socket in translated_bright_node.inputs if socket.name == 'Contrast')
assert translated_contrast_socket.default_value > 0.0

result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type='RESTORATION')
assert result == {{'FINISHED'}}, result
all_node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK ')]
for required in [
    'CompositorNodeStabilize',
    'CompositorNodeMovieDistortion',
    'CompositorNodeDenoise',
    'CompositorNodeDespeckle',
    'CompositorNodeBilateralblur',
    'CompositorNodeAntiAliasing',
]:
    assert required in all_node_types, required

result = bpy.ops.video_toolkit.create_compositor_nodes(stack_type='NODE_LIBRARY')
assert result == {{'FINISHED'}}, result
library_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Library ')
]
for required in [
    'CompositorNodeConvertToDisplay',
    'CompositorNodeRGBToBW',
    'CompositorNodeNormalize',
    'CompositorNodeGlare',
    'CompositorNodeLensdist',
    'CompositorNodeCornerPin',
    'CompositorNodeTransform',
    'CompositorNodeChannelMatte',
    'CompositorNodeLumaMatte',
    'CompositorNodeSequencerStripInfo',
    'CompositorNodeConvolve',
    'CompositorNodeOutputFile',
]:
    assert required in library_node_types, required
assert len(set(library_node_types)) == len(compositor_node_types())
library_summary = scene.video_toolkit_last_compositor_nodes
assert library_summary.startswith(str(len(compositor_node_types())) + ' nodes:')

bpy.ops.wm.save_as_mainfile(filepath={str(blend)!r})
Path({str(report)!r}).write_text(json.dumps({{
    'video': {str(video)!r},
    'selected_strip': strip.name,
    'before_png': {str(before)!r},
    'after_png': {str(after)!r},
    'translated_png': {str(translated)!r},
    'color_managed_png': {str(color_managed)!r},
    'sampled_color_management_png': {str(sampled_color_management)!r},
    'recommended_recipe_mix_png': {str(recommended_recipe_mix)!r},
    'diagnostic_grade_png': {str(diagnostic_grade)!r},
    'sampled_white_balance_png': {str(sampled_white_balance)!r},
    'sampled_levels_gamma_png': {str(sampled_levels_gamma)!r},
    'sampled_hue_chroma_png': {str(sampled_hue_chroma)!r},
    'sampled_pro_grade_base_png': {str(sampled_pro_grade_base)!r},
    'sampled_pro_grade_png': {str(sampled_pro_grade)!r},
    'master_color_wheels_png': {str(master_color_wheels)!r},
    'primary_color_board_png': {str(primary_color_board)!r},
    'sampled_color_board_png': {str(sampled_color_board)!r},
    'reference_color_board_base_png': {str(reference_color_board_base)!r},
    'reference_color_board_png': {str(reference_color_board)!r},
    'before': before_stats,
    'after': after_stats,
    'translated': translated_stats,
    'color_managed': color_managed_stats,
    'sampled_color_management': sampled_color_management_stats,
    'recommended_recipe_mix': recommended_recipe_mix_stats,
    'diagnostic_grade': diagnostic_grade_stats,
    'sampled_white_balance': sampled_white_balance_stats,
    'sampled_levels_gamma': sampled_levels_gamma_stats,
    'sampled_hue_chroma': sampled_hue_chroma_stats,
    'sampled_pro_grade_base': sampled_pro_grade_base_stats,
    'sampled_pro_grade': sampled_pro_grade_stats,
    'master_color_wheels': master_color_wheels_stats,
    'primary_color_board': primary_color_board_stats,
    'sampled_color_board': sampled_color_board_stats,
    'reference_color_board_base': reference_color_board_base_stats,
    'reference_color_board': reference_color_board_stats,
    'rgb_abs_diff': diff,
    'translated_rgb_abs_diff': translated_diff,
    'translated_workflow_rgb_abs_diff': translated_workflow_diff,
    'color_management_rgb_abs_diff': color_management_diff,
    'sampled_color_management_rgb_abs_diff': sampled_color_management_diff,
    'recommended_recipe_mix_rgb_abs_diff': recommended_recipe_mix_diff,
    'diagnostic_grade_rgb_abs_diff': diagnostic_grade_diff,
    'sampled_white_balance_rgb_abs_diff': sampled_white_balance_diff,
    'sampled_levels_gamma_rgb_abs_diff': sampled_levels_gamma_diff,
    'sampled_hue_chroma_rgb_abs_diff': sampled_hue_chroma_diff,
    'sampled_pro_grade_rgb_abs_diff': sampled_pro_grade_diff,
    'master_color_wheels_rgb_abs_diff': master_color_wheels_diff,
    'primary_color_board_rgb_abs_diff': primary_color_board_diff,
    'sampled_color_board_rgb_abs_diff': sampled_color_board_diff,
    'reference_color_board_rgb_abs_diff': reference_color_board_diff,
    'edited_modifiers': edited,
    'native_modifier_types': types,
    'translated_chain_summary': scene.video_toolkit_last_translation,
    'translated_modifier_types': translated_types,
    'translated_workflow_summary': translated_workflow_summary,
    'translated_workflow_supported_filters': translated_workflow_supported,
    'translated_workflow_node_count': translated_workflow_node_count,
    'translated_workflow_modifier_types': translated_workflow_modifier_types,
    'translated_workflow_node_types': translated_workflow_node_types,
    'color_management_summary': color_management_summary,
    'sampled_color_management_summary': sampled_color_management_summary,
    'palette_modifier_types': palette_types,
    'palette_summary': palette_summary,
    'diagnostics_summary': scene.video_toolkit_last_diagnostics,
    'diagnostics_text': diagnostics_text_name,
    'diagnostics_report_excerpt': diagnostics_report.splitlines()[:12],
    'recipe_recommendations_text': recipe_recommendations_name,
    'recipe_recommendations_ids': recommended_recipe_ids,
    'recipe_recommendations_excerpt': recipe_recommendations_report.splitlines()[:24],
    'recommended_recipe_mix_summary': scene.video_toolkit_last_recommended_recipe_mix,
    'recommended_recipe_mix_ids': recipe_mix_ids,
    'recommended_recipe_mix_modifier_types': recipe_mix_types,
    'recommended_recipe_mix_node_summary': recommended_recipe_mix_node_summary,
    'recommended_recipe_mix_node_ids': recipe_mix_node_ids,
    'recommended_recipe_mix_node_types': recommended_recipe_mix_node_types,
    'professional_workflow_summary': professional_workflow_summary,
    'professional_workflow_recipe_ids': professional_workflow_recipe_ids,
    'professional_workflow_node_count': professional_workflow_node_count,
    'professional_workflow_node_types': professional_workflow_node_types,
    'professional_color_management_node_types': professional_color_management_node_types,
    'diagnostic_grade_summary': scene.video_toolkit_last_diagnostic_grade,
    'diagnostic_grade_modifier_types': diagnostic_grade_types,
    'sampled_white_balance_summary': scene.video_toolkit_last_sampled_white_balance,
    'sampled_white_balance_modifier_types': sampled_white_balance_types,
    'sampled_levels_gamma_summary': scene.video_toolkit_last_sampled_levels_gamma,
    'sampled_levels_gamma_modifier_types': sampled_levels_gamma_types,
    'sampled_hue_chroma_summary': scene.video_toolkit_last_sampled_hue_chroma,
    'sampled_hue_chroma_modifier_types': sampled_hue_chroma_types,
    'sampled_pro_grade_summary': scene.video_toolkit_last_sampled_pro_grade,
    'sampled_pro_grade_modifier_types': sampled_pro_grade_types,
    'master_color_wheels_modifier_types': master_color_wheels_modifier_types,
    'master_color_wheels_modifier_names': master_color_wheels_modifier_names,
    'master_color_wheels_modifier_roles': master_color_wheels_modifier_roles,
    'master_color_wheels_compositor_summary': master_color_wheels_compositor_summary,
    'master_color_wheels_node_types': master_color_wheels_node_types,
    'primary_color_board_modifier_types': primary_color_board_modifier_types,
    'primary_color_board_compositor_summary': primary_color_board_compositor_summary,
    'primary_color_board_node_types': primary_color_board_node_types,
    'sampled_color_board_summary': sampled_color_board_summary,
    'sampled_color_board_modifier_types': sampled_color_board_modifier_types,
    'sampled_color_board_node_count': sampled_color_board_node_count,
    'sampled_color_board_node_types': sampled_color_board_node_types,
    'reference_color_board_summary': reference_color_board_summary,
    'reference_color_board_modifier_types': reference_color_board_modifier_types,
    'reference_color_board_node_count': reference_color_board_node_count,
    'reference_color_board_node_types': reference_color_board_node_types,
    'primary_correction_modifier_types': primary_correction_types,
    'normalizer_keyframes': normalizer_keyframes,
    'timeline_match_reference': {str(reference_video)!r},
    'timeline_match_keyframes': timeline_match_keyframes,
    'color_timeline_gamma_keyframes': color_timeline_gamma_keyframes,
    'color_timeline_gain_keyframes': color_timeline_gain_keyframes,
    'compositor_color_node_types': color_node_types,
    'native_room_summary': native_room_summary,
    'native_room_node_types': native_room_node_types,
    'native_room_links': native_room_links,
    'sidecar_recipe_summary': sidecar_recipe_summary,
    'sidecar_recipe_node_types': sidecar_recipe_node_types,
    'tool_recipe_summary': tool_recipe_summary,
    'tool_recipe_node_types': tool_recipe_node_types,
    'tool_recipe_filter_ids': tool_recipe_filter_ids,
    'channel_mixer_summary': channel_mixer_summary,
    'channel_mixer_node_types': channel_mixer_node_types,
    'channel_mixer_matrix_values': channel_mixer_matrix_values[:3],
    'colormatrix_summary': colormatrix_summary,
    'colormatrix_node_types': colormatrix_node_types,
    'colormatrix_matrix_values': colormatrix_matrix_values[:3],
    'all_recipe_summary': all_recipe_summary,
    'all_recipe_ids': all_recipe_ids,
    'all_recipe_count': len(all_recipe_ids),
    'catalog_coverage_report': catalog_report_name,
    'catalog_coverage_excerpt': catalog_coverage_report.splitlines()[:18],
    'sampled_cm_compositor_summary': sampled_cm_compositor_summary,
    'sampled_cm_compositor_node_types': sampled_cm_compositor_node_types,
    'sampled_cm_compositor_exposure': sampled_cm_exposure_socket.default_value,
    'sampled_cm_compositor_view_transform': sampled_cm_display_node['video_toolkit_view_transform'],
    'sampled_cm_compositor_input': sampled_cm_display_node['video_toolkit_sequencer_input'],
    'sampled_compositor_summary': sampled_compositor_summary,
    'sampled_compositor_node_types': sampled_compositor_node_types,
    'sampled_compositor_exposure': sampled_exposure_socket.default_value,
    'identity_compositor_summary': identity_compositor_summary,
    'identity_compositor_node_types': identity_compositor_node_types,
    'diagnostic_compositor_summary': diagnostic_compositor_summary,
    'diagnostic_compositor_node_types': diagnostic_compositor_node_types,
    'diagnostic_compositor_report_excerpt': diagnostic_compositor_report.splitlines()[:12],
    'lighting_compositor_summary': lighting_compositor_summary,
    'lighting_compositor_node_types': lighting_compositor_node_types,
    'lighting_compositor_keyframes': lighting_compositor_keyframes,
    'timeline_compositor_summary': timeline_compositor_summary,
    'timeline_compositor_node_types': timeline_compositor_node_types,
    'timeline_compositor_gamma_keyframes': timeline_compositor_gamma_keyframes,
    'timeline_compositor_gain_keyframes': timeline_compositor_gain_keyframes,
    'matched_compositor_summary': matched_compositor_summary,
    'matched_compositor_node_types': matched_compositor_node_types,
    'reference_board_compositor_summary': reference_board_compositor_summary,
    'reference_board_compositor_node_types': reference_board_compositor_node_types,
    'translated_compositor_summary': translated_compositor_summary,
    'translated_compositor_node_types': translated_compositor_node_types,
    'translated_compositor_contrast': translated_contrast_socket.default_value,
    'compositor_all_node_types': all_node_types,
    'compositor_library_node_types': library_node_types,
    'compositor_library_summary': library_summary,
    'compositor_links': len(tree.links),
    'blend': {str(blend)!r},
}}, indent=2), encoding='utf-8')
video_toolkit.unregister()
"""


if __name__ == "__main__":
    raise SystemExit(main())
