#!/usr/bin/env python3
"""Run a headless Blender smoke test against the local add-on."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(os.environ.get("BLENDER", ROOT / ".local" / "blender" / "blender"))


def main() -> int:
    if not BLENDER.exists():
        raise SystemExit(f"Blender not found: {BLENDER}. Run scripts/download_blender.py first.")
    fixture = ROOT / "tests" / "fixtures" / "blender_smoke.mp4"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=96x64:rate=12:duration=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(fixture),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    script = _smoke_script(fixture)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        smoke_path = Path(handle.name)
    try:
        result = subprocess.run(
            [str(BLENDER), "--background", "--factory-startup", "--python", str(smoke_path)],
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
        smoke_path.unlink(missing_ok=True)
    return 0


def _smoke_script(fixture: Path) -> str:
    return f"""
import os
import sys
sys.path.insert(0, {str(ROOT)!r})
import bpy
import video_toolkit
from video_toolkit.addon import (
    LIVE_COLOR_SIDECAR_CATEGORIES,
    _compositor_node_control_names,
    _video_toolkit_compositor_control_nodes,
)
from video_toolkit.compositor import compositor_node_types

video_toolkit.register()
scene = bpy.context.scene
scene.sequence_editor_create()
scene.video_toolkit_output_dir = {str((ROOT / 'tests' / 'output'))!r}
scene.video_toolkit_crf = 28
scene.video_toolkit_preset = 'veryfast'
scene.video_toolkit_analysis_samples = 12
strip = scene.sequence_editor.strips.new_movie(
    name='smoke',
    filepath={str(fixture)!r},
    channel=1,
    frame_start=1,
)
second_strip = scene.sequence_editor.strips.new_movie(
    name='smoke second selected',
    filepath={str(fixture)!r},
    channel=2,
    frame_start=1,
)
for candidate in scene.sequence_editor.strips_all:
    candidate.select = False
strip.select = True
second_strip.select = True
scene.sequence_editor.active_strip = strip
scene.video_toolkit_apply_target = 'SELECTED'
bpy.ops.video_toolkit.apply_color_management_preset(preset_id='STANDARD_VIDEO')
assert scene.view_settings.view_transform == 'Standard'
assert scene.view_settings.gamma == 1.0
bpy.ops.video_toolkit.apply_color_management_preset(preset_id='AGX_PUNCH')
assert scene.view_settings.view_transform in {{'AgX', 'Khronos PBR Neutral', 'Standard'}}
assert 'AgX Punch' in scene.video_toolkit_last_color_management
bpy.ops.video_toolkit.apply_color_management_preset(preset_id='VIEW_CURVE_CONTRAST')
assert scene.view_settings.use_curve_mapping
view_curve_points = [tuple(point.location[:]) for point in scene.view_settings.curve_mapping.curves[0].points]
assert view_curve_points[1][1] < view_curve_points[1][0]
assert view_curve_points[-2][1] > view_curve_points[-2][0]
result = bpy.ops.video_toolkit.apply_sampled_color_management()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_sampled_color_management.startswith('sampled color management')
assert scene.view_settings.use_curve_mapping
assert scene.view_settings.view_transform in {{'AgX', 'Khronos PBR Neutral', 'Filmic', 'Standard'}}
assert 0.88 <= scene.view_settings.gamma <= 1.16
sampled_view_curve_points = [tuple(point.location[:]) for point in scene.view_settings.curve_mapping.curves[0].points]
assert len(sampled_view_curve_points) >= 5
assert sampled_view_curve_points[2][0] == 0.5
bpy.ops.video_toolkit.apply_filter(filter_id='neutral_grade')
assert any(m.name.startswith('VTK Neutral Grade') for m in strip.modifiers)
assert any(m.name.startswith('VTK Neutral Grade') for m in second_strip.modifiers)
scene.video_toolkit_apply_target = 'ACTIVE'
bpy.ops.video_toolkit.analyze_color(mode='AUTO')
assert len(strip.modifiers) >= 5
bpy.ops.video_toolkit.analyze_color(mode='PALETTE')
assert 'palette #' in scene.video_toolkit_last_analysis
bpy.ops.video_toolkit.color_diagnostics()
assert scene.video_toolkit_last_diagnostics.startswith('diagnosis')
assert scene.video_toolkit_last_diagnostics_text in bpy.data.texts
assert 'Suggested native Blender tools' in bpy.data.texts[scene.video_toolkit_last_diagnostics_text].as_string()
bpy.ops.video_toolkit.recommend_catalog_recipes()
assert scene.video_toolkit_last_recipe_recommendations.startswith('VTK Recipe Recommendations')
assert scene.video_toolkit_last_recipe_recommendations in bpy.data.texts
recipe_report = bpy.data.texts[scene.video_toolkit_last_recipe_recommendations].as_string()
assert 'Top Blender-native recipes:' in recipe_report
assert 'Frame stats:' in recipe_report
assert 'Exposure Lift' in recipe_report
assert 'Gamma Brighten' in recipe_report
recommended_recipe_ids = scene.get('video_toolkit_last_recommended_recipe_ids', '').split(',')
assert scene.video_toolkit_sidecar_tool in recommended_recipe_ids
assert any(recipe_id in recommended_recipe_ids for recipe_id in ('exposure_lift', 'gamma_brighten', 'saturation_reduce'))
bpy.ops.video_toolkit.apply_recommended_recipe_mix()
assert scene.video_toolkit_last_recommended_recipe_mix.startswith('recommended recipe mix')
recipe_mix_ids = scene.get('video_toolkit_last_recommended_recipe_mix_ids', '').split(',')
assert 1 <= len(recipe_mix_ids) <= scene.video_toolkit_recommendation_mix_count
assert recipe_mix_ids[0] in recommended_recipe_ids
recipe_mix_types = [m.type for m in strip.modifiers if m.name.startswith('VTK Recommended Recipe Mix')]
assert recipe_mix_types, 'No recommended recipe mix modifiers were added'
assert any(modifier_type in recipe_mix_types for modifier_type in ('BRIGHT_CONTRAST', 'COLOR_BALANCE', 'CURVES', 'HUE_CORRECT'))
bpy.ops.video_toolkit.create_recommended_recipe_mix_nodes()
assert scene.video_toolkit_last_compositor_nodes.startswith('recommended recipe mix nodes')
recipe_mix_node_ids = scene.get('video_toolkit_last_recommended_recipe_mix_node_ids', '').split(',')
assert recipe_mix_node_ids == recipe_mix_ids
tree = scene.compositing_node_group if hasattr(scene, 'compositing_node_group') else scene.node_tree
recipe_mix_node_types = [
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
    assert required in recipe_mix_node_types, required
assert any(required in recipe_mix_node_types for required in ('CompositorNodeColorBalance', 'CompositorNodeCurveRGB', 'CompositorNodeHueCorrect'))
bpy.ops.video_toolkit.apply_professional_color_workflow()
assert scene.video_toolkit_last_professional_workflow.startswith('professional color workflow')
assert scene.video_toolkit_last_sampled_color_management.startswith('sampled color management')
workflow_recipe_ids = scene.get('video_toolkit_last_professional_workflow_recipe_ids', '').split(',')
assert workflow_recipe_ids == recipe_mix_ids
assert scene.get('video_toolkit_last_professional_workflow_node_count', 0) >= 20
workflow_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Professional Color Workflow ')
]
workflow_cm_types = [
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
    assert required in workflow_types, required
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeExposure',
    'CompositorNodeColorBalance',
    'CompositorNodeCurveRGB',
    'CompositorNodeConvertToDisplay',
    'CompositorNodeOutputFile',
]:
    assert required in workflow_cm_types, required
scene.video_toolkit_apply_target = 'SELECTED'
bpy.ops.video_toolkit.apply_diagnostic_grade()
assert scene.video_toolkit_last_diagnostic_grade.startswith('diagnostic grade')
assert any(m.name.startswith('VTK Diagnostic Grade') for m in strip.modifiers)
assert any(m.name.startswith('VTK Diagnostic Grade') for m in second_strip.modifiers)
bpy.ops.video_toolkit.apply_sampled_white_balance()
assert scene.video_toolkit_last_sampled_white_balance.startswith('sampled white balance')
sampled_types = [m.type for m in strip.modifiers if m.name.startswith('VTK Sampled White Balance')]
assert sampled_types == ['WHITE_BALANCE', 'COLOR_BALANCE', 'BRIGHT_CONTRAST', 'CURVES', 'HUE_CORRECT'], sampled_types
assert any(m.name.startswith('VTK Sampled White Balance') for m in second_strip.modifiers)
bpy.ops.video_toolkit.apply_sampled_levels_gamma()
assert scene.video_toolkit_last_sampled_levels_gamma.startswith('sampled levels/gamma')
levels_types = [m.type for m in strip.modifiers if m.name.startswith('VTK Sampled Levels Gamma')]
assert levels_types == ['CURVES', 'COLOR_BALANCE', 'BRIGHT_CONTRAST', 'TONEMAP', 'HUE_CORRECT'], levels_types
assert any(m.name.startswith('VTK Sampled Levels Gamma') for m in second_strip.modifiers)
bpy.ops.video_toolkit.apply_sampled_hue_chroma()
assert scene.video_toolkit_last_sampled_hue_chroma.startswith('sampled hue/chroma')
hue_chroma_types = [m.type for m in strip.modifiers if m.name.startswith('VTK Sampled Hue Chroma')]
assert hue_chroma_types == ['HUE_CORRECT', 'COLOR_BALANCE', 'CURVES'], hue_chroma_types
assert any(m.name.startswith('VTK Sampled Hue Chroma') for m in second_strip.modifiers)
bpy.ops.video_toolkit.apply_sampled_pro_grade()
assert scene.video_toolkit_last_sampled_pro_grade.startswith('sampled pro grade')
pro_grade_types = [m.type for m in strip.modifiers if m.name.startswith('VTK Sampled Pro Grade')]
assert pro_grade_types == [
    'WHITE_BALANCE', 'COLOR_BALANCE', 'CURVES', 'COLOR_BALANCE', 'BRIGHT_CONTRAST',
    'TONEMAP', 'HUE_CORRECT', 'COLOR_BALANCE', 'CURVES', 'HUE_CORRECT'
], pro_grade_types
assert any(m.name.startswith('VTK Sampled Pro Grade') for m in second_strip.modifiers)
bpy.ops.video_toolkit.apply_sampled_color_board()
assert scene.video_toolkit_last_sampled_color_board.startswith('sampled color board')
sampled_board_types = [m.type for m in strip.modifiers if m.name.startswith('VTK Sampled Color Board')]
assert sampled_board_types == [
    'WHITE_BALANCE', 'BRIGHT_CONTRAST', 'COLOR_BALANCE', 'COLOR_BALANCE', 'CURVES',
    'HUE_CORRECT', 'TONEMAP', 'CURVES', 'HUE_CORRECT'
], sampled_board_types
assert any(m.name.startswith('VTK Sampled Color Board') for m in second_strip.modifiers)
assert scene.get('video_toolkit_last_sampled_color_board_node_count', 0) >= 10
sampled_board_node_types = [
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
    assert required in sampled_board_node_types, required
scene.video_toolkit_apply_target = 'ACTIVE'
bpy.ops.video_toolkit.normalize_lighting()
normalizer = next(m for m in strip.modifiers if m.name.startswith('VTK Live Flicker Normalizer'))
def action_keyframe_count(action, data_path):
    if hasattr(action, 'fcurves'):
        return sum(len(fcurve.keyframe_points) for fcurve in action.fcurves if fcurve.data_path == data_path)
    total = 0
    for layer in action.layers:
        for action_strip in layer.strips:
            for channelbag in action_strip.channelbags:
                total += sum(len(fcurve.keyframe_points) for fcurve in channelbag.fcurves if fcurve.data_path == data_path)
    return total
normalizer_path = normalizer.path_from_id('bright')
assert scene.animation_data is not None
assert scene.animation_data.action is not None
assert action_keyframe_count(scene.animation_data.action, normalizer_path) >= 2
bpy.ops.video_toolkit.match_lighting_timeline()
timeline_match = next(m for m in strip.modifiers if m.name.startswith('VTK Live Timeline Match'))
timeline_match_path = timeline_match.path_from_id('bright')
assert action_keyframe_count(scene.animation_data.action, timeline_match_path) >= 2
bpy.ops.video_toolkit.match_color_timeline()
color_timeline_match = next(m for m in strip.modifiers if m.name.startswith('VTK Live Color Timeline Match'))
color_gamma_path = color_timeline_match.color_balance.path_from_id('gamma')
color_gain_path = color_timeline_match.color_balance.path_from_id('gain')
assert action_keyframe_count(scene.animation_data.action, color_gamma_path) >= 6
assert action_keyframe_count(scene.animation_data.action, color_gain_path) >= 6
result = bpy.ops.video_toolkit.apply_reference_color_board()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_reference_color_board.startswith('reference color board to')
reference_board_types = [m.type for m in strip.modifiers if m.name.startswith('VTK Reference Color Board')]
assert reference_board_types == [
    'WHITE_BALANCE', 'BRIGHT_CONTRAST', 'COLOR_BALANCE', 'COLOR_BALANCE', 'CURVES',
    'HUE_CORRECT', 'TONEMAP', 'CURVES', 'HUE_CORRECT'
], reference_board_types
assert scene.get('video_toolkit_last_reference_color_board_node_count', 0) >= 10
reference_board_node_types = [
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
    assert required in reference_board_node_types, required
scene.video_toolkit_ffmpeg_chain = (
    'colorspace=iall=bt709:all=bt709:irange=tv:range=pc,'
    'colorspace_cuda=range=pc,'
    'normalize=smoothing=18:independence=0.65:strength=0.55,'
    'colorlevels=rimin=0.02:rimax=0.98,'
    'colorcorrect=rl=0.05:bl=-0.04:rh=0.03:bh=-0.02:saturation=1.06,'
    'colorcontrast=rc=0.12:gm=-0.05:by=0.08:rcw=0.5:gmw=0.4:byw=0.5:pl=1,'
    'selectivecolor=reds=0.10 -0.04 -0.02 0.00:blues=-0.04 0.02 0.10 0.03:whites=0.02 0.00 -0.08 0.01,'
    'monochrome=cb=0.05:cr=-0.04:high=0.1,'
    'colorize=hue=35:saturation=0.25:lightness=0.55:mix=0.85,'
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
    'vibrance=intensity=0.4,'
    'pseudocolor=preset=viridis:opacity=0.75:index=1,'
    'exposure=exposure=0.25:black=0.02,'
    'histeq=strength=0.25:intensity=0.22:antibanding=1,'
    'zscale=primariesin=bt709:transferin=bt709:matrixin=bt709:rangein=limited:primaries=bt2020:transfer=bt2020-10:matrix=bt2020nc:range=full'
)
bpy.ops.video_toolkit.translate_ffmpeg_chain()
for required_filter in [
    'colorspace',
    'normalize',
    'colorlevels',
    'colorspace_cuda',
    'procamp_vaapi',
    'tonemap_opencl',
    'tonemap_vaapi',
    'chromakey',
    'chromakey_cuda',
    'colorkey_opencl',
    'despill',
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
assert compositor_node_count >= 68, scene.video_toolkit_last_translation
assert 'color management:' in scene.video_toolkit_last_translation
assert scene.sequencer_colorspace_settings.name in {'sRGB', 'Gamma 2.2 Encoded Rec.709', 'Gamma 2.4 Encoded Rec.709', 'Rec.1886', 'Linear Rec.709'}
translated_types = [m.type for m in strip.modifiers if m.name.startswith('VTK Translated Color Chain')]
assert {{'CURVES', 'HUE_CORRECT', 'COLOR_BALANCE', 'BRIGHT_CONTRAST', 'TONEMAP', 'WHITE_BALANCE'}}.issubset(set(translated_types))
result = bpy.ops.video_toolkit.apply_translated_color_workflow()
assert result == {{'FINISHED'}}, result
assert scene.video_toolkit_last_translated_workflow.startswith('translated color workflow')
assert 'colorspace, colorspace_cuda, normalize, colorlevels, colorcorrect' in scene.video_toolkit_last_translated_workflow
assert 'identity' in scene.video_toolkit_last_translated_workflow
assert 'ssim' in scene.video_toolkit_last_translated_workflow
assert 'xcorrelate' in scene.video_toolkit_last_translated_workflow
assert 'procamp_vaapi' in scene.video_toolkit_last_translated_workflow
assert 'blend_vulkan' in scene.video_toolkit_last_translated_workflow
assert 'blackdetect' in scene.video_toolkit_last_translated_workflow
assert 'blurdetect' in scene.video_toolkit_last_translated_workflow
assert 'idet' in scene.video_toolkit_last_translated_workflow
assert 'deflicker' in scene.video_toolkit_last_translated_workflow
assert 'vidstabtransform' in scene.video_toolkit_last_translated_workflow
assert 'minterpolate' in scene.video_toolkit_last_translated_workflow
assert scene.get('video_toolkit_last_translated_workflow_node_count', 0) >= 10
translated_workflow_types = [
    node.bl_idname
    for node in (scene.compositing_node_group if hasattr(scene, 'compositing_node_group') else scene.node_tree).nodes
    if node.name.startswith('VTK Translated Color Workflow ')
]
workflow_modifier_types = [m.type for m in strip.modifiers if m.name.startswith('VTK Translated Color Workflow')]
assert {{'CURVES', 'HUE_CORRECT', 'COLOR_BALANCE', 'BRIGHT_CONTRAST', 'TONEMAP', 'WHITE_BALANCE'}}.issubset(set(workflow_modifier_types))
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueCorrect',
    'CompositorNodeTonemap',
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
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in translated_workflow_types, required
scene.video_toolkit_ffmpeg_chain = 'setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=full,setrange=limited,zscale=primariesin=bt709:transferin=bt709:matrixin=bt709:rangein=limited:primaries=bt2020:transfer=bt2020-10:matrix=bt2020nc:range=full'
bpy.ops.video_toolkit.translate_ffmpeg_chain()
assert 'translated setparams, setrange, zscale into 0 live modifier(s)' in scene.video_toolkit_last_translation
assert 'color management:' in scene.video_toolkit_last_translation
result = bpy.ops.video_toolkit.apply_filter(filter_id='native_ffmpeg_color_metadata_pipeline')
assert result == {{'FINISHED'}}, result
assert scene['video_toolkit_color_management_output_transfer'] == 'bt2020-10'
assert scene['video_toolkit_color_management_output_range'] == 'limited'
assert 'FFmpeg Metadata Pipeline' in scene.video_toolkit_last_color_management
assert 'color management:' in scene.video_toolkit_last_compositor_nodes
metadata_tree = scene.compositing_node_group if hasattr(scene, 'compositing_node_group') else scene.node_tree
metadata_nodes = [
    node for node in metadata_tree.nodes
    if node.get('video_toolkit_filter_id') == 'native_ffmpeg_color_metadata_pipeline'
]
assert metadata_nodes
assert any(node.get('video_toolkit_color_management_output_transfer') == 'bt2020-10' for node in metadata_nodes)
assert bpy.types.VIDEO_TOOLKIT_PT_video_filters.bl_category == 'Video Effects'
assert bpy.types.VIDEO_TOOLKIT_MT_tools.bl_label == 'Video Effects'
assert LIVE_COLOR_SIDECAR_CATEGORIES == (
    'Live Blender Color',
    'Native Blender Primitives',
    'Native Color & Composite',
    'Live Blender Modifiers',
)
assert scene.video_toolkit_sidecar_section == 'BROWSER'
for sidecar_section in ['ENHANCE', 'ANALYSIS', 'COLOR', 'COMPOSITOR', 'LIVE', 'STRIP', 'MODIFIERS', 'RENDER', 'BROWSER']:
    result = bpy.ops.video_toolkit.set_sidecar_section(section=sidecar_section)
    assert result == {{'FINISHED'}}, result
    assert scene.video_toolkit_sidecar_section == sidecar_section
assert not hasattr(bpy.types, 'VIDEO_TOOLKIT_PT_video_effects_analysis')
assert not hasattr(bpy.types, 'VIDEO_TOOLKIT_PT_video_effects_color_management')
assert not hasattr(bpy.types, 'VIDEO_TOOLKIT_PT_video_effects_compositor')
assert not hasattr(bpy.types, 'VIDEO_TOOLKIT_PT_video_effects_live_tools')
assert not hasattr(bpy.types, 'VIDEO_TOOLKIT_PT_video_effects_strip')
assert not hasattr(bpy.types, 'VIDEO_TOOLKIT_PT_video_effects_modifiers')
assert not hasattr(bpy.types, 'VIDEO_TOOLKIT_PT_video_effects_render')
scene.video_toolkit_sidecar_group = 'LIVE_BLENDER_COLOR'
scene.video_toolkit_sidecar_tool = 'live_gamma_grade'
bpy.ops.video_toolkit.apply_sidecar_tool()
assert any(m.name.startswith('VTK Live Gamma Grade') for m in strip.modifiers)
bpy.ops.video_toolkit.create_sidecar_compositor_nodes()
assert scene.video_toolkit_last_compositor_nodes.startswith('tool compositor Live Gamma Grade')
tree = scene.compositing_node_group if hasattr(scene, 'compositing_node_group') else scene.node_tree
sidecar_recipe_node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK Tool Live Gamma Grade ')]
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
scene.video_toolkit_sidecar_tool = 'primary_color_board'
bpy.ops.video_toolkit.apply_sidecar_tool()
primary_board_types = [m.type for m in strip.modifiers if m.name.startswith('VTK Primary Color Board')]
assert {{'BRIGHT_CONTRAST', 'COLOR_BALANCE', 'CURVES', 'HUE_CORRECT', 'TONEMAP'}}.issubset(set(primary_board_types))
bpy.ops.video_toolkit.create_sidecar_compositor_nodes()
assert scene.video_toolkit_last_compositor_nodes.startswith('tool compositor Primary Color Board')
primary_board_node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK Tool Primary Color Board ')]
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
    assert required in primary_board_node_types, required
scene.video_toolkit_sidecar_group = 'NATIVE_COLOR_COMPOSITE'
scene.video_toolkit_sidecar_tool = 'native_rgb_channel_board'
bpy.ops.video_toolkit.apply_sidecar_tool()
assert scene.video_toolkit_last_compositor_nodes.startswith('tool compositor RGB Channel Board')
rgb_board_nodes = [
    node for node in tree.nodes
    if node.get('video_toolkit_filter_id') == 'native_rgb_channel_board'
]
assert rgb_board_nodes
assert {{'CompositorNodeSeparateColor', 'CompositorNodeCombineColor', 'CompositorNodeColorBalance'}}.issubset(
    {{node.bl_idname for node in rgb_board_nodes}}
)
rgb_control_nodes = _video_toolkit_compositor_control_nodes(scene, limit=20)
assert {{'CompositorNodeSeparateColor', 'CompositorNodeCombineColor', 'CompositorNodeColorBalance'}}.issubset(
    {{node.bl_idname for node in rgb_control_nodes}}
)
rgb_control_names = {{
    node.bl_idname: _compositor_node_control_names(node)
    for node in rgb_control_nodes
}}
assert 'mode' in rgb_control_names['CompositorNodeSeparateColor']
assert 'mode' in rgb_control_names['CompositorNodeCombineColor']
assert 'Gamma' in rgb_control_names['CompositorNodeColorBalance']
scene.video_toolkit_sidecar_tool = 'native_ffmpeg_color_metadata_pipeline'
bpy.ops.video_toolkit.apply_sidecar_tool()
assert scene.video_toolkit_last_compositor_nodes.startswith('tool compositor FFmpeg Metadata Pipeline')
assert 'color management:' in scene.video_toolkit_last_compositor_nodes
metadata_sidecar_nodes = [
    node for node in tree.nodes
    if node.get('video_toolkit_filter_id') == 'native_ffmpeg_color_metadata_pipeline'
]
assert metadata_sidecar_nodes
assert any(node.get('video_toolkit_color_management_output_transfer') == 'bt2020-10' for node in metadata_sidecar_nodes)
metadata_control_nodes = _video_toolkit_compositor_control_nodes(scene, limit=20)
metadata_control_names = {{
    node.bl_idname: _compositor_node_control_names(node)
    for node in metadata_control_nodes
}}
assert 'from_color_space' in metadata_control_names['CompositorNodeConvertColorSpace']
assert 'to_color_space' in metadata_control_names['CompositorNodeConvertColorSpace']
assert 'Intensity' in metadata_control_names['CompositorNodeTonemap']
assert 'Invert' in metadata_control_names['CompositorNodeConvertToDisplay']
from video_toolkit.addon import _tool_has_compositor_stack
from video_toolkit.catalog import all_tools
from video_toolkit.ffmpeg_native import NATIVE_FFMPEG_COMPOSITOR_FILTERS, NATIVE_FFMPEG_FILTERS
expected_recipe_ids = [tool.id for tool in all_tools() if _tool_has_compositor_stack(tool)]
bpy.ops.video_toolkit.create_all_tool_compositor_nodes()
assert scene.video_toolkit_last_compositor_nodes.startswith('all tool compositor recipes:')
assert f'{{len(expected_recipe_ids)}} tools' in scene.video_toolkit_last_compositor_nodes
created_recipe_ids = scene.get('video_toolkit_last_compositor_recipe_ids', '').split(',')
assert created_recipe_ids == expected_recipe_ids
assert 'live_pro_color_stack' in created_recipe_ids
for color_board_id in [
    'primary_color_board',
    'log_zone_color_board',
    'asc_cdl_finish_board',
    'six_vector_hue_board',
    'secondary_skin_vector',
    'palette_separation_board',
    'broadcast_safe_finish',
    'match_prep_neutralizer',
]:
    assert color_board_id in created_recipe_ids
assert 'native_white_balance_editor' in created_recipe_ids
assert 'native_mask_slot' not in created_recipe_ids
bpy.ops.video_toolkit.write_catalog_coverage_report()
assert scene.video_toolkit_last_catalog_report == 'VTK Video Effects Catalog Coverage'
assert scene.video_toolkit_last_catalog_report in bpy.data.texts
catalog_report = bpy.data.texts[scene.video_toolkit_last_catalog_report].as_string()
assert f'Compositor-compatible catalog recipes: {{len(expected_recipe_ids)}}' in catalog_report
assert 'VSE-only native tools:' in catalog_report
assert 'native_mask_slot: Mask Slot' in catalog_report
assert 'Rendered fallback tools:' in catalog_report
assert 'Tracked native compositor node library:' in catalog_report
assert f'Native-translated FFmpeg filters: {{len(NATIVE_FFMPEG_FILTERS)}}' in catalog_report
assert 'Native-translated FFmpeg color filters: eq, hue, huesaturation' in catalog_report
assert 'Native compositor-only FFmpeg filters: ' + ', '.join(NATIVE_FFMPEG_COMPOSITOR_FILTERS) in catalog_report
assert 'Native Color Management metadata filters: colorspace, colorspace_cuda, colormatrix, setparams, setrange, zscale' in catalog_report
assert 'Rendered fallback FFmpeg filters:' in catalog_report
assert 'Rendered-only FFmpeg filters:' in catalog_report
assert 'deflicker' in catalog_report
assert 'vidstabdetect' in catalog_report
assert 'Live approximation plus rendered fallback filters: bwdif, deflicker, deshake, hqdn3d, minterpolate, nlmeans, normalize, scale, tmix, unsharp, vidstabdetect, vidstabtransform' in catalog_report
assert 'Representative FFmpeg color-chain translation:' in catalog_report
assert 'Colorcontrast is approximated with Blender opponent-channel Color Balance controls.' in catalog_report
for filter_id in (
    'live_pro_color_stack',
    'auto_enhance',
    'neutral_grade',
    'punchy_color',
    'soft_contrast',
    'exposure_lift',
    'gamma_brighten',
    'gamma_deepen',
    'warm_balance',
    'cool_balance',
    'saturation_boost',
    'saturation_reduce',
    'monochrome',
    'faded_film',
    'high_contrast_curve',
    'medium_contrast_curve',
    'levels_expand',
    'levels_soft_clamp',
    'shadow_highlight_balance',
    'vibrance',
    'skin_safe_vibrance',
    'exposure_protect',
    'temperature_warm',
    'temperature_cool',
    'legal_range_clamp',
    'hdr_tone_compress',
    'black_point_cleanup',
    'white_point_recovery',
    'luma_s_curve',
    'red_gamma_trim',
    'green_gamma_trim',
    'blue_gamma_trim',
    'magenta_green_tint',
    'green_cast_repair',
    'shadow_cool_tint',
    'highlight_warm_tint',
    'skin_tone_isolation',
    'native_all_color_tools',
    'vse_bright_contrast',
    'vse_color_balance',
    'vse_curves',
    'vse_hue_correct',
    'vse_mask',
    'vse_tonemap',
    'vse_white_balance',
):
    bpy.ops.video_toolkit.apply_filter(filter_id=filter_id)
assert len(strip.modifiers) >= 99
high_curve = next(m for m in strip.modifiers if m.name.startswith('VTK High Contrast Curve') and m.type == 'CURVES')
high_points = [tuple(p.location[:]) for p in high_curve.curve_mapping.curves[0].points]
assert high_points[1][1] < high_points[1][0]
assert high_points[-2][1] > high_points[-2][0]
saturation = next(m for m in strip.modifiers if m.name.startswith('VTK Saturation Boost') and m.type == 'HUE_CORRECT')
assert saturation.curve_mapping.curves[1].points[0].location[1] > 0.5
monochrome = next(m for m in strip.modifiers if m.name.startswith('VTK Monochrome') and m.type == 'HUE_CORRECT')
assert monochrome.curve_mapping.curves[1].points[0].location[1] == 0.0
levels = next(m for m in strip.modifiers if m.name.startswith('VTK Levels Expand') and m.type == 'CURVES')
assert len(levels.curve_mapping.curves[1].points) >= 4
vibrance = next(m for m in strip.modifiers if m.name.startswith('VTK Vibrance') and m.type == 'HUE_CORRECT')
assert vibrance.curve_mapping.curves[1].points[0].location[1] > 0.5
temperature = next(m for m in strip.modifiers if m.name.startswith('VTK Temperature Warm') and m.type == 'WHITE_BALANCE')
assert temperature.white_value[0] > temperature.white_value[2]
red_trim = next(m for m in strip.modifiers if m.name.startswith('VTK Red Gamma Trim') and m.type == 'COLOR_BALANCE')
assert red_trim.color_balance.gamma[0] > red_trim.color_balance.gamma[1]
green_repair = next(m for m in strip.modifiers if m.name.startswith('VTK Green Cast Repair') and m.type == 'WHITE_BALANCE')
assert green_repair.white_value[1] < green_repair.white_value[0]
white_recovery = next(m for m in strip.modifiers if m.name.startswith('VTK White Point Recovery') and m.type == 'TONEMAP')
assert white_recovery.intensity > 0.0
scene.sequence_editor.active_strip = strip
for candidate in scene.sequence_editor.strips_all:
    candidate.select = False
strip.select = True
scene.video_toolkit_apply_target = 'ADJUSTMENT'
bpy.ops.video_toolkit.apply_filter(filter_id='auto_enhance')
adjustment = scene.sequence_editor.active_strip
assert adjustment.type == 'ADJUSTMENT'
assert adjustment.channel > strip.channel
assert any(m.name.startswith('VTK Auto Enhance') for m in adjustment.modifiers)
scene.sequence_editor.active_strip = strip
for candidate in scene.sequence_editor.strips_all:
    candidate.select = False
strip.select = True
scene.video_toolkit_apply_target = 'ACTIVE'
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='COLOR')
tree = scene.compositing_node_group if hasattr(scene, 'compositing_node_group') else scene.node_tree
node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK ')]
assert 'CompositorNodeMovieClip' in node_types
assert 'CompositorNodeColorCorrection' in node_types
assert 'CompositorNodeTonemap' in node_types
assert len(tree.links) >= 12
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='NATIVE_COLOR_ROOM')
assert scene.video_toolkit_last_compositor_nodes.startswith('native color room graph')
native_room_node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK Native Color Room ')]
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
assert len([link for link in tree.links if link.from_node.name.startswith('VTK Native Color Room ')]) >= 16
bpy.ops.video_toolkit.create_tool_compositor_nodes(filter_id='live_pro_color_stack')
assert scene.video_toolkit_last_compositor_nodes.startswith('tool compositor Live Pro Color Stack')
tool_recipe_node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK Tool Live Pro Color Stack ')]
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
recipe_nodes = [node for node in tree.nodes if node.name.startswith('VTK Tool Live Pro Color Stack ')]
recipe_filter_ids = [node['video_toolkit_filter_id'] for node in recipe_nodes]
assert set(recipe_filter_ids) == {{'live_pro_color_stack'}}
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='SAMPLED_COLOR_MANAGEMENT')
assert scene.video_toolkit_last_compositor_nodes.startswith('sampled color management')
sampled_cm_node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK Sampled Color Management ')]
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
    assert required in sampled_cm_node_types, required
sampled_cm_exposure = next(node for node in tree.nodes if node.name == 'VTK Sampled Color Management Exposure')
sampled_cm_exposure_socket = next(socket for socket in sampled_cm_exposure.inputs if socket.name == 'Exposure')
assert abs(sampled_cm_exposure_socket.default_value) > 0.001
sampled_cm_display = next(node for node in tree.nodes if node.name == 'VTK Sampled Color Management Display Convert')
assert sampled_cm_display['video_toolkit_view_transform']
assert sampled_cm_display['video_toolkit_sequencer_input'] == 'bt709'
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='SAMPLED_COLOR_BOARD')
assert scene.video_toolkit_last_compositor_nodes.startswith('sampled color board compositor')
sampled_board_compositor_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK Sampled Color Board ')]
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
    assert required in sampled_board_compositor_types, required
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='SAMPLED_COLOR')
assert scene.video_toolkit_last_compositor_nodes.startswith('sampled compositor grade')
sampled_node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK Sampled ')]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeExposure',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeColorCorrection',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueCorrect',
    'CompositorNodeTonemap',
]:
    assert required in sampled_node_types, required
sampled_exposure = next(node for node in tree.nodes if node.name == 'VTK Sampled Exposure')
exposure_socket = next(socket for socket in sampled_exposure.inputs if socket.name == 'Exposure')
assert abs(exposure_socket.default_value) > 0.001
sampled_curves = next(node for node in tree.nodes if node.name == 'VTK Sampled RGB Curves')
assert len(sampled_curves.mapping.curves[0].points) >= 5
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='IDENTITY_COLOR')
assert scene.video_toolkit_last_compositor_nodes.startswith('palette compositor')
assert 'palette #' in scene.video_toolkit_last_compositor_nodes
identity_node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK Palette Identity ')]
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
    assert required in identity_node_types, required
identity_curve = next(node for node in tree.nodes if node.name == 'VTK Palette Identity Curves')
assert len(identity_curve.mapping.curves[0].points) >= 5
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='DIAGNOSTIC_COLOR')
assert scene.video_toolkit_last_compositor_nodes.startswith('diagnostic compositor grade')
assert scene.video_toolkit_last_diagnostics_text in bpy.data.texts
assert 'Suggested native Blender tools' in bpy.data.texts[scene.video_toolkit_last_diagnostics_text].as_string()
diagnostic_node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK Diagnostic Grade ')]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in diagnostic_node_types, required
assert any(
    node_type in diagnostic_node_types
    for node_type in (
        'CompositorNodeBrightContrast',
        'CompositorNodeColorBalance',
        'CompositorNodeCurveRGB',
        'CompositorNodeHueCorrect',
        'CompositorNodeTonemap',
    )
), diagnostic_node_types
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='LIGHTING_NORMALIZE')
assert scene.video_toolkit_last_compositor_nodes.startswith('compositor lighting normalizer')
lighting_node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK Lighting Normalizer ')]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeBrightContrast',
    'CompositorNodeTonemap',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in lighting_node_types, required
lighting_bright = next(node for node in tree.nodes if node.name == 'VTK Lighting Normalizer Brightness')
lighting_socket = next(socket for socket in lighting_bright.inputs if socket.name in ('Brightness', 'Bright'))
assert tree.animation_data is not None
assert tree.animation_data.action is not None
assert action_keyframe_count(tree.animation_data.action, lighting_socket.path_from_id('default_value')) >= 2
for candidate in scene.sequence_editor.strips_all:
    candidate.select = False
strip.select = True
second_strip.select = True
scene.sequence_editor.active_strip = strip
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='COLOR_TIMELINE_MATCH')
assert scene.video_toolkit_last_compositor_nodes.startswith('compositor color timeline match to')
timeline_node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK Color Timeline Match ')]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeColorBalance',
    'CompositorNodeTonemap',
    'CompositorNodeLevels',
    'CompositorNodeViewer',
    'CompositorNodeOutputFile',
]:
    assert required in timeline_node_types, required
timeline_balance = next(node for node in tree.nodes if node.name == 'VTK Color Timeline Match Balance')
assert action_keyframe_count(tree.animation_data.action, timeline_balance['video_toolkit_gamma_socket_path']) >= 2
assert action_keyframe_count(tree.animation_data.action, timeline_balance['video_toolkit_gain_socket_path']) >= 2
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='MATCHED_COLOR')
assert scene.video_toolkit_last_compositor_nodes.startswith('matched compositor to')
matched_node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK Matched to ')]
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
    assert required in matched_node_types, required
matched_curves = next(node for node in tree.nodes if node.name.startswith('VTK Matched to ') and node.bl_idname == 'CompositorNodeCurveRGB')
assert len(matched_curves.mapping.curves[0].points) >= 5
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='REFERENCE_COLOR_BOARD')
assert scene.video_toolkit_last_compositor_nodes.startswith('reference color board compositor to')
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
scene.video_toolkit_ffmpeg_chain = (
    'colorspace=iall=bt709:all=bt709:irange=tv:range=pc,'
    'colorspace_cuda=range=pc,'
    'eq=contrast=1.12:saturation=1.08:gamma=1.02,'
    'colorbalance=rs=0.04:bm=0.03:bh=-0.04:pl=1,'
    'curves=preset=strong_contrast,'
    'lut1d=file=warm_print.spi1d:interp=cubic,'
    'lut3d=file=teal_orange.cube:interp=tetrahedral,'
    'haldclut=interp=tetrahedral:clut=all,'
    'colormap=patch_size=64x64:nb_patches=32:type=absolute:kernel=weuclidean,'
    'procamp_vaapi=brightness=8:contrast=1.18:saturation=1.14:hue=4,'
    'tonemap_opencl=tonemap=mobius:param=0.35:desat=0.45:peak=600:transfer=bt709:matrix=bt709:primaries=bt709:range=pc,'
    'tonemap_vaapi=transfer=bt709:matrix=bt709:primaries=bt709:range=pc,'
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
    'histeq=strength=0.20:intensity=0.18'
)
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='TRANSLATED_COLOR')
assert scene.video_toolkit_last_compositor_nodes.startswith('translated compositor')
assert 'color management:' in scene.video_toolkit_last_compositor_nodes
assert 'tlut2' in scene.video_toolkit_last_compositor_nodes
assert 'identity' in scene.video_toolkit_last_compositor_nodes
assert 'ssim' in scene.video_toolkit_last_compositor_nodes
assert 'xcorrelate' in scene.video_toolkit_last_compositor_nodes
assert 'procamp_vaapi' in scene.video_toolkit_last_compositor_nodes
assert 'convolution_opencl' in scene.video_toolkit_last_compositor_nodes
assert 'blackdetect' in scene.video_toolkit_last_compositor_nodes
assert 'blurdetect' in scene.video_toolkit_last_compositor_nodes
assert 'idet' in scene.video_toolkit_last_compositor_nodes
assert 'deflicker' in scene.video_toolkit_last_compositor_nodes
assert 'vidstabtransform' in scene.video_toolkit_last_compositor_nodes
assert 'minterpolate' in scene.video_toolkit_last_compositor_nodes
compositor_filter_node_count = int(
    scene.video_toolkit_last_compositor_nodes.split('compositor-native filter node(s): ', 1)[1].split(';', 1)[0]
)
assert compositor_filter_node_count >= 52, scene.video_toolkit_last_compositor_nodes
translated_node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK Translated ')]
for required in [
    'CompositorNodeMovieClip',
    'CompositorNodeConvertColorSpace',
    'CompositorNodeBrightContrast',
    'CompositorNodeColorBalance',
    'CompositorNodeCurveRGB',
    'CompositorNodeHueCorrect',
    'CompositorNodeChromaMatte',
    'CompositorNodeColorMatte',
    'CompositorNodeDiffMatte',
    'CompositorNodeLumaMatte',
    'CompositorNodeRGB',
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
    assert required in translated_node_types, required
translated_convolve = next(node for node in tree.nodes if node.name == 'VTK Translated Convolve')
translated_kernel_socket = next(
    socket
    for socket in translated_convolve.inputs
    if getattr(socket, 'identifier', '') == 'Color Kernel'
)
assert translated_kernel_socket.is_linked
translated_kernel_node = next(node for node in tree.nodes if node.name == 'VTK Translated Convolve Kernel')
assert tuple(translated_kernel_node.image.size[:]) == (3, 3)
translated_kernel_pixels = list(translated_kernel_node.image.pixels[:20])
assert translated_kernel_pixels[4] < 0.0
assert translated_kernel_pixels[16] > 4.0
translated_gaussian_blur = next(node for node in tree.nodes if node.name == 'VTK Translated Gaussian Blur')
translated_gaussian_size = next(socket for socket in translated_gaussian_blur.inputs if socket.name == 'Size').default_value
assert translated_gaussian_size[0] > translated_gaussian_size[1]
translated_smart_blur = next(node for node in tree.nodes if node.name == 'VTK Translated Smart Blur')
translated_smart_threshold = next(socket for socket in translated_smart_blur.inputs if socket.name == 'Threshold')
assert translated_smart_threshold.default_value > 0.05
translated_directional_blur = next(node for node in tree.nodes if node.name == 'VTK Translated Directional Blur')
translated_direction_socket = next(socket for socket in translated_directional_blur.inputs if socket.name == 'Direction')
translated_amount_socket = next(socket for socket in translated_directional_blur.inputs if socket.name == 'Amount')
assert 0.52 < translated_direction_socket.default_value < 0.53
assert translated_amount_socket.default_value > 0.10
translated_denoise = next(node for node in tree.nodes if node.name == 'VTK Translated High Quality Denoise')
translated_denoise_quality = next(socket for socket in translated_denoise.inputs if socket.name == 'Quality')
assert translated_denoise_quality.default_value == 'High'
assert translated_denoise['video_toolkit_ffmpeg_filter'] == 'hqdn3d'
translated_despeckle = next(node for node in tree.nodes if node.name == 'VTK Translated Median Despeckle')
translated_despeckle_neighbor = next(socket for socket in translated_despeckle.inputs if socket.name == 'Neighbor Threshold')
translated_despeckle_color = next(socket for socket in translated_despeckle.inputs if socket.name == 'Color Threshold')
assert translated_despeckle_neighbor.default_value > translated_despeckle_color.default_value
translated_deblock = next(node for node in tree.nodes if node.name == 'VTK Translated Deblock Smoothing')
translated_deblock_contrast = next(socket for socket in translated_deblock.inputs if socket.name == 'Contrast Limit')
assert translated_deblock_contrast.default_value > 2.0
translated_bright = next(node for node in tree.nodes if node.name == 'VTK Translated Bright Contrast')
translated_contrast = next(socket for socket in translated_bright.inputs if socket.name == 'Contrast')
assert translated_contrast.default_value > 0.0
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='RESTORATION')
node_types = [node.bl_idname for node in tree.nodes if node.name.startswith('VTK ')]
assert 'CompositorNodeStabilize' in node_types
assert 'CompositorNodeMovieDistortion' in node_types
assert 'CompositorNodeDenoise' in node_types
bpy.ops.video_toolkit.create_compositor_nodes(stack_type='NODE_LIBRARY')
library_node_types = [
    node.bl_idname
    for node in tree.nodes
    if node.name.startswith('VTK Library ')
]
for required in compositor_node_types():
    assert required in library_node_types, required
assert len(set(library_node_types)) == len(compositor_node_types())
assert scene.video_toolkit_last_compositor_nodes.startswith(str(len(compositor_node_types())) + ' nodes:')
bpy.ops.video_toolkit.apply_filter(filter_id='deflicker_normalize')
assert scene.video_toolkit_last_output
assert os.path.exists(scene.video_toolkit_last_output)
video_toolkit.unregister()
"""


if __name__ == "__main__":
    raise SystemExit(main())
