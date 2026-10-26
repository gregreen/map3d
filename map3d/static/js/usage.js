// Adds a "select" button to each highlighted code block.
(function () {
  "use strict";

  function selectNode(node) {
    const range = document.createRange();
    range.selectNodeContents(node);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  }

  function addButtons() {
    document.querySelectorAll(".add-click-select").forEach((container) => {
      const codeBlock = container.querySelector(".highlight");
      if (!codeBlock || container.querySelector(".click-select")) {
        return;
      }

      const button = document.createElement("button");
      button.type = "button";
      button.className = "click-select";
      button.textContent = "select";
      button.setAttribute("aria-label", "Select this code block");

      button.addEventListener("click", async () => {
        const pre = codeBlock.querySelector("pre") || codeBlock;
        selectNode(pre);
        try {
          await navigator.clipboard.writeText(pre.innerText);
          button.textContent = "copied";
        } catch {
          button.textContent = "selected";
        }
        window.setTimeout(() => {
          button.textContent = "select";
        }, 1600);
      });

      container.appendChild(button);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", addButtons);
  } else {
    addButtons();
  }
})();
