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
    """Flatten saved subgraphs and virtual links into executable API nodes.

    Resolve constant switches before traversing their inputs so disabled prompt
    enhancers do not introduce unused model dependencies.
    """
    definitions = {s['id']: s for s in workflow.get('definitions', {}).get('subgraphs', [])}
    graph = {}
    missing = object()

    def context(document, prefix='', bindings=None):
        bindings = bindings or {}
        nodes = {str(n['id']): n for n in document['nodes']}
        links = {str(l['id'] if isinstance(l, dict) else l[0]):
                 ([l['id'], l['origin_id'], l['origin_slot'], l['target_id'], l['target_slot'], l['type']]
                  if isinstance(l, dict) else l) for l in document['links']}
        setters = {n.get('widgets_values_named', {}).get('Constant'): n
                   for n in nodes.values() if n['type'] == 'SetNode'}
        children = {}
        resolving = set()

        def value(node, name):
            socket = next((x for x in node.get('inputs', []) if x['name'] == name), {})
            if socket.get('link') is not None:
                link = links[str(socket['link'])]
                return resolve(link[1], link[2])
            return node.get('widgets_values_named', {}).get(name, missing)

        def resolve(node_id, slot):
            key = str(node_id)
            if key == str(document.get('inputNode', {}).get('id', '__none__')):
                return bindings.get(document['inputs'][slot]['name'], missing)
            node = nodes[key]
            kind = node['type']
            if node.get('mode', 0) != 0:
                raise ValueError(f'Unsupported bypass/mute at {prefix + key}.')
            if kind == 'GetNode':
                setter = setters[node['widgets_values_named']['Constant']]
                return resolve(setter['id'], 0)
            if kind in ('SetNode', 'Reroute', 'PreviewAny'):
                return value(node, node['inputs'][0]['name'])
            if kind == 'ComfySwitchNode':
                switch = value(node, 'switch')
                if isinstance(switch, bool):
                    return value(node, 'on_true' if switch else 'on_false')
            if kind in definitions:
                if key not in children:
                    definition = definitions[kind]
                    bound = {x['name']: value(node, x['name']) for x in definition.get('inputs', [])}
                    children[key] = context(definition, prefix + key + ':', bound)
                return children[key](slot)
            api_key = prefix + key
            if api_key not in graph:
                if api_key in resolving:
                    raise ValueError(f'Cycle in workflow at {api_key}.')
                if kind not in info:
                    raise ValueError(f'Missing node: {kind}')
                resolving.add(api_key)
                schema = info[kind].get('input', {})
                specs = {**schema.get('required', {}), **schema.get('optional', {})}
                named = node.get('widgets_values_named') or {}
                inputs = {}
                extra = set()
                if kind == 'VHS_VideoCombine':
                    formats = specs['format'][1].get('formats', {})
                    extra = {item[0] for item in formats.get(named.get('format'), [])}
                names = set(named) | {x['name'] for x in node.get('inputs', [])}
                for name in sorted(names):
                    if name not in specs and name not in extra and not ('.' in name and name.split('.')[0] in specs):
                        continue
                    item = value(node, name)
                    if item is missing:
                        continue
                    item = copy.deepcopy(item)
                    if name in specs and not isinstance(item, list):
                        type_name = specs[name][0]
                        if type_name == 'BOOLEAN': item = bool(item)
                        elif type_name == 'INT': item = int(item)
                        elif type_name == 'FLOAT': item = float(item)
                    inputs[name] = item
                graph[api_key] = {'class_type': kind, 'inputs': inputs}
                resolving.remove(api_key)
            return [api_key, slot]

        def output(slot):
            output_id = document['outputNode']['id']
            link = next(l for l in links.values() if l[3] == output_id and l[4] == slot)
            return resolve(link[1], link[2])
        return output if prefix else resolve

    resolve = context(workflow)
    resolve('5187', 0)
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
