# ComfyUI Pose Effects

Local, offline keypoint animation editing for OpenPose/DWPose pose data.
No cloud services, no API calls — pure math.

## Install
Copy this folder into `ComfyUI/custom_nodes/` and restart ComfyUI:
```
ComfyUI/custom_nodes/comfyui-pose-effects/
```
No extra dependencies (uses numpy, torch, cv2 already bundled with ComfyUI).

## Nodes
- **Load Pose JSON** — paste JSON or give a file path -> POSE_KEYPOINT
- **Pose Keypoint Effects** — head_bob / head_pulse / arm_stretch / passthrough
- **Render Pose Frames** — POSE_KEYPOINT -> IMAGE batch (OpenPose-style skeleton)
- **Save Pose JSON** — write the modified animation back to disk

## Typical graph
Load Pose JSON -> Pose Keypoint Effects -> Render Pose Frames -> (Video Combine / Wan pose input)

Also works directly after a DWPose Estimator node (POSE_KEYPOINT in/out).

## Effect parameters
| effect | strength meaning | notes |
|---|---|---|
| (any) + mode=constant | fixed value applied to ALL frames | permanent big head, long arms, or head offset — no animation |
|---|---|---|
| head_bob | pixels of vertical travel (try 35) | neck_follow keeps head attached |
| head_pulse | max scale factor (try 2.5) | pivots at neck; include_face scales the 70 face pts |
| arm_stretch | max length factor (try 1.7) | alternate_arms = wavy L/R phase offset; hands ride along |

- `cycles`: whole numbers start & end at neutral -> seamless loops
- `hold_frames`: leave the first N frames unmodified (identity anchor for Wan)
- `strip_face`: zero all face keypoints (body-only skeleton — fixes "floating ball" artifacts)
