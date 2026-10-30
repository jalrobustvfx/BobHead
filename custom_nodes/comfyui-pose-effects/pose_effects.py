"""
Pose Keypoint Effects — local OpenPose animation editing for ComfyUI.
Nodes:
  - Load Pose JSON (path or pasted string) -> POSE_KEYPOINT
  - Pose Keypoint Effects (bob / pulse / arm stretch) -> POSE_KEYPOINT
  - Render Pose Frames -> IMAGE batch (OpenPose-style skeleton video frames)
  - Save Pose JSON -> writes modified JSON to disk
COCO-18 body format with 70-pt face and 21-pt hands (DWPose-style).
"""

import json
import math
import copy
import os

import numpy as np
import torch

# COCO-18 indices
NOSE, NECK = 0, 1
R_SHO, R_ELB, R_WRI = 2, 3, 4
L_SHO, L_ELB, L_WRI = 5, 6, 7
HEAD_PTS = [0, 14, 15, 16, 17]

LIMB_SEQ = [
    (1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7),
    (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13),
    (1, 0), (0, 14), (14, 16), (0, 15), (15, 17),
]

# standard OpenPose limb colors (RGB)
LIMB_COLORS = [
    (255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0),
    (85, 255, 0), (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255),
    (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255), (170, 0, 255),
    (255, 0, 255), (255, 0, 170),
]
POINT_COLORS = [
    (255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0),
    (85, 255, 0), (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255),
    (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255), (170, 0, 255),
    (255, 0, 255), (255, 0, 170), (255, 0, 85),
]

HAND_SEQ = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
]


# ---------------------------------------------------------------- helpers

def _valid(x, y, c):
    return c > 0 and not (x == 0 and y == 0)


def _offset_y(kps, indices, dy):
    for i in indices:
        x, y, c = kps[i * 3], kps[i * 3 + 1], kps[i * 3 + 2]
        if _valid(x, y, c):
            kps[i * 3 + 1] = y + dy


def _scale_about(kps, indices, cx, cy, s):
    for i in indices:
        x, y, c = kps[i * 3], kps[i * 3 + 1], kps[i * 3 + 2]
        if _valid(x, y, c):
            kps[i * 3] = cx + (x - cx) * s
            kps[i * 3 + 1] = cy + (y - cy) * s


def _wave01(t, cycles, n):
    """0..1 pulse wave, starts and ends at 0 for seamless loops."""
    return (1.0 - math.cos(2.0 * math.pi * cycles * t / max(n, 1))) / 2.0


def _sine(t, cycles, n, phase=0.0):
    return math.sin(2.0 * math.pi * cycles * t / max(n, 1) + phase)


def _as_pose_list(pose):
    """Accept a single-frame dict or a list of frames; return list."""
    if isinstance(pose, dict):
        return [pose]
    return pose


# ---------------------------------------------------------------- nodes

class LoadPoseJSON:
    """Load an OpenPose animation JSON from a file path or a pasted string."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "json_string": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "file_path": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("POSE_KEYPOINT", "INT")
    RETURN_NAMES = ("pose_keypoint", "frame_count")
    FUNCTION = "load"
    CATEGORY = "PoseEffects"

    def load(self, json_string, file_path=""):
        raw = None
        if file_path and os.path.isfile(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                raw = f.read()
        elif json_string.strip():
            raw = json_string
        if raw is None:
            raise ValueError("Provide either a valid file_path or paste JSON into json_string.")
        data = json.loads(raw)
        data = _as_pose_list(data)
        return (data, len(data))


class SavePoseJSON:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pose_keypoint": ("POSE_KEYPOINT",),
                "file_path": ("STRING", {"default": "output/pose_modified.json"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_path",)
    FUNCTION = "save"
    CATEGORY = "PoseEffects"
    OUTPUT_NODE = True

    def save(self, pose_keypoint, file_path):
        d = os.path.dirname(file_path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(pose_keypoint, f)
        return (file_path,)


class PoseKeypointEffects:
    """Apply head bob / head pulse / arm stretch to a pose animation."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pose_keypoint": ("POSE_KEYPOINT",),
                "effect": (["head_bob", "head_pulse", "arm_stretch", "passthrough"],),
                "mode": (["animated", "constant"], {
                    "tooltip": "animated: effect oscillates over cycles. "
                               "constant: effect applied at full strength on every frame "
                               "(fixed big head / fixed long arms / fixed head offset)"}),
                "strength": ("FLOAT", {"default": 2.5, "min": -10.0, "max": 10.0, "step": 0.05,
                                       "tooltip": "head_bob: pixels of vertical offset (negative = up). "
                                                  "head_pulse/arm_stretch: scale factor (e.g. 2.5)"}),
                "cycles": ("FLOAT", {"default": 6.0, "min": 0.1, "max": 64.0, "step": 0.1,
                                     "tooltip": "Whole numbers loop seamlessly"}),
                "hold_frames": ("INT", {"default": 0, "min": 0, "max": 512,
                                        "tooltip": "Frames at the start left unmodified (identity anchor)"}),
                "neck_follow": ("FLOAT", {"default": 0.45, "min": 0.0, "max": 1.0, "step": 0.05,
                                          "tooltip": "head_bob only: fraction of offset applied to neck"}),
                "include_face": ("BOOLEAN", {"default": True,
                                             "tooltip": "Move/scale the 70 face keypoints with the head"}),
                "strip_face": ("BOOLEAN", {"default": False,
                                           "tooltip": "Zero out face keypoints entirely (body-only skeleton)"}),
                "alternate_arms": ("BOOLEAN", {"default": True,
                                               "tooltip": "arm_stretch only: L/R arms half a cycle out of phase"}),
            }
        }

    RETURN_TYPES = ("POSE_KEYPOINT",)
    RETURN_NAMES = ("pose_keypoint",)
    FUNCTION = "apply"
    CATEGORY = "PoseEffects"

    def apply(self, pose_keypoint, effect, mode, strength, cycles, hold_frames,
              neck_follow, include_face, strip_face, alternate_arms):
        data = copy.deepcopy(_as_pose_list(pose_keypoint))
        n = len(data)
        active = max(n - hold_frames, 1)

        for fi, frame in enumerate(data):
            people = frame.get("people") or []
            t = fi - hold_frames
            in_hold = fi < hold_frames

            for person in people:
                kp = person.get("pose_keypoints_2d") or []
                if strip_face and person.get("face_keypoints_2d"):
                    person["face_keypoints_2d"] = [0.0] * len(person["face_keypoints_2d"])
                fk = person.get("face_keypoints_2d") or []

                if in_hold or effect == "passthrough" or not kp:
                    continue

                if effect == "head_bob":
                    if mode == "constant":
                        dy = strength
                    else:
                        dy = strength * _sine(t, cycles, active)
                    _offset_y(kp, HEAD_PTS, dy)
                    _offset_y(kp, [NECK], dy * neck_follow)
                    if include_face and not strip_face and fk:
                        _offset_y(fk, range(len(fk) // 3), dy)

                elif effect == "head_pulse":
                    if mode == "constant":
                        s = strength
                    else:
                        s = 1.0 + (strength - 1.0) * _wave01(t, cycles, active)
                    nx, ny, nc = kp[NECK * 3], kp[NECK * 3 + 1], kp[NECK * 3 + 2]
                    if nc == 0:
                        nx, ny = kp[NOSE * 3], kp[NOSE * 3 + 1]
                    _scale_about(kp, HEAD_PTS, nx, ny, s)
                    if include_face and not strip_face and fk:
                        _scale_about(fk, range(len(fk) // 3), nx, ny, s)

                elif effect == "arm_stretch":
                    arms = [
                        (R_SHO, R_ELB, R_WRI, "hand_right_keypoints_2d", 0.0),
                        (L_SHO, L_ELB, L_WRI, "hand_left_keypoints_2d",
                         math.pi if alternate_arms else 0.0),
                    ]
                    for sho, elb, wri, hand_key, phase in arms:
                        if mode == "constant":
                            s = strength
                        else:
                            w = (1.0 - math.cos(2.0 * math.pi * cycles * t / active + phase)) / 2.0
                            s = 1.0 + (strength - 1.0) * w
                        sx, sy, sc = kp[sho * 3], kp[sho * 3 + 1], kp[sho * 3 + 2]
                        if sc == 0:
                            continue
                        wx0, wy0 = kp[wri * 3], kp[wri * 3 + 1]
                        _scale_about(kp, [elb, wri], sx, sy, s)
                        dx, dy = kp[wri * 3] - wx0, kp[wri * 3 + 1] - wy0
                        hk = person.get(hand_key) or []
                        for i in range(len(hk) // 3):
                            x, y, c = hk[i * 3], hk[i * 3 + 1], hk[i * 3 + 2]
                            if _valid(x, y, c):
                                hk[i * 3] = x + dx
                                hk[i * 3 + 1] = y + dy

        return (data,)


class RenderPoseFrames:
    """Render POSE_KEYPOINT animation to an IMAGE batch (OpenPose-style)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pose_keypoint": ("POSE_KEYPOINT",),
                "line_width": ("INT", {"default": 4, "min": 1, "max": 16}),
                "point_radius": ("INT", {"default": 4, "min": 1, "max": 16}),
                "draw_face": ("BOOLEAN", {"default": True}),
                "draw_hands": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "width_override": ("INT", {"default": 0, "min": 0, "max": 8192}),
                "height_override": ("INT", {"default": 0, "min": 0, "max": 8192}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "render"
    CATEGORY = "PoseEffects"

    def render(self, pose_keypoint, line_width, point_radius, draw_face, draw_hands,
               width_override=0, height_override=0):
        try:
            import cv2
        except ImportError:
            raise RuntimeError("RenderPoseFrames requires opencv-python (cv2), "
                               "which ships with ComfyUI's requirements.")

        data = _as_pose_list(pose_keypoint)
        frames = []
        for frame in data:
            w = width_override or int(frame.get("canvas_width", 768))
            h = height_override or int(frame.get("canvas_height", 1024))
            sx = w / frame.get("canvas_width", w) if width_override else 1.0
            sy = h / frame.get("canvas_height", h) if height_override else 1.0
            img = np.zeros((h, w, 3), dtype=np.uint8)

            for person in frame.get("people") or []:
                kp = person.get("pose_keypoints_2d") or []
                pts = []
                for i in range(len(kp) // 3):
                    x, y, c = kp[i * 3] * sx, kp[i * 3 + 1] * sy, kp[i * 3 + 2]
                    pts.append((int(round(x)), int(round(y)), c, _valid(x, y, c)))

                for li, (a, b) in enumerate(LIMB_SEQ):
                    if a < len(pts) and b < len(pts) and pts[a][3] and pts[b][3]:
                        cv2.line(img, pts[a][:2], pts[b][:2],
                                 LIMB_COLORS[li % len(LIMB_COLORS)], line_width,
                                 lineType=cv2.LINE_AA)
                for pi, p in enumerate(pts):
                    if p[3]:
                        cv2.circle(img, p[:2], point_radius,
                                   POINT_COLORS[pi % len(POINT_COLORS)], -1,
                                   lineType=cv2.LINE_AA)

                if draw_face:
                    fk = person.get("face_keypoints_2d") or []
                    for i in range(len(fk) // 3):
                        x, y, c = fk[i * 3] * sx, fk[i * 3 + 1] * sy, fk[i * 3 + 2]
                        if _valid(x, y, c):
                            cv2.circle(img, (int(round(x)), int(round(y))),
                                       max(1, point_radius // 2), (255, 255, 255), -1,
                                       lineType=cv2.LINE_AA)

                if draw_hands:
                    for key in ("hand_left_keypoints_2d", "hand_right_keypoints_2d"):
                        hk = person.get(key) or []
                        hpts = []
                        for i in range(len(hk) // 3):
                            x, y, c = hk[i * 3] * sx, hk[i * 3 + 1] * sy, hk[i * 3 + 2]
                            hpts.append((int(round(x)), int(round(y)), c, _valid(x, y, c)))
                        for a, b in HAND_SEQ:
                            if a < len(hpts) and b < len(hpts) and hpts[a][3] and hpts[b][3]:
                                cv2.line(img, hpts[a][:2], hpts[b][:2], (0, 0, 255),
                                         max(1, line_width // 2), lineType=cv2.LINE_AA)
                        for p in hpts:
                            if p[3]:
                                cv2.circle(img, p[:2], max(1, point_radius // 2),
                                           (0, 0, 255), -1, lineType=cv2.LINE_AA)

            frames.append(torch.from_numpy(img.astype(np.float32) / 255.0))

        if not frames:
            frames = [torch.zeros((64, 64, 3), dtype=torch.float32)]
        return (torch.stack(frames, dim=0),)


NODE_CLASS_MAPPINGS = {
    "PE_LoadPoseJSON": LoadPoseJSON,
    "PE_SavePoseJSON": SavePoseJSON,
    "PE_PoseKeypointEffects": PoseKeypointEffects,
    "PE_RenderPoseFrames": RenderPoseFrames,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PE_LoadPoseJSON": "Load Pose JSON (PoseEffects)",
    "PE_SavePoseJSON": "Save Pose JSON (PoseEffects)",
    "PE_PoseKeypointEffects": "Pose Keypoint Effects",
    "PE_RenderPoseFrames": "Render Pose Frames",
}
