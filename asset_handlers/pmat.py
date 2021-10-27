import bpy

from ..content_managment.content_manager import ContentManager
from ..pragma_udm_wrapper import UdmProperty
from ..utils.node import *


def import_pmat(asset: UdmProperty, material_name: str):
    assert 'pbr' in asset
    material_asset = asset['pbr']
    cm = ContentManager()
    maps = {}
    for map_name, texture in material_asset['textures'].items():
        path = cm.find_path(texture, 'materials', extension='.dds')
        image = bpy.data.images.load(str(path))
        maps[map_name] = image
    properties = material_asset['properties']

    material = bpy.data.materials.get(material_name, None) or bpy.data.materials.new(material_name)

    if material.get('LOADED'):
        return 'LOADED'

    material['source_loaded'] = True
    material.use_nodes = True
    clean_nodes(material)

    output = create_node(material, Nodes.ShaderNodeOutputMaterial, location=(800, 200))
    shader = create_node(material, Nodes.ShaderNodeBsdfPrincipled, location=(400, 200))
    connect_nodes(material, shader.outputs['BSDF'], output.inputs['Surface'])
    if 'albedo_map' in maps:
        albedo = create_texture_node(material, maps['albedo_map'], 'Albedo', location=(-400, 250))
        connect_nodes(material, albedo.outputs['Color'], shader.inputs['Base Color'])
    if 'normal_map' in maps:
        normalmap_node = create_node(material, Nodes.ShaderNodeNormalMap)
        normal = create_texture_node(material, maps['normal_map'], 'Normal', location=(-400, 000))
        normal.image.colorspace_settings.name = 'Non-Color'
        connect_nodes(material, normal.outputs['Color'], normalmap_node.inputs['Color'])
        connect_nodes(material, normalmap_node.outputs['Normal'], shader.inputs['Normal'])
    if 'rma_map' in maps:
        rma = create_texture_node(material, maps['rma_map'], 'RMA', location=(-400, -250))
        rma.image.colorspace_settings.name = 'Non-Color'
        rma_split = create_node(material, Nodes.ShaderNodeSeparateRGB, location=(-50, -250))
        connect_nodes(material, rma.outputs['Color'], rma_split.inputs['Image'])
