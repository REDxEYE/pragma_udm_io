from typing import List

import bpy
from mathutils import Vector, Quaternion, Matrix

from ..pragma_udm_wrapper import UdmProperty
from ..utils import ROT90_X, ROTN90_Z


def import_pskel(name: str, asset: UdmProperty):
    assert asset['assetType'] == 'PSKEL'
    armature_asset = asset['assetData']

    armature = bpy.data.armatures.new(f"{name}_ARM_DATA")
    armature_obj = bpy.data.objects.new(f"{name}_ARM", armature)

    bpy.context.scene.collection.objects.link(armature_obj)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj

    bpy.ops.object.mode_set(mode='EDIT')
    bone_names = {}

    def _collect_bones(current_node, bones: List[UdmProperty]):
        bones.append(current_node)
        bone = armature.edit_bones.new(current_node.name[-63:])
        bone.tail = (Vector([0, 1, 0])) + bone.head
        transform = current_node['pose']

        pos = Vector(transform[0:3])
        rot = Quaternion([transform[6], *transform[3:6]])
        scl = Vector(transform[7:10])
        mat = Matrix.Translation(pos) @ rot.to_matrix().to_4x4() @ Matrix.Scale(1, 4, scl)
        mat = ROT90_X @ mat
        mat = mat @ ROTN90_Z
        bone.matrix = mat

        bone_names[current_node['index']] = current_node.name

        for child in current_node.get('children', []):
            child_bone = _collect_bones(child, bones)
            child_bone.parent = bone
        return bone

    all_bones = []
    for bone in armature_asset['bones']:
        _collect_bones(bone, all_bones)

    bpy.context.scene.collection.objects.unlink(armature_obj)
    return bone_names, armature_obj
