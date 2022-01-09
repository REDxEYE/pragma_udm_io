from pathlib import Path

import bpy

from ..content_managment.content_manager import ContentManager
from ..pragma_udm_wrapper import UdmProperty
from ..utils.node import *
from .vtf import load_texture
from ..utils.texture_utils import texture_from_data


def _load_textures(textures):
    cm = ContentManager()
    maps = {}
    for map_name, texture in textures.items():
        path: Path = (cm.find_path(texture, 'materials', extension='.dds') or
                      cm.find_path(texture, 'materials', extension='.vtf'))
        if path is None:
            continue
        if path.suffix == '.vtf':
            image = bpy.data.images.get(texture, None)
            if image is None:
                image_data, w, h = load_texture(path.open('rb'))
                image = texture_from_data(texture, image_data, w, h, False)
        else:
            image = bpy.data.images.get(texture, None)
            if image is None:
                image = bpy.data.images.load(str(path))
                image.name = texture
        maps[map_name] = image
    return maps


def _add_alpha(material, properties, albedo, shader):
    if 'alpha_mode' not in properties:
        return
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


def _add_color_factor(material, properties, input_socket, output_socket):
    if 'color_factor' in properties:
        color = properties['color_factor']
        color_mix = create_node(material, Nodes.ShaderNodeMixRGB, location=(-50, 250))
        color_mix.blend_type = 'MULTIPLY'
        color_mix.inputs['Fac'].default_value = 1.0
        connect_nodes(material, input_socket, color_mix.inputs['Color1'])
        color_mix.inputs['Color2'].default_value = (*color, 1.0)[:4]
        connect_nodes(material, color_mix.outputs['Color'], output_socket)
        return color_mix.outputs['Color']
    else:
        connect_nodes(material, input_socket, output_socket)
        return input_socket


def _add_normal_map(material, maps, shader):
    if 'normal_map' in maps:
        normal = create_texture_node(material, maps['normal_map'], 'Normal', location=(-400, 000))
        normal.image.colorspace_settings.name = 'Non-Color'
        normalmap_node = create_node(material, Nodes.ShaderNodeNormalMap, location=(-50, 000))
        connect_nodes(material, normal.outputs['Color'], normalmap_node.inputs['Color'])
        connect_nodes(material, normalmap_node.outputs['Normal'], shader.inputs['Normal'])


def _add_rma_map(material, properties, maps, shader):
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


def _handle_pbr(material_asset: UdmProperty, material_name: str):
    maps = _load_textures(material_asset['textures'])
    properties = material_asset['properties']

    material = bpy.data.materials.get(material_name, None) or bpy.data.materials.new(material_name)

    if material.get('udm_loaded'):
        return 'LOADED'

    material['udm_loaded'] = True
    material.use_nodes = True
    clean_nodes(material)

    output = create_node(material, Nodes.ShaderNodeOutputMaterial, location=(800, 200))
    shader = create_node(material, Nodes.ShaderNodeBsdfPrincipled, location=(400, 200))
    connect_nodes(material, shader.outputs['BSDF'], output.inputs['Surface'])

    if 'albedo_map' in maps:
        albedo = create_texture_node(material, maps['albedo_map'], 'Albedo', location=(-400, 250))

        _add_color_factor(material, properties, albedo.outputs['Color'], shader.inputs['Base Color'])

        _add_alpha(material, properties, albedo, shader)

    _add_normal_map(material, maps, shader)

    _add_rma_map(material, properties, maps, shader)

    if 'emission_map ' in maps:
        emission_map = create_texture_node(material, maps['emission_map'], 'Emission', location=(-700, 250))
        connect_nodes(material, emission_map.outputs['Color'], shader.inputs['Emission'])
        shader.inputs['Emission Strength'].default_value = properties.get('emission_factor', 1.0)


def _handle_pbr_blend(material_asset: UdmProperty, material_name: str):
    maps = _load_textures(material_asset['textures'])
    properties = material_asset['properties']

    material = bpy.data.materials.get(material_name, None) or bpy.data.materials.new(material_name)

    if material.get('udm_loaded'):
        return 'LOADED'

    material['udm_loaded'] = True
    material.use_nodes = True
    clean_nodes(material)

    output = create_node(material, Nodes.ShaderNodeOutputMaterial, location=(800, 200))
    shader = create_node(material, Nodes.ShaderNodeBsdfPrincipled, location=(400, 200))
    connect_nodes(material, shader.outputs['BSDF'], output.inputs['Surface'])

    if 'albedo_map' in maps and 'albedo_map2' in maps:
        albedo = create_texture_node(material, maps['albedo_map'], 'Albedo', location=(-650, 250))
        albedo2 = create_texture_node(material, maps['albedo_map2'], 'Albedo2', location=(-650, 0))

        mix_node = create_node(material, Nodes.ShaderNodeMixRGB, location=(-50, 200))

        vertex_color_node = create_node(material, Nodes.ShaderNodeVertexColor, location=(-650, 350))
        vertex_color_node.layer_name = 'alpha'
        connect_nodes(material, vertex_color_node.outputs['Alpha'], mix_node.inputs['Fac'])

        connect_nodes(material, albedo.outputs['Color'], mix_node.inputs['Color1'])
        connect_nodes(material, albedo2.outputs['Color'], mix_node.inputs['Color2'])

        _add_color_factor(material, properties, mix_node.outputs['Color'], shader.inputs['Base Color'])

        _add_alpha(material, properties, albedo, shader)

    _add_normal_map(material, maps, shader)

    _add_rma_map(material, properties, maps, shader)

    if 'emission_map ' in maps:
        emission_map = create_texture_node(material, maps['emission_map'], 'Emission', location=(-700, 250))
        connect_nodes(material, emission_map.outputs['Color'], shader.inputs['Emission'])
        shader.inputs['Emission Strength'].default_value = properties.get('emission_factor', 1.0)


def _handle_unlit(material_asset: UdmProperty, material_name: str):
    maps = _load_textures(material_asset['textures'])
    properties = material_asset['properties']

    material = bpy.data.materials.get(material_name, None) or bpy.data.materials.new(material_name)

    if material.get('udm_loaded'):
        return 'LOADED'

    material['udm_loaded'] = True
    material.use_nodes = True
    clean_nodes(material)

    output = create_node(material, Nodes.ShaderNodeOutputMaterial, location=(800, 200))
    shader = create_node(material, Nodes.ShaderNodeBsdfPrincipled, location=(400, 200))
    shader.inputs['Specular'].default_value = 0.0
    connect_nodes(material, shader.outputs['BSDF'], output.inputs['Surface'])

    if 'albedo_map' in maps:
        albedo = create_texture_node(material, maps['albedo_map'], 'Albedo', location=(-400, 250))

        color_out = _add_color_factor(material, properties, albedo.outputs['Color'], shader.inputs['Base Color'])
        connect_nodes(material, color_out, shader.inputs['Emission'])
        _add_alpha(material, properties, albedo, shader)


def _handle_water(material_asset: UdmProperty, material_name: str):
    maps = _load_textures(material_asset['textures'])
    properties = material_asset['properties']

    material = bpy.data.materials.get(material_name, None) or bpy.data.materials.new(material_name)
    material.use_screen_refraction = True
    material.use_backface_culling = True

    if material.get('udm_loaded'):
        return 'LOADED'

    material['udm_loaded'] = True
    material.use_nodes = True
    clean_nodes(material)

    output = create_node(material, Nodes.ShaderNodeOutputMaterial, location=(800, 200))
    shader = create_node(material, Nodes.ShaderNodeBsdfPrincipled, location=(400, 200))
    shader.inputs['Specular'].default_value = 0.5
    shader.inputs['Roughness'].default_value = 0.035
    shader.inputs['Transmission'].default_value = 1
    shader.inputs['Base Color'].default_value = properties['fog']['color']
    connect_nodes(material, shader.outputs['BSDF'], output.inputs['Surface'])
    create_texture_node(material, maps['dudv_map'], 'DUDV', (-500, 0))
    _add_normal_map(material, maps, shader)


def import_pmat(asset: UdmProperty, material_name: str):
    if 'pbr' in asset:
        return _handle_pbr(asset['pbr'], material_name)
    elif 'pbr_blend' in asset:
        return _handle_pbr_blend(asset['pbr_blend'], material_name)
    elif 'unlit' in asset:
        return _handle_unlit(asset['unlit'], material_name)
    elif 'water' in asset:
        return _handle_water(asset['water'], material_name)
    else:
        print(asset.to_dict())
        print(f'Unsupported shader {next(asset.items())[0]}')
        return 'UNSUPPORTED'
