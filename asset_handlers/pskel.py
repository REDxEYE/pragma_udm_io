from typing import List, Dict

import bpy
from mathutils import Vector, Quaternion, Matrix

from ..pragma_udm_wrapper import UdmProperty
from pragma_udm_io.utils import ROT90_X, ROTN90_Z


def import_pskel(name: str, asset: UdmProperty):
    assert asset['assetType'] == 'PSKEL'
    armature_asset = asset['assetData']

    def _collect_bones(current_node, bones: List[Dict]):
        bone_info = {'bone': current_node, 'parent': None}
        bones.append(bone_info)
        bone_names[current_node['index']] = current_node.name
        for child in current_node.get('children', []):
            bone = _collect_bones(child, bones)
            bone['parent'] = current_node
        return bone_info

    bone_names = {}
    all_bones = []
    for bone in armature_asset['bones']:
        _collect_bones(bone, all_bones)
    if len(all_bones) == 1:
        return [], None

    armature = bpy.data.armatures.new(f"{name}_ARM_DATA")
    armature_obj = bpy.data.objects.new(f"{name}_ARM", armature)

    bpy.context.scene.collection.objects.link(armature_obj)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj

    bpy.ops.object.mode_set(mode='EDIT')

    for bone_info in all_bones:
        bone = bone_info['bone']
        parent = bone_info['parent']
        bl_bone = armature.edit_bones.new(bone.name[-63:])
        bl_bone.tail = (Vector([0, 1, 0])) + bl_bone.head
        transform = bone['pose']

        pos = Vector(transform[0:3])
        rot = Quaternion([transform[6], *transform[3:6]])
        scl = Vector(transform[7:10])
        mat = Matrix.Translation(pos) @ rot.to_matrix().to_4x4() @ Matrix.Scale(1, 4, scl)
        mat = ROT90_X @ mat
        mat = mat @ ROTN90_Z

        bl_bone.matrix = mat
        if parent is not None:
            parent = armature.edit_bones.get(parent.name[-63:])
            bl_bone.parent = parent

    bpy.context.scene.collection.objects.unlink(armature_obj)
    return bone_names, armature_obj
