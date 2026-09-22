/* QR-код без внешних библиотек.
 *
 * Поддерживаются версии 1–6 и уровень коррекции M — этого с запасом хватает
 * на адрес страницы (до 108 байт). Версии выше 6 требуют блока версии,
 * а он здесь не нужен.
 *
 * Ссылка на спецификацию: ISO/IEC 18004. Пользоваться просто:
 *     var matrix = CourseQR.matrix("https://example.com");
 *     CourseQR.render(element, "https://example.com");
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.CourseQR = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // ---------- арифметика поля Галуа GF(256) ----------
  var EXP = new Array(512);
  var LOG = new Array(256);
  (function () {
    var x = 1;
    for (var i = 0; i < 255; i++) {
      EXP[i] = x;
      LOG[x] = i;
      x <<= 1;
      if (x & 0x100) x ^= 0x11d; // порождающий многочлен QR
    }
    for (var j = 255; j < 512; j++) EXP[j] = EXP[j - 255];
  })();

  function gfMul(a, b) {
    if (a === 0 || b === 0) return 0;
    return EXP[LOG[a] + LOG[b]];
  }

  /* Многочлен-генератор для нужного числа байт коррекции.
   *
   * Умножение накапливает коэффициенты от младшей степени к старшей,
   * а деление ниже работает со старшим коэффициентом первым — поэтому
   * перед возвратом порядок переворачивается. Перепутать порядок легко,
   * и тогда QR собирается, но не читается ни одним сканером.
   */
  function generator(degree) {
    var poly = [1];
    for (var i = 0; i < degree; i++) {
      var next = new Array(poly.length + 1).fill(0);
      for (var j = 0; j < poly.length; j++) {
        next[j] ^= gfMul(poly[j], EXP[i]);
        next[j + 1] ^= poly[j];
      }
      poly = next;
    }
    return poly.reverse();
  }

  /* Остаток от деления — это и есть байты коррекции. */
  function remainder(data, ecLength) {
    var gen = generator(ecLength);
    var result = data.concat(new Array(ecLength).fill(0));
    for (var i = 0; i < data.length; i++) {
      var factor = result[i];
      if (factor === 0) continue;
      for (var j = 0; j < gen.length; j++) {
        result[i + j] ^= gfMul(gen[j], factor);
      }
    }
    return result.slice(data.length);
  }

  // ---------- таблицы версий (уровень M) ----------
  // [байт данных, байт коррекции на блок, блоков]
  var VERSIONS = {
    1: [16, 10, 1],
    2: [28, 16, 1],
    3: [44, 26, 1],
    4: [64, 18, 2],
    5: [86, 24, 2],
    6: [108, 16, 4]
  };
  var ALIGNMENT = { 1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34] };

  // ---------- сборка потока данных ----------
  function utf8(text) {
    var bytes = [];
    for (var i = 0; i < text.length; i++) {
      var code = text.charCodeAt(i);
      if (code < 0x80) bytes.push(code);
      else if (code < 0x800) {
        bytes.push(0xc0 | (code >> 6), 0x80 | (code & 0x3f));
      } else {
        bytes.push(0xe0 | (code >> 12), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f));
      }
    }
    return bytes;
  }

  function pickVersion(byteCount) {
    for (var version = 1; version <= 6; version++) {
      var capacity = VERSIONS[version][0] * 8;
      if (4 + 8 + byteCount * 8 <= capacity) return version;
    }
    return null;
  }

  function buildCodewords(bytes, version) {
    var bits = [];
    function push(value, length) {
      for (var i = length - 1; i >= 0; i--) bits.push((value >> i) & 1);
    }

    push(0b0100, 4); // байтовый режим
    push(bytes.length, 8); // для версий 1–9 счётчик занимает 8 бит
    for (var i = 0; i < bytes.length; i++) push(bytes[i], 8);

    var capacity = VERSIONS[version][0] * 8;
    for (var t = 0; t < 4 && bits.length < capacity; t++) bits.push(0); // терминатор
    while (bits.length % 8 !== 0) bits.push(0);

    var codewords = [];
    for (var b = 0; b < bits.length; b += 8) {
      var value = 0;
      for (var k = 0; k < 8; k++) value = (value << 1) | bits[b + k];
      codewords.push(value);
    }
    var pad = [0xec, 0x11];
    var index = 0;
    while (codewords.length < VERSIONS[version][0]) {
      codewords.push(pad[index % 2]);
      index++;
    }

    // блоки и коррекция
    var perBlock = VERSIONS[version][0] / VERSIONS[version][2];
    var ecLength = VERSIONS[version][1];
    var blocks = [];
    var ecBlocks = [];
    for (var n = 0; n < VERSIONS[version][2]; n++) {
      var chunk = codewords.slice(n * perBlock, (n + 1) * perBlock);
      blocks.push(chunk);
      ecBlocks.push(remainder(chunk, ecLength));
    }

    // чередование: сначала данные по столбцам, потом коррекция
    var result = [];
    for (var c = 0; c < perBlock; c++) {
      for (var bi = 0; bi < blocks.length; bi++) result.push(blocks[bi][c]);
    }
    for (var e = 0; e < ecLength; e++) {
      for (var bj = 0; bj < ecBlocks.length; bj++) result.push(ecBlocks[bj][e]);
    }
    return result;
  }

  // ---------- матрица ----------
  function createMatrix(version, codewords) {
    var size = version * 4 + 17;
    var modules = [];
    var reserved = [];
    for (var i = 0; i < size; i++) {
      modules.push(new Array(size).fill(false));
      reserved.push(new Array(size).fill(false));
    }

    function set(row, col, dark) {
      modules[row][col] = dark;
      reserved[row][col] = true;
    }

    // узоры поиска и разделители
    function finder(row, col) {
      for (var r = -1; r <= 7; r++) {
        for (var c = -1; c <= 7; c++) {
          var rr = row + r;
          var cc = col + c;
          if (rr < 0 || rr >= size || cc < 0 || cc >= size) continue;
          var edge = r === -1 || r === 7 || c === -1 || c === 7;
          var ring = r === 0 || r === 6 || c === 0 || c === 6;
          var core = r >= 2 && r <= 4 && c >= 2 && c <= 4;
          set(rr, cc, !edge && (ring || core));
        }
      }
    }
    finder(0, 0);
    finder(0, size - 7);
    finder(size - 7, 0);

    // тактовые линии
    for (var t = 8; t < size - 8; t++) {
      var dark = t % 2 === 0;
      set(6, t, dark);
      set(t, 6, dark);
    }

    // узоры выравнивания
    var positions = ALIGNMENT[version] || [];
    for (var a = 0; a < positions.length; a++) {
      for (var b2 = 0; b2 < positions.length; b2++) {
        var pr = positions[a];
        var pc = positions[b2];
        if ((pr === 6 && pc === 6) || (pr === 6 && pc === size - 7) || (pr === size - 7 && pc === 6)) continue;
        for (var r2 = -2; r2 <= 2; r2++) {
          for (var c2 = -2; c2 <= 2; c2++) {
            var chebyshev = Math.max(Math.abs(r2), Math.abs(c2));
            set(pr + r2, pc + c2, chebyshev !== 1);
          }
        }
      }
    }

    // места под формат и тёмный модуль
    for (var f = 0; f <= 8; f++) {
      if (!reserved[8][f]) set(8, f, false);
      if (!reserved[f][8]) set(f, 8, false);
    }
    for (var g = 0; g < 8; g++) {
      if (!reserved[8][size - 1 - g]) set(8, size - 1 - g, false);
      if (!reserved[size - 1 - g][8]) set(size - 1 - g, 8, false);
    }
    set(size - 8, 8, true); // всегда тёмный

    // данные зигзагом: два столбца справа налево
    var bitIndex = 0;
    var totalBits = codewords.length * 8;
    for (var right = size - 1; right >= 1; right -= 2) {
      if (right === 6) right = 5;
      for (var vert = 0; vert < size; vert++) {
        for (var j = 0; j < 2; j++) {
          var x = right - j;
          var upward = ((right + 1) & 2) === 0;
          var y = upward ? size - 1 - vert : vert;
          if (reserved[y][x] || bitIndex >= totalBits) continue;
          var byte = codewords[bitIndex >> 3];
          modules[y][x] = ((byte >> (7 - (bitIndex & 7))) & 1) === 1;
          bitIndex++;
        }
      }
    }
    return { modules: modules, reserved: reserved, size: size };
  }

  var MASKS = [
    function (x, y) { return (x + y) % 2 === 0; },
    function (x, y) { return y % 2 === 0; },
    function (x, y) { return x % 3 === 0; },
    function (x, y) { return (x + y) % 3 === 0; },
    function (x, y) { return (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0; },
    function (x, y) { return ((x * y) % 2) + ((x * y) % 3) === 0; },
    function (x, y) { return (((x * y) % 2) + ((x * y) % 3)) % 2 === 0; },
    function (x, y) { return (((x + y) % 2) + ((x * y) % 3)) % 2 === 0; }
  ];

  function applyMask(matrix, reserved, size, maskIndex) {
    var result = matrix.map(function (row) { return row.slice(); });
    for (var y = 0; y < size; y++) {
      for (var x = 0; x < size; x++) {
        if (reserved[y][x]) continue;
        if (MASKS[maskIndex](x, y)) result[y][x] = !result[y][x];
      }
    }
    return result;
  }

  function penalty(matrix, size) {
    var score = 0;
    var x, y, run, dark = 0;

    function runsLine(get) {
      var total = 0;
      for (var i = 0; i < size; i++) {
        var current = get(0, i);
        var length = 1;
        for (var j = 1; j < size; j++) {
          var value = get(j, i);
          if (value === current) length++;
          else {
            if (length >= 5) total += 3 + (length - 5);
            current = value;
            length = 1;
          }
        }
        if (length >= 5) total += 3 + (length - 5);
      }
      return total;
    }
    score += runsLine(function (i, j) { return matrix[j][i]; }); // строки
    score += runsLine(function (i, j) { return matrix[i][j]; }); // столбцы

    for (y = 0; y < size - 1; y++) {
      for (x = 0; x < size - 1; x++) {
        var v = matrix[y][x];
        if (v === matrix[y][x + 1] && v === matrix[y + 1][x] && v === matrix[y + 1][x + 1]) score += 3;
      }
    }

    var patternA = [true, false, true, true, true, false, true, false, false, false, false];
    var patternB = [false, false, false, false, true, false, true, true, true, false, true];
    function hasPattern(get, at) {
      for (var p = 0; p < 11; p++) {
        if (get(at + p) !== patternA[p]) break;
        if (p === 10) return true;
      }
      for (var q = 0; q < 11; q++) {
        if (get(at + q) !== patternB[q]) break;
        if (q === 10) return true;
      }
      return false;
    }
    for (y = 0; y < size; y++) {
      for (x = 0; x <= size - 11; x++) {
        if (hasPattern(function (i) { return matrix[y][i]; }, x)) score += 40;
        if (hasPattern(function (i) { return matrix[i][y]; }, x)) score += 40;
      }
    }

    for (y = 0; y < size; y++) for (x = 0; x < size; x++) if (matrix[y][x]) dark++;
    var percent = (dark * 100) / (size * size);
    score += 10 * Math.floor(Math.abs(percent - 50) / 5);
    return score;
  }

  function formatBits(maskIndex) {
    var data = (0b00 << 3) | maskIndex; // 00 — уровень коррекции M
    var value = data << 10;
    for (var i = 14; i >= 10; i--) {
      if (((value >> i) & 1) === 1) value ^= 0x537 << (i - 10);
    }
    return ((data << 10) | value) ^ 0x5412;
  }

  function writeFormat(matrix, size, maskIndex) {
    var bits = formatBits(maskIndex);
    function bit(i) { return ((bits >> i) & 1) === 1; }

    for (var i = 0; i <= 5; i++) matrix[i][8] = bit(i);
    matrix[7][8] = bit(6);
    matrix[8][8] = bit(7);
    matrix[8][7] = bit(8);
    for (var j = 9; j < 15; j++) matrix[8][14 - j] = bit(j);

    for (var k = 0; k < 8; k++) matrix[8][size - 1 - k] = bit(k);
    for (var m = 8; m < 15; m++) matrix[size - 15 + m][8] = bit(m);
    matrix[size - 8][8] = true;
  }

  function matrix(text) {
    var bytes = utf8(text);
    var version = pickVersion(bytes.length);
    if (version === null) return null; // слишком длинный адрес — QR не рисуем

    var codewords = buildCodewords(bytes, version);
    var built = createMatrix(version, codewords);

    var best = null;
    var bestScore = Infinity;
    for (var maskIndex = 0; maskIndex < 8; maskIndex++) {
      var candidate = applyMask(built.modules, built.reserved, built.size, maskIndex);
      writeFormat(candidate, built.size, maskIndex);
      var score = penalty(candidate, built.size);
      if (score < bestScore) {
        bestScore = score;
        best = candidate;
      }
    }
    return best;
  }

  function render(element, text, options) {
    options = options || {};
    var cells = matrix(text);
    if (!cells) return false;

    var size = cells.length;
    var quiet = options.quiet == null ? 2 : options.quiet;
    var total = size + quiet * 2;
    var scale = options.scale || Math.max(2, Math.floor(160 / total));
    var canvas = document.createElement("canvas");
    canvas.width = total * scale;
    canvas.height = total * scale;
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", "QR-код со ссылкой на эту страницу");

    // canvas может быть недоступен (старый браузер, отключённая графика,
    // тестовое окружение) — тогда просто тихо не рисуем QR.
    var context = canvas.getContext && canvas.getContext("2d");
    if (!context) return false;

    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = "#000000";
    for (var y = 0; y < size; y++) {
      for (var x = 0; x < size; x++) {
        if (cells[y][x]) {
          context.fillRect((x + quiet) * scale, (y + quiet) * scale, scale, scale);
        }
      }
    }

    element.innerHTML = "";
    element.appendChild(canvas);
    return true;
  }

  return { matrix: matrix, render: render };
});
