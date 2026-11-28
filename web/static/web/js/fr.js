/* Fundraiser screens: +/- quantity buttons with a running total, and "Copy link" buttons. */
(function () {
  "use strict";
  var money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
  document.querySelectorAll("[data-grid]").forEach(function (grid) {
    var inputs = grid.querySelectorAll("input[data-price]");
    var count = grid.querySelector("[data-count]"), sum = grid.querySelector("[data-sum]");
    function total() {
      var n = 0, s = 0;
      inputs.forEach(function (i) {
        var q = Math.max(0, Math.min(50, parseInt(i.value, 10) || 0));
        n += q; s += q * parseFloat(i.dataset.price);
        i.closest(".qty").classList.toggle("qty--on", q > 0);
      });
      count.textContent = n + (n === 1 ? " pizza" : " pizzas");
      sum.textContent = money.format(s);
    }
    grid.addEventListener("click", function (e) {
      var b = e.target.closest("[data-step]");
      if (!b) return;
      var i = b.parentNode.querySelector("input");
      i.value = Math.max(0, Math.min(50, (parseInt(i.value, 10) || 0) + parseInt(b.dataset.step, 10))) || "";
      total();
    });
    grid.addEventListener("input", total);
    total();
  });
  document.querySelectorAll("[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () {
      var text = b.dataset.copy, label = b.textContent;
      var done = function () { b.textContent = "Copied!"; setTimeout(function () { b.textContent = label; }, 1600); };
      if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () { window.prompt("Copy this:", text); });
      else window.prompt("Copy this:", text);
    });
  });
  document.querySelectorAll("[data-preset-subject]").forEach(function (b) {
    b.addEventListener("click", function () {
      var subj = document.getElementById("msg_subject"), body = document.getElementById("msg_body");
      if (body.value.trim() && !window.confirm("Replace what you've written?")) return;
      subj.value = b.dataset.presetSubject; body.value = b.dataset.presetMessage; body.focus();
    });
  });
})();
