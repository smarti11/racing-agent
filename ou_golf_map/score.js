/* Score parsing and nine-hole totals for the OU Golf Map.
   Loaded in the browser as a plain script and required from Node tests. */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.OUScore = api;
})(typeof self !== "undefined" ? self : this, function () {
  var WORDS = {
    one: 1,
    two: 2,
    three: 3,
    four: 4,
    five: 5,
    six: 6,
    seven: 7,
    eight: 8,
    nine: 9,
    ten: 10,
    eleven: 11,
    twelve: 12,
    thirteen: 13,
    fourteen: 14,
    fifteen: 15,
    sixteen: 16,
    seventeen: 17,
    eighteen: 18,
    nineteen: 19,
    twenty: 20,
  };

  var WORD_RE =
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty";

  function clampStrokes(value) {
    var n = typeof value === "number" ? value : parseInt(String(value).trim(), 10);
    if (!isFinite(n) || Math.round(n) !== n) return null;
    if (n < 1 || n > 20) return null;
    return n;
  }

  function normalize(text) {
    return String(text || "")
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, " ")
      .replace(/-/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function tokenValue(token) {
    if (/^\d{1,2}$/.test(token)) return parseInt(token, 10);
    return Object.prototype.hasOwnProperty.call(WORDS, token) ? WORDS[token] : null;
  }

  function relativeAmount(raw, direction) {
    var re = new RegExp(
      "\\b(?:a|an|" + WORD_RE + "|\\d{1,2})\\s+" + direction + "\\b"
    );
    var match = raw.match(re);
    if (!match) return null;
    var token = match[0].split(/\s+/)[0];
    if (token === "a" || token === "an") return 1;
    return tokenValue(token);
  }

  function resultWord(raw, par) {
    if (par == null) return null;
    var table = [
      [/hole\s+in\s+one|\bace\b/, 1 - par],
      [/double\s+eagle|\balbatross\b/, -3],
      [/\beagle\b/, -2],
      [/\bbirdie\b/, -1],
      [/\beven(?:\s+par)?\b|\bpar\b/, 0],
      [/triple\s+bog(?:ey|ie)/, 3],
      [/double\s+bog(?:ey|ie)/, 2],
      [/\bbog(?:ey|ie)\b/, 1],
    ];
    for (var i = 0; i < table.length; i += 1) {
      if (table[i][0].test(raw)) return clampStrokes(par + table[i][1]);
    }
    return null;
  }

  function lastSpokenNumber(raw) {
    var re = new RegExp("\\b(\\d{1,2}|" + WORD_RE + ")\\b", "g");
    var found = null;
    var match;
    while ((match = re.exec(raw))) {
      var n = tokenValue(match[1]);
      var strokes = clampStrokes(n);
      if (strokes != null) found = strokes;
    }
    return found;
  }

  /**
   * Turn a spoken score into strokes.
   * A plain number wins ("five", "I shot a 6").
   * "one over" / "two under" and birdie, par, bogey use the hole's par.
   */
  function parseSpokenScore(text, par) {
    var raw = normalize(text);
    if (!raw) return null;
    var holePar = typeof par === "number" && par >= 3 && par <= 6 ? par : null;

    var over = relativeAmount(raw, "over");
    if (over != null && holePar != null) return clampStrokes(holePar + over);
    var under = relativeAmount(raw, "under");
    if (under != null && holePar != null) return clampStrokes(holePar - under);

    var spoken = lastSpokenNumber(raw);
    if (spoken != null) return spoken;
    return resultWord(raw, holePar);
  }

  function nineSummary(scores, pars, start, end) {
    var strokes = 0;
    var parSum = 0;
    var counted = 0;
    var parKnown = 0;
    var holes = end - start + 1;
    for (var n = start; n <= end; n += 1) {
      var value = scores ? scores[n] : null;
      if (value == null && scores) value = scores[String(n)];
      if (value == null) continue;
      strokes += value;
      counted += 1;
      var holePar = pars ? pars[n] : null;
      if (holePar == null && pars) holePar = pars[String(n)];
      if (holePar != null) {
        parSum += holePar;
        parKnown += 1;
      }
    }
    var toPar = counted > 0 && parKnown === counted ? strokes - parSum : null;
    return {
      strokes: strokes,
      counted: counted,
      holes: holes,
      parSum: parSum,
      toPar: toPar,
      complete: counted === holes,
    };
  }

  function formatToPar(n) {
    if (n === 0) return "E";
    return n > 0 ? "+" + n : String(n);
  }

  function formatStrokes(summary) {
    if (!summary || summary.counted === 0) return "—";
    var text = String(summary.strokes);
    if (summary.toPar != null) text += " (" + formatToPar(summary.toPar) + ")";
    if (!summary.complete) text += " · " + summary.counted + "/" + summary.holes;
    return text;
  }

  return {
    clampStrokes: clampStrokes,
    parseSpokenScore: parseSpokenScore,
    nineSummary: nineSummary,
    formatToPar: formatToPar,
    formatStrokes: formatStrokes,
  };
});
