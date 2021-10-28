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

        if 'color_factor' in properties:
            color = properties['color_factor']
            color_mix = create_node(material, Nodes.ShaderNodeMixRGB, location=(-50, 250))
            color_mix.blend_type = 'MULTIPLY'
            color_mix.inputs['Fac'].default_value = 1.0
            connect_nodes(material, albedo.outputs['Color'], color_mix.inputs['Color1'])
            color_mix.inputs['Color2'].default_value = (*color, 1.0)
            connect_nodes(material, color_mix.outputs['Color'], shader.inputs['Base Color'])
        else:
            connect_nodes(material, albedo.outputs['Color'], shader.inputs['Base Color'])

        if 'alpha_mode' in properties:
            alpha_mode = properties['alpha_mode']
            if isinstance(alpha_mode, str):
                alpha_mode = {'Opaque': 0, 'Mask': 1, 'Blend': 2}[alpha_mode]
            if alpha_mode == 1:
                material.blend_method = 'CLIP'
                material.alpha_threshold = properties.get('alpha_cutoff', 0.5)
            elif alpha_mode == 2:
                material.blend_method = 'HASHED'

            if alpha_mode > 0:
                connect_nodes(material, albedo.outputs['Alpha'], shader.inputs['Alpha'])

    if 'normal_map' in maps:
        normal = create_texture_node(material, maps['normal_map'], 'Normal', location=(-400, 000))
        normal.image.colorspace_settings.name = 'Non-Color'
        normalmap_node = create_node(material, Nodes.ShaderNodeNormalMap, location=(-50, 000))
        connect_nodes(material, normal.outputs['Color'], normalmap_node.inputs['Color'])
        connect_nodes(material, normalmap_node.outputs['Normal'], shader.inputs['Normal'])

    if 'rma_map' in maps:
        rma = create_texture_node(material, maps['rma_map'], 'RMA', location=(-400, -250))
        rma.image.colorspace_settings.name = 'Non-Color'
        rma_split = create_node(material, Nodes.ShaderNodeSeparateRGB, location=(-50, -250))
        connect_nodes(material, rma.outputs['Color'], rma_split.inputs['Image'])
        if 'roughness_factor' in properties or 'specular_factor' in properties:
            if 'roughness_factor' in properties:
                roughness_factor = properties['roughness_factor']
            else:
                roughness_factor = 1 - properties['specular_factor']
            r_multiply = create_node(material, Nodes.ShaderNodeMath, name='Roughness-Multiplier', location=(-50, -400))
            r_multiply.operation = 'MULTIPLY'
            connect_nodes(material, rma_split.outputs['G'], r_multiply.inputs[0])
            r_multiply.inputs[1].default_value = roughness_factor
            connect_nodes(material, r_multiply.outputs[0], shader.inputs['Roughness'])
        else:
            connect_nodes(material, rma_split.outputs['G'], shader.inputs['Roughness'])

        if 'metalness_factor' in properties:
            m_multiply = create_node(material, Nodes.ShaderNodeMath, name='Metallic-Multiplier', location=(-50, -550))
            m_multiply.operation = 'MULTIPLY'
            connect_nodes(material, rma_split.outputs['B'], m_multiply.inputs[0])
            m_multiply.inputs[1].default_value = properties['metalness_factor']
            connect_nodes(material, m_multiply.outputs[0], shader.inputs['Metallic'])
        else:
            connect_nodes(material, rma_split.outputs['B'], shader.inputs['Metallic'])

    if 'emission_map ' in maps:
        emission_map = create_texture_node(material, maps['emission_map'], 'Emission', location=(-700, 250))
        connect_nodes(material, emission_map.outputs['Color'], shader.inputs['Emission'])
        shader.inputs['Emission Strength'].default_value = properties.get('emission_factor', 1.0)
