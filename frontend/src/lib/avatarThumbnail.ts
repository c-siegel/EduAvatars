import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const SIZE = 256;

// Renders a head close-up of a .glb avatar into a PNG once — for the preview tiles of the avatar
// library (Step1Appearance.tsx), so a real image is shown there instead of initials.
// A separate, lean three.js setup instead of reusing TalkingHeadAvatar: its renderer runs in an
// endless animation loop without `preserveDrawingBuffer`, so a `toBlob()` snapshot at an
// arbitrary moment would reliably return a blank image there.
export async function captureAvatarThumbnail(glbUrl: string): Promise<Blob> {
  const canvas = document.createElement("canvas");
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true });
  renderer.setSize(SIZE, SIZE, false);

  try {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(25, 1, 0.1, 10);

    scene.add(new THREE.AmbientLight(0xffffff, 1.4));
    const key = new THREE.DirectionalLight(0xffffff, 1.2);
    key.position.set(0.6, 1, 1);
    scene.add(key);

    const gltf = await new GLTFLoader().loadAsync(glbUrl);
    const model = gltf.scene;
    scene.add(model);

    // Roughly zoom in on the head: take the bounding box of the whole model and aim the camera at
    // the upper part (Ready Player Me avatars stand upright, the head is at the very top).
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const headY = box.max.y - size.y * 0.09;
    camera.position.set(box.getCenter(new THREE.Vector3()).x, headY, size.z + size.y * 0.32);
    camera.lookAt(box.getCenter(new THREE.Vector3()).x, headY, 0);

    renderer.render(scene, camera);

    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("Snapshot fehlgeschlagen.");
    return blob;
  } finally {
    renderer.dispose();
  }
}
