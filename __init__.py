import bpy
from pragma_udm_io.ui import *

bl_info = {
    "name": "Pragma UDM IO",
    "author": "RED_EYE",
    "version": (0, 0, 2),
    "blender": (2, 80, 0),
    "location": "File > Import-Export > UDM assets",
    "description": "Pragma Engine assets. "
                   "To remove addon, disable it, restart blender and then click \"remove\" button",
    "category": "Import-Export"
}

classes = (
    PragmaPluginPreferences,
    PRAGMA_OT_PMLDImport,
)

register_, unregister_ = bpy.utils.register_classes_factory(classes)


def menu_import(self, context):
    # source_io_icon = custom_icons["main"]["sourceio_icon"]
    # self.layout.menu(PRAGMA_OT_PMLDImport.bl_idname, icon_value=source_io_icon.icon_id)
    layout = self.layout
    layout.operator(PRAGMA_OT_PMLDImport.bl_idname,
                    text="Pramga model (.pmdl, .pmdl_b)", )  # icon_value=crowbar_icon.icon_id)


def register():
    # register_custom_icon()
    register_()
    bpy.types.TOPBAR_MT_file_import.append(menu_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)

    # SingletonMeta.cleanup()

    # unregister_custom_icon()
    unregister_()
