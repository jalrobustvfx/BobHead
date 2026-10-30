"""Export this workflow's named widgets and links without a browser session."""
import argparse
import copy
import json
import shutil
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from server import ancestors, build_prompt


def compile_workflow(workflow, info):
    nodes = {str(n['id']): n for n in workflow['nodes']}
    links = {link[0]: link for link in workflow['links']}
    setters = {n['widgets_values_named']['Constant']: n for n in workflow['nodes'] if n['type'] == 'SetNode'}

    def resolve(node_id, slot, seen=()):
        node_id = str(node_id)
        if node_id in seen: raise ValueError('Cycle in virtual links.')
        node = nodes[node_id]
        if node['type'] == 'GetNode':
            setter = setters[node['widgets_values_named']['Constant']]
            return resolve(str(setter['id']), 0, seen + (node_id,))
        if node['type'] in ('SetNode', 'Reroute'):
            link = links[node['inputs'][0]['link']]
            return resolve(link[1], link[2], seen + (node_id,))
        if node.get('mode', 0) != 0: raise ValueError(f'Unsupported bypass/mute at {node_id}.')
        return [node_id, slot]

    graph = {}
    for key, node in nodes.items():
        kind = node['type']
        if kind in ('GetNode', 'SetNode', 'Reroute', 'Note', 'MarkdownNote'): continue
        if kind not in info: continue  # Missing executable dependencies are caught below.
        schema = info[kind].get('input', {})
        specs = {**schema.get('required', {}), **schema.get('optional', {})}
        values = node.get('widgets_values_named') or {}
        if not isinstance(values, dict): raise ValueError(f'Named widget export required for node {key}.')
        extra_fields = set()
        if kind == 'VHS_VideoCombine':
            formats = specs['format'][1].get('formats', {})
            extra_fields = {item[0] for item in formats.get(values.get('format'), [])}
        inputs = {}
        for name, value in values.items():
            if name in specs or name in extra_fields or ('.' in name and name.split('.')[0] in specs):
                value = copy.deepcopy(value)
                if name in specs:
                    type_name = specs[name][0]
                    if type_name == 'BOOLEAN' and not isinstance(value, bool): value = bool(value)
                    elif type_name == 'INT': value = int(value)
                    elif type_name == 'FLOAT': value = float(value)
                inputs[name] = value
        for socket in node.get('inputs', []):
            if socket.get('link') is not None:
                link = links[socket['link']]
                inputs[socket['name']] = resolve(link[1], link[2])
        graph[key] = {'class_type': kind, 'inputs': inputs}
    return ancestors(graph)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('workflow', type=Path)
    parser.add_argument('--comfy-url', default='http://127.0.0.1:8188')
    args = parser.parse_args()
    workflow = json.loads(args.workflow.read_text(encoding='utf-8-sig'))
    with urllib.request.urlopen(args.comfy_url + '/object_info', timeout=30) as response:
        info = json.load(response)
    raw = compile_workflow(workflow, info)
    api = build_prompt(raw, 'upload-your-video.mp4', {'duration': 5}, 'bobhead')
    # Validate every edge against the installed node's output slots and types.
    edge_count = 0
    for key, node in api.items():
        for name, value in node['inputs'].items():
            if isinstance(value, list) and len(value) == 2 and str(value[0]) in api:
                source = info[api[str(value[0])]['class_type']]
                if not 0 <= value[1] < len(source['output']): raise ValueError(f'Invalid output slot: {key}.{name}')
                edge_count += 1
    dimensions = api['5164']['inputs']
    for name, expected in [('width', 'width'), ('height', 'height'), ('num_frames', 'batch_size')]:
        source_id, slot = dimensions[name]
        actual_name = info[api[source_id]['class_type']]['output_name'][slot]
        if actual_name != expected:
            raise ValueError(f'{name} is connected to {actual_name}, expected {expected}.')
    out = ROOT / 'workflows'
    destination = out / args.workflow.name
    if destination.resolve() != args.workflow.resolve():
        shutil.copy2(args.workflow, destination)
    (out / (args.workflow.stem + '_API_source.json')).write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding='utf-8')
    (out / 'BobHead_API.json').write_text(json.dumps(api, indent=2, ensure_ascii=False), encoding='utf-8')
    metadata = {'workflow': args.workflow.name, 'nodes': len(api), 'links_checked': edge_count,
                'dimensions': {k: api['5164']['inputs'][k] for k in ('width', 'height', 'num_frames')},
                'motion_lora_strength': api['5144']['inputs']['strength_1']}
    (ROOT / 'environment' / 'app-workflow.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(json.dumps(metadata))
