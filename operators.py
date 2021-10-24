from pathlib import Path

import bpy
from bpy.props import StringProperty, CollectionProperty, BoolProperty, FloatProperty
from .import_udm import import_udm_model


class PRAGMA_OT_PMLDImport(bpy.types.Operator):
    """Load Pragme PMDL file"""
    bl_idname = "pragma.pmdl"
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
        for n, file in enumerate(self.files):
            import_udm_model(directory / file.name)
            pass
            # TODO: Implement me
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}
