document.addEventListener("DOMContentLoaded", () => {
  const bar = document.getElementById("budget-bar");
  if (!bar) return;

  const widthPercent = parseFloat(bar.style.width);
  if (widthPercent > 75) {
    bar.classList.add("green");
  } else if (widthPercent > 30) {
    bar.classList.add("yellow");
  } else if (widthPercent > 10) {
    bar.classList.add("red");
  } else {
    bar.classList.add("critical");
  }
});
