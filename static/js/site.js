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

