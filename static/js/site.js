// Keyboard enhancement for the title page. Normal links work without JavaScript.
const names = Array.from(document.querySelectorAll(".index-name"));

names.forEach((name, index) => {
  name.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowRight") {
      event.preventDefault();
      names[(index + 1) % names.length].focus();
    } else if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
      event.preventDefault();
      names[(index - 1 + names.length) % names.length].focus();
    }
  });
});

// A small particle animation for mouse hover. The real link text remains in
// the DOM for accessibility, and links work normally without JavaScript.
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const activeEffects = new WeakMap();

function stopDisintegration(link) {
  const effect = activeEffects.get(link);
  if (!effect) return;

  cancelAnimationFrame(effect.frame);
  effect.canvas.remove();
  link.classList.remove("is-disintegrating");
  activeEffects.delete(link);
}

function disintegrate(link) {
  if (reducedMotion.matches || activeEffects.has(link)) return;

  const label = link.querySelector(".index-name-text");
  if (!label) return;

  const bounds = label.getBoundingClientRect();
  const width = Math.ceil(bounds.width);
  const height = Math.ceil(bounds.height);
  if (!width || !height) return;

  // Render the exact visible name onto an offscreen canvas, then sample its
  // opaque pixels. The display canvas only paints the sampled dust particles.
  const sample = document.createElement("canvas");
  sample.width = width;
  sample.height = height;
  const source = sample.getContext("2d", { willReadFrequently: true });
  if (!source) return;

  const style = getComputedStyle(label);
  source.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
  source.textBaseline = "middle";
  source.fillStyle = style.color;
  source.fillText(label.textContent.trim(), 0, height / 2);

  const pixels = source.getImageData(0, 0, width, height).data;
  const particles = [];
  const spacing = 3;

  for (let y = 0; y < height; y += spacing) {
    for (let x = 0; x < width; x += spacing) {
      if (pixels[(y * width + x) * 4 + 3] < 120) continue;
      particles.push({
        x, y,
        dx: (Math.random() - .2) * 32,
        dy: (Math.random() - .65) * 26,
        delay: Math.random() * .3,
      });
    }
  }

  const canvas = document.createElement("canvas");
  canvas.className = "index-name-particles";
  const scale = Math.min(window.devicePixelRatio || 1, 2);
  const overhang = 32;
  canvas.width = Math.ceil((width + overhang * 2) * scale);
  canvas.height = Math.ceil((height + overhang * 2) * scale);
  canvas.style.width = `${width + overhang * 2}px`;
  canvas.style.height = `${height + overhang * 2}px`;

  const linkBounds = link.getBoundingClientRect();
  canvas.style.left = `${bounds.left - linkBounds.left - overhang}px`;
  canvas.style.top = `${bounds.top - linkBounds.top - overhang}px`;
  const context = canvas.getContext("2d");
  if (!context) return;
  context.scale(scale, scale);
  context.fillStyle = style.color;

  link.append(canvas);
  link.classList.add("is-disintegrating");

  const effect = { canvas, frame: 0 };
  activeEffects.set(link, effect);
  let start;

  function animate(timestamp) {
    if (start === undefined) start = timestamp;
    const progress = Math.min((timestamp - start) / 850, 1);
    context.clearRect(0, 0, width + overhang * 2, height + overhang * 2);

    for (const particle of particles) {
      const fraction = Math.max(0, (progress - particle.delay) / (1 - particle.delay));
      context.globalAlpha = (1 - fraction) ** 1.6;
      context.fillRect(
        particle.x + overhang + particle.dx * fraction,
        particle.y + overhang + particle.dy * fraction,
        spacing - .4,
        spacing - .4,
      );
    }

    context.globalAlpha = 1;
    if (progress < 1) effect.frame = requestAnimationFrame(animate);
  }

  effect.frame = requestAnimationFrame(animate);
}

names.forEach((link) => {
  link.addEventListener("pointerenter", (event) => {
    if (event.pointerType === "mouse" || event.pointerType === "pen") {
      disintegrate(link);
    }
  });
  link.addEventListener("pointerleave", () => stopDisintegration(link));
});

reducedMotion.addEventListener("change", () => {
  if (reducedMotion.matches) names.forEach(stopDisintegration);
});

// Each visit gets a new composition. Place names at random coordinates while
// keeping them inside the page and separated from each other.
const nameGrid = document.querySelector(".name-grid");

function scatterPositions(items, width, height, padding, gap) {
  const placed = [];
  const positions = new Array(items.length);
  const largestFirst = items
    .map((item, index) => ({ ...item, index }))
    .sort((a, b) => b.width * b.height - a.width * a.height);

  for (const item of largestFirst) {
    const maxX = width - padding - item.width;
    const maxY = height - padding - item.height;
    if (maxX < padding || maxY < padding) return null;

    let position = null;
    for (let attempt = 0; attempt < 1200; attempt += 1) {
      const x = padding + Math.random() * (maxX - padding);
      const y = padding + Math.random() * (maxY - padding);
      const overlaps = placed.some((other) =>
        x < other.x + other.width + gap &&
        x + item.width + gap > other.x &&
        y < other.y + other.height + gap &&
        y + item.height + gap > other.y
      );

      if (!overlaps) {
        position = { x, y, width: item.width, height: item.height };
        break;
      }
    }

    if (!position) return null;
    placed.push(position);
    positions[item.index] = position;
  }

  return positions;
}

let scatterWidth = 0;

function scatterNames() {
  if (!nameGrid || names.length === 0) return;

  names.forEach(stopDisintegration);
  nameGrid.style.visibility = "hidden";
  nameGrid.classList.add("is-scattered");

  const width = nameGrid.clientWidth;
  const padding = width < 600 ? 8 : 16;
  const gap = width < 600 ? 24 : 36;
  const items = names.map((link) => ({
    width: Math.ceil(link.offsetWidth),
    height: Math.ceil(link.offsetHeight),
  }));
  const widest = Math.max(...items.map((item) => item.width));
  const tallest = Math.max(...items.map((item) => item.height));

  const footer = document.querySelector(".site-footer");
  const footerHeight = footer ? footer.offsetHeight : 0;
  const availableHeight = window.innerHeight - nameGrid.getBoundingClientRect().top - footerHeight;
  const namesPerRow = Math.max(1, Math.floor((width - 2 * padding + gap) / (widest + gap)));
  const packingHeight = Math.ceil((names.length / namesPerRow) * (tallest + gap) * 1.7);
  let height = Math.max(320, availableHeight, packingHeight);
  let positions = null;

  // A crowded page grows downwards instead of allowing overlapping links.
  for (let attempt = 0; attempt < 24 && !positions; attempt += 1) {
    positions = scatterPositions(items, width, height, padding, gap);
    if (!positions) height += Math.max(100, tallest + gap);
  }

  if (positions) {
    nameGrid.style.height = `${Math.ceil(height)}px`;
    positions.forEach((position, index) => {
      names[index].style.left = `${position.x}px`;
      names[index].style.top = `${position.y}px`;
    });
    scatterWidth = width;
  } else {
    // Keep a usable, non-overlapping grid if the viewport is exceptionally narrow.
    nameGrid.classList.remove("is-scattered");
    nameGrid.style.height = "";
    names.forEach((link) => {
      link.style.left = "";
      link.style.top = "";
    });
  }

  nameGrid.style.visibility = "";
}

if (nameGrid && names.length) {
  // Wait until font metrics are ready before measuring the link rectangles.
  document.fonts.ready.then(scatterNames);

  let resizeTimer;
  window.addEventListener("resize", () => {
    if (Math.abs(nameGrid.clientWidth - scatterWidth) < 8) return;
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(scatterNames, 120);
  });

  // History navigation can restore a cached page without re-running scripts.
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) scatterNames();
  });
}

