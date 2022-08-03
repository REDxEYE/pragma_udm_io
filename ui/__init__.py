import bpy

from .operators import PRAGMA_OT_PMLDImport, PRAGMA_OT_PMATImport, PRAGMA_OT_PMAPImport
from .prefs import PragmaPluginPreferences


class PRAGMA_MT_Menu(bpy.types.Menu):
    bl_label = "Pragma Assets"
    bl_idname = "IMPORT_MT_PRAGMA"

    def draw(self, context):
        layout = self.layout
        layout.operator(PRAGMA_OT_PMAPImport.bl_idname, text="Pramga map (.pmap, .pmap_b)", )
        layout.operator(PRAGMA_OT_PMLDImport.bl_idname, text="Pramga model (.pmdl, .pmdl_b)", )
        layout.operator(PRAGMA_OT_PMATImport.bl_idname, text="Pramga material (.pmat, .pmat_b)", )
