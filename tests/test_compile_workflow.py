import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from compile_workflow import compile_workflow


class SubgraphTests(unittest.TestCase):
    def setUp(self):
        self.info = {
            'Source': {'input': {}},
            'Edit': {'input': {'required': {'image': ['IMAGE'], 'prompt': ['STRING']}}},
            'Final': {'input': {'required': {'image': ['IMAGE']}}},
        }
        self.workflow = {
            'nodes': [
                {'id': 1, 'type': 'Source'},
                {'id': 2, 'type': 'edit-subgraph', 'widgets_values_named': {'prompt': 'Keep my hair', 'refine': False},
                 'inputs': [{'name': 'image', 'link': 1}]},
                {'id': 5187, 'type': 'Final', 'inputs': [{'name': 'image', 'link': 2}]},
            ],
            'links': [[1, 1, 0, 2, 0, 'IMAGE'], [2, 2, 0, 5187, 0, 'IMAGE']],
            'definitions': {'subgraphs': [{
                'id': 'edit-subgraph', 'inputNode': {'id': -10}, 'outputNode': {'id': -20},
                'inputs': [{'name': 'image'}, {'name': 'prompt'}, {'name': 'refine'}],
                'nodes': [
                    {'id': 1, 'type': 'Edit', 'inputs': [{'name': 'image', 'link': 10}, {'name': 'prompt', 'link': 14}]},
                    {'id': 2, 'type': 'ComfySwitchNode', 'inputs': [
                        {'name': 'on_false', 'link': 11}, {'name': 'on_true', 'link': 12}, {'name': 'switch', 'link': 13}]},
                    {'id': 3, 'type': 'MissingEnhancer'},
                ],
                'links': [
                    {'id': 10, 'origin_id': -10, 'origin_slot': 0, 'target_id': 1, 'target_slot': 0, 'type': 'IMAGE'},
                    {'id': 11, 'origin_id': -10, 'origin_slot': 1, 'target_id': 2, 'target_slot': 0, 'type': 'STRING'},
                    {'id': 12, 'origin_id': 3, 'origin_slot': 0, 'target_id': 2, 'target_slot': 1, 'type': 'STRING'},
                    {'id': 13, 'origin_id': -10, 'origin_slot': 2, 'target_id': 2, 'target_slot': 2, 'type': 'BOOLEAN'},
                    {'id': 14, 'origin_id': 2, 'origin_slot': 0, 'target_id': 1, 'target_slot': 1, 'type': 'STRING'},
                    {'id': 15, 'origin_id': 1, 'origin_slot': 0, 'target_id': -20, 'target_slot': 0, 'type': 'IMAGE'},
                ],
            }]},
        }

    def test_external_bindings_namespaces_and_disabled_branch(self):
        before = copy.deepcopy(self.workflow)
        result = compile_workflow(self.workflow, self.info)
        self.assertEqual(result['2:1']['inputs'], {'image': ['1', 0], 'prompt': 'Keep my hair'})
        self.assertEqual(result['5187']['inputs']['image'], ['2:1', 0])
        self.assertNotIn('2:3', result)
        self.assertEqual(self.workflow, before)

    def test_enabled_missing_dependency_is_reported(self):
        self.workflow['nodes'][1]['widgets_values_named']['refine'] = True
        with self.assertRaisesRegex(ValueError, 'Missing node: MissingEnhancer'):
            compile_workflow(self.workflow, self.info)


if __name__ == '__main__':
    unittest.main()
