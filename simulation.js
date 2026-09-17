import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { DrosophilaConnectome } from './connectome.js';

// --- Simulation State ---
const state = {
    flyPosition: new THREE.Vector3(0, 0, 0),
    flyHeading: 0.0,
    legs: {},
    wings: {},
    proboscis: null,
    baseRotations: {},
    isXRayActive: true, // Default ON so the internal brain is visible!
    bodyMeshes: [],
    brainNeuropils: {},
    brainModel: null,
};

const connectome = new DrosophilaConnectome();

// --- DOM Elements ---
const container = document.getElementById('canvas-container');
const compassCanvas = document.getElementById('compass-canvas');
const compassCtx = compassCanvas ? compassCanvas.getContext('2d') : null;
const compassHeadingText = document.getElementById('compass-heading');

const behaviorBadge   = document.getElementById('behavior-badge');
const behaviorSubtext = document.getElementById('behavior-subtext');

const barDNb01 = document.getElementById('bar-dnb01');
const hzDNb01  = document.getElementById('hz-dnb01');
const barDNp09 = document.getElementById('bar-dnp09');
const hzDNp09  = document.getElementById('hz-dnp09');
const barDNA   = document.getElementById('bar-dna');
const hzDNA    = document.getElementById('hz-dna');
const btnToggleXRay = document.getElementById('btn-toggle-xray');

// --- Three.js Setup ---
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0e14);
scene.fog = new THREE.FogExp2(0x0a0e14, 0.007);

const camera = new THREE.PerspectiveCamera(48, window.innerWidth / window.innerHeight, 0.05, 1000);
camera.position.set(4.5, 3.8, 5.5);

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.25;
container.appendChild(renderer.domElement);

// --- Orbit Controls (Pure Spectator Mode) ---
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.minDistance = 0.8;  // Extreme macro zoom to inspect brain & eyes
controls.maxDistance = 60.0;
controls.maxPolarAngle = Math.PI / 2.05; // Stay above ground plane
controls.target.set(0, 0.45, 0);

// --- Lighting ---
const hemiLight = new THREE.HemisphereLight(0xddeeff, 0x151b22, 1.4);
scene.add(hemiLight);

const sunLight = new THREE.DirectionalLight(0xfff5e6, 2.6);
sunLight.position.set(25, 40, 20);
sunLight.castShadow = true;
sunLight.shadow.mapSize.width = 2048;
sunLight.shadow.mapSize.height = 2048;
sunLight.shadow.camera.near = 0.5;
sunLight.shadow.camera.far = 150;
const d = 30;
sunLight.shadow.camera.left = -d;
sunLight.shadow.camera.right = d;
sunLight.shadow.camera.top = d;
sunLight.shadow.camera.bottom = -d;
scene.add(sunLight);

// Ground subtle grid
const grid = new THREE.GridHelper(500, 250, 0x30363d, 0x161b22);
grid.position.y = -0.01;
scene.add(grid);

// --- Fly Root & Asset Loading ---
const flyRoot = new THREE.Group();
scene.add(flyRoot);

const loader = new GLTFLoader();

// 1. Load Environment (env.glb)
loader.load('env.glb', (gltf) => {
    console.log('>> env.glb loaded successfully');
    const env = gltf.scene;
    env.traverse((child) => {
        if (child.isMesh) {
            child.receiveShadow = true;
            if (child.material) child.material.roughness = 0.88;
        }
    });
    scene.add(env);
}, undefined, (err) => {
    console.warn('env.glb fallback plane:', err);
    const plane = new THREE.Mesh(
        new THREE.PlaneGeometry(600, 600),
        new THREE.MeshStandardMaterial({ color: 0x161b22, roughness: 0.9 })
    );
    plane.rotation.x = -Math.PI / 2;
    plane.receiveShadow = true;
    scene.add(plane);
});

// 2. Load Drosophila melanogaster (drosophila_melanogaster.glb)
const legNames = [
    'Leg_Front_Coxa_L', 'Leg_Front_Femur_L', 'Leg_Front_Tibia_L', 'Leg_Front_Tarsus_L',
    'Leg_Front_Coxa_R', 'Leg_Front_Femur_R', 'Leg_Front_Tibia_R', 'Leg_Front_Tarsus_R',
    'Leg_Mid_Coxa_L',   'Leg_Mid_Femur_L',   'Leg_Mid_Tibia_L',   'Leg_Mid_Tarsus_L',
    'Leg_Mid_Coxa_R',   'Leg_Mid_Femur_R',   'Leg_Mid_Tibia_R',   'Leg_Mid_Tarsus_R',
    'Leg_Hind_Coxa_L',  'Leg_Hind_Femur_L',  'Leg_Hind_Tibia_L',  'Leg_Hind_Tarsus_L',
    'Leg_Hind_Coxa_R',  'Leg_Hind_Femur_R',  'Leg_Hind_Tibia_R',  'Leg_Hind_Tarsus_R'
];

loader.load('drosophila_melanogaster.glb', (gltf) => {
    console.log('>> drosophila_melanogaster.glb loaded');
    const fly = gltf.scene;
    fly.scale.set(1.5, 1.5, 1.5);
    flyRoot.add(fly);

    fly.traverse((child) => {
        if (child.isMesh) {
            child.castShadow = true;
            child.receiveShadow = true;
            state.bodyMeshes.push(child);
            child.userData.origMaterial = child.material;

            // Apply default X-ray translucency so the brain is visible
            if (child.name.includes('Head') || child.name.includes('Thorax')) {
                const mat = child.material.clone();
                mat.transparent = true;
                mat.opacity = 0.55;
                child.material = mat;
            }
        }

        if (legNames.includes(child.name)) {
            state.legs[child.name] = child;
            state.baseRotations[child.name] = child.rotation.clone();
        }

        if (child.name === 'Wing_L' || child.name === 'Wing_R') {
            state.wings[child.name] = child;
            state.baseRotations[child.name] = child.rotation.clone();
        }

        if (child.name.includes('Proboscis')) {
            state.proboscis = child;
            state.baseRotations['Proboscis'] = child.rotation.clone();
        }
    });

    // 3. Load 3D Brain Model into Head Capsule
    loadBrainModel();
}, undefined, (err) => {
    console.error('Error loading fly model:', err);
});

function loadBrainModel() {
    loader.load('drosophila_brain.glb', (gltf) => {
        console.log('>> drosophila_brain.glb loaded into head');
        const brain = gltf.scene;
        brain.scale.set(1.55, 1.55, 1.55);
        brain.position.set(0, 0.82, 0.84); // Nestled inside head capsule
        flyRoot.add(brain);
        state.brainModel = brain;

        brain.traverse((child) => {
            if (child.isMesh) {
                state.brainNeuropils[child.name] = child;
            }
        });
    }, undefined, (err) => {
        console.warn('Could not load brain model:', err);
    });
}

// --- X-Ray Cuticle Toggle ---
function applyXRay(active) {
    state.isXRayActive = active;
    if (btnToggleXRay) {
        btnToggleXRay.innerText = active ? '✨ Normal Cuticle View' : '🧠 X-Ray Brain View';
        btnToggleXRay.style.background = active
            ? 'linear-gradient(135deg, #238636 0%, #2ea043 100%)'
            : 'linear-gradient(135deg, #1f6feb 0%, #8957e5 100%)';
    }

    state.bodyMeshes.forEach((mesh) => {
        if (active) {
            const xrayMat = mesh.userData.origMaterial.clone();
            xrayMat.transparent = true;
            xrayMat.opacity = mesh.name.includes('Eye') ? 0.75 : 0.35;
            xrayMat.roughness = 0.15;
            mesh.material = xrayMat;
        } else {
            mesh.material = mesh.userData.origMaterial;
        }
    });
}

if (btnToggleXRay) {
    btnToggleXRay.addEventListener('click', () => applyXRay(!state.isXRayActive));
}

window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

// --- Central Complex Compass Dial ---
function drawEPGCompass(heading) {
    if (!compassCtx) return;
    const ctx = compassCtx;
    const w = compassCanvas.width;
    const h = compassCanvas.height;
    const cx = w / 2;
    const cy = h / 2;
    const radius = 52;

    ctx.clearRect(0, 0, w, h);

    const numWedges = 16;
    const wedgeAngle = (Math.PI * 2) / numWedges;

    for (let i = 0; i < numWedges; i++) {
        const start = i * wedgeAngle - Math.PI / 2;
        const end = start + wedgeAngle;
        const activity = connectome.epgActivity[i];
        const norm = Math.min(1.0, Math.max(0.0, (activity - 10) / 75));

        const r = Math.round(20 + 35 * norm);
        const g = Math.round(50 + 205 * norm);
        const b = Math.round(80 + 175 * norm);
        ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;

        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.arc(cx, cy, radius + norm * 8, start, end);
        ctx.closePath();
        ctx.fill();

        ctx.strokeStyle = '#12171f';
        ctx.lineWidth = 1.5;
        ctx.stroke();
    }

    // Inner dial ring
    ctx.beginPath();
    ctx.arc(cx, cy, 22, 0, Math.PI * 2);
    ctx.fillStyle = '#0a0e14';
    ctx.fill();
    ctx.strokeStyle = '#30363d';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Needle
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(heading);

    ctx.beginPath();
    ctx.moveTo(0, -18);
    ctx.lineTo(5, -5);
    ctx.lineTo(-5, -5);
    ctx.closePath();
    ctx.fillStyle = '#f85149';
    ctx.fill();

    ctx.restore();

    const deg = Math.round(((-heading * 180 / Math.PI) % 360 + 360) % 360);
    if (compassHeadingText) compassHeadingText.innerText = `Heading: ${deg}°`;
}

function updateHUD() {
    const stateLabels = {
        'EXPLORATORY_WALK':   { title: 'STATUS: FORAGING WALK', sub: 'Autonomous exploration via Central Complex & DNb01', color: '#3fb950' },
        'BODY_SACCADE':       { title: 'STATUS: ORIENTATION SACCADE', sub: 'Rapid heading reset via asymmetric DNa01/DNa02', color: '#58a6ff' },
        'CEPHALIC_GROOMING':  { title: 'STATUS: CEPHALIC GROOMING', sub: 'Front-leg sweeps across eyes & antennae (aDN1 / DNp09)', color: '#bc8cff' },
        'TARSI_RUBBING':      { title: 'STATUS: TARSI SCRUBBING', sub: 'Distal front tarsi rubbing to remove particulates', color: '#bc8cff' },
        'WING_GROOMING':      { title: 'STATUS: WING GROOMING', sub: 'Hind legs cleaning wing margins', color: '#58a6ff' },
        'PROBOSCIS_SAMPLING': { title: 'STATUS: GUSTATORY PROBING', sub: 'Substrate evaluation & antennal odor sampling', color: '#f0883e' },
    };

    const cur = stateLabels[connectome.state] || stateLabels['EXPLORATORY_WALK'];
    if (behaviorBadge) {
        behaviorBadge.innerText = cur.title;
        behaviorBadge.style.color = cur.color;
    }
    if (behaviorSubtext) behaviorSubtext.innerText = cur.sub;

    const dns = connectome.dns;
    if (hzDNb01) hzDNb01.innerText = `${dns.DNb01.toFixed(1)} Hz`;
    if (barDNb01) barDNb01.style.width = `${Math.min(100, (dns.DNb01 / 80) * 100)}%`;

    const groomHz = Math.max(dns.DNp09, dns.aDN1);
    if (hzDNp09) hzDNp09.innerText = `${groomHz.toFixed(1)} Hz`;
    if (barDNp09) barDNp09.style.width = `${Math.min(100, (groomHz / 90) * 100)}%`;

    const steerHz = Math.max(dns.DNa01, dns.DNa02);
    if (hzDNA) hzDNA.innerText = `${steerHz.toFixed(1)} Hz`;
    if (barDNA) barDNA.style.width = `${Math.min(100, (steerHz / 65) * 100)}%`;

    drawEPGCompass(state.flyHeading);
}

// --- Main Simulation Loop ---
let lastTime = performance.now();

function animate() {
    requestAnimationFrame(animate);

    const now = performance.now();
    const dt = Math.min(0.08, (now - lastTime) / 1000.0);
    lastTime = now;

    // 1. Biological Connectome Step
    connectome.updateAutonomous(dt, state.flyHeading);

    // 2. Autonomous Fly Motion on Plane
    state.flyHeading += connectome.turnRate * dt;

    const forwardVec = new THREE.Vector3(
        -Math.sin(state.flyHeading),
        0,
        -Math.cos(state.flyHeading)
    );

    const deltaMove = forwardVec.multiplyScalar(connectome.walkingSpeed * dt * 0.45);
    state.flyPosition.add(deltaMove);

    // Subtle body pitch & vertical sway during gait
    const bodyBob = connectome.walkingSpeed > 1.0 ? Math.sin(connectome.cpgPhase * 2.0) * 0.02 : 0;
    flyRoot.position.set(state.flyPosition.x, state.flyPosition.y + bodyBob, state.flyPosition.z);
    flyRoot.rotation.y = state.flyHeading;

    // 3. Leg Kinematics (Grooming or Tripod Walking)
    for (const [prefix, side] of [
        ['Leg_Front', 'L'], ['Leg_Front', 'R'],
        ['Leg_Mid', 'L'],   ['Leg_Mid', 'R'],
        ['Leg_Hind', 'L'],  ['Leg_Hind', 'R'],
    ]) {
        const kin = connectome.getLegKinematics(prefix, side);

        const coxaObj   = state.legs[`${prefix}_Coxa_${side}`];
        const femurObj  = state.legs[`${prefix}_Femur_${side}`];
        const tibiaObj  = state.legs[`${prefix}_Tibia_${side}`];
        const tarsusObj = state.legs[`${prefix}_Tarsus_${side}`];

        if (coxaObj && state.baseRotations[coxaObj.name]) {
            const base = state.baseRotations[coxaObj.name];
            coxaObj.rotation.set(base.x + kin.coxa.x, base.y + kin.coxa.y, base.z + kin.coxa.z);
        }
        if (femurObj && state.baseRotations[femurObj.name]) {
            const base = state.baseRotations[femurObj.name];
            femurObj.rotation.set(base.x + kin.femur.x, base.y, base.z);
        }
        if (tibiaObj && state.baseRotations[tibiaObj.name]) {
            const base = state.baseRotations[tibiaObj.name];
            tibiaObj.rotation.set(base.x + kin.tibia.x, base.y, base.z);
        }
        if (tarsusObj && state.baseRotations[tarsusObj.name]) {
            const base = state.baseRotations[tarsusObj.name];
            tarsusObj.rotation.set(base.x + kin.tarsus.x, base.y, base.z);
        }
    }

    // 4. Proboscis Extension during Gustatory Sampling
    if (state.proboscis && state.baseRotations['Proboscis']) {
        const base = state.baseRotations['Proboscis'];
        state.proboscis.rotation.x = base.x + connectome.proboscisExtension * 0.35;
    }

    // 5. Dynamic 3D Brain Neuropil Glow Animation
    if (state.brainModel) {
        // Pulse brain size slightly with biological breathing
        const pulse = 1.0 + Math.sin(now * 0.006) * 0.03;
        state.brainModel.scale.set(1.55 * pulse, 1.55 * pulse, 1.55 * pulse);

        // Modulate emission of active neuropils
        for (const [name, mesh] of Object.entries(state.brainNeuropils)) {
            if (!mesh.material) continue;
            let act = 0.3;
            if (name.includes('CX')) act = connectome.neuropilActivity.centralComplex;
            else if (name.includes('Antennal')) act = connectome.neuropilActivity.antennalLobes;
            else if (name.includes('Optic')) act = connectome.neuropilActivity.opticLobes;
            else if (name.includes('Mushroom')) act = connectome.neuropilActivity.mushroomBody;

            if (mesh.material.emissiveIntensity !== undefined) {
                mesh.material.emissiveIntensity = 0.5 + act * 2.5;
            }
        }
    }

    // 6. Smooth Spectator Tracking Camera
    controls.target.lerp(new THREE.Vector3(state.flyPosition.x, 0.42, state.flyPosition.z), 0.06);
    controls.update();

    // 7. Update HUD
    updateHUD();

    renderer.render(scene, camera);
}

animate();
