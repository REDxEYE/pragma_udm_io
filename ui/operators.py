from pathlib import Path

import bpy
from bpy.props import StringProperty, CollectionProperty, BoolProperty, FloatProperty

from ..pragma_udm_wrapper import UDM
from ..asset_handlers.pmat import import_pmat
from ..content_managment.content_manager import ContentManager
from ..asset_handlers.pmdl import import_pmdl
from .prefs import get_game_root


class PRAGMA_OT_PMLDImport(bpy.types.Operator):
    """Load Pragme PMDL file"""
    bl_idname = "pragma.import_pmdl"
    bl_label = "Import Pragma Pmdl file"
    bl_options = {'UNDO'}

    filepath: StringProperty(subtype="FILE_PATH")
    files: CollectionProperty(name='File paths', type=bpy.types.OperatorFileListElement)
    filter_glob: StringProperty(default="*.pmdl;*.pmdl_b", options={'HIDDEN'})

    single_collection: BoolProperty(name="Load everything into 1 collection", default=False, subtype='UNSIGNED')

    def execute(self, context):

        if Path(self.filepath).is_file():
            directory = Path(self.filepath).parent.absolute()
        else:
            directory = Path(self.filepath).absolute()
        ContentManager().set_root(get_game_root())
        for n, file in enumerate(self.files):
            import_pmdl(directory / file.name)
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}


class PRAGMA_OT_PMATImport(bpy.types.Operator):
    """Load Pragme PMDL file"""
    bl_idname = "pragma.import_pmat"
    bl_label = "Import Pragma Pmat file"
    bl_options = {'UNDO'}

    filepath: StringProperty(subtype="FILE_PATH")
    files: CollectionProperty(name='File paths', type=bpy.types.OperatorFileListElement)
    filter_glob: StringProperty(default="*.pmat;*.pmat_b", options={'HIDDEN'})

    def execute(self, context):

        if Path(self.filepath).is_file():
            directory = Path(self.filepath).parent.absolute()
        else:
            directory = Path(self.filepath).absolute()
        ContentManager().set_root(get_game_root())
        for n, file in enumerate(self.files):
            udm = UDM()
            udm.load(directory / file.name)
            print(udm, udm.root)
            import_pmat(udm.root, file.name)
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}
