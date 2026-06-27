from video_toolkit.catalog import (
    blender_modifier_tools,
    categories,
    ffmpeg_tools,
    get_tool,
    all_tools,
)


def test_tool_ids_are_unique():
    ids = [tool.id for tool in all_tools()]
    assert len(ids) == len(set(ids))


def test_expected_blender_vse_modifiers_are_covered():
    modifiers = {tool.blender_modifier for tool in blender_modifier_tools()}
    assert modifiers == {
        "BRIGHT_CONTRAST",
        "COLOR_BALANCE",
        "CURVES",
        "HUE_CORRECT",
        "MASK",
        "TONEMAP",
        "WHITE_BALANCE",
    }


def test_professional_restoration_tools_are_present():
    expected = {
        "deflicker",
        "lighting_normalizer",
        "deflicker_normalize",
        "denoise_light",
        "denoise_strong",
        "restore_sharpness",
        "deinterlace",
        "quick_deshake",
        "stabilize",
    }
    assert expected.issubset({tool.id for tool in all_tools()})


def test_categories_keep_ui_order():
    assert categories() == (
        "Enhance",
        "Color & Tone",
        "Restoration",
        "Resolution & Motion",
        "Blender VSE Modifiers",
    )


def test_ffmpeg_tools_have_filters_or_stabilization():
    for tool in ffmpeg_tools():
        assert tool.ffmpeg_filter or tool.two_pass_stabilize


def test_get_tool_rejects_unknown_id():
    try:
        get_tool("missing")
    except KeyError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("unknown tool id should raise KeyError")

