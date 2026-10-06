/* SonarGrid — vanilla JS port of the 21st.dev sonar-grid.tsx component.
   A dot field that answers clicks with expanding rings, plus ambient pings.
   Runs against <canvas id="sonargrid">, colored by the canvas's CSS `color`
   (var(--lime) in live.html). Idles when no ring is alive, pauses in hidden
   tabs, and renders a still grid under prefers-reduced-motion. No dependencies. */
(() => {
  "use strict";

  // Configuration (same defaults as the React component)
  const spacing = 26;          // distance between dots, CSS px
  const dotRadius = 1.4;       // dot radius at rest, CSS px
  const baseOpacity = 0.18;    // resting dot opacity; wavefront dots go to 1
  const pingEvery = 2.4;       // seconds between ambient pings (0 disables)
  const speed = 260;           // wavefront speed, CSS px per second
  const ringWidth = 90;        // wavefront thickness, CSS px
  const amplitude = 2.2;       // dot growth at the wave peak
  const maxRings = 6;          // older rings dropped first
  const pingArea = [0.15, 0.2, 0.85, 0.8]; // ambient spawn box, fractions [x0, y0, x1, y1]

  const MAX_DPR = 2;
  const TAU = Math.PI * 2;

  const canvas = document.getElementById("sonargrid");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let rings = [];
  let width = 0;
  let height = 0;
  let raf = 0;
  let timer = 0;
  let fill = getComputedStyle(canvas).color;
  let nextPing = performance.now() + pingEvery * 1000;

  function addRing(x, y, born) {
    rings.push({ x: x, y: y, born: born });
    while (rings.length > maxRings) rings.shift();
  }

  function draw(now) {
    const lifetime = (Math.hypot(width, height) + ringWidth) / speed; // seconds until a ring leaves the canvas
    rings = rings.filter((r) => (now - r.born) / 1000 < lifetime);
    const live = rings.map((r) => {
      const age = (now - r.born) / 1000;
      const radius = age * speed;
      return { x: r.x, y: r.y, radius: radius, reach: radius + ringWidth, fade: 1 - age / lifetime };
    });

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = fill;

    const cols = Math.ceil(width / spacing) + 1;
    const rows = Math.ceil(height / spacing) + 1;
    const offsetX = (width - (cols - 1) * spacing) / 2;
    const offsetY = (height - (rows - 1) * spacing) / 2;

    // Pass 1: every resting dot in a single path and a single fill.
    const hot = [];
    ctx.globalAlpha = baseOpacity;
    ctx.beginPath();
    for (let i = 0; i < cols; i++) {
      const cx = offsetX + i * spacing;
      for (let j = 0; j < rows; j++) {
        const cy = offsetY + j * spacing;
        let energy = 0;
        for (const r of live) {
          if (Math.abs(cx - r.x) > r.reach || Math.abs(cy - r.y) > r.reach) continue;
          const dist = Math.abs(Math.hypot(cx - r.x, cy - r.y) - r.radius);
          if (dist >= ringWidth) continue;
          const t = 1 - dist / ringWidth;
          const k = t * t * (3 - 2 * t) * r.fade; // smoothstep, fading with age
          if (k > energy) energy = k;
        }
        if (energy < 0.01) {
          ctx.moveTo(cx + dotRadius, cy);
          ctx.arc(cx, cy, dotRadius, 0, TAU);
        } else {
          hot.push(cx, cy, energy);
        }
      }
    }
    ctx.fill();

    // Pass 2: only the dots on a wavefront get their own alpha and radius.
    for (let k = 0; k < hot.length; k += 3) {
      const energy = hot[k + 2];
      ctx.globalAlpha = baseOpacity + (1 - baseOpacity) * energy;
      ctx.beginPath();
      ctx.arc(hot[k], hot[k + 1], dotRadius * (1 + amplitude * energy), 0, TAU);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function resize() {
    width = Math.max(1, window.innerWidth);
    height = Math.max(1, window.innerHeight);
    const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw(performance.now());
  }

  function scheduleIdle(delay) {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => tick(performance.now()), Math.max(16, delay));
  }

  function tick(now) {
    raf = 0;
    if (document.hidden) return;
    if (reduceMotion.matches) {
      rings = [];
      draw(now);
      return;
    }
    if (pingEvery > 0 && now >= nextPing) {
      const [x0, y0, x1, y1] = pingArea;
      addRing(width * (x0 + Math.random() * (x1 - x0)), height * (y0 + Math.random() * (y1 - y0)), now);
      nextPing = now + pingEvery * 1000;
    }
    draw(now);
    if (rings.length > 0) raf = requestAnimationFrame(tick);
    else if (pingEvery > 0) scheduleIdle(nextPing - now);
  }

  function wake() {
    if (!raf) {
      window.clearTimeout(timer);
      raf = requestAnimationFrame(tick);
    }
  }

  resize();
  // One ring already mid-expansion so the first paint shows the idea.
  if (!reduceMotion.matches) {
    const [x0, y0, x1, y1] = pingArea;
    addRing(width * (x0 + (x1 - x0) * 0.68), height * (y0 + (y1 - y0) * 0.34), performance.now() - 500);
  }

  // The canvas is fixed and pointer-events:none, so listen on the document.
  // Clicks on controls (buttons, links, inputs, rows) don't ping.
  document.addEventListener("pointerdown", (e) => {
    if (reduceMotion.matches) return;
    if (e.target.closest && e.target.closest("button, a, input, select, textarea, [role=button], .card, tr")) return;
    addRing(e.clientX, e.clientY, performance.now());
    wake();
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) wake();
  });
  reduceMotion.addEventListener("change", wake);
  window.addEventListener("resize", resize);
  wake();
})();
