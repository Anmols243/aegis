/* BackgroundPixelStars — vanilla JS port of the 16-bit pixel starfield.
   Retro 16 FPS canvas: twinkling pixel stars on a grid + occasional
   shooting stars with fading trails. Runs against <canvas id="pixelstars">.
   (Ported from background-pixel-stars.tsx; no dependencies.) */
(() => {
  "use strict";

  // 16-bit color palette (reduced color options)
  const STAR_COLORS = [
    "#FFFFFF", // White
    "#FFFFAA", // Light yellow
    "#AAAAFF", // Light blue
    "#FFAAAA", // Light red
    "#AAFFAA", // Light green
    "#FFAAFF", // Light purple
    "#AAFFFF", // Light cyan
  ];

  // Configuration constants
  const starDensity = 0.00004; // Reduced density for larger stars
  const twinkleProbability = 0.7;
  const minTwinkleSpeed = 2;
  const maxTwinkleSpeed = 4;
  const pixelSize = 5;
  const starRegenerationInterval = 5000; // ms between partial regenerations
  const percentToRegenerate = 0.15;

  // Shooting star configuration
  const shootingStarPixelSize = 2;
  const targetFps = 16; // 16 FPS for that retro feel
  const frameInterval = 1000 / targetFps;

  const canvas = document.getElementById("pixelstars");
  if (!canvas) return;

  const bgStars = [];
  let shootingStars = [];
  let lastRender = 0;

  function makeStar(w, h) {
    const twinkle = Math.random() < twinkleProbability;
    const base = Math.random() * 0.5 + 0.5;
    return {
      x: Math.floor(Math.random() * (w / pixelSize)) * pixelSize,
      y: Math.floor(Math.random() * (h / pixelSize)) * pixelSize,
      color: STAR_COLORS[(Math.random() * STAR_COLORS.length) | 0],
      baseOpacity: base,
      currentOpacity: base,
      twinkle: twinkle,
      twinkleSpeed: minTwinkleSpeed + Math.random() * (maxTwinkleSpeed - minTwinkleSpeed),
      twinkleDirection: -1, // -1 fading out, 1 fading in
      twinkleTimer: 0,
    };
  }

  function initStars() {
    bgStars.length = 0;
    const n = Math.floor(canvas.width * canvas.height * starDensity);
    for (let i = 0; i < n; i++) bgStars.push(makeStar(canvas.width, canvas.height));
  }

  function regenStars() {
    if (!bgStars.length) return;
    const n = Math.max(1, Math.floor(bgStars.length * percentToRegenerate));
    for (let i = 0; i < n; i++) {
      bgStars[(Math.random() * bgStars.length) | 0] = makeStar(canvas.width, canvas.height);
    }
  }

  function randomStart() {
    // Start from anywhere along the top edge, angled 45-135 degrees
    // (90 = straight down, 45 = down-right, 135 = down-left)
    return { x: Math.random() * window.innerWidth, y: 0, angle: 45 + Math.random() * 90 };
  }

  function newShootingStar() {
    const s = randomStart();
    return {
      id: Date.now() + Math.random(),
      x: s.x, y: s.y, angle: s.angle, scale: 1,
      speed: Math.random() * 5 + 8,
      distance: 0,
      trail: [],
    };
  }

  function animate(ts) {
    // Skip frames to hold the retro 16 FPS cadence
    if (ts - lastRender < frameInterval) {
      requestAnimationFrame(animate);
      return;
    }
    lastRender = ts;

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      requestAnimationFrame(animate);
      return;
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 1. Draw and update background stars
    for (const st of bgStars) {
      ctx.fillStyle = st.color;
      ctx.globalAlpha = st.currentOpacity;
      ctx.fillRect(st.x, st.y, pixelSize, pixelSize);
      if (st.twinkle) {
        st.twinkleTimer += 1 / targetFps;
        if (st.twinkleTimer >= st.twinkleSpeed) {
          st.twinkleTimer = 0;
          st.twinkleDirection *= -1;
        }
        const p = st.twinkleTimer / st.twinkleSpeed;
        st.currentOpacity = p < 0.5
          ? (st.twinkleDirection < 0 ? st.baseOpacity : st.baseOpacity * 0.3)
          : (st.twinkleDirection < 0 ? st.baseOpacity * 0.3 : st.baseOpacity);
      }
    }
    ctx.globalAlpha = 1;

    // 2. Update shooting stars
    if (shootingStars.length) {
      shootingStars = shootingStars
        .map((st) => {
          const nx = st.x + st.speed * Math.cos((st.angle * Math.PI) / 180);
          const ny = st.y + st.speed * Math.sin((st.angle * Math.PI) / 180);
          const nd = st.distance + st.speed;
          const trail = st.trail.slice();
          if (nd % 8 < st.speed) trail.push({ x: st.x, y: st.y, opacity: 1.0 }); // pixelated trail
          const upd = trail
            .map((pt) => ({ x: pt.x, y: pt.y, opacity: pt.opacity - 0.1 }))
            .filter((pt) => pt.opacity > 0);
          return { ...st, x: nx, y: ny, distance: nd, trail: upd };
        })
        .filter(
          (st) =>
            st.x >= -30 && st.x <= window.innerWidth + 30 &&
            st.y >= -30 && st.y <= window.innerHeight + 30
        );

      // 3. Draw shooting stars
      for (const st of shootingStars) {
        for (const pt of st.trail) {
          ctx.save();
          ctx.translate(pt.x, pt.y);
          ctx.rotate((st.angle * Math.PI) / 180);
          ctx.translate(-pt.x, -pt.y);
          ctx.fillStyle = "rgba(180, 242, 255, " + pt.opacity.toFixed(3) + ")";
          ctx.fillRect(pt.x, pt.y, shootingStarPixelSize, shootingStarPixelSize);
          ctx.restore();
        }
        // Pixelated star head: 4x2 block with two corners knocked out
        ctx.save();
        ctx.translate(st.x, st.y);
        ctx.rotate((st.angle * Math.PI) / 180);
        ctx.translate(-st.x, -st.y);
        ctx.fillStyle = "#ffffff";
        ctx.globalAlpha = 1.0;
        for (let y = 0; y < 2; y++) {
          for (let x = 0; x < 4; x++) {
            if ((x === 0 && y === 1) || (x === 3 && y === 0)) continue;
            ctx.fillRect(
              st.x + x * shootingStarPixelSize,
              st.y + y * shootingStarPixelSize,
              shootingStarPixelSize,
              shootingStarPixelSize
            );
          }
        }
        ctx.restore();
      }
      ctx.globalAlpha = 1;
    }

    requestAnimationFrame(animate);
  }

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    initStars();
  }

  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  initStars();
  requestAnimationFrame(animate);

  // A new shooting star every 2-6 seconds
  (function spawn() {
    shootingStars = shootingStars.concat([newShootingStar()]);
    setTimeout(spawn, Math.random() * 4000 + 2000);
  })();

  setInterval(regenStars, starRegenerationInterval);
  window.addEventListener("resize", resize);
})();
