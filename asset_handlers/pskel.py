from typing import List, Dict

import bpy
import numpy as np
from mathutils import Vector, Quaternion, Matrix

from ..pragma_udm_wrapper import pose_to_matrix, convert_pragma_matrix
from ..pragma_udm_wrapper.properties import ElementProperty
from pragma_udm_io.utils import ROT90_X, ROTN90_Z

def convert_loc(x): return Vector([x[0], -x[2], x[1]])
def convert_quat(q): return Quaternion([q[3], q[0], -q[2], q[1]])
def convert_scale(s): return Vector([s[0], s[2], s[1]])

def to_matrix(m):
    return Matrix([
        [m[0],m[1],m[2],m[3]],
        [m[4],m[5],m[6],m[7]],
        [m[8],m[9],m[10],m[11]],
        [m[12],m[13],m[14],m[15]]
    ])

u = 1.0
def convert_matrix(m):
    return Matrix([
        [   m[0],   -m[ 8],    m[4],  m[12]*u],
        [  -m[2],    m[10],   -m[6], -m[14]*u],
        [   m[1],   -m[ 9],    m[5],  m[13]*u],
        [ m[3]/u, -m[11]/u,  m[7]/u,    m[15]],
    ])
def matrix_to_list(m):
    return [m[0][0],m[0][1],m[0][2],m[0][3],m[1][0],m[1][1],m[1][2],m[1][3],m[2][0],m[2][1],m[2][2],m[2][3],m[3][0],m[3][1],m[3][2],m[3][3]]

def nearby_signed_perm_matrix(rot):
    """Returns a signed permutation matrix close to rot.to_matrix().
    (A signed permutation matrix is like a permutation matrix, except
    the non-zero entries can be ±1.)
    """
    m = rot.to_matrix()
    x, y, z = m[0], m[1], m[2]

    # Set the largest entry in the first row to ±1
    a, b, c = abs(x[0]), abs(x[1]), abs(x[2])
    i = 0 if a >= b and a >= c else 1 if b >= c else 2
    x[i] = 1 if x[i] > 0 else -1
    x[(i+1) % 3] = 0
    x[(i+2) % 3] = 0

    # Same for second row: only two columns to consider now.
    a, b = abs(y[(i+1) % 3]), abs(y[(i+2) % 3])
    j = (i+1) % 3 if a >= b else (i+2) % 3
    y[j] = 1 if y[j] > 0 else -1
    y[(j+1) % 3] = 0
    y[(j+2) % 3] = 0

    # Same for third row: only one column left
    k = (0 + 1 + 2) - i - j
    z[k] = 1 if z[k] > 0 else -1
    z[(k+1) % 3] = 0
    z[(k+2) % 3] = 0

    return m

def import_pskel(name: str, asset: ElementProperty, scale=1.0):
    assert asset['assetType'] == 'PSKEL'
    armature_asset = asset['assetData']

    bone_name_to_bone = {}
    def _collect_bones(current_node, bones: List[Dict]):
        bone_info = {'bone': current_node, 'parent': None, 'children': []}
        bones.append(bone_info)
        bone_names[current_node['index']] = current_node.name
        bone_name_to_bone[current_node.name] = bone_info
        for child in current_node.get('children', {}).values():
            bone = _collect_bones(child, bones)
            bone['parent'] = current_node
            bone_info['children'].append(bone)
        return bone_info

    bone_names = {}
    all_bones = []
    for bone in armature_asset['bones'].values():
        _collect_bones(bone, all_bones)
    if len(all_bones) == 1:
        return [], None

    armature = bpy.data.armatures.new(f"{name}_ARM_DATA")
    armature_obj = bpy.data.objects.new(f"{name}_ARM", armature)

    bpy.context.scene.collection.objects.link(armature_obj)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj

    bpy.ops.object.mode_set(mode='EDIT')

    rootBones = []

    bind_trans = {}
    bind_rot = {}
    editbone_trans = {}
    editbone_rot = {}
    rotation_before = {}
    rotation_after = {}
    edit_bones = {}

    def generate_bind_pose_matrices(bones):
        invBindMatrices = {}
        for bone_info in bones:
            bone = bone_info['bone']
            transform = bone['pose']
            pos = Vector(transform[0:3])
            rot = Quaternion([transform[6], *transform[3:6]])
            m = Matrix.LocRotScale(Vector(pos) /40.0,Quaternion(rot),(1,1,1)).inverted()
            m = matrix_to_list(m)
            m = convert_matrix(m)
            m = m.transposed()
            invBindMatrices[bone.name] = matrix_to_list(m)
        return invBindMatrices

    invBindMatrices = generate_bind_pose_matrices(all_bones)

    for key in invBindMatrices:
        invBindMatrices[key][3] *= 4.0;
        invBindMatrices[key][7] *= 4.0;
        invBindMatrices[key][11] *= 4.0;

    for bone_info in all_bones:
        bone = bone_info['bone']
        parent = bone_info['parent']
        bl_bone = armature.edit_bones.new(bone.name[-63:])
        bl_bone.tail = (Vector([0, 1, 0])) + bl_bone.head
        transform = bone['pose']

        pos = Vector(transform[0:3])
        rot = Quaternion([transform[6], *transform[3:6]])
        pos = pos *4.0

        bind_trans[bone.name] = Vector(pos)
        bind_rot[bone.name] = Quaternion(rot)

        invBindMatrix = invBindMatrices[bone.name]
        if parent is not None:
            print("Bone has parent, guessing bind pose...")
            bind_local = to_matrix(invBindMatrices[parent.name]) @ to_matrix(invBindMatrix).inverted_safe()
            print("Parent matrix: ",to_matrix(invBindMatrices[parent.name]))
            print("This matrix: ",to_matrix(invBindMatrix))
            print("bind_local: ",bind_local)
            t, r, _s = bind_local.decompose()
            bind_trans[bone.name] = Vector(t)
            bind_rot[bone.name] = Quaternion(r)

            print("bind_trans: ",t)
            print("bind_rot: ",r)

        if parent is None:
            rootBones.append(bone_info)

        editbone_trans[bone.name] = bind_trans[bone.name]
        editbone_rot[bone.name] = bind_rot[bone.name]
        rotation_before[bone.name] = Quaternion((1, 0, 0, 0))
        rotation_after[bone.name] = Quaternion((1, 0, 0, 0))
        edit_bones[bone.name] = bl_bone
        print("Final translation: ",editbone_trans[bone.name])
        print("Final rotation: ",editbone_rot[bone.name])
        print("\n\n\n\n")

    bind_arma_mats = {}
    editbone_arma_mats = {}

    def temperance(bone_id, parent_rot):
        # Try to put our tip at the centroid of our children
        child_locs = [
            editbone_trans[child['bone'].name]
            for child in bone_name_to_bone[bone_id]['children']
        ]
        child_locs = [loc for loc in child_locs]
        if child_locs:
            centroid = sum(child_locs, Vector((0, 0, 0)))
            rot = Vector((0, 1, 0)).rotation_difference(centroid)

            # Snap to the local axes; required for local_rotation to be
            # accurate when vnode has a non-uniform scaling.
            rot = nearby_signed_perm_matrix(rot).to_quaternion()
            return rot

        return parent_rot

    def pick_bone_rotation(bone_id, parent_rot):
        return temperance(bone_id, parent_rot)

    def local_rotation(vnode_id, rot):
        """Appends a local rotation to vnode's world transform:
        (new world transform) = (old world transform) @ (rot)
        without changing the world transform of vnode's children.

        For correctness, rot must be a signed permutation of the axes
        (eg. (X Y Z)->(X -Z Y)) OR vnode's scale must always be uniform.
        """
        rotation_before[vnode_id] @= rot

        # Append the inverse rotation after children's TRS to cancel it out.
        rot_inv = rot.conjugated()
        for child_bone_info in bone_name_to_bone[vnode_id]['children']:
            rotation_after[child_bone_info['bone'].name] = \
                rot_inv @ rotation_after[child_bone_info['bone'].name]

    def rotate_edit_bone(bone_id, rot):
        """Rotate one edit bone without affecting anything else."""
        editbone_rot[bone_id] @= rot
        # Cancel out the rotation so children aren't affected.
        rot_inv = rot.conjugated()
        for child_bone_info in bone_name_to_bone[bone_id]['children']:
            editbone_trans[child_bone_info['bone'].name] = rot_inv @ editbone_trans[child_bone_info['bone'].name]
            editbone_rot[child_bone_info['bone'].name] = rot_inv @ editbone_rot[child_bone_info['bone'].name]
        # Need to rotate the bone's final TRS by the same amount so skinning
        # isn't affected.
        local_rotation(bone_id, rot)

    def prettify_bones(bone_info, parent_rot=None):
        rot = None

        rot = pick_bone_rotation(bone_info['bone'].name, parent_rot)
        if rot is not None:
            rotate_edit_bone(bone_info['bone'].name, rot)

        for child_bone_info in bone_info['children']:
            prettify_bones(child_bone_info,rot)

    def calc_bind_poses(bone_info):
        if bone_info['parent'] is not None:
            parent_bind_mat = bind_arma_mats[bone_info['parent'].name]
            parent_editbone_mat = editbone_arma_mats[bone_info['parent'].name]
        else:
            parent_bind_mat = Matrix.Identity(4)
            parent_editbone_mat = Matrix.Identity(4)

        t, r = bind_trans[bone_info['bone'].name], bind_rot[bone_info['bone'].name]
        local_to_parent = Matrix.Translation(t) @ Quaternion(r).to_matrix().to_4x4()
        bind_arma_mats[bone_info['bone'].name] = parent_bind_mat @ local_to_parent

        t, r = editbone_trans[bone_info['bone'].name], editbone_rot[bone_info['bone'].name]
        local_to_parent = Matrix.Translation(t) @ Quaternion(r).to_matrix().to_4x4()
        editbone_arma_mats[bone_info['bone'].name] = parent_editbone_mat @ local_to_parent

        print("Bone: ",bone_info['bone'].name)
        print("bind_arma_mat: ",bind_arma_mats[bone_info['bone'].name])
        print("editbone_arma_mat: ",editbone_arma_mats[bone_info['bone'].name])
        print("")
        print("")
        print("")
        print("")

        for child_bone_info in bone_info['children']:
            calc_bind_poses(child_bone_info)

    def apply_bone_pose(bone_info,parent_info=None):
        editbone = edit_bones[bone_info['bone'].name]
        # Give the position of the bone in armature space
        arma_mat = editbone_arma_mats[bone_info['bone'].name]
        editbone.head = arma_mat @ Vector((0, 0, 0))
        editbone.tail = arma_mat @ Vector((0, 1, 0))
        # editbone.length = vnode.bone_length
        editbone.align_roll(arma_mat @ Vector((0, 0, 1)) - editbone.head)

        if parent_info is not None:
            parent = armature.edit_bones.get(parent_info['bone'].name[-63:])
            editbone.parent = parent

        for child_bone_info in bone_info['children']:
            apply_bone_pose(child_bone_info,bone_info)

    for bone_info in rootBones:
        prettify_bones(bone_info)

    for bone_info in rootBones:
        calc_bind_poses(bone_info)

    for bone_info in rootBones:
        apply_bone_pose(bone_info)

    print("rotation_before: ",rotation_before)
    print("rotation_after: ",rotation_after)

        #bl_bone.head = arma_mat @ Vector((0, 0, 0))
        #bl_bone.tail = arma_mat @ Vector((0, 1, 0))
        # bl_bone.length = vnode.bone_length
        #bl_bone.align_roll(arma_mat @ Vector((0, 0, 1)) - bl_bone.head)

        #bl_bone.matrix = mat
        #if parent is not None:
        #    parent = armature.edit_bones.get(parent.name[-63:])
        #    bl_bone.parent = parent

    bpy.ops.object.mode_set(mode='POSE')
    for bone_info in all_bones:
        bone = bone_info['bone']
        armature_obj.pose.bones[bone.name[-63:]].rotation_mode = 'QUATERNION'

    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.scene.collection.objects.unlink(armature_obj)
    return bone_names, armature_obj
