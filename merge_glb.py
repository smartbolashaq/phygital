#!/usr/bin/env python3
"""Merge two GLB files into one, preserving each part's original world transform.

The chassis (model3d2) and roof (model3d3) were exported separately but share a
coordinate system. Loading them into two <model-viewer> elements made each one
auto-fit its own container, so the small roof got blown up to the size of the
whole car. Merging them into a single glTF scene keeps the true relative scale.

The roof is placed under a named node ("RoofGroup") so it can be animated
independently later if needed.
"""
import struct, json, sys

def load(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'glTF', f'{path}: not a GLB'
    off = 12
    chunks = {}
    while off < len(d):
        ln = struct.unpack('<I', d[off:off+4])[0]
        ty = d[off+4:off+8]
        chunks[ty] = d[off+8:off+8+ln]
        pad = ((4 - (ln % 4)) % 4) if ln % 4 else 0
        off += 8 + ln + pad
    return json.loads(chunks[b'JSON'].decode('utf8')), chunks.get(b'BIN\x00', b'')

def merge(base_path, add_path, out_path, add_group_name='RoofGroup'):
    A, abin = load(base_path)     # chassis — keeps index 0 for everything
    B, bbin = load(add_path)      # roof

    # pad base binary to 4 bytes so the appended data stays aligned
    pad = (4 - (len(abin) % 4)) % 4
    abin_p = abin + b'\x00' * pad
    bin_offset = len(abin_p)

    out = dict(A)

    # ---- offsets for every array we splice in from B
    off_bv   = len(A.get('bufferViews', []))
    off_acc  = len(A.get('accessors', []))
    off_mesh = len(A.get('meshes', []))
    off_mat  = len(A.get('materials', []))
    off_tex  = len(A.get('textures', []))
    off_img  = len(A.get('images', []))
    off_smp  = len(A.get('samplers', []))
    off_node = len(A.get('nodes', []))

    # ---- bufferViews: shift byteOffset into the appended region
    bvs = list(A.get('bufferViews', []))
    for bv in B.get('bufferViews', []):
        nb = dict(bv)
        nb['buffer'] = 0
        nb['byteOffset'] = nb.get('byteOffset', 0) + bin_offset
        bvs.append(nb)
    out['bufferViews'] = bvs

    # ---- accessors
    accs = list(A.get('accessors', []))
    for ac in B.get('accessors', []):
        na = dict(ac)
        if 'bufferView' in na:
            na['bufferView'] += off_bv
        if 'sparse' in na:  # rare, but keep indices valid
            sp = json.loads(json.dumps(na['sparse']))
            if 'bufferView' in sp.get('indices', {}):
                sp['indices']['bufferView'] += off_bv
            if 'bufferView' in sp.get('values', {}):
                sp['values']['bufferView'] += off_bv
            na['sparse'] = sp
        accs.append(na)
    out['accessors'] = accs

    # ---- images / samplers / textures
    imgs = list(A.get('images', []))
    for im in B.get('images', []):
        ni = dict(im)
        if 'bufferView' in ni:
            ni['bufferView'] += off_bv
        imgs.append(ni)
    if imgs: out['images'] = imgs

    smps = list(A.get('samplers', []))
    for s in B.get('samplers', []):
        smps.append(dict(s))
    if smps: out['samplers'] = smps

    texs = list(A.get('textures', []))
    for t in B.get('textures', []):
        nt = dict(t)
        if 'source' in nt:  nt['source']  += off_img
        if 'sampler' in nt: nt['sampler'] += off_smp
        texs.append(nt)
    if texs: out['textures'] = texs

    # ---- materials: every texture reference must be re-pointed
    def fix_texrefs(obj):
        if isinstance(obj, dict):
            o = {}
            for k, v in obj.items():
                if k == 'index' and isinstance(v, int):
                    o[k] = v + off_tex
                else:
                    o[k] = fix_texrefs(v)
            return o
        if isinstance(obj, list):
            return [fix_texrefs(v) for v in obj]
        return obj

    mats = list(A.get('materials', []))
    for m in B.get('materials', []):
        mats.append(fix_texrefs(dict(m)))
    if mats: out['materials'] = mats

    # ---- meshes
    meshes = list(A.get('meshes', []))
    for m in B.get('meshes', []):
        nm = json.loads(json.dumps(m))
        for p in nm.get('primitives', []):
            p['attributes'] = {k: v + off_acc for k, v in p.get('attributes', {}).items()}
            if 'indices' in p:  p['indices']  += off_acc
            if 'material' in p: p['material'] += off_mat
            if 'targets' in p:
                p['targets'] = [{k: v + off_acc for k, v in t.items()} for t in p['targets']]
        meshes.append(nm)
    out['meshes'] = meshes

    # ---- nodes
    nodes = list(A.get('nodes', []))
    for n in B.get('nodes', []):
        nn = json.loads(json.dumps(n))
        if 'mesh' in nn:     nn['mesh'] += off_mesh
        if 'children' in nn: nn['children'] = [c + off_node for c in nn['children']]
        if 'skin' in nn:     nn.pop('skin', None)      # skins not merged
        if 'camera' in nn:   nn.pop('camera', None)
        nodes.append(nn)

    # wrap B's scene roots in one named group node
    b_scene = B.get('scenes', [{}])[B.get('scene', 0)]
    b_roots = [r + off_node for r in b_scene.get('nodes', [])]
    group_index = len(nodes)
    nodes.append({'name': add_group_name, 'children': b_roots})
    out['nodes'] = nodes

    # ---- scene: append the group to the base scene's roots
    scenes = json.loads(json.dumps(A.get('scenes', [{'nodes': []}])))
    si = A.get('scene', 0)
    scenes[si].setdefault('nodes', [])
    scenes[si]['nodes'] = list(scenes[si]['nodes']) + [group_index]
    out['scenes'] = scenes
    out['scene'] = si

    # ---- extensions union
    used = list(dict.fromkeys(A.get('extensionsUsed', []) + B.get('extensionsUsed', [])))
    req  = list(dict.fromkeys(A.get('extensionsRequired', []) + B.get('extensionsRequired', [])))
    if used: out['extensionsUsed'] = used
    if req:  out['extensionsRequired'] = req

    # ---- single combined buffer
    newbin = abin_p + bbin
    binpad = (4 - (len(newbin) % 4)) % 4
    newbin = newbin + b'\x00' * binpad
    out['buffers'] = [{'byteLength': len(newbin)}]
    out.pop('animations', None)

    # ---- write GLB
    js = json.dumps(out, separators=(',', ':')).encode('utf8')
    js += b' ' * ((4 - (len(js) % 4)) % 4)
    total = 12 + 8 + len(js) + 8 + len(newbin)
    with open(out_path, 'wb') as f:
        f.write(b'glTF')
        f.write(struct.pack('<I', 2))
        f.write(struct.pack('<I', total))
        f.write(struct.pack('<I', len(js))); f.write(b'JSON'); f.write(js)
        f.write(struct.pack('<I', len(newbin))); f.write(b'BIN\x00'); f.write(newbin)
    print(f'wrote {out_path}: {total/1e6:.2f} MB, '
          f'nodes={len(out["nodes"])} meshes={len(out["meshes"])} '
          f'group "{add_group_name}" at node {group_index}')
    return group_index

if __name__ == '__main__':
    merge('rp/ppt/media/model3d2.glb', 'rp/ppt/media/model3d3.glb',
          '/tmp/assembly_raw.glb')
