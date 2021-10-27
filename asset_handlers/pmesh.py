from typing import Dict

import bpy
import numpy as np

from ..pragma_udm_wrapper import UdmProperty
from pragma_udm_io.utils import ROTN90_X, transform_vec3, get_material


def import_pmesh(name_prefix, asset: UdmProperty, root: UdmProperty, bone_names: Dict[int,str]):
    assert asset['assetType'] == 'PMESH'
    sub_mesh_data = asset['assetData']
    assert sub_mesh_data['geometryType'] == 'Triangles'
    skin_id = sub_mesh_data['skinMaterialIndex']
    vertices: np.ndarray = sub_mesh_data['vertices']
    indices: np.ndarray = sub_mesh_data['indices']
    weights: np.ndarray = sub_mesh_data['vertexWeights']
    material_name = root['materials'][skin_id]
    mesh_data = bpy.data.meshes.new(f'{name_prefix}_{material_name}_MESH')
    mesh_obj = bpy.data.objects.new(f'{name_prefix}_{material_name}', mesh_data)
    pos = transform_vec3(vertices['pos'], ROTN90_X)
    mesh_data.from_pydata(pos, [], indices.reshape((-1, 3)).tolist())
    mesh_data.update()

    mesh_data.polygons.foreach_set("use_smooth", np.ones(len(mesh_data.polygons)))

    normals = transform_vec3(vertices['n'], ROTN90_X)
    mesh_data.normals_split_custom_set_from_vertices(normals)
    mesh_data.use_auto_smooth = True

    uv_data = mesh_data.uv_layers.new()

    vertex_indices = np.zeros((len(mesh_data.loops, )), dtype=np.uint32)
    mesh_data.loops.foreach_get('vertex_index', vertex_indices)
    uvs = vertices['uv']
    uvs[:, 1] = 1 - uvs[:, 1]
    uv_data.data.foreach_set('uv', uvs[vertex_indices].flatten())

    weight_groups = {bone: mesh_obj.vertex_groups.new(name=bone) for bone in
                     bone_names.values()}

    for n, weights in enumerate(weights):
        for bone_index, weight in zip(weights['id'], weights['w']):
            if weight >= 0 and bone_index >= 0:
                bone_name = bone_names[bone_index]
                weight_groups[bone_name].add([n], weight, 'REPLACE')


    get_material(material_name, mesh_obj)

    mesh_data.update()

    return mesh_obj
