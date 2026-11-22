/* Live prices. The numbers come from the page (web/pricing.py), so the server and this script never disagree.
   The server re-prices every request on its own; this is only what the visitor sees while choosing. */
(function () {
  "use strict";
  var rulesEl = document.getElementById("rules");
  var R = rulesEl ? JSON.parse(rulesEl.textContent) : null;
  var fmt0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  var fmt2 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
  function money(n) { return Math.round(n) === n ? fmt0.format(n) : fmt2.format(n); }

  function estimate(style, guests, addons, extraHours) {
    var s = R.styles[style] || R.styles.truck;
    guests = Math.max(0, Math.min(parseInt(guests, 10) || 0, R.maxGuests));
    extraHours = Math.max(0, parseInt(extraHours, 10) || 0);
    var perPerson = s.rate;
    addons.forEach(function (k) { if (R.addons[k]) perPerson += R.addons[k].rate; });
    var food = perPerson * guests;
    var minApplies = food < s.minimum;
    var billed = minApplies ? s.minimum : food;
    var hours = extraHours * R.extraHour;
    var total = billed + hours;
    var deposit = Math.round(total * R.depositPct * 100) / 100;
    var sugs = [];
    if (minApplies && guests) {
      Object.keys(R.addons).forEach(function (k) {
        if (addons.indexOf(k) !== -1) return;
        var extra = Math.max(0, food + R.addons[k].rate * guests - s.minimum);
        sugs.push({ key: k, name: R.addons[k].name, extra: extra, free: extra === 0 });
      });
      sugs.sort(function (a, b) { return a.extra - b.extra || R.addons[b.key].rate - R.addons[a.key].rate; });
    }
    return { s: s, guests: guests, perPerson: perPerson, food: food, minApplies: minApplies, billed: billed,
             hours: hours, extraHours: extraHours, total: total, deposit: deposit, sugs: sugs };
  }

  function checkedStyle(scope) {
    var el = scope.querySelector('input[name="style"]:checked');
    return el ? el.value : "truck";
  }

  /* Home page ticket */
  var quick = document.getElementById("quick");
  if (quick && R) {
    var range = document.getElementById("qg"), out = document.getElementById("qg-out");
    var totalEl = document.getElementById("q-total"), noteEl = document.getElementById("q-note"), depEl = document.getElementById("q-dep");
    var runQuick = function () {
      var e = estimate(checkedStyle(quick), range.value, [], 0);
      out.textContent = e.guests;
      totalEl.textContent = money(e.total);
      if (e.minApplies) {
        var free = e.sugs.filter(function (x) { return x.free; });
        noteEl.innerHTML = "That's our " + e.s.name + " minimum." +
          (free.length ? " You could add <strong>" + free[0].name.toLowerCase() + "</strong> for no extra cost." : "");
      } else {
        noteEl.textContent = money(e.perPerson) + " a guest, " + e.s.hours + " hours of serving.";
      }
      depEl.textContent = money(e.deposit) + " holds your date. The rest is due a week before.";
    };
    quick.addEventListener("input", runQuick);
    runQuick();
  }

  /* Catering form + side ticket */
  var form = document.getElementById("cform");
  if (form && R) {
    var lines = document.getElementById("est-lines"), total = document.getElementById("est-total");
    var note = document.getElementById("est-note"), sugList = document.getElementById("est-sugs"), dep = document.getElementById("est-dep");
    var guestsIn = form.querySelector('[name="guests"]'), hoursIn = form.querySelector('[name="extra_hours"]');
    var dateIn = form.querySelector('[name="event_date"]');

    var addonsPicked = function () {
      return Array.prototype.map.call(form.querySelectorAll('input[name="addons"]:checked'), function (x) { return x.value; });
    };
    var row = function (label, value, cls) {
      return "<dt" + (cls ? ' class="' + cls + '"' : "") + ">" + label + "</dt><dd" + (cls ? ' class="' + cls + '"' : "") + ">" + value + "</dd>";
    };
    var run = function () {
      var picked = addonsPicked();
      var e = estimate(checkedStyle(form), guestsIn.value, picked, hoursIn.value);
      var html = row(e.s.name, money(e.s.rate) + " &times; " + e.guests);
      picked.forEach(function (k) { html += row(R.addons[k].name, money(R.addons[k].rate) + " &times; " + e.guests); });
      if (e.minApplies) html += row("Minimum for " + e.s.name, money(e.s.minimum), "min");
      if (e.extraHours) html += row("Extra time", e.extraHours + " hr &times; " + money(R.extraHour));
      lines.innerHTML = html;
      total.textContent = money(e.total);
      note.textContent = e.guests ? (e.s.hours + e.extraHours) + " hours of serving. Setup and cleanup don't count." : "Enter your guest count.";
      sugList.innerHTML = "";
      e.sugs.slice(0, 3).forEach(function (sg) {
        var li = document.createElement("li"), b = document.createElement("button");
        b.type = "button";
        b.textContent = sg.free ? "Add " + sg.name.toLowerCase() + " at no extra cost" : "Add " + sg.name.toLowerCase() + " for " + money(sg.extra) + " more";
        b.addEventListener("click", function () {
          var box = form.querySelector('input[name="addons"][value="' + sg.key + '"]');
          if (box) { box.checked = true; run(); }
        });
        li.appendChild(b); sugList.appendChild(li);
      });
      var due = "";
      if (dateIn && dateIn.value) {
        var d = new Date(dateIn.value + "T12:00:00");
        d.setDate(d.getDate() - R.balanceDays);
        due = " on " + d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
      }
      dep.textContent = money(e.deposit) + " down holds the date. " + money(e.total - e.deposit) + " is due" + (due || " 7 days before") + ".";
    };
    form.addEventListener("input", run);
    form.addEventListener("change", run);
    run();

    /* Tell them right away if the Bus is already booked that day */
    var warn = document.getElementById("datewarn");
    if (dateIn && warn && window.DATE_CHECK_URL) {
      dateIn.addEventListener("change", function () {
        warn.hidden = true;
        if (!dateIn.value) return;
        fetch(window.DATE_CHECK_URL + "?date=" + encodeURIComponent(dateIn.value))
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (j) { if (j && j.booked) warn.hidden = false; })
          .catch(function () {});
      });
    }

    /* Only ask about tasting days when they want a tasting */
    var tasting = form.querySelector('[name="wants_tasting"]'), when = document.getElementById("tastingwhen");
    if (tasting && when) {
      var sync = function () { when.hidden = !tasting.checked; };
      tasting.addEventListener("change", sync); sync();
    }
  }

  /* Fundraising calculator */
  var fund = document.getElementById("fund");
  if (fund) {
    var F = JSON.parse(fund.textContent);
    var sel = document.getElementById("c-sellers"), each = document.getElementById("c-each");
    var calc = function () {
      document.getElementById("c-sellers-out").textContent = sel.value;
      document.getElementById("c-each-out").textContent = each.value;
      var raised = sel.value * each.value * F.avg * F.share / 100;
      document.getElementById("c-total").textContent = fmt0.format(Math.round(raised));
    };
    sel.addEventListener("input", calc); each.addEventListener("input", calc); calc();
  }
})();
