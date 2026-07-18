import * as THREE from "/vendor/three.module.js";

const canvas = document.querySelector("#universe");
const statusEl = document.querySelector("#run-status");
const phaseEl = document.querySelector("#phase-copy");
const headlineEl = document.querySelector("#headline-copy");
const runPanelEl = document.querySelector("#run-panel");
const timelinesEl = document.querySelector("#timeline-panel");
const judgeEl = document.querySelector("#judge-panel");
const decisionEl = document.querySelector("#decision-panel");
const fallbackEl = document.querySelector("#render-fallback");

let renderer;
try {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
} catch (error) {
  fallbackEl.hidden = false;
  console.error("Everett could not initialize WebGL", error);
}

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x05070d);
scene.fog = new THREE.FogExp2(0x05070d, 0.065);
const camera = new THREE.PerspectiveCamera(44, innerWidth / innerHeight, 0.1, 100);
camera.position.set(0, 3.7, 14);
if (renderer) {
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(innerWidth, innerHeight);
  renderer.setAnimationLoop(animate);
}

scene.add(new THREE.HemisphereLight(0x85e7ff, 0x07070a, 2.2));
const keyLight = new THREE.PointLight(0x85e7ff, 80, 40);
keyLight.position.set(0, 7, 4);
scene.add(keyLight);
const rimLight = new THREE.PointLight(0x42e7c5, 45, 26);
rimLight.position.set(-5, 2, -2);
scene.add(rimLight);

const starGeometry = new THREE.BufferGeometry();
const stars = new Float32Array(1900 * 3);
for (let index = 0; index < stars.length; index += 3) {
  stars[index] = (Math.random() - 0.5) * 40;
  stars[index + 1] = (Math.random() - 0.35) * 24;
  stars[index + 2] = (Math.random() - 0.5) * 36;
}
starGeometry.setAttribute("position", new THREE.BufferAttribute(stars, 3));
scene.add(new THREE.Points(starGeometry, new THREE.PointsMaterial({ color: 0x8ac4e7, size: 0.027, transparent: true, opacity: 0.82 })));

function createPlanetTexture() {
  const textureCanvas = document.createElement("canvas");
  textureCanvas.width = textureCanvas.height = 512;
  const context = textureCanvas.getContext("2d");
  context.fillStyle = "#061426";
  context.fillRect(0, 0, 512, 512);
  for (let index = 0; index < 900; index += 1) {
    const x = Math.random() * 512;
    const y = Math.random() * 512;
    const radius = 1 + Math.random() * 15;
    context.fillStyle = Math.random() > 0.76 ? "rgba(80, 229, 197, 0.32)" : "rgba(21, 93, 124, 0.28)";
    context.beginPath();
    context.ellipse(x, y, radius * 1.8, radius, Math.random() * Math.PI, 0, Math.PI * 2);
    context.fill();
  }
  for (let index = 0; index < 70; index += 1) {
    context.strokeStyle = "rgba(129, 232, 255, 0.2)";
    context.lineWidth = 0.5 + Math.random();
    context.beginPath();
    context.moveTo(Math.random() * 512, Math.random() * 512);
    context.lineTo(Math.random() * 512, Math.random() * 512);
    context.stroke();
  }
  const texture = new THREE.CanvasTexture(textureCanvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

const CORE_POSITION = new THREE.Vector3(0, -0.35, 0);
const core = new THREE.Group();
const coreBody = new THREE.Mesh(
  new THREE.SphereGeometry(1.48, 64, 64),
  new THREE.MeshStandardMaterial({ map: createPlanetTexture(), color: 0x83d6e6, emissive: 0x0f5365, emissiveIntensity: 0.85, roughness: 0.5, metalness: 0.28 })
);
const coreGlow = new THREE.Mesh(
  new THREE.SphereGeometry(0.18, 20, 20),
  new THREE.MeshBasicMaterial({ color: 0x85e7ff, transparent: true, opacity: 0.95 })
);
coreGlow.position.z = 1.4;
const coreWire = new THREE.Mesh(
  new THREE.SphereGeometry(1.52, 32, 20),
  new THREE.MeshBasicMaterial({ color: 0x72ddff, wireframe: true, transparent: true, opacity: 0.12 })
);
core.add(coreBody, coreGlow, coreWire);
core.position.copy(CORE_POSITION);
scene.add(core);
const coreHalo = new THREE.Mesh(
  new THREE.TorusGeometry(1.92, 0.025, 8, 96),
  new THREE.MeshBasicMaterial({ color: 0x72ddff, transparent: true, opacity: 0.72 })
);
coreHalo.rotation.x = Math.PI / 2.8;
coreHalo.position.copy(CORE_POSITION);
scene.add(coreHalo);

const nodePositions = [new THREE.Vector3(-4.5, 0.25, -0.6), new THREE.Vector3(0, 2.35, -2.5), new THREE.Vector3(4.5, 0.35, -0.6)];
const colors = { ready: 0x60758d, running: 0x85e7ff, succeeded: 0x9bf4bd, failed: 0xff727d, timeout: 0xff9f77, winner: 0xffd68a };
const nodes = nodePositions.map((position, index) => makeNode(position, index));
const paths = nodePositions.map((position) => makePath(position));
paths.forEach((path) => scene.add(path));

const hostedDemoState = {
  run_id: "DEMO-01",
  phase: "collapsed",
  winner: "B",
  timelines: [
    { id: "A", strategy: "Add a response cache while preserving report correctness.", status: "succeeded" },
    { id: "B", strategy: "Eliminate the N+1 query pattern in the report path.", status: "succeeded" },
    { id: "C", strategy: "Precompute report summaries before serving requests.", status: "succeeded" },
  ],
  scoreboard: [
    { timeline: "A", tests_passed: true, speedup: 2.18, diff_lines: 31, score: 2.03 },
    { timeline: "B", tests_passed: true, speedup: 11.42, diff_lines: 44, score: 11.2 },
    { timeline: "C", tests_passed: true, speedup: 8.93, diff_lines: 86, score: 8.5 },
  ],
};

let state = hostedDemoState;

function makeNode(position, index) {
  const group = new THREE.Group();
  group.position.copy(position);
  const shell = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.7, 3),
    new THREE.MeshStandardMaterial({ color: colors.ready, emissive: colors.ready, emissiveIntensity: 0.6, roughness: 0.25, metalness: 0.55 })
  );
  const pulse = new THREE.Mesh(
    new THREE.SphereGeometry(0.17, 18, 18),
    new THREE.MeshBasicMaterial({ color: 0xf5f8ff, transparent: true, opacity: 0.92 })
  );
  pulse.position.z = 0.65;
  const orbit = new THREE.Mesh(
    new THREE.TorusGeometry(0.98, 0.018, 8, 64),
    new THREE.MeshBasicMaterial({ color: colors.ready, transparent: true, opacity: 0.55 })
  );
  orbit.rotation.x = Math.PI / 2.4 + index * 0.18;
  group.add(shell, pulse, orbit);
  group.userData = { shell, pulse, orbit, index, status: "ready" };
  scene.add(group);
  return group;
}

function makePath(target) {
  const curve = new THREE.QuadraticBezierCurve3(CORE_POSITION.clone(), new THREE.Vector3(target.x * 0.35, 2.9, target.z * 0.25), target);
  const geometry = new THREE.TubeGeometry(curve, 54, 0.021, 6, false);
  return new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ color: 0x29465a, transparent: true, opacity: 0.5 }));
}

function applyState(next) {
  state = next;
  const timelines = next.timelines.length ? next.timelines : ["A", "B", "C"].map((id) => ({ id, strategy: "Awaiting a strategy", status: "ready" }));
  timelines.slice(0, 3).forEach((timeline, index) => {
    const node = nodes[index];
    const status = next.winner === timeline.id ? "winner" : timeline.status || "ready";
    const color = colors[status] || colors.ready;
    node.userData.status = status;
    node.userData.shell.material.color.setHex(color);
    node.userData.shell.material.emissive.setHex(color);
    node.userData.pulse.material.color.setHex(color);
    node.userData.orbit.material.color.setHex(color);
    paths[index].material.color.setHex(status === "ready" ? 0x29465a : color);
    paths[index].material.opacity = status === "ready" ? 0.32 : 0.82;
  });
  renderPanels(timelines, next.scoreboard || []);
  const phase = (next.phase || "ready").toUpperCase();
  statusEl.textContent = next.run_id ? `${phase} / ${next.run_id}` : "READY TO FORK";
  phaseEl.textContent = phaseCopy(next.phase, next.winner);
  headlineEl.textContent = next.winner ? `Timeline ${next.winner} survived. The losing futures became evidence.` : "Three futures. One objective judge. One surviving branch.";
}

function renderPanels(timelines, scoreboard) {
  renderRunBrief(timelines, scoreboard);
  timelinesEl.innerHTML = `<h2 class="panel-title">Timeline status</h2>${timelines.map((timeline) => `<div class="timeline-card"><div class="timeline-meta"><span class="timeline-id">${timeline.id}</span><span class="badge ${badgeStatus(timeline)}">${labelStatus(timeline)}</span></div><div class="strategy">${escapeHtml(timeline.strategy)}</div></div>`).join("")}`;
  judgeEl.innerHTML = scoreboard.length ? `<h2 class="panel-title">Objective judge</h2>${scoreboard.map((entry) => scoreRow(entry)).join("")}` : `<h2 class="panel-title">Objective judge</h2><div class="empty">Waiting for objective measurements.</div>`;
  renderDecision(scoreboard);
}

function renderRunBrief(timelines, scoreboard) {
  const complete = timelines.filter((timeline) => ["succeeded", "failed", "timeout"].includes(timeline.status)).length;
  const passing = scoreboard.filter((entry) => entry.tests_passed).length;
  runPanelEl.innerHTML = `<h2 class="panel-title">Run telemetry</h2><div class="metric-grid"><div><span>FUTURES</span><strong>${timelines.length || 3}</strong></div><div><span>COMPLETE</span><strong>${complete}/${timelines.length || 3}</strong></div><div><span>TESTS GREEN</span><strong>${passing || "-"}</strong></div><div><span>PHASE</span><strong>${escapeHtml((state.phase || "ready").toUpperCase())}</strong></div></div>`;
}

function scoreRow(entry) {
  const isWinner = state.winner === entry.timeline;
  const score = Number(entry.score || 0);
  const maxScore = Math.max(...state.scoreboard.map((candidate) => Math.max(Number(candidate.score || 0), 0)), 1);
  const width = Math.max(4, Math.round((Math.max(score, 0) / maxScore) * 100));
  return `<div class="score-row ${isWinner ? "winner" : ""}"><div><strong>${entry.timeline}${isWinner ? " / WINNER" : ""}</strong><span class="test-state ${entry.tests_passed ? "pass" : "fail"}">${entry.tests_passed ? "TESTS PASS" : "TESTS FAIL"}</span><div class="score-meter"><i style="width:${width}%"></i></div></div><div class="score-numbers"><b>${Number(entry.speedup || 0).toFixed(2)}x</b><span>${Number(entry.diff_lines || 0)} lines</span><em>${score.toFixed(2)}</em></div></div>`;
}

function renderDecision(scoreboard) {
  if (!scoreboard.length) {
    decisionEl.innerHTML = `<h2 class="panel-title">Decision evidence</h2><div class="empty">The judge will expose the hard gate and score evidence when measurements arrive.</div>`;
    return;
  }
  const winner = scoreboard.find((entry) => entry.timeline === state.winner) || [...scoreboard].sort((a, b) => Number(b.score) - Number(a.score))[0];
  const runnerUp = [...scoreboard].filter((entry) => entry.timeline !== winner.timeline && entry.tests_passed).sort((a, b) => Number(b.score) - Number(a.score))[0];
  const margin = runnerUp ? Number(winner.score - runnerUp.score).toFixed(2) : "-";
  decisionEl.innerHTML = `<h2 class="panel-title">Decision evidence</h2><div class="verdict"><span>SELECTED</span><strong>TIMELINE ${escapeHtml(winner.timeline)}</strong></div><div class="evidence-row"><span>Hard gate</span><b class="${winner.tests_passed ? "pass" : "fail"}">${winner.tests_passed ? "Tests passing" : "Tests failed"}</b></div><div class="evidence-row"><span>Observed speed</span><b>${Number(winner.speedup || 0).toFixed(2)}x faster</b></div><div class="evidence-row"><span>Change impact</span><b>${Number(winner.diff_lines || 0)} lines</b></div><div class="evidence-row"><span>Score margin</span><b>${margin}</b></div><p class="decision-copy">Selected because it cleared the test gate and produced the highest objective score among the explored timelines.</p>`;
}

function badgeStatus(timeline) { return state.winner === timeline.id ? "winner" : (timeline.status || "ready").toLowerCase(); }
function labelStatus(timeline) { return state.winner === timeline.id ? "WINNER" : (timeline.status || "ready").toUpperCase(); }
function phaseCopy(phase, winner) { if (winner) return `Wavefunction collapsed to timeline ${winner}.`; if (phase === "exploring") return "Three workers are exploring independent futures."; if (phase === "judged") return "The fitness harness is ranking the futures."; return "Awaiting a run from Codex."; }
function escapeHtml(value) { const element = document.createElement("span"); element.textContent = value; return element.innerHTML; }

function animate(time) {
  if (!renderer) return;
  const seconds = time * 0.001;
  core.rotation.y += 0.003;
  core.rotation.x = Math.sin(seconds * 0.7) * 0.14;
  coreHalo.rotation.z += 0.004;
  nodes.forEach((node) => {
    const active = node.userData.status === "running";
    const winner = node.userData.status === "winner";
    const pulse = active ? 1 + Math.sin(seconds * 4 + node.userData.index) * 0.09 : winner ? 1.28 : 1;
    node.scale.setScalar(pulse);
    node.userData.orbit.rotation.z += active ? 0.022 : 0.005;
  });
  camera.position.x = Math.sin(seconds * 0.09) * 0.55;
  camera.lookAt(0, 0.55, 0);
  renderer.render(scene, camera);
}

async function refresh() {
  try { applyState(await (await fetch("/api/state", { cache: "no-store" })).json()); } catch (_) {}
}
addEventListener("resize", () => { if (renderer) { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); } });
applyState(hostedDemoState);
refresh();
setInterval(refresh, 1000);
