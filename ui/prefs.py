from pathlib import Path

import bpy


def get_game_root():
    return Path(bpy.context.preferences.addons['pragma_udm_io'].preferences.path)


def set_game_root(path):
    bpy.context.preferences.addons['pragma_udm_io'].preferences.path = str(path)


class PragmaPluginPreferences(bpy.types.AddonPreferences):
    bl_idname = 'pragma_udm_io'

    path: bpy.props.StringProperty(name="Game root", subtype='FILE_PATH', description='')

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "path")
