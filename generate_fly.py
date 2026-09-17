"""
Drosophila melanogaster (Fruit Fly) 3D Model Generator - v4 Master
===================================================================
High quality, anatomically authentic low-poly 3D fruit fly model:
- Natural perched posture with full 6-leg support on ground (Z = 0).
- Fully integrated head with almond/kidney-shaped wrap-around ruby compound eyes.
- Aristate antennae with plumose arista and ventral proboscis.
- Realistic humped mesothorax with posterior scutellum shield.
- Discrete 6-segment banded abdomen with crisp alternating melanic tergite plates.
- Realistic contoured translucent wings with costal curve, veins, and rest overlap.
- True Forward-Kinematics joint origins for legs and wings.
- Balanced studio lighting and beautifully framed 3/4 camera.
"""

import bpy
import bmesh
import math
from mathutils import Vector, Matrix, Euler, Quaternion
import os

def clean_scene():
    if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    for col in (bpy.data.meshes, bpy.data.materials, bpy.data.textures, bpy.data.armatures, bpy.data.lights, bpy.data.cameras):
        for item in list(col):
            col.remove(item)

def create_pbr_material(name, base_color, roughness=0.35, specular=0.5, alpha=1.0, is_translucent=False):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
        output = nodes.get("Material Output")
        mat.node_tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
        
    bsdf.inputs["Base Color"].default_value = base_color
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = roughness
    if "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = specular
    elif "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = specular
    if "Alpha" in bsdf.inputs:
        bsdf.inputs["Alpha"].default_value = alpha

    if is_translucent:
        if "Transmission" in bsdf.inputs:
            bsdf.inputs["Transmission"].default_value = 0.80
        elif "Transmission Weight" in bsdf.inputs:
            bsdf.inputs["Transmission Weight"].default_value = 0.80
        if hasattr(mat, "blend_method"):
            mat.blend_method = 'BLEND'
        if hasattr(mat, "shadow_method"):
            mat.shadow_method = 'NONE'
            
    return mat

def parent_keep_transform(child, parent):
    bpy.context.view_layer.update()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()

def create_limb_segment(name, p1, p2, r1, r2, segments=8, mat=None):
    """
    Creates an articulated limb cylinder from p1 to p2.
    Origin is strictly placed at p1 (joint pivot).
    """
    p1 = Vector(p1)
    p2 = Vector(p2)
    delta = p2 - p1
    length = max(delta.length, 1e-5)
    direction = delta.normalized()

    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=segments,
        radius1=r1, radius2=r2, depth=length,
        matrix=Matrix.Translation((0, 0, length / 2.0))
    )
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm.to_mesh(mesh)
    bm.free()

    for poly in mesh.polygons:
        poly.use_smooth = True

    obj = bpy.data.objects.new(name, mesh)
    obj.location = p1
    
    rot_quat = Vector((0, 0, 1)).rotation_difference(direction)
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = rot_quat
    obj.rotation_mode = 'XYZ'

    if mat:
        obj.data.materials.append(mat)
    return obj

# -------------------------------------------------------------
# Detailed Anatomical Builders
# -------------------------------------------------------------

def build_thorax(materials, col, center):
    """
    Mesothorax:
    - Scutum: Dorsally humped oval shield.
    - Scutellum: Posterior triangular shield overhanging petiole.
    """
    cx, cy, cz = center
    bm = bmesh.new()
    
    # Scutum
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=18, radius=0.46)
    for v in bm.verts:
        v.co.x *= 1.10
        v.co.y *= 1.35
        v.co.z *= 0.88
        # Flatten dorsum slightly, keep hump at anterior third
        if v.co.z > 0:
            v.co.z += 0.08 * math.exp(-((v.co.y - 0.08)**2) * 8.0)
        # Narrow toward neck at front
        if v.co.y > 0.2:
            f = 1.0 - 0.35 * (v.co.y - 0.2)
            v.co.x *= f
            v.co.z *= f
        # Scutellum taper at posterior
        if v.co.y < -0.2:
            f = 1.0 + 0.25 * (v.co.y + 0.2)
            v.co.x *= max(0.5, f)

    # Scutellum shield geometry (posterior triangular plate)
    scut = [
        Vector((0.0, -0.58, 0.10)),
        Vector((-0.18, -0.40, 0.08)),
        Vector((0.18, -0.40, 0.08)),
        Vector((0.0, -0.74, 0.04)),
    ]
    bm_s = [bm.verts.new(v) for v in scut]
    bm.faces.new([bm_s[0], bm_s[1], bm_s[2]])
    bm.faces.new([bm_s[0], bm_s[2], bm_s[3]])
    bm.faces.new([bm_s[0], bm_s[3], bm_s[1]])

    mesh = bpy.data.meshes.new("Thorax_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True

    obj = bpy.data.objects.new("Thorax", mesh)
    obj.location = Vector((cx, cy, cz))
    col.objects.link(obj)
    obj.data.materials.append(materials["cuticle_tan"])
    return obj

def build_head_complex(materials, body_col, sensory_col, thorax_obj, head_pos):
    """
    Anatomically authentic Drosophila head:
    - Slender cervix (neck).
    - Head capsule: flattened anterior-posteriorly, curved vertex.
    - Large wrap-around compound eyes (kidney/almond shaped, burgundy-ruby).
    - Antennae nestled in facial depression with feathery arista.
    - Hinged ventral mouthparts.
    """
    hx, hy, hz = head_pos

    # 1. Neck
    neck = create_limb_segment("Neck", (hx, hy - 0.18, hz - 0.05), (hx, hy - 0.02, hz), 0.08, 0.11, 8, materials["cuticle_tan"])
    body_col.objects.link(neck)
    parent_keep_transform(neck, thorax_obj)

    # 2. Central Head Capsule (Face + Vertex)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=18, v_segments=14, radius=0.28)
    for v in bm.verts:
        v.co.x *= 1.08  # Width between eyes
        v.co.y *= 0.65  # Flattened front-to-back
        v.co.z *= 1.15  # Height
        # Facial depression (antennal fovea)
        if v.co.y > 0.0 and abs(v.co.x) < 0.10:
            v.co.y -= 0.05
            
    head_mesh = bpy.data.meshes.new("Head_Mesh")
    bm.to_mesh(head_mesh)
    bm.free()
    for poly in head_mesh.polygons:
        poly.use_smooth = True

    head_obj = bpy.data.objects.new("Head", head_mesh)
    head_obj.location = Vector((hx, hy, hz))
    body_col.objects.link(head_obj)
    head_obj.data.materials.append(materials["cuticle_tan"])
    parent_keep_transform(head_obj, thorax_obj)

    # 3. Compound Eyes (Almond/Kidney shaped, wrapping around lateral head)
    for side, sign in [("L", -1), ("R", 1)]:
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=16, radius=0.24)
        for v in bm.verts:
            # Ellipsoid eye geometry
            v.co.x *= 0.82
            v.co.y *= 1.28
            v.co.z *= 1.35
            # Kidney curve: inner medial surface slightly flattened against head capsule
            if sign * v.co.x < 0:
                v.co.x *= 0.70
            # Bulbous forward wrap
            if v.co.y > 0:
                v.co.y += 0.02

        eye_mesh = bpy.data.meshes.new(f"Eye_{side}_Mesh")
        bm.to_mesh(eye_mesh)
        bm.free()
        for poly in eye_mesh.polygons:
            poly.use_smooth = True

        eye_obj = bpy.data.objects.new(f"Eye_{side}", eye_mesh)
        # Position seamlessly wrapping the lateral frons
        eye_pos = Vector((hx + sign * 0.22, hy + 0.02, hz + 0.02))
        eye_obj.location = eye_pos
        eye_obj.rotation_euler = Euler((math.radians(10), math.radians(sign * -12), math.radians(sign * 20)), 'XYZ')
        sensory_col.objects.link(eye_obj)
        eye_obj.data.materials.append(materials["compound_eye"])
        parent_keep_transform(eye_obj, head_obj)

    # 4. Antennae (Aristate with branched arista)
    for side, sign in [("L", -1), ("R", 1)]:
        ant_base = Vector((hx + sign * 0.05, hy + 0.16, hz + 0.02))
        ant_mid = Vector((hx + sign * 0.08, hy + 0.26, hz + 0.06))
        ant_pedicel = create_limb_segment(f"Antenna_{side}", ant_base, ant_mid, 0.028, 0.014, 6, materials["cuticle_dark"])
        sensory_col.objects.link(ant_pedicel)
        parent_keep_transform(ant_pedicel, head_obj)

        # Arista (main feathered bristle)
        arista_tip = Vector((hx + sign * 0.14, hy + 0.38, hz + 0.16))
        arista = create_limb_segment(f"Arista_{side}", ant_mid, arista_tip, 0.010, 0.003, 4, materials["cuticle_dark"])
        sensory_col.objects.link(arista)
        parent_keep_transform(arista, ant_pedicel)

    # 5. Proboscis (Ventral mouthparts)
    prob_base = Vector((hx, hy + 0.02, hz - 0.16))
    prob_mid = Vector((hx, hy + 0.04, hz - 0.30))
    prob_tip = Vector((hx, hy - 0.03, hz - 0.38))
    
    p1 = create_limb_segment("Proboscis_Haustellum", prob_base, prob_mid, 0.075, 0.055, 8, materials["cuticle_tan"])
    body_col.objects.link(p1)
    parent_keep_transform(p1, head_obj)
    
    p2 = create_limb_segment("Proboscis_Labellum", prob_mid, prob_tip, 0.055, 0.035, 6, materials["cuticle_tan"])
    body_col.objects.link(p2)
    parent_keep_transform(p2, p1)

    return head_obj

def build_segmented_abdomen(materials, body_col, thorax_obj, start_pos):
    """
    Abdomen: Discrete 6-segment overlapping tergite plates.
    Produces authentic, crisp Drosophila melanogaster melanic striping!
    """
    ax, ay, az = start_pos
    
    # 6 segments (T1 to T6)
    segments_data = [
        {"len": 0.24, "rx": 0.42, "rz": 0.36, "dark_ratio": 0.25}, # T1: narrow dark border
        {"len": 0.26, "rx": 0.46, "rz": 0.38, "dark_ratio": 0.40}, # T2: wide tan, dark stripe
        {"len": 0.26, "rx": 0.46, "rz": 0.38, "dark_ratio": 0.50}, # T3: striped
        {"len": 0.25, "rx": 0.42, "rz": 0.34, "dark_ratio": 0.60}, # T4: dark band
        {"len": 0.22, "rx": 0.34, "rz": 0.28, "dark_ratio": 0.85}, # T5: mostly dark
        {"len": 0.20, "rx": 0.22, "rz": 0.18, "dark_ratio": 1.00}, # T6: solid melanic tip
    ]

    current_y = ay
    current_z = az
    abdomen_root = None

    for i, seg in enumerate(segments_data):
        seg_name = f"Abdomen_T{i+1}"
        next_y = current_y - seg["len"]
        next_z = current_z - 0.03 * (i + 1) # gentle natural droop
        
        bm = bmesh.new()
        # Ring shell for tergite
        bmesh.ops.create_cone(
            bm, cap_ends=True, cap_tris=False, segments=16,
            radius1=seg["rx"], radius2=seg["rx"] * 0.92, depth=seg["len"],
            matrix=Matrix.Translation((0, 0, seg["len"] / 2.0))
        )
        for v in bm.verts:
            # Ellipsoid cross section
            v.co.y *= (seg["rz"] / seg["rx"])
            
        mesh = bpy.data.meshes.new(f"{seg_name}_Mesh")
        bm.to_mesh(mesh)
        bm.free()
        for poly in mesh.polygons:
            poly.use_smooth = True

        obj = bpy.data.objects.new(seg_name, mesh)
        # Position at segment joint
        obj.location = Vector((ax, current_y, current_z))
        
        # Orient along Y-axis
        obj.rotation_euler = Euler((math.radians(-90), 0, 0), 'XYZ')
        
        # Material assignment
        if seg["dark_ratio"] >= 0.75:
            obj.data.materials.append(materials["cuticle_dark"])
        elif seg["dark_ratio"] >= 0.35:
            # Striped: add both materials
            obj.data.materials.append(materials["cuticle_tan"])
            obj.data.materials.append(materials["cuticle_dark"])
            for poly in mesh.polygons:
                # Top half of cylinder is posterior
                if poly.center.z > seg["len"] * (1.0 - seg["dark_ratio"]):
                    poly.material_index = 1
                else:
                    poly.material_index = 0
        else:
            obj.data.materials.append(materials["cuticle_tan"])

        body_col.objects.link(obj)
        
        if i == 0:
            abdomen_root = obj
            parent_keep_transform(obj, thorax_obj)
        else:
            parent_keep_transform(obj, abdomen_root)

        current_y = next_y + 0.03 # 0.03 mm overlap between plates
        current_z = next_z

    return abdomen_root

def build_wings(materials, wings_col, thorax_obj, thorax_center):
    """
    Wings: Realistic curved profile, translucent membrane, resting scissor-crossed over abdomen.
    """
    tx, ty, tz = thorax_center
    wings = []
    
    for side, sign in [("L", -1), ("R", 1)]:
        hinge = Vector((tx + sign * 0.26, ty - 0.12, tz + 0.28))
        
        bm = bmesh.new()
        verts_local = [
            (0.0, 0.0, 0.0),                     # 0: Hinge
            (sign * 0.11, -0.30, 0.01),          # 1: Costal base
            (sign * 0.25, -0.80, 0.015),         # 2: Costal mid
            (sign * 0.32, -1.45, 0.01),          # 3: Sub-apex anterior
            (sign * 0.24, -2.05, 0.0),           # 4: Apex anterior
            (sign * 0.08, -2.30, -0.005),        # 5: Wing tip
            (sign * -0.09, -2.15, -0.01),        # 6: Apex posterior
            (sign * -0.22, -1.60, -0.015),       # 7: Posterior mid
            (sign * -0.28, -0.98, -0.015),       # 8: Alula / anal lobe
            (sign * -0.18, -0.45, -0.01),        # 9: Posterior base
            (sign * 0.09, -0.65, 0.005),         # 10: R-M junction
            (sign * 0.11, -1.25, 0.005),         # 11: Radial fork
            (sign * -0.04, -1.45, -0.005),       # 12: Medial fork
        ]
        
        bm_verts = [bm.verts.new(Vector(v)) for v in verts_local]
        bm.verts.ensure_lookup_table()
        
        faces = [
            (0, 1, 10, 9),
            (1, 2, 11, 10),
            (2, 3, 11),
            (3, 4, 5, 11),
            (5, 12, 11),
            (5, 6, 12),
            (6, 7, 12),
            (12, 7, 8, 11),
            (11, 8, 10),
            (10, 8, 9),
        ]
        for f in faces:
            bm.faces.new([bm_verts[i] for i in f])
            
        bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=0.006)

        mesh = bpy.data.meshes.new(f"Wing_{side}_Mesh")
        bm.to_mesh(mesh)
        bm.free()
        for poly in mesh.polygons:
            poly.use_smooth = True

        wing_obj = bpy.data.objects.new(f"Wing_{side}", mesh)
        wing_obj.location = hinge
        # Rest angle: folded flat over abdomen with gentle scissor overlap
        wing_obj.rotation_euler = Euler((math.radians(-2), math.radians(sign * 10), math.radians(sign * -5)), 'XYZ')
        
        wings_col.objects.link(wing_obj)
        wing_obj.data.materials.append(materials["wing_membrane"])
        parent_keep_transform(wing_obj, thorax_obj)
        wings.append(wing_obj)
        
    return wings

def build_halteres(materials, wings_col, thorax_obj, thorax_center):
    """Balancing organs (halteres) on metathorax behind wings."""
    tx, ty, tz = thorax_center
    halteres = []
    for side, sign in [("L", -1), ("R", 1)]:
        base = (tx + sign * 0.24, ty - 0.36, tz + 0.06)
        tip = (tx + sign * 0.38, ty - 0.44, tz + 0.12)
        h_stalk = create_limb_segment(f"Haltere_{side}", base, tip, 0.015, 0.034, 8, materials["haltere"])
        wings_col.objects.link(h_stalk)
        parent_keep_transform(h_stalk, thorax_obj)
        halteres.append(h_stalk)
    return halteres

def build_articulated_leg(prefix, side, sign, sockets, materials, col, thorax_obj):
    """
    4-part kinematic leg chain: Coxa -> Femur -> Tibia -> Tarsus.
    Origins placed at joint articulation points for Forward Kinematics.
    """
    p_socket = Vector(sockets["socket"])
    p_trochanter = Vector(sockets["trochanter"])
    p_knee = Vector(sockets["knee"])
    p_ankle = Vector(sockets["ankle"])
    p_claw = Vector(sockets["claw"])

    # 1. Coxa
    coxa = create_limb_segment(f"{prefix}_Coxa_{side}", p_socket, p_trochanter, 0.075, 0.065, 8, materials["cuticle_tan"])
    col.objects.link(coxa)
    parent_keep_transform(coxa, thorax_obj)

    # 2. Femur
    femur = create_limb_segment(f"{prefix}_Femur_{side}", p_trochanter, p_knee, 0.065, 0.048, 8, materials["cuticle_tan"])
    col.objects.link(femur)
    parent_keep_transform(femur, coxa)

    # 3. Tibia
    tibia = create_limb_segment(f"{prefix}_Tibia_{side}", p_knee, p_ankle, 0.045, 0.032, 8, materials["cuticle_dark"])
    col.objects.link(tibia)
    parent_keep_transform(tibia, femur)

    # 4. Tarsus
    tarsus = create_limb_segment(f"{prefix}_Tarsus_{side}", p_ankle, p_claw, 0.030, 0.016, 6, materials["cuticle_dark"])
    col.objects.link(tarsus)
    parent_keep_transform(tarsus, tibia)

    return [coxa, femur, tibia, tarsus]

def build_all_legs(materials, cols, thorax_obj, body_z):
    """
    Realistic low-slung insect stance:
    - Body at perched height Z = 0.52 mm.
    - Arched knees (Z ~ 0.65 - 0.72 mm).
    - Feet planted at Z = 0.0 mm.
    """
    leg_data = [
        {
            "prefix": "Leg_Front",
            "coords": {
                "socket":     (0.18, 0.26, body_z - 0.18),
                "trochanter": (0.30, 0.36, body_z - 0.22),
                "knee":       (0.55, 0.65, body_z + 0.14),  # Arched knee reaching forward
                "ankle":      (0.75, 0.92, 0.15),
                "claw":       (0.88, 1.10, 0.00),           # Planted on ground
            }
        },
        {
            "prefix": "Leg_Mid",
            "coords": {
                "socket":     (0.22, 0.00, body_z - 0.20),
                "trochanter": (0.38, 0.02, body_z - 0.24),
                "knee":       (0.78, 0.05, body_z + 0.18),  # Lateral knee arch
                "ankle":      (1.08, 0.03, 0.14),
                "claw":       (1.25, 0.02, 0.00),           # Planted on ground
            }
        },
        {
            "prefix": "Leg_Hind",
            "coords": {
                "socket":     (0.20, -0.24, body_z - 0.20),
                "trochanter": (0.35, -0.34, body_z - 0.24),
                "knee":       (0.75, -0.68, body_z + 0.20), # Rear knee arch
                "ankle":      (1.12, -1.08, 0.15),
                "claw":       (1.32, -1.38, 0.00),          # Planted on ground
            }
        },
    ]

    for cfg in leg_data:
        for side, sign in [("L", -1), ("R", 1)]:
            target_col = cols["Legs_Left"] if side == "L" else cols["Legs_Right"]
            sockets = {
                k: (sign * v[0], v[1], v[2])
                for k, v in cfg["coords"].items()
            }
            build_articulated_leg(cfg["prefix"], side, sign, sockets, materials, target_col, thorax_obj)

def setup_studio_lighting_and_camera(body_z):
    """Framed camera showing entire fly + 3-point lighting."""
    # Key Light
    key_data = bpy.data.lights.new('Key_Light', 'SUN')
    key_data.energy = 3.5
    key_data.color = (1.0, 0.98, 0.94)
    key_obj = bpy.data.objects.new('Key_Light', key_data)
    bpy.context.scene.collection.objects.link(key_obj)
    key_obj.rotation_euler = (math.radians(52), math.radians(-28), math.radians(42))

    # Fill Light
    fill_data = bpy.data.lights.new('Fill_Light', 'SUN')
    fill_data.energy = 1.6
    fill_data.color = (0.88, 0.93, 1.0)
    fill_obj = bpy.data.objects.new('Fill_Light', fill_data)
    bpy.context.scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(38), math.radians(42), math.radians(-138))

    # Rim / Back Light
    rim_data = bpy.data.lights.new('Rim_Light', 'SUN')
    rim_data.energy = 2.2
    rim_data.color = (1.0, 1.0, 1.0)
    rim_obj = bpy.data.objects.new('Rim_Light', rim_data)
    bpy.context.scene.collection.objects.link(rim_obj)
    rim_obj.rotation_euler = (math.radians(-40), math.radians(15), math.radians(-45))

    # Camera (Wide enough to capture entire fly including all feet and wings)
    cam_data = bpy.data.cameras.new('Camera')
    cam_data.lens = 45
    cam_obj = bpy.data.objects.new('Camera', cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = (4.6, 5.0, 3.4)
    cam_obj.rotation_euler = (math.radians(65), 0, math.radians(138))
    bpy.context.scene.camera = cam_obj

# -------------------------------------------------------------
# Main Generation
# -------------------------------------------------------------

def generate_drosophila():
    print(">> Generating Master Anatomical Drosophila melanogaster v4...")
    clean_scene()
    
    materials = {
        "cuticle_tan": create_pbr_material("Mat_Cuticle_Tan", (0.76, 0.55, 0.28, 1.0), roughness=0.38, specular=0.55),
        "cuticle_dark": create_pbr_material("Mat_Cuticle_Dark", (0.09, 0.06, 0.04, 1.0), roughness=0.30, specular=0.50),
        "compound_eye": create_pbr_material("Mat_Compound_Eye", (0.72, 0.03, 0.03, 1.0), roughness=0.18, specular=0.85),
        "wing_membrane": create_pbr_material("Mat_Wing_Membrane", (0.92, 0.96, 0.98, 0.35), roughness=0.12, specular=0.70, is_translucent=True),
        "haltere": create_pbr_material("Mat_Haltere", (0.88, 0.84, 0.70, 0.90), roughness=0.35, specular=0.40),
    }

    root_col = bpy.context.scene.collection
    fly_col = bpy.data.collections.new("Drosophila_Melanogaster")
    root_col.children.link(fly_col)
    
    cols = {
        "Body": bpy.data.collections.new("01_Body"),
        "Sensory": bpy.data.collections.new("02_Sensory"),
        "Wings": bpy.data.collections.new("03_Wings_Halteres"),
        "Legs_Left": bpy.data.collections.new("04_Legs_Left"),
        "Legs_Right": bpy.data.collections.new("05_Legs_Right"),
    }
    for c in cols.values():
        fly_col.children.link(c)

    # Perched fly height: Thorax center at Z = 0.52 mm
    BODY_Z = 0.52
    thorax_center = (0.0, 0.0, BODY_Z)
    
    # 1. Thorax (Root)
    thorax = build_thorax(materials, cols["Body"], thorax_center)

    # 2. Head Complex (Head capsule, neck, wrap-around ruby compound eyes, antennae, proboscis)
    head_pos = (0.0, 0.56, BODY_Z + 0.02)
    build_head_complex(materials, cols["Body"], cols["Sensory"], thorax, head_pos)

    # 3. Segmented Abdomen (6 discrete overlapping banded plates)
    abdomen_start = (0.0, -0.52, BODY_Z - 0.03)
    build_segmented_abdomen(materials, cols["Body"], thorax, abdomen_start)

    # 4. Wings & Halteres
    build_wings(materials, cols["Wings"], thorax, thorax_center)
    build_halteres(materials, cols["Wings"], thorax, thorax_center)

    # 5. Articulated Legs (6 sprawling legs supporting fly on ground Z=0)
    build_all_legs(materials, cols, thorax, BODY_Z)

    # Lighting & Camera
    setup_studio_lighting_and_camera(BODY_Z)

    # Select root Thorax
    bpy.context.view_layer.objects.active = thorax
    thorax.select_set(True)

    total_verts = sum(len(o.data.vertices) for o in bpy.data.objects if o.type == 'MESH')
    total_faces = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
    print(f">> Master Drosophila generated! Total Meshes: {len([o for o in bpy.data.objects if o.type == 'MESH'])}, Vertices: {total_verts}, Polygons: {total_faces}")
    return thorax

def save_and_export(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    blend_path = os.path.join(output_dir, "drosophila_melanogaster.blend")
    glb_path = os.path.join(output_dir, "drosophila_melanogaster.glb")

    print(f">> Saving .blend: {blend_path}")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    print(f">> Exporting .glb: {glb_path}")
    bpy.ops.export_scene.gltf(
        filepath=glb_path,
        export_format='GLB'
    )
    print(">> Done.")
    return blend_path, glb_path

if __name__ == "__main__":
    generate_drosophila()
    target_dir = r"C:\Users\GE\.gemini\antigravity\scratch\drosophila_model"
    save_and_export(target_dir)
