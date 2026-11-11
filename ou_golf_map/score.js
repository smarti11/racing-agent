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

  /**
   * Scorecard yards adjusted for the rise from the tee to the green.
   * One yard is added for every three feet uphill, and one yard is
   * subtracted for every three feet downhill.
   */
  function playsLike(yards, teeFt, greenFt) {
    var y = typeof yards === "number" ? yards : parseInt(yards, 10);
    var tee = typeof teeFt === "number" ? teeFt : parseFloat(teeFt);
    var green = typeof greenFt === "number" ? greenFt : parseFloat(greenFt);
    if (!isFinite(y) || !isFinite(tee) || !isFinite(green)) return null;
    var deltaFt = Math.round(green - tee);
    var adjusted = Math.round(y + deltaFt / 3);
    if (adjusted < 1) adjusted = 1;
    return { yards: adjusted, deltaFt: deltaFt, flat: y };
  }

  function formatPlaysLike(info) {
    if (!info) return "";
    var hill = "level";
    if (info.deltaFt > 1) hill = info.deltaFt + " ft up";
    else if (info.deltaFt < -1) hill = Math.abs(info.deltaFt) + " ft down";
    return "plays " + info.yards + " · " + hill;
  }

  function holeValue(bag, n) {
    if (!bag) return null;
    if (bag[n] != null) return bag[n];
    if (bag[String(n)] != null) return bag[String(n)];
    return null;
  }

  function summaryLine(label, summary) {
    if (!summary || summary.counted === 0) return label + ": not scored";
    return label + ": " + formatStrokes(summary);
  }

  /**
   * Plain-text card a phone can store in Files or Notes.
   * Missing holes stay listed so a front nine still reads in order.
   */
  function scorecardText(courseName, scores, pars, dateLabel, details) {
    var lines = [String(courseName || "Score")];
    if (dateLabel) lines.push(String(dateLabel));
    if (details && details.heading) lines.push(String(details.heading));
    lines.push("");
    for (var n = 1; n <= 18; n += 1) {
      if (n === 10) lines.push("");
      var par = holeValue(pars, n);
      var strokes = holeValue(scores, n);
      var info = details && details.holes ? holeValue(details.holes, n) : null;
      var extra = "";
      if (info && info.hcp != null) extra += "  Hcp " + info.hcp;
      if (info && info.yards != null) {
        extra += "  " + (info.teeName || "Tee") + " " + info.yards;
        if (info.plays != null) extra += "  plays " + info.plays;
      }
      lines.push(
        "Hole " +
          n +
          "  Par " +
          (par == null ? "—" : par) +
          "  " +
          (strokes == null ? "not scored" : strokes) +
          extra
      );
    }
    lines.push("");
    lines.push(summaryLine("Out", nineSummary(scores, pars, 1, 9)));
    lines.push(summaryLine("In", nineSummary(scores, pars, 10, 18)));
    lines.push(summaryLine("18 holes", nineSummary(scores, pars, 1, 18)));
    lines.push("");
    lines.push("Saved from OU Golf Map on this phone.");
    return lines.join("\n");
  }

  function scorecardFilename(courseName, date) {
    var when = date instanceof Date ? date : new Date();
    var y = when.getFullYear();
    var m = String(when.getMonth() + 1);
    var d = String(when.getDate());
    if (m.length < 2) m = "0" + m;
    if (d.length < 2) d = "0" + d;
    var slug = String(courseName || "score")
      .replace(/&/g, " and ")
      .replace(/[^a-zA-Z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
    return (slug || "score") + "-" + y + "-" + m + "-" + d + ".txt";
  }

  return {
    clampStrokes: clampStrokes,
    parseSpokenScore: parseSpokenScore,
    nineSummary: nineSummary,
    formatToPar: formatToPar,
    formatStrokes: formatStrokes,
    playsLike: playsLike,
    formatPlaysLike: formatPlaysLike,
    scorecardText: scorecardText,
    scorecardFilename: scorecardFilename,
  };
});
