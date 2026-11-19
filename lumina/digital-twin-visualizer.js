/**
 * Codebase Digital Twin: Interactive 3D Dependency Graph & Blast Radius Simulator
 * High-performance 3D projection engine with dynamic depth, particle pulses, and blast simulation.
 */

class CodebaseDigitalTwinVisualizer {
  constructor(canvasEl, options = {}) {
    this.canvas = canvasEl;
    this.ctx = this.canvas.getContext('2d');
    this.options = options;

    // 3D Camera & Projection
    this.rotX = 0.45;
    this.rotY = -0.55;
    this.zoom = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.autoRotate = true;

    // Interaction state
    this.isDragging = false;
    this.lastMouseX = 0;
    this.lastMouseY = 0;
    this.hoveredNode = null;
    this.selectedNode = null;

    // Data & Layout
    this.nodes = [];
    this.edges = [];
    this.blastData = null;
    this.activeFilter = 'all';

    // Particle flow animation
    this.particles = [];
    this.animFrameId = null;

    this.initCanvasSize();
    this.bindEvents();
    this.startRenderLoop();
  }

  initCanvasSize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = (rect.height || 520) * dpr;
    this.width = rect.width;
    this.height = rect.height || 520;
    this.ctx.scale(dpr, dpr);
  }

  setData(data) {
    if (!data) return;
    this.nodes = data.nodes || [];
    this.edges = data.edges || [];
    this.blastData = data.blast_radius || null;

    this.layoutNodes3D();
    this.initParticles();
  }

  setBlastRadius(blast) {
    this.blastData = blast;
    if (blast && blast.affected_node_ids) {
      const affectedSet = new Set(blast.affected_node_ids);
      const directSet = new Set(blast.direct_targets || []);

      this.nodes.forEach(n => {
        n.is_affected = affectedSet.has(n.id);
        n.is_direct_target = directSet.has(n.id);
      });
      this.edges.forEach(e => {
        e.is_blast_path = affectedSet.has(e.source) && affectedSet.has(e.target);
      });
    }
  }

  layoutNodes3D() {
    const count = this.nodes.length;
    if (count === 0) return;

    // Categorize nodes by layer in 3D space
    const apis = this.nodes.filter(n => n.type === 'api_endpoint');
    const funcs = this.nodes.filter(n => n.type === 'function');
    const modules = this.nodes.filter(n => n.type === 'module');
    const tests = this.nodes.filter(n => n.type === 'test');

    const arrangeRing = (items, z, radius, yOffset = 0) => {
      const n = items.length;
      items.forEach((item, i) => {
        const theta = (i / Math.max(1, n)) * Math.PI * 2;
        item.x3d = Math.cos(theta) * radius;
        item.y3d = Math.sin(theta) * (radius * 0.75) + yOffset;
        item.z3d = z;
      });
    };

    arrangeRing(apis, 110, 190, -40);       // Top Layer: APIs (Z = +110)
    arrangeRing(funcs, 20, 230, 0);          // Middle Layer: Business Logic Functions (Z = +20)
    arrangeRing(modules, -40, 140, 30);      // Core Layer: Modules (Z = -40)
    arrangeRing(tests, -110, 210, 50);       // Base Layer: Test Cases (Z = -110)
  }

  initParticles() {
    this.particles = [];
    for (let i = 0; i < 40; i++) {
      this.particles.push({
        edgeIndex: Math.floor(Math.random() * Math.max(1, this.edges.length)),
        progress: Math.random(),
        speed: 0.005 + Math.random() * 0.008,
      });
    }
  }

  project3D(x, y, z) {
    // 3D rotation around Y and X axes
    const cosY = Math.cos(this.rotY);
    const sinY = Math.sin(this.rotY);
    const x1 = x * cosY - z * sinY;
    const z1 = z * cosY + x * sinY;

    const cosX = Math.cos(this.rotX);
    const sinX = Math.sin(this.rotX);
    const y2 = y * cosX - z1 * sinX;
    const z2 = z1 * cosX + y * sinX;

    // Perspective projection
    const fov = 480 * this.zoom;
    const distance = 460 - z2;
    const scale = distance > 10 ? fov / distance : 0.1;

    const screenX = this.width / 2 + this.panX + x1 * scale;
    const screenY = this.height / 2 + this.panY + y2 * scale;

    return { x: screenX, y: screenY, scale, z: z2 };
  }

  bindEvents() {
    window.addEventListener('resize', () => this.initCanvasSize());

    this.canvas.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.autoRotate = false;
      this.lastMouseX = e.clientX;
      this.lastMouseY = e.clientY;
    });

    window.addEventListener('mouseup', () => {
      this.isDragging = false;
    });

    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      if (this.isDragging) {
        const dx = e.clientX - this.lastMouseX;
        const dy = e.clientY - this.lastMouseY;
        this.rotY += dx * 0.008;
        this.rotX += dy * 0.008;
        // Limit X pitch to prevent flipping upside down
        this.rotX = Math.max(-1.4, Math.min(1.4, this.rotX));
        this.lastMouseX = e.clientX;
        this.lastMouseY = e.clientY;
      } else {
        this.checkHover(mouseX, mouseY);
      }
    });

    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92;
      this.zoom = Math.max(0.4, Math.min(2.5, this.zoom * zoomFactor));
    }, { passive: false });
  }

  checkHover(mouseX, mouseY) {
    let closest = null;
    let minD = 18;

    for (const node of this.nodes) {
      if (!node.proj) continue;
      const d = Math.hypot(node.proj.x - mouseX, node.proj.y - mouseY);
      if (d < minD) {
        closest = node;
        minD = d;
      }
    }

    if (closest !== this.hoveredNode) {
      this.hoveredNode = closest;
      if (this.options.onHover) {
        this.options.onHover(closest, mouseX, mouseY);
      }
    }
  }

  startRenderLoop() {
    const loop = () => {
      if (this.autoRotate) {
        this.rotY += 0.0025;
      }
      this.render();
      this.animFrameId = requestAnimationFrame(loop);
    };
    loop();
  }

  render() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.width, this.height);

    // 1. Draw subtle 3D reference planes
    this.renderReferenceGrid();

    // 2. Project all nodes
    const nodeMap = new Map();
    for (const node of this.nodes) {
      if (node.x3d === undefined) continue;
      node.proj = this.project3D(node.x3d, node.y3d, node.z3d);
      nodeMap.set(node.id, node);
    }

    // 3. Render edges
    for (const edge of this.edges) {
      const s = nodeMap.get(edge.source);
      const t = nodeMap.get(edge.target);
      if (!s || !t || !s.proj || !t.proj) continue;

      const isBlast = edge.is_blast_path;
      ctx.beginPath();
      ctx.moveTo(s.proj.x, s.proj.y);
      ctx.lineTo(t.proj.x, t.proj.y);

      if (isBlast) {
        ctx.strokeStyle = 'rgba(255, 75, 43, 0.85)';
        ctx.lineWidth = 2.4;
        ctx.shadowColor = '#ff4b2b';
        ctx.shadowBlur = 8;
      } else {
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.lineWidth = 1.0;
        ctx.shadowBlur = 0;
      }
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    // 4. Render energy particles along edges
    for (const p of this.particles) {
      p.progress += p.speed;
      if (p.progress >= 1.0) p.progress = 0;

      const edge = this.edges[p.edgeIndex];
      if (!edge) continue;
      const s = nodeMap.get(edge.source);
      const t = nodeMap.get(edge.target);
      if (!s || !t || !s.proj || !t.proj) continue;

      const px = s.proj.x + (t.proj.x - s.proj.x) * p.progress;
      const py = s.proj.y + (t.proj.y - s.proj.y) * p.progress;

      ctx.beginPath();
      ctx.arc(px, py, edge.is_blast_path ? 3.0 : 1.6, 0, Math.PI * 2);
      ctx.fillStyle = edge.is_blast_path ? '#ff5722' : 'rgba(226, 168, 101, 0.7)';
      ctx.fill();
    }

    // 5. Sort nodes by Z-depth for proper occlusion
    const sortedNodes = [...this.nodes].filter(n => n.proj).sort((a, b) => b.proj.z - a.proj.z);

    // 6. Render nodes
    for (const node of sortedNodes) {
      this.renderNode(node);
    }
  }

  renderReferenceGrid() {
    const ctx = this.ctx;
    const layers = [
      { z: 110, label: 'API LAYER', color: 'rgba(56, 189, 248, 0.12)' },
      { z: 20, label: 'LOGIC & CALL GRAPH', color: 'rgba(234, 179, 8, 0.08)' },
      { z: -110, label: 'VERIFICATION & TESTS', color: 'rgba(52, 211, 153, 0.10)' },
    ];

    for (const lay of layers) {
      const p1 = this.project3D(-260, -180, lay.z);
      const p2 = this.project3D(260, -180, lay.z);
      const p3 = this.project3D(260, 180, lay.z);
      const p4 = this.project3D(-260, 180, lay.z);

      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.lineTo(p3.x, p3.y);
      ctx.lineTo(p4.x, p4.y);
      ctx.closePath();
      ctx.strokeStyle = lay.color;
      ctx.lineWidth = 1;
      ctx.stroke();

      // Layer annotation
      ctx.fillStyle = lay.color.replace('0.12', '0.4').replace('0.08', '0.4').replace('0.10', '0.4');
      ctx.font = '9px JetBrains Mono, monospace';
      ctx.fillText(lay.label, p1.x + 8, p1.y + 14);
    }
  }

  renderNode(node) {
    const ctx = this.ctx;
    const p = node.proj;
    const isDirect = node.is_direct_target;
    const isAffected = node.is_affected;
    const isHovered = this.hoveredNode === node;

    // Filter check
    if (this.activeFilter !== 'all') {
      if (this.activeFilter === 'affected' && !isAffected) return;
      if (this.activeFilter === 'api' && node.type !== 'api_endpoint') return;
      if (this.activeFilter === 'test' && node.type !== 'test') return;
      if (this.activeFilter === 'function' && node.type !== 'function') return;
    }

    const baseRadius = node.type === 'module' ? 8 : (node.type === 'api_endpoint' ? 9 : 6);
    const radius = Math.max(3, baseRadius * p.scale);

    // Color mapping
    let fillColor = '#ab9c94';
    let strokeColor = 'rgba(255, 255, 255, 0.3)';

    if (node.type === 'api_endpoint') {
      fillColor = '#38bdf8'; // Cyan
    } else if (node.type === 'test') {
      fillColor = '#34d399'; // Emerald
    } else if (node.type === 'function') {
      fillColor = '#eab308'; // Amber
    } else if (node.type === 'module') {
      fillColor = '#a855f7'; // Purple
    }

    // Blast radius override
    if (isDirect) {
      fillColor = '#ff2a2a'; // Fire Red
      strokeColor = '#ffffff';
    } else if (isAffected) {
      fillColor = '#ff7a00'; // High-voltage orange
      strokeColor = '#ffc107';
    }

    // Pulsing halo for direct target
    if (isDirect) {
      ctx.beginPath();
      ctx.arc(p.x, p.y, radius * 2.2, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255, 42, 42, 0.25)';
      ctx.fill();

      ctx.beginPath();
      ctx.arc(p.x, p.y, radius * 3.4, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(255, 80, 40, 0.45)';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    // Node body
    ctx.beginPath();
    ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
    ctx.fillStyle = fillColor;
    ctx.fill();
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = isHovered || isDirect ? 2.5 : 1.2;
    ctx.stroke();

    // Node label for APIs, Direct Targets, or Hovered items
    if (isHovered || isDirect || p.scale > 0.85 || node.type === 'api_endpoint') {
      ctx.fillStyle = isDirect ? '#ff4d4d' : (isAffected ? '#ffa142' : '#f0e6df');
      ctx.font = `${Math.max(10, Math.round(11 * p.scale))}px Plus Jakarta Sans, sans-serif`;
      ctx.fillText(node.name, p.x + radius + 6, p.y + 4);
    }
  }

  resetView() {
    this.rotX = 0.45;
    this.rotY = -0.55;
    this.zoom = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.autoRotate = true;
  }
}

window.CodebaseDigitalTwinVisualizer = CodebaseDigitalTwinVisualizer;
