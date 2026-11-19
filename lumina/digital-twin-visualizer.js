/**
 * Codebase Digital Twin: Humanly-Readable 3D Architecture & Blast Radius Visualizer
 * Designed specifically for Lumina's warm luxury glassmorphic aesthetic.
 *
 * Provides isometric architectural tiers, tactile glass capsule cards,
 * dynamic dependency illumination, and pre-patch blast radius simulation.
 */

class CodebaseDigitalTwinVisualizer {
  constructor(canvasEl, options = {}) {
    this.canvas = canvasEl;
    this.ctx = this.canvas.getContext('2d');
    this.options = options;

    // 3D Camera & Projection: gentle isometric angle
    this.rotX = 0.35;
    this.rotY = -0.42;
    this.zoom = 1.0;
    this.panX = 0;
    this.panY = -12;
    this.autoRotate = true;

    // Interaction state
    this.isDragging = false;
    this.dragStartX = 0;
    this.dragStartY = 0;
    this.lastMouseX = 0;
    this.lastMouseY = 0;
    this.hasMovedSignificantly = false;

    this.hoveredNode = null;
    this.selectedNode = null;

    // Data
    this.nodes = [];
    this.edges = [];
    this.blastData = null;
    this.activeFilter = 'all';

    // Particle flow animation along dependencies
    this.particles = [];
    this.animFrameId = null;

    this.initCanvasSize();
    this.bindEvents();
    this.startRenderLoop();
  }

  initCanvasSize() {
    const parent = this.canvas.parentElement;
    const rect = parent ? parent.getBoundingClientRect() : { width: 800, height: 480 };
    const dpr = window.devicePixelRatio || 1;
    this.width = rect.width > 50 ? rect.width : 800;
    this.height = rect.height > 50 ? rect.height : (this.options.defaultHeight || 480);

    this.canvas.width = this.width * dpr;
    this.canvas.height = this.height * dpr;
    this.ctx.setTransform(1, 0, 0, 1, 0, 0);
    this.ctx.scale(dpr, dpr);
  }

  setData(data) {
    if (!data) return;
    this.nodes = (data.nodes || []).map(n => ({ ...n }));
    this.edges = (data.edges || []).map(e => ({ ...e }));
    this.blastData = data.blast_radius || null;

    this.layoutNodesHumanly();
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

  /**
   * Arranges nodes into humanly readable architectural tiers:
   * Left: Public Ingress APIs (Sky Blue)
   * Center: Core Logic Functions & Blast Target (Amber & Crimson)
   * Right: Subsystem Modules (Cognac Gold)
   * Bottom: Verification Tests (Emerald)
   */
  layoutNodesHumanly() {
    const apis = this.nodes.filter(n => n.type === 'api_endpoint');
    const funcs = this.nodes.filter(n => n.type === 'function');
    const modules = this.nodes.filter(n => n.type === 'module');
    const tests = this.nodes.filter(n => n.type === 'test');

    // 1. APIs on the left ingress tier (X: -240 to -200)
    apis.forEach((item, i) => {
      const count = Math.max(1, apis.length);
      const ySpread = 220;
      const yStep = count > 1 ? ySpread / (count - 1) : 0;
      item.x3d = -240 + (i % 2) * 35;
      item.y3d = -ySpread / 2 + i * yStep;
      item.z3d = 40 - i * 15;
    });

    // 2. Core Functions in center midfield (X: -70 to +110)
    funcs.forEach((item, i) => {
      const count = Math.max(1, funcs.length);
      const row = i % 3;
      const col = Math.floor(i / 3);
      item.x3d = -70 + col * 90;
      item.y3d = -90 + row * 85 + (col % 2 === 1 ? 28 : 0);
      item.z3d = 10 - row * 20;
    });

    // 3. Modules on the right infrastructure tier (X: +220 to +260)
    modules.forEach((item, i) => {
      const count = Math.max(1, modules.length);
      const ySpread = 200;
      const yStep = count > 1 ? ySpread / (count - 1) : 0;
      item.x3d = 230 - (i % 2) * 30;
      item.y3d = -ySpread / 2 + i * yStep;
      item.z3d = -20 - i * 15;
    });

    // 4. Tests on the bottom verification tier (Y: +145 to +195)
    tests.forEach((item, i) => {
      const count = Math.max(1, tests.length);
      const xSpread = 340;
      const xStep = count > 1 ? xSpread / (count - 1) : 0;
      item.x3d = -xSpread / 2 + i * xStep;
      item.y3d = 150 + (i % 2) * 25;
      item.z3d = -40 + i * 15;
    });
  }

  initParticles() {
    this.particles = [];
    const count = Math.min(28, Math.max(8, this.edges.length * 2));
    for (let i = 0; i < count; i++) {
      this.particles.push({
        edgeIndex: Math.floor(Math.random() * Math.max(1, this.edges.length)),
        progress: Math.random(),
        speed: 0.0035 + Math.random() * 0.005,
      });
    }
  }

  project3D(x, y, z) {
    const cosY = Math.cos(this.rotY);
    const sinY = Math.sin(this.rotY);
    const x1 = x * cosY - z * sinY;
    const z1 = z * cosY + x * sinY;

    const cosX = Math.cos(this.rotX);
    const sinX = Math.sin(this.rotX);
    const y2 = y * cosX - z1 * sinX;
    const z2 = z1 * cosX + y * sinX;

    const fov = 420 * this.zoom;
    const distance = 480 - z2;
    const scale = distance > 10 ? fov / distance : 0.1;

    const screenX = this.width / 2 + this.panX + x1 * scale;
    const screenY = this.height / 2 + this.panY + y2 * scale;

    return { x: screenX, y: screenY, scale, z: z2 };
  }

  bindEvents() {
    window.addEventListener('resize', () => this.initCanvasSize());

    this.canvas.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.dragStartX = e.clientX;
      this.dragStartY = e.clientY;
      this.lastMouseX = e.clientX;
      this.lastMouseY = e.clientY;
      this.hasMovedSignificantly = false;
      this.canvas.style.cursor = 'grabbing';
    });

    window.addEventListener('mouseup', (e) => {
      if (this.isDragging) {
        this.isDragging = false;
        this.canvas.style.cursor = this.hoveredNode ? 'pointer' : 'grab';
      }
    });

    this.canvas.addEventListener('click', (e) => {
      if (!this.hasMovedSignificantly) {
        if (this.hoveredNode) {
          this.selectedNode = this.selectedNode === this.hoveredNode ? null : this.hoveredNode;
          if (this.options.onSelect) {
            this.options.onSelect(this.selectedNode);
          }
        } else {
          this.selectedNode = null;
        }
      }
    });

    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      if (this.isDragging) {
        const dx = e.clientX - this.lastMouseX;
        const dy = e.clientY - this.lastMouseY;
        if (Math.hypot(e.clientX - this.dragStartX, e.clientY - this.dragStartY) > 5) {
          this.hasMovedSignificantly = true;
          this.autoRotate = false;
        }
        this.rotY += dx * 0.006;
        this.rotX += dy * 0.006;
        this.rotX = Math.max(-0.85, Math.min(0.85, this.rotX));
        this.lastMouseX = e.clientX;
        this.lastMouseY = e.clientY;
      } else {
        this.checkHover(mouseX, mouseY);
      }
    });

    this.canvas.addEventListener('mouseleave', () => {
      this.hoveredNode = null;
      if (this.options.onHover) {
        this.options.onHover(null, 0, 0);
      }
    });

    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.07 : 0.93;
      this.zoom = Math.max(0.55, Math.min(1.85, this.zoom * zoomFactor));
    }, { passive: false });
  }

  checkHover(mouseX, mouseY) {
    let hit = null;

    // Check capsules in reverse z-index order (front-to-back)
    for (let i = this.nodes.length - 1; i >= 0; i--) {
      const node = this.nodes[i];
      if (!node.bounds) continue;
      const b = node.bounds;
      if (mouseX >= b.x && mouseX <= b.x + b.w && mouseY >= b.y && mouseY <= b.y + b.h) {
        hit = node;
        break;
      }
    }

    // Proximity fallback
    if (!hit) {
      let minD = 24;
      for (const node of this.nodes) {
        if (!node.proj) continue;
        const d = Math.hypot(node.proj.x - mouseX, node.proj.y - mouseY);
        if (d < minD) {
          hit = node;
          minD = d;
        }
      }
    }

    if (hit !== this.hoveredNode) {
      this.hoveredNode = hit;
      this.canvas.style.cursor = hit ? 'pointer' : (this.isDragging ? 'grabbing' : 'grab');
      if (this.options.onHover) {
        this.options.onHover(hit, mouseX, mouseY);
      }
    }
  }

  startRenderLoop() {
    const loop = () => {
      if (this.autoRotate && !this.isDragging) {
        this.rotY += 0.0014;
      }
      this.render();
      this.animFrameId = requestAnimationFrame(loop);
    };
    loop();
  }

  render() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.width, this.height);

    // 1. Draw subtle luxury ambient background
    this.renderAmbientGrid();

    // 2. Project all nodes into 3D camera
    const nodeMap = new Map();
    for (const node of this.nodes) {
      if (node.x3d === undefined) continue;
      node.proj = this.project3D(node.x3d, node.y3d, node.z3d);
      nodeMap.set(node.id, node);
    }

    // 3. Render connection edges
    this.renderEdges(nodeMap);

    // 4. Render energy particles along call paths
    this.renderParticles(nodeMap);

    // 5. Sort nodes by Z-depth for proper visual layering
    const sortedNodes = [...this.nodes].filter(n => n.proj).sort((a, b) => b.proj.z - a.proj.z);

    // 6. Render humanly-readable capsules
    for (const node of sortedNodes) {
      this.renderCapsuleNode(node);
    }
  }

  renderAmbientGrid() {
    const ctx = this.ctx;
    // Elegant warm vignette matching Lumina obsidian background
    const grad = ctx.createRadialGradient(
      this.width / 2, this.height / 2, 40,
      this.width / 2, this.height / 2, Math.max(this.width, this.height) * 0.7
    );
    grad.addColorStop(0, 'rgba(32, 26, 22, 0.48)');
    grad.addColorStop(1, 'rgba(14, 11, 10, 0.92)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, this.width, this.height);

    // Subtle champagne coordinate reference plane
    const p1 = this.project3D(-280, 160, -80);
    const p2 = this.project3D(280, 160, -80);
    const p3 = this.project3D(280, -180, 60);
    const p4 = this.project3D(-280, -180, 60);

    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.lineTo(p3.x, p3.y);
    ctx.lineTo(p4.x, p4.y);
    ctx.closePath();
    ctx.strokeStyle = 'rgba(194, 131, 64, 0.08)';
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  renderEdges(nodeMap) {
    const ctx = this.ctx;
    const isSimulated = this.blastData && this.blastData.total_affected > 0;

    for (const edge of this.edges) {
      const s = nodeMap.get(edge.source);
      const t = nodeMap.get(edge.target);
      if (!s || !t || !s.proj || !t.proj) continue;

      const isBlast = edge.is_blast_path;
      const isSelectedConn = this.selectedNode && (edge.source === this.selectedNode.id || edge.target === this.selectedNode.id);
      const isHoveredConn = this.hoveredNode && (edge.source === this.hoveredNode.id || edge.target === this.hoveredNode.id);

      ctx.beginPath();
      const midX = (s.proj.x + t.proj.x) / 2;
      const midY = (s.proj.y + t.proj.y) / 2 - 14;
      ctx.moveTo(s.proj.x, s.proj.y);
      ctx.quadraticCurveTo(midX, midY, t.proj.x, t.proj.y);

      if (isBlast) {
        ctx.strokeStyle = '#e05244'; // Rich crimson
        ctx.lineWidth = 2.4;
        ctx.shadowColor = 'rgba(224, 82, 68, 0.55)';
        ctx.shadowBlur = 8;
      } else if (isSelectedConn || isHoveredConn) {
        ctx.strokeStyle = '#e2a865'; // Glowing cognac
        ctx.lineWidth = 2.2;
        ctx.shadowColor = 'rgba(226, 168, 101, 0.65)';
        ctx.shadowBlur = 6;
      } else {
        ctx.strokeStyle = isSimulated ? 'rgba(194, 131, 64, 0.08)' : 'rgba(194, 131, 64, 0.20)';
        ctx.lineWidth = 1.1;
        ctx.shadowBlur = 0;
      }
      ctx.stroke();
      ctx.shadowBlur = 0;
    }
  }

  renderParticles(nodeMap) {
    const ctx = this.ctx;
    for (const p of this.particles) {
      p.progress += p.speed;
      if (p.progress >= 1.0) p.progress = 0;

      const edge = this.edges[p.edgeIndex];
      if (!edge) continue;
      const s = nodeMap.get(edge.source);
      const t = nodeMap.get(edge.target);
      if (!s || !t || !s.proj || !t.proj) continue;

      const midX = (s.proj.x + t.proj.x) / 2;
      const midY = (s.proj.y + t.proj.y) / 2 - 14;

      const tVal = p.progress;
      const px = (1 - tVal) * (1 - tVal) * s.proj.x + 2 * (1 - tVal) * tVal * midX + tVal * tVal * t.proj.x;
      const py = (1 - tVal) * (1 - tVal) * s.proj.y + 2 * (1 - tVal) * tVal * midY + tVal * tVal * t.proj.y;

      ctx.beginPath();
      ctx.arc(px, py, edge.is_blast_path ? 2.6 : 1.7, 0, Math.PI * 2);
      ctx.fillStyle = edge.is_blast_path ? '#e05244' : 'rgba(226, 168, 101, 0.70)';
      ctx.fill();
    }
  }

  /**
   * Renders a humanly-readable, tactile glass capsule for each component.
   * Completely eliminates text collision by giving every component an isolated capsule card.
   */
  renderCapsuleNode(node) {
    const ctx = this.ctx;
    const p = node.proj;
    const isDirect = node.is_direct_target;
    const isAffected = node.is_affected;
    const isHovered = this.hoveredNode === node;
    const isSelected = this.selectedNode === node;
    const isSimulated = this.blastData && this.blastData.total_affected > 0;

    // Filter check
    if (this.activeFilter !== 'all') {
      if (this.activeFilter === 'affected' && !isAffected) return;
      if (this.activeFilter === 'api' && node.type !== 'api_endpoint') return;
      if (this.activeFilter === 'test' && node.type !== 'test') return;
      if (this.activeFilter === 'function' && node.type !== 'function') return;
    }

    // Lumina warm luxury palette
    let badgeColor = '#c28340'; // Warm gold default
    let typeLabel = 'FUNC';

    if (node.type === 'api_endpoint') {
      badgeColor = '#6db1d4'; // Soft Sky Blue
      typeLabel = 'API';
    } else if (node.type === 'test') {
      badgeColor = '#52c27c'; // Soft Emerald
      typeLabel = 'TEST';
    } else if (node.type === 'module') {
      badgeColor = '#e2a865'; // Warm Cognac Gold
      typeLabel = 'MOD';
    }

    // Blast state overrides
    if (isDirect) {
      badgeColor = '#e05244'; // Rich Crimson
      typeLabel = 'TARGET';
    } else if (isAffected) {
      badgeColor = '#e5a93b'; // Vibrant Amber
      typeLabel = 'IMPACT';
    }

    // Clean humanly-shortened display name
    let cleanName = node.name;
    if (cleanName.length > 21) {
      cleanName = cleanName.substring(0, 19) + '…';
    }

    ctx.font = '500 11.5px Plus Jakarta Sans, system-ui, sans-serif';
    const textMetrics = ctx.measureText(cleanName);
    const capsuleWidth = Math.max(78, textMetrics.width + 44);
    const capsuleHeight = 26;

    const x = p.x - capsuleWidth / 2;
    const y = p.y - capsuleHeight / 2;

    // Record capsule bounding box for accurate mouse clicks/hovers
    node.bounds = { x, y, w: capsuleWidth, h: capsuleHeight };

    // Glowing halo for direct patch target
    if (isDirect) {
      ctx.beginPath();
      this.drawRoundedRect(ctx, x - 6, y - 6, capsuleWidth + 12, capsuleHeight + 12, 14);
      ctx.fillStyle = 'rgba(224, 82, 68, 0.22)';
      ctx.fill();

      ctx.beginPath();
      this.drawRoundedRect(ctx, x - 12, y - 12, capsuleWidth + 24, capsuleHeight + 24, 18);
      ctx.strokeStyle = 'rgba(224, 82, 68, 0.35)';
      ctx.lineWidth = 1.2;
      ctx.stroke();
    }

    // Capsule Backdrop
    ctx.beginPath();
    this.drawRoundedRect(ctx, x, y, capsuleWidth, capsuleHeight, 8);

    // Warm dark glass fill
    let bgFill = 'rgba(24, 20, 18, 0.94)';
    if (isSimulated && !isAffected && !isDirect) {
      bgFill = 'rgba(20, 17, 15, 0.40)'; // Dim unaffected items
    } else if (isDirect) {
      bgFill = 'rgba(48, 22, 18, 0.98)';
    } else if (isSelected || isHovered) {
      bgFill = 'rgba(42, 33, 28, 0.98)';
    }

    ctx.fillStyle = bgFill;
    ctx.fill();

    // Border
    let borderColor = 'rgba(255, 255, 255, 0.12)';
    if (isDirect) {
      borderColor = '#e05244';
    } else if (isAffected) {
      borderColor = '#e5a93b';
    } else if (isSelected || isHovered) {
      borderColor = '#e2a865';
    }
    ctx.strokeStyle = borderColor;
    ctx.lineWidth = isDirect || isSelected || isHovered ? 1.8 : 1.0;
    ctx.stroke();

    // Type indicator dot
    ctx.beginPath();
    ctx.arc(x + 12, y + capsuleHeight / 2, 4.2, 0, Math.PI * 2);
    ctx.fillStyle = badgeColor;
    ctx.fill();

    // Label Text
    ctx.fillStyle = (isSimulated && !isAffected && !isDirect) ? '#7d7069' : '#f7efe8';
    ctx.fillText(cleanName, x + 24, y + 17);

    // JetBrains Mono Type pill
    ctx.font = '700 8.5px JetBrains Mono, monospace';
    ctx.fillStyle = badgeColor;
    ctx.fillText(typeLabel, x + capsuleWidth - 36, y + 16);
  }

  drawRoundedRect(ctx, x, y, width, height, radius) {
    ctx.moveTo(x + radius, y);
    ctx.arcTo(x + width, y, x + width, y + height, radius);
    ctx.arcTo(x + width, y + height, x, y + height, radius);
    ctx.arcTo(x, y + height, x, y, radius);
    ctx.arcTo(x, y, x + width, y, radius);
    ctx.closePath();
  }

  resetView() {
    this.rotX = 0.35;
    this.rotY = -0.42;
    this.zoom = 1.0;
    this.panX = 0;
    this.panY = -12;
    this.autoRotate = true;
    this.selectedNode = null;
  }
}

window.CodebaseDigitalTwinVisualizer = CodebaseDigitalTwinVisualizer;
