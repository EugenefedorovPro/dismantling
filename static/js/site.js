// Keyboard enhancement for the title page. Normal links work without JavaScript.
const names = Array.from(document.querySelectorAll(".index-name"));

names.forEach((name) => {
  name.addEventListener("keydown", (event) => {
    const visualOrder = Array.from(document.querySelectorAll(".index-name"));
    const index = visualOrder.indexOf(name);
    if (event.key === "ArrowDown" || event.key === "ArrowRight") {
      event.preventDefault();
      visualOrder[(index + 1) % visualOrder.length].focus();
    } else if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
      event.preventDefault();
      visualOrder[(index - 1 + visualOrder.length) % visualOrder.length].focus();
    }
  });
});

// A small particle animation for mouse hover. The real link text remains in
// the DOM for accessibility, and links work normally without JavaScript.
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const activeEffects = new WeakMap();

function resetDisintegration(link) {
  const effect = activeEffects.get(link);
  if (effect) {
    cancelAnimationFrame(effect.frame);
    effect.canvas.remove();
    activeEffects.delete(link);
  }
  link.classList.remove("is-disintegrating");
}

function stopDisintegration(link) {
  if (activeEffects.get(link)?.navigating) return;
  resetDisintegration(link);
}

function disintegrate(link, onFinished = null) {
  if (reducedMotion.matches) return false;
  const currentEffect = activeEffects.get(link);
  if (currentEffect) {
    if (onFinished) {
      currentEffect.navigating = true;
      currentEffect.onFinished = onFinished;
      if (currentEffect.completed) onFinished();
    }
    return true;
  }

  const label = link.querySelector(".index-name-text");
  if (!label) return false;

  const bounds = label.getBoundingClientRect();
  const width = Math.ceil(bounds.width);
  const height = Math.ceil(bounds.height);
  if (!width || !height) return false;

  // Render the exact visible name onto an offscreen canvas, then sample its
  // opaque pixels. The display canvas only paints the sampled dust particles.
  const sample = document.createElement("canvas");
  sample.width = width;
  sample.height = height;
  const source = sample.getContext("2d", { willReadFrequently: true });
  if (!source) return false;

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
  if (!context) return false;
  context.scale(scale, scale);
  context.fillStyle = style.color;

  link.append(canvas);
  link.classList.add("is-disintegrating");

  const effect = {
    canvas,
    frame: 0,
    navigating: Boolean(onFinished),
    onFinished,
    completed: false,
  };
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
    if (progress < 1) {
      effect.frame = requestAnimationFrame(animate);
    } else {
      effect.completed = true;
      if (effect.onFinished) effect.onFinished();
    }
  }

  effect.frame = requestAnimationFrame(animate);
  return true;
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

// On phones, a tap plays the complete disintegration before opening the poem.
const mobileMode = window.matchMedia("(max-width: 760px)");
let navigationPending = false;

names.forEach((link) => {
  link.addEventListener("click", (event) => {
    if (
      !mobileMode.matches || reducedMotion.matches || event.defaultPrevented ||
      event.button !== 0 || event.metaKey || event.ctrlKey ||
      event.shiftKey || event.altKey
    ) return;

    event.preventDefault();
    if (navigationPending) return;
    navigationPending = true;
    const href = link.href;
    const started = disintegrate(link, () => window.location.assign(href));
    if (!started) window.location.assign(href);
  });
});

// The layout and reading order are deterministic, and CSS distributes the
// names across the available space. Restore links after back/forward navigation.
window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    navigationPending = false;
    names.forEach(resetDisintegration);
  }
});
