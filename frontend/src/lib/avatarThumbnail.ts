import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const SIZE = 256;

// Rendert einmalig eine Kopf-Nahaufnahme eines .glb-Avatars in ein PNG — für die Vorschau-Kacheln
// der Avatar-Bibliothek (Step1Appearance.tsx), damit dort ein echtes Bild statt der Initialen steht.
// Eigener, schlanker three.js-Aufbau statt Wiederverwendung von TalkingHeadAvatar: dessen Renderer
// läuft in einer Endlos-Animationsschleife ohne `preserveDrawingBuffer`, ein `toBlob()`-Schnappschuss
// zu einem beliebigen Zeitpunkt würde dort zuverlässig ein leeres Bild liefern.
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

    // Grob auf den Kopf zoomen: Bounding-Box des ganzen Modells nehmen und die Kamera auf den
    // oberen Bereich (Ready-Player-Me-Avatare stehen aufrecht, Kopf ist ganz oben) ausrichten.
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
