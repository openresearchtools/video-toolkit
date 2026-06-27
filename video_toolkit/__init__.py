"""Open Research Video Toolkit Blender add-on entry point."""

bl_info = {
    "name": "Open Research Video Toolkit",
    "author": "Open Research Tools",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "Video Sequencer > Tools > Video Filters",
    "description": "One-click video enhancement, VSE filters, and restoration tools.",
    "category": "Sequencer",
}


def register():
    from . import addon

    addon.register()


def unregister():
    from . import addon

    addon.unregister()

