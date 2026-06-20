## 2026-06-20 - Three.js Raycasting Optimization
**Learning:** In Three.js, executing `raycaster.intersectObjects` on every `mousemove` against hundreds of intricate detail meshes (struts, nodes) creates a severe synchronous main-thread bottleneck, especially in complex animated scenes.
**Action:** Always filter raycast targets to include only necessary interactive bounding volumes or primary structural meshes, and always throttle the `mousemove` event handler via `requestAnimationFrame` to decouple event frequency from render frequency.
