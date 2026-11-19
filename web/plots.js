// Mini librería de gráficas en canvas (sin dependencias: el lab puede no tener internet).
const Plot = (() => {
  const C = {
    grid: '#1f2a4d', axis: '#3a4775', text: '#8b96bd', title: '#e6ebff',
    cyan: '#3be0c8', violet: '#9b8cff', amber: '#ffc25c', red: '#ff6b81', green: '#4fe39a', blue: '#5aa8ff',
  };
  const FONT = '11px "JetBrains Mono", ui-monospace, monospace';
  const ro = new ResizeObserver(es => es.forEach(e => {
    const c = e.target.querySelector('canvas');
    if (c && c._draw) c._draw();
  }));

  function setup(cv) {
    if (!cv._observed) { ro.observe(cv.parentElement); cv._observed = true; }
    const dpr = window.devicePixelRatio || 1;
    const w = cv.clientWidth, h = cv.clientHeight;
    cv.width = Math.max(1, w * dpr); cv.height = Math.max(1, h * dpr);
    const g = cv.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    g.font = FONT;
    return { g, w, h, oculto: w < 40 || h < 40 };
  }

  function nice(lo, hi, n = 5) {
    const span = hi - lo || 1;
    const step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const r = step0 / mag;
    const step = (r < 1.5 ? 1 : r < 3 ? 2 : r < 7 ? 5 : 10) * mag;
    const t = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) t.push(+v.toFixed(12));
    return t;
  }
  const fmt = v => {
    const a = Math.abs(v);
    if (a === 0) return '0';
    if (a >= 1e4 || a < 1e-2) return v.toExponential(0).replace('e+', 'e');
    return +v.toFixed(a < 1 ? 2 : a < 10 ? 1 : 0) + '';
  };

  function empty(cv, msg = 'sin datos') {
    cv._draw = () => {
      const { g, w, h, oculto } = setup(cv);
      if (oculto) return;
      g.fillStyle = C.text; g.globalAlpha = .5; g.textAlign = 'center';
      g.fillText(msg, w / 2, h / 2);
    };
    cv._draw();
  }

  // ---------------------------------------------------------------- XY
  function line(cv, o) {
    cv._draw = () => drawLine(cv, o);
    cv._draw();
  }

  function drawLine(cv, o) {
    const { g, w, h, oculto } = setup(cv);
      if (oculto) return;
    const S = o.series.filter(s => s.x && s.x.length);
    if (!S.length) { g.fillStyle = C.text; g.textAlign = 'center'; g.fillText('sin datos', w / 2, h / 2); return; }
    const L = 52, R = 14, T = 12, B = o.xlabel ? 34 : 22;
    const pw = w - L - R, ph = h - T - B;
    const tf = o.logy ? (v => v > 0 ? Math.log10(v) : NaN) : (v => v);
    let xs = [], ys = [];
    S.forEach(s => { s.x.forEach(v => xs.push(v)); s.y.forEach(v => { const t = tf(v); if (isFinite(t)) ys.push(t); }); });
    (o.hlines || []).forEach(l => ys.push(tf(l.y)));
    let [x0, x1] = o.xlim || [Math.min(...xs), Math.max(...xs)];
    let [y0, y1] = o.ylim ? o.ylim.map(tf) : [Math.min(...ys), Math.max(...ys)];
    if (!isFinite(y0)) { y0 = 0; y1 = 1; }
    if (y0 === y1) { y0 -= 1; y1 += 1; }
    if (!o.ylim && !o.logy) { const m = (y1 - y0) * .08; y0 -= m; y1 += m; }
    if (o.logy && !o.ylim) { y0 = Math.floor(y0); y1 = Math.ceil(y1); if (y0 === y1) y0 -= 1; }
    if (x0 === x1) { x0 -= 1; x1 += 1; }
    const X = v => L + (v - x0) / (x1 - x0) * pw;
    const Y = v => T + (1 - (tf(v) - y0) / (y1 - y0)) * ph;

    // grid
    g.strokeStyle = C.grid; g.lineWidth = 1; g.fillStyle = C.text;
    g.textAlign = 'right'; g.textBaseline = 'middle';
    if (o.logy) {
      for (let d = y0; d <= y1; d++) {
        const yy = T + (1 - (d - y0) / (y1 - y0)) * ph;
        g.globalAlpha = 1; g.beginPath(); g.moveTo(L, yy); g.lineTo(L + pw, yy); g.stroke();
        g.fillText('1e' + d, L - 6, yy);
        g.globalAlpha = .35;
        for (let k = 2; k < 10 && d < y1; k++) {
          const y2 = T + (1 - (d + Math.log10(k) - y0) / (y1 - y0)) * ph;
          g.beginPath(); g.moveTo(L, y2); g.lineTo(L + pw, y2); g.stroke();
        }
        g.globalAlpha = 1;
      }
    } else {
      nice(y0, y1, Math.max(2, Math.round(ph / 45))).forEach(v => {
        const yy = T + (1 - (v - y0) / (y1 - y0)) * ph;
        g.beginPath(); g.moveTo(L, yy); g.lineTo(L + pw, yy); g.stroke();
        g.fillText(fmt(v), L - 6, yy);
      });
    }
    g.textAlign = 'center'; g.textBaseline = 'top';
    nice(x0, x1, Math.max(2, Math.round(pw / 80))).forEach(v => {
      const xx = X(v);
      g.beginPath(); g.moveTo(xx, T); g.lineTo(xx, T + ph); g.stroke();
      g.fillText(fmt(v), xx, T + ph + 5);
    });
    g.strokeStyle = C.axis; g.strokeRect(L + .5, T + .5, pw, ph);
    if (o.xlabel) { g.fillStyle = C.text; g.fillText(o.xlabel, L + pw / 2, h - 14); }
    if (o.ylabel) {
      g.save(); g.translate(11, T + ph / 2); g.rotate(-Math.PI / 2); g.textAlign = 'center';
      g.textBaseline = 'middle'; g.fillText(o.ylabel, 0, 0); g.restore();
    }

    g.save(); g.beginPath(); g.rect(L, T, pw, ph); g.clip();
    (o.hlines || []).forEach(l => {
      g.strokeStyle = l.color || C.amber; g.setLineDash([5, 4]); g.lineWidth = 1.2;
      g.beginPath(); g.moveTo(L, Y(l.y)); g.lineTo(L + pw, Y(l.y)); g.stroke(); g.setLineDash([]);
    });
    (o.vlines || []).forEach(l => {
      g.strokeStyle = l.color || C.amber; g.setLineDash([5, 4]); g.lineWidth = 1.2;
      g.beginPath(); g.moveTo(X(l.x), T); g.lineTo(X(l.x), T + ph); g.stroke(); g.setLineDash([]);
      if (l.label) { g.fillStyle = l.color || C.amber; g.textAlign = 'left'; g.textBaseline = 'top'; g.fillText(l.label, X(l.x) + 4, T + 3); }
    });
    S.forEach(s => {
      g.strokeStyle = g.fillStyle = s.color || C.cyan;
      g.lineWidth = s.width || 1.4; g.globalAlpha = s.alpha || 1;
      if (s.dash) g.setLineDash(s.dash);
      if (s.fill) {
        g.beginPath(); g.moveTo(X(s.x[0]), T + ph);
        for (let i = 0; i < s.x.length; i++) g.lineTo(X(s.x[i]), Y(s.y[i]));
        g.lineTo(X(s.x[s.x.length - 1]), T + ph); g.closePath();
        const gr = g.createLinearGradient(0, T, 0, T + ph);
        gr.addColorStop(0, (s.color || C.cyan) + '44'); gr.addColorStop(1, (s.color || C.cyan) + '00');
        g.fillStyle = gr; g.fill(); g.fillStyle = s.color || C.cyan;
      }
      if (s.columns) {
        const bw = Math.max(2, Math.abs(X(s.x[0] + s.columns) - X(s.x[0])) * .9);
        g.globalAlpha = s.alpha || .55;
        for (let i = 0; i < s.x.length; i++) g.fillRect(X(s.x[i]) - bw / 2, Y(s.y[i]), bw, T + ph - Y(s.y[i]));
        g.globalAlpha = 1;
      }
      if (s.stem) {
        g.lineWidth = s.width || 1.4;
        for (let i = 0; i < s.x.length; i++) { g.beginPath(); g.moveTo(X(s.x[i]), T + ph); g.lineTo(X(s.x[i]), Y(s.y[i])); g.stroke();
          g.beginPath(); g.arc(X(s.x[i]), Y(s.y[i]), s.r || 3.5, 0, 7); g.fill(); }
      }
      if (s.err) {
        g.lineWidth = 1.2;
        for (let i = 0; i < s.x.length; i++) {
          const e = s.err[i]; if (!e) continue; const px = X(s.x[i]);
          g.beginPath(); g.moveTo(px, Y(s.y[i] - e)); g.lineTo(px, Y(s.y[i] + e));
          g.moveTo(px - 4, Y(s.y[i] - e)); g.lineTo(px + 4, Y(s.y[i] - e));
          g.moveTo(px - 4, Y(s.y[i] + e)); g.lineTo(px + 4, Y(s.y[i] + e)); g.stroke();
        }
      }
      if (!s.pointsOnly && !s.columns && !s.stem) {
        g.beginPath(); let pen = false;
        for (let i = 0; i < s.x.length; i++) {
          const yv = s.y[i];
          if (yv === null || !isFinite(tf(yv))) { pen = false; continue; }
          const px = X(s.x[i]), py = Y(yv);
          pen ? g.lineTo(px, py) : g.moveTo(px, py); pen = true;
        }
        g.stroke();
      }
      g.setLineDash([]);
      if (s.points || s.pointsOnly) {
        for (let i = 0; i < s.x.length; i++) {
          const yv = s.y[i]; if (yv === null || !isFinite(tf(yv))) continue;
          g.beginPath(); g.arc(X(s.x[i]), Y(yv), s.r || 3.5, 0, 7); g.fill();
        }
      }
      g.globalAlpha = 1;
    });
    g.restore();

    // leyenda
    const leg = S.filter(s => s.label);
    if (leg.length) {
      g.textAlign = 'left'; g.textBaseline = 'middle';
      let lx = L + 10, ly = T + 12;
      const wbox = Math.max(...leg.map(s => g.measureText(s.label).width)) + 34;
      if (o.legendRight !== false) lx = L + pw - wbox - 8;
      g.fillStyle = '#0a0f1dcc'; g.strokeStyle = C.grid;
      g.beginPath(); g.roundRect(lx - 6, ly - 10, wbox + 4, leg.length * 18 + 4, 6); g.fill(); g.stroke();
      leg.forEach((s, i) => {
        g.fillStyle = g.strokeStyle = s.color || C.cyan; g.lineWidth = 2;
        if (s.dash) g.setLineDash(s.dash);
        g.beginPath(); g.moveTo(lx, ly + i * 18); g.lineTo(lx + 18, ly + i * 18); g.stroke(); g.setLineDash([]);
        g.fillStyle = C.text; g.fillText(s.label, lx + 24, ly + i * 18);
      });
    }
  }

  // ---------------------------------------------------------------- constelación
  function iq(cv, d, o = {}) {
    cv._draw = () => {
      const { g, w, h, oculto } = setup(cv);
      if (oculto) return;
      const s = Math.min(w, h), P = 8, cx = w / 2, cy = h / 2;
      if (!d || !d.i || !d.i.length) { g.fillStyle = C.text; g.textAlign = 'center'; g.fillText('sin datos', cx, cy); return; }
      let lim = o.lim;
      if (!lim) { let m = 0; for (let k = 0; k < d.i.length; k++) m = Math.max(m, Math.abs(d.i[k]), Math.abs(d.q[k])); lim = Math.max(1.1, m * 1.1); }
      const sc = (s / 2 - P) / lim;
      g.strokeStyle = C.grid; g.lineWidth = 1;
      g.strokeRect(cx - s / 2 + P + .5, cy - s / 2 + P + .5, s - 2 * P, s - 2 * P);
      g.beginPath(); g.moveTo(cx - s / 2 + P, cy); g.lineTo(cx + s / 2 - P, cy); g.moveTo(cx, cy - s / 2 + P); g.lineTo(cx, cy + s / 2 - P); g.stroke();
      g.beginPath(); g.arc(cx, cy, sc, 0, 7); g.setLineDash([3, 4]); g.stroke(); g.setLineDash([]);
      g.fillStyle = o.color || C.cyan; g.globalAlpha = o.alpha || .55;
      const r = o.r || 1.8;
      for (let k = 0; k < d.i.length; k++) { g.beginPath(); g.arc(cx + d.i[k] * sc, cy - d.q[k] * sc, r, 0, 7); g.fill(); }
      g.globalAlpha = 1;
      if (d.extra) {
        g.fillStyle = C.amber;
        for (let k = 0; k < d.extra.i.length; k++) { g.beginPath(); g.arc(cx + d.extra.i[k] * sc, cy - d.extra.q[k] * sc, r + .6, 0, 7); g.fill(); }
      }
      if (o.ideal !== false) {
        g.strokeStyle = '#ffffffcc'; g.lineWidth = 1.5; const a = Math.SQRT1_2 * sc, t = 5;
        [[a, a], [-a, a], [-a, -a], [a, -a]].forEach(([x, y]) => {
          g.beginPath(); g.moveTo(cx + x - t, cy - y); g.lineTo(cx + x + t, cy - y); g.moveTo(cx + x, cy - y - t); g.lineTo(cx + x, cy - y + t); g.stroke();
        });
      }
      if (o.labels) {
        g.fillStyle = C.text; g.font = FONT; g.textAlign = 'center';
        const a = Math.SQRT1_2 * sc;
        [['00', a, a], ['01', -a, a], ['11', -a, -a], ['10', a, -a]].forEach(([b, x, y]) =>
          g.fillText(b, cx + x, cy - y + (y > 0 ? -12 : 18)));
      }
      g.fillStyle = C.text; g.textAlign = 'left'; g.fillText('I', cx + s / 2 - P - 12, cy - 8);
      g.fillText('Q', cx + 6, cy - s / 2 + P + 12);
    };
    cv._draw();
  }

  // ---------------------------------------------------------------- ojo
  function eye(cv, d) {
    cv._draw = () => {
      const { g, w, h, oculto } = setup(cv);
      if (oculto) return;
      if (!d || !d.trazos || !d.trazos.length) { g.fillStyle = C.text; g.textAlign = 'center'; g.fillText('sin datos', w / 2, h / 2); return; }
      const P = 10, n = d.trazos[0].length - 1;
      let m = 0; d.trazos.forEach(t => t.forEach(v => m = Math.max(m, Math.abs(v))));
      m = Math.max(m, 1) * 1.05;
      const X = k => P + k / n * (w - 2 * P), Y = v => h / 2 - v / m * (h / 2 - P);
      g.strokeStyle = C.grid; g.strokeRect(P + .5, P + .5, w - 2 * P, h - 2 * P);
      g.beginPath(); g.moveTo(P, h / 2); g.lineTo(w - P, h / 2);
      [d.sps / 2, d.sps * 1.5].forEach(k => { g.moveTo(X(k), P); g.lineTo(X(k), h - P); });
      g.stroke();
      g.strokeStyle = C.violet; g.globalAlpha = .22; g.lineWidth = 1.2;
      d.trazos.forEach(t => { g.beginPath(); t.forEach((v, k) => k ? g.lineTo(X(k), Y(v)) : g.moveTo(X(k), Y(v))); g.stroke(); });
      g.globalAlpha = 1; g.strokeStyle = C.amber; g.setLineDash([4, 4]);
      g.beginPath(); g.moveTo(X(d.sps), P); g.lineTo(X(d.sps), h - P); g.stroke(); g.setLineDash([]);
      g.fillStyle = C.text; g.fillText('t = kTs', X(d.sps) + 4, h - P - 6);
    };
    cv._draw();
  }

  // ---------------------------------------------------------------- barras
  function bars(cv, labels, vals, o = {}) {
    cv._draw = () => {
      const { g, w, h, oculto } = setup(cv);
      if (oculto) return;
      const ok = vals.map((v, i) => [v, i]).filter(([v]) => v !== null && (!o.logy || v > 0));
      if (!labels.length) { g.fillStyle = C.text; g.textAlign = 'center'; g.fillText('sin resultados', w / 2, h / 2); return; }
      const L = 52, R = 12, T = 14, B = 46, pw = w - L - R, ph = h - T - B;
      const tf = o.logy ? Math.log10 : (v => v);
      let y0, y1;
      if (o.logy) {
        const t = ok.map(([v]) => Math.log10(v));
        y1 = t.length ? Math.ceil(Math.max(...t) + .2) : 0; y0 = t.length ? Math.floor(Math.min(...t)) - 1 : -6;
        if (o.floor !== undefined) y0 = Math.min(y0, o.floor);
      } else { y0 = 0; y1 = o.max || Math.max(1e-9, ...ok.map(([v, i]) => v + ((o.err && o.err[i]) || 0))) * 1.15; }
      const Y = v => T + (1 - (tf(v) - y0) / (y1 - y0)) * ph;
      g.strokeStyle = C.grid; g.fillStyle = C.text; g.textAlign = 'right'; g.textBaseline = 'middle';
      const ticks = o.logy ? Array.from({ length: y1 - y0 + 1 }, (_, k) => y0 + k) : nice(y0, y1, 5);
      ticks.forEach(t => {
        const yy = T + (1 - (t - y0) / (y1 - y0)) * ph;
        g.beginPath(); g.moveTo(L, yy); g.lineTo(L + pw, yy); g.stroke();
        g.fillText(o.logy ? '1e' + t : (o.pct ? (t * 100).toFixed(0) + '%' : fmt(t)), L - 6, yy);
      });
      g.strokeStyle = C.axis; g.strokeRect(L + .5, T + .5, pw, ph);
      const bw = pw / labels.length;
      labels.forEach((lab, i) => {
        const v = vals[i], x = L + i * bw + bw * .18, ww = bw * .64;
        g.textAlign = 'center'; g.textBaseline = 'top'; g.fillStyle = C.text;
        let t = lab; while (g.measureText(t).width > bw - 4 && t.length > 3) t = t.slice(0, -2) + '…';
        g.fillText(t, L + i * bw + bw / 2, T + ph + 8);
        if (v === null || (o.logy && v <= 0)) {
          g.fillStyle = C.green; g.fillText(v === null ? '—' : '0', L + i * bw + bw / 2, T + ph - 18); return;
        }
        const yy = Y(v);
        const gr = g.createLinearGradient(0, yy, 0, T + ph);
        const col = (o.colors && o.colors[i]) || o.color || C.cyan; gr.addColorStop(0, col); gr.addColorStop(1, col + '33');
        g.fillStyle = gr; g.beginPath(); g.roundRect(x, yy, ww, T + ph - yy, [5, 5, 0, 0]); g.fill();
        const cx = L + i * bw + bw / 2, e = o.err && o.err[i];
        if (e) { g.strokeStyle = C.title; g.lineWidth = 1.3; g.beginPath(); g.moveTo(cx, Y(v + e)); g.lineTo(cx, Y(Math.max(v - e, 0)));
          g.moveTo(cx - 5, Y(v + e)); g.lineTo(cx + 5, Y(v + e)); g.moveTo(cx - 5, Y(Math.max(v - e, 0))); g.lineTo(cx + 5, Y(Math.max(v - e, 0))); g.stroke(); }
        g.fillStyle = C.title; g.textBaseline = 'bottom';
        g.fillText(o.fmt ? o.fmt(v) : o.pct ? (v * 100).toFixed(1) + '%' : v.toExponential(1), cx, (e ? Y(v + e) : yy) - 3);
      });
      if (o.ylabel) {
        g.save(); g.translate(11, T + ph / 2); g.rotate(-Math.PI / 2); g.textAlign = 'center'; g.fillStyle = C.text;
        g.fillText(o.ylabel, 0, 0); g.restore();
      }
    };
    cv._draw();
  }

  return { line, iq, eye, bars, empty, C };
})();
