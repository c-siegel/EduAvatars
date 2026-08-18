// "three" ships no bundled types in the installed version and @types/three isn't a dependency —
// minimal ambient declaration (any-typed) so avatarThumbnail.ts compiles, same pattern as
// talkinghead.d.ts for @met4citizen/talkinghead.
declare module "three";
declare module "three/addons/loaders/GLTFLoader.js";
