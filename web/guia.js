// Laboratorio guiado: un paso físico a la vez → "Listo" → medir → validar. La validación está en logica/guia.py.
const Guia = (() => {
  const CLAVE = 'p3_guia';
  const NUEVO = () => ({ rol: null, i: 0, est: {}, pend: null, fadIdx: 0, olvido: false,
    dists: '1, 2, 4, 8', obsDist: 4, obst: ['Madera', 'Persona', 'Metal'], nlam: 3, canDist: 3 });
  const MATERIALES = ['Madera', 'Puerta', 'Vidrio', 'Persona', 'Pared', 'Metal'];
  const SIM_DB = { Madera: 4, Puerta: 4, Vidrio: 2, Persona: 6, Pared: 9, Metal: 14 };
  const ROLES = { sim: 'Ensayo simulado', solo: 'Un PC con los 2 USRP', pc1: 'Soy la máquina 1 (TX)', pc2: 'Soy la máquina 2 (RX)' };
  let G = NUEVO(), ocupado = false, ultimo = null, turno = 0;

  const salvar = () => { try { localStorage.setItem(CLAVE, JSON.stringify(G)); } catch (e) { } };
  const listaDist = () => [...new Set(String(G.dists).split(/[,; ]+/).map(Number).filter(d => d > 0))];

  // ---------------------------------------------------------------- definición de pasos
  function pasos() {
    const L = [{ k: 'rol', tipo: 'rol', fase: 'Preparación', t: '¿Cómo está armado el laboratorio?' }];
    const r = G.rol;
    if (!r) return L;
    if (r === 'solo' || r === 'pc1') {
      L.push({ k: 'redtx', tipo: 'red', ip: 'ip_tx', fase: 'Conexión', t: 'Conecta el USRP 1 (TX) a ' + (r === 'solo' ? 'este PC' : 'la máquina 1') });
      L.push({ k: 'txon', tipo: 'tx', fase: 'Conexión', t: 'Pon la antena y enciende la transmisión' });
    }
    if (r === 'pc1') return L.concat({ k: 'finpc1', tipo: 'finpc1', fase: 'Listo', t: 'La máquina 1 queda transmitiendo' });
    if (r === 'solo' || r === 'pc2')
      L.push({ k: 'redrx', tipo: 'red', ip: 'ip_rx', fase: 'Conexión', t: 'Conecta el USRP 2 (RX) a ' + (r === 'solo' ? 'este PC' : 'la máquina 2') });
    L.push({ k: 'enlace', tipo: 'enlace', fase: 'Conexión', t: 'Comprueba el enlace a ' + P.rx_dist_sim + ' m' });
    listaDist().forEach(d => L.push({ k: 'd:' + d, tipo: 'medir', db: 'distancia', d, fase: 'Distancia', t: `Coloca el RX a ${d} m del TX` }));
    L.push({ k: 'o:LOS', tipo: 'medir', db: 'obstruccion', cond: 'LOS', fase: 'Obstáculos', t: `RX a ${G.obsDist} m, sin nada en medio` });
    G.obst.forEach(c => L.push({ k: 'o:' + c, tipo: 'medir', db: 'obstruccion', cond: c, fase: 'Obstáculos', t: `Pon el obstáculo de ${c.toLowerCase()}` }));
    L.push({ k: 'fad', tipo: 'medir', db: 'fading', fase: 'Fading', t: 'Desplaza el RX en pasos pequeños' });
    L.push({ k: 'c:los', tipo: 'medir', db: 'canal', esc: 'los', fase: 'Multitrayectoria', t: 'Canal con línea de vista despejada' });
    L.push({ k: 'c:multi', tipo: 'medir', db: 'canal', esc: 'multi', fase: 'Multitrayectoria', t: 'Canal en un lugar reflectante' });
    L.push({ k: 'fin', tipo: 'fin', fase: 'Final', t: 'Resumen del laboratorio' });
    return L;
  }
  const actual = () => { const L = pasos(); G.i = Math.max(0, Math.min(G.i, L.length - 1)); return L[G.i]; };

  // parámetros que se envían a Python para el paso (no pisan los de los módulos manuales)
  function params(s) {
    const q = { ...P, sim_sigma: Math.min(P.sim_sigma, 1), sim_olvido: P.rx_hw === 'sim' && G.olvido };
    if (s.db === 'distancia') q.dist_m = s.d;
    if (s.db === 'obstruccion') Object.assign(q, { obst_dist: +G.obsDist, obst_cond: s.cond, obst_sim_db: SIM_DB[s.cond] || 8 });
    if (s.db === 'fading') Object.assign(q, { fad_idx: G.fadIdx, fad_nlam: +G.nlam, fad_frac: 8 });
    if (s.db === 'canal') Object.assign(q, { canal_esc: s.esc, canal_dist: +G.canDist });
    return q;
  }

  // ---------------------------------------------------------------- dibujo del montaje
  function dibujo(texto, obst, eco) {
    return `<svg class="diag" viewBox="0 0 620 120" role="img" aria-label="Montaje: ${esc(texto)}">
      <rect class="box" x="8" y="38" width="76" height="46" rx="9"/><text class="t2" x="46" y="66" text-anchor="middle">TX</text>
      <rect class="box" x="536" y="38" width="76" height="46" rx="9"/><text class="t2" x="574" y="66" text-anchor="middle">RX</text>
      <line class="los" x1="88" y1="61" x2="532" y2="61"/>
      ${obst ? `<rect class="blk" x="296" y="20" width="28" height="82" rx="4"/><text x="310" y="14" text-anchor="middle">${esc(obst)}</text>` : ''}
      ${eco ? '<path class="ray" d="M88 55L310 12L532 55M88 68L260 108L532 68"/>' : ''}
      <text x="${obst ? 450 : 310}" y="116" text-anchor="middle">${esc(texto)}</text></svg>`;
  }

  const campo = (id, rotulo, val, tipo = 'text') => `<label>${rotulo}<input type="${tipo}" data-g="${id}" value="${esc(val)}"></label>`;

  function cuerpo(s) {
    const li = a => `<ul>${a.map(t => `<li>${t}</li>`).join('')}</ul>`;
    if (s.tipo === 'rol') return li(['Elige una opción. Con dos computadoras, abre la app en ambas.']) +
      `<div class="g-botones">${Object.entries(ROLES).map(([v, n]) => `<button class="btn ${G.rol === v ? 'primary' : ''}" data-rol="${v}">${n}</button>`).join('')}</div>
      <div id="gPrevio"></div>
      ${G.rol && G.rol !== 'pc1' ? `<div class="form" style="margin-top:16px">${campo('dists', 'Distancias a medir (m)', G.dists)}
        <label>Obstáculos que vas a probar<div class="chips">${MATERIALES.map(m => `<button class="chip" data-mat="${m}">${G.obst.includes(m) ? '✓ ' : ''}${m}</button>`).join('')}</div></label></div>` : ''}`;
    if (s.tipo === 'red') return li(['Enciende el USRP y conéctalo con el cable Ethernet Gigabit.',
      G.rol === 'solo' ? 'Con los dos en un PC usa un switch o dos tarjetas de red, y <b>IP distintas</b>.' : 'La IP de fábrica del N210 es 192.168.10.2.',
      'Pulsa <b>Listo</b>: se comprueba la IP del PC, el ping y que UHD lo reconozca.']) +
      `<div class="form">${campo(s.ip, 'IP del USRP', P[s.ip])}</div>`;
    if (s.tipo === 'tx') return li(['Atornilla la antena en <b>TX/RX</b> del USRP 1 y déjalo en su sitio definitivo.',
      `Se transmitirá con f<sub>c</sub> ${fmtHz(P.fc)}, ganancia ${P.gain_tx} dB.`]);
    if (s.tipo === 'finpc1') return li(['No cierres la app ni muevas el USRP 1.',
      'En la máquina 2 abre la app y elige <b>Soy la máquina 2 (RX)</b>.',
      'Ambas máquinas deben usar los mismos parámetros (módulo 01).']) + '<div class="g-botones"><button class="btn danger" data-acc="txoff">Detener transmisión</button></div>';
    if (s.tipo === 'enlace') return li([G.rol === 'pc2' ? 'Confirma que la máquina 1 está transmitiendo.' : 'Deja el transmisor encendido.',
      'Antena puesta en el RX, a la distancia de prueba y con línea de vista.']) + dibujo(P.rx_dist_sim + ' m') +
      `<div class="form">${campo('rx_dist_sim', 'Distancia de prueba (m)', P.rx_dist_sim, 'number')}</div>`;
    if (s.db === 'distancia') return li(['Mide con cinta la distancia entre antenas.', 'Misma altura y orientación que antes; nada en medio.']) + dibujo(s.d + ' m');
    if (s.db === 'obstruccion') {
      if (s.cond === 'LOS') return li([`Pon TX y RX a ${G.obsDist} m y <b>márcalos</b>: no se vuelven a mover en esta fase.`, 'Retira cualquier objeto entre las antenas.']) +
        dibujo(G.obsDist + ' m · sin obstáculo') + `<div class="form">${campo('obsDist', 'Distancia fija (m)', G.obsDist, 'number')}</div>`;
      return li(['Retira el obstáculo anterior. <b>No muevas TX ni RX.</b>', `Coloca el obstáculo de <b>${s.cond.toLowerCase()}</b> cortando la línea entre antenas y apártate.`]) +
        dibujo(G.obsDist + ' m', s.cond);
    }
    if (s.db === 'fading') {
      const paso = 29979.2458 / (P.fc / 1e6) / 8, n = nPos();   // λ/8 en cm
      const hecho = G.fadIdx >= n;
      return li(hecho ? ['Barrido completo.'] : [
        G.fadIdx === 0 ? 'Marca el punto de partida del RX y ten una regla a mano.' : `Avanza el RX <b>${paso.toFixed(1)} cm</b> en línea recta.`,
        `Posición <b>${G.fadIdx + 1} de ${n}</b> → a <b>${(G.fadIdx * paso).toFixed(1)} cm</b> de la marca. No toques el TX.`]) +
        `<div class="progress" style="margin-bottom:14px"><div style="width:${100 * Math.min(G.fadIdx, n) / n}%"></div></div>` +
        (G.fadIdx === 0 ? `<div class="form">${campo('nlam', 'Longitudes de onda a recorrer', G.nlam, 'number')}</div>` : '');
    }
    if (s.db === 'canal') return li(s.esc === 'los' ? ['Antenas a la vista, lejos de paredes y objetos metálicos.']
      : ['Lleva el enlace a un pasillo, esquina o junto a superficies metálicas.', 'Mantén aproximadamente la misma distancia.']) +
      dibujo(G.canDist + ' m', null, s.esc === 'multi') + `<div class="form">${campo('canDist', 'Distancia (m)', G.canDist, 'number')}</div>`;
    if (s.tipo === 'fin') {
      const L = pasos().filter(x => !['rol', 'fin'].includes(x.tipo)), e = x => G.est[x.k] || {};
      const falta = L.filter(x => e(x).s !== 'hecho'), conf = L.filter(x => e(x).confirmado);
      return li([`Pasos completados: <b>${L.length - falta.length} de ${L.length}</b>.`,
        falta.length ? 'Pendientes o saltados: ' + falta.map(x => esc(x.t)).join(' · ') : 'No queda ningún paso pendiente.',
        conf.length ? 'Aceptados pese a la alerta (revísalos en el informe): ' + conf.map(x => esc(x.t)).join(' · ') : 'Ninguna medida se aceptó contra la alerta.']) +
        '<div class="g-botones"><button class="btn primary" data-acc="analisis">Ver análisis comparativo</button></div>';
    }
    return '';
  }

  const nPos = () => Math.ceil(+G.nlam * 8) + 1;

  // ---------------------------------------------------------------- render
  function pintar() {
    const L = pasos(), s = actual(), mi = ++turno;
    $('#gLista').innerHTML = L.map((x, i) => {
      const e = (G.est[x.k] || {}).s;
      return `<li class="${i === G.i ? 'act' : ''} ${e || ''}" data-ir="${i}"><i>${e === 'hecho' ? '✓' : e === 'saltado' ? '–' : ''}</i>${esc(x.t)}</li>`;
    }).join('');
    const mide = ['red', 'tx', 'enlace', 'medir'].includes(s.tipo);
    const fadFin = s.db === 'fading' && G.fadIdx >= nPos();
    const hecho = (G.est[s.k] || {}).s === 'hecho';
    const listo = { red: 'Listo, verificar conexión', tx: 'Listo, transmitir', enlace: 'Listo, probar enlace' }[s.tipo]
      || (s.db === 'fading' ? `Listo, medir posición ${G.fadIdx + 1}` : 'Listo, medir');
    $('#gPaso').innerHTML = `<span class="g-fase">${s.fase} · paso ${G.i + 1}${G.rol ? ' de ' + L.length : ''}</span><h2>${esc(s.t)}</h2>${cuerpo(s)}
      ${s.tipo === 'medir' && !fadFin ? '<div class="g-esperado" id="gEsperado">Estimando…</div>' : ''}
      ${s.tipo === 'medir' && P.rx_hw === 'sim' ? `<label class="toggle" style="margin-bottom:14px"><input type="checkbox" data-g="olvido" ${G.olvido ? 'checked' : ''}><span></span>ensayo: simular que NO hice el paso</label>` : ''}
      <div class="g-botones" style="margin-top:6px">
        ${G.i ? '<button class="btn ghost" data-acc="atras">← Atrás</button>' : ''}
        ${mide && !fadFin ? `<button class="btn ${hecho ? '' : 'primary'}" data-acc="listo">${hecho ? 'Volver a hacer' : listo}</button>` : ''}
        ${s.db === 'fading' && (G.fadIdx > 0) ? '<button class="btn ghost" data-acc="refad">Reiniciar barrido</button>' : ''}
        ${(hecho || fadFin || (s.tipo === 'rol' && G.rol)) ? '<button class="btn primary" data-acc="sig">Siguiente paso →</button>' : ''}
        ${mide && !hecho && !fadFin ? '<button class="btn ghost" data-acc="saltar">Saltar paso</button>' : ''}
      </div>`;
    pintarResultado(s);
    if (s.tipo === 'medir' && !fadFin) api.guia_esperado(params(s), s.db).then(t => { if (mi === turno && $('#gEsperado')) $('#gEsperado').textContent = t; });
    if (s.tipo === 'rol') api.guia_resumen().then(n => {
      const tot = Object.values(n).reduce((a, b) => a + b, 0);
      if (mi === turno && tot && $('#gPrevio')) $('#gPrevio').innerHTML = `<p class="note wa">Hay ${tot} medidas guardadas. Para una práctica limpia pulsa <b>Nueva práctica</b> (se guarda una copia).</p>`;
    });
    if (G.pend) abrirModal();
  }

  function pintarResultado(s) {
    const el = $('#gResultado');
    if (!ultimo || ultimo.k !== s.k) {
      const e = G.est[s.k];
      el.innerHTML = e && e.texto ? `<div class="verdict ${e.confirmado ? 'warn' : 'ok'}"><div>${e.confirmado ? 'Guardado por confirmación tuya' : 'Paso completado'}<small>${esc(e.texto)}</small></div></div>` : '';
      return;
    }
    const u = ultimo;
    el.innerHTML = `<div class="verdict ${u.cls}"><span style="font-size:22px">${ICONO[u.cls]}</span><div>${esc(u.titulo)}<small>${esc(u.detalle || '')}</small></div></div>
      ${u.pasos ? `<div class="steps">${u.pasos.map(p => `<div class="step ${p.estado}"><i>${ICONO[p.estado]}</i><b>${esc(p.paso)}</b><span>${esc(p.detalle)}</span></div>`).join('')}</div>` : ''}
      ${u.comando ? `<p class="note">Ejecuta en una terminal y vuelve a pulsar Listo:</p><code class="g-cmd">${esc(u.comando)}</code>` : ''}`;
  }

  const mostrar = (s, cls, titulo, detalle, extra = {}) => { ultimo = { k: s.k, cls, titulo, detalle, ...extra }; };
  function completar(s, texto, confirmado = false) { G.est[s.k] = { ...G.est[s.k], s: 'hecho', texto, confirmado }; }

  // ---------------------------------------------------------------- acciones
  async function listo(btn) {
    const s = actual();
    if (s.tipo === 'red' && G.rol === 'solo' && P.ip_tx.trim() === P.ip_rx.trim()) {
      mostrar(s, 'ko', 'Las dos IP son iguales', 'Cada USRP necesita la suya (usrp_burn_mb_eeprom --values="ip-addr=192.168.10.3").');
      return pintar();
    }
    ocupado = true; ultimo = null;
    try {
      await busy(btn, async () => {
        if (s.tipo === 'medir') return medir(s);
        const r = s.tipo === 'red' ? await api.guia_red(P[s.ip]) : s.tipo === 'tx' ? await api.guia_tx(P) : await api.guia_enlace(P);
        delete G.est[s.k];
        if (!r.ok) return mostrar(s, 'ko', 'No se pudo completar', r.error);
        if (s.tipo === 'red') {
          mostrar(s, r.listo ? 'ok' : 'ko', r.listo ? 'USRP detectado' : 'No veo el USRP', r.listo ? P[s.ip] : '¿Está encendido y con el cable puesto?', { pasos: r.pasos, comando: r.listo ? null : r.comando });
          if (r.listo) completar(s, 'USRP detectado en ' + P[s.ip]);
        } else if (s.tipo === 'tx') {
          mostrar(s, 'ok', 'Transmitiendo', 'El transmisor queda activo.'); completar(s, 'Transmisión iniciada'); txEstado();
        } else {
          mostrar(s, r.listo ? 'ok' : 'ko', r.listo ? 'Enlace funcionando' : 'El enlace no está listo', r.listo ? 'Puedes empezar a medir.' : 'Corrige los puntos en rojo y repite.', { pasos: r.pasos });
          if (r.listo) completar(s, 'Enlace verificado');
        }
      });
    } catch (e) { console.error(e); mostrar(s, 'ko', 'Error inesperado', String(e)); }
    finally { ocupado = false; salvar(); pintar(); }
  }

  async function medir(s) {
    const prev = G.est[s.k];
    if (prev && prev.id && s.db !== 'fading') await api.borrar(s.db, prev.id);   // rehacer: reemplaza la anterior
    if (s.db !== 'fading') delete G.est[s.k];       // en fading se conserva la marca de confirmación del barrido
    const r = await api.guia_medir(params(s), s.db);
    if (!r.ok) {
      console.error(r.tb);
      return mostrar(s, 'ko', 'No se pudo medir', r.error + (G.rol === 'pc2' ? ' ¿Sigue transmitiendo la máquina 1?' : ''));
    }
    if (r.estado === 'invalido') return mostrar(s, 'ko', r.pregunta, `Esperado: ${r.esperado} · Medido: ${r.medido}`);
    if (r.estado === 'sospechoso') { G.pend = { k: s.k, db: s.db, ...r }; return; }
    aceptar(s, r, false);
  }

  function aceptar(s, r, confirmado) {
    const texto = `${r.medido} · esperado: ${r.esperado}`;
    mostrar(s, confirmado ? 'warn' : 'ok', confirmado ? 'Guardado por confirmación tuya' : 'Coincide con lo esperado', texto);
    if (s.db !== 'fading') { G.est[s.k] = { id: r.id }; return completar(s, texto, confirmado); }
    ultimo.titulo = `Posición ${G.fadIdx + 1}: ${ultimo.titulo.toLowerCase()}`;
    if (confirmado) G.est[s.k] = { confirmado: true };
    const conf = confirmado || (G.est[s.k] || {}).confirmado;
    G.fadIdx++;
    if (G.fadIdx < nPos() && G.est[s.k]) delete G.est[s.k].s;
    if (G.fadIdx >= nPos()) completar(s, `${nPos()} posiciones medidas`, conf);
  }

  function abrirModal() {
    const p = G.pend;
    $('#gmTitulo').textContent = '¿Estás seguro? El resultado no cuadra';
    $('#gmPregunta').textContent = p.pregunta;
    $('#gmEsperado').textContent = p.esperado;
    $('#gmMedido').textContent = p.medido;
    if ($('#gModal').hidden) { $('#gModal').hidden = false; $('#gmRepetir').focus(); }
  }

  async function resolver(seguro) {
    const p = G.pend; if (!p || ocupado) return;
    ocupado = true;
    try {
      const s = pasos().find(x => x.k === p.k);
      if (seguro && s && await api.guia_confirmar(p.db, p.id)) aceptar(s, p, true);
      else {
        await api.borrar(p.db, p.id);
        if (s) mostrar(s, 'warn', 'Medida descartada', 'Revisa el montaje y vuelve a pulsar Listo.');
      }
      G.pend = null; $('#gModal').hidden = true;
    } finally { ocupado = false; salvar(); pintar(); }
  }

  const ir = i => { G.i = i; ultimo = null; salvar(); pintar(); };

  function elegirRol(r) {
    if (G.rol !== r) { G.est = {}; G.fadIdx = 0; }
    G.rol = r;
    P.tx_hw = r === 'solo' || r === 'pc1' ? 'usrp' : 'ninguno';
    P.rx_hw = r === 'sim' ? 'sim' : 'usrp';
    if (r === 'pc2' && P.ip_rx === '192.168.10.3') P.ip_rx = '192.168.10.2';
    guardar(); pintarControles(); ultimo = null; salvar(); pintar();
  }

  function iniciar() {
    try { G = { ...NUEVO(), ...JSON.parse(localStorage.getItem(CLAVE) || '{}') }; } catch (e) { }
    $('#page-guia').addEventListener('click', async e => {
      if (ocupado) return;
      const b = e.target.closest('[data-acc],[data-rol],[data-mat],[data-ir]'); if (!b) return;
      if (b.dataset.rol) return elegirRol(b.dataset.rol);
      if (b.dataset.mat) {
        const m = b.dataset.mat;
        G.obst = MATERIALES.filter(x => x === m ? !G.obst.includes(m) : G.obst.includes(x)); salvar(); return pintar();
      }
      if (b.dataset.ir) return ir(+b.dataset.ir);
      const a = b.dataset.acc, s = actual();
      if (a === 'listo') return listo(b);
      if (a === 'atras') return ir(G.i - 1);
      if (a === 'sig') return ir(G.i + 1);
      if (a === 'saltar') { G.est[s.k] = { ...G.est[s.k], s: 'saltado', texto: '' }; return ir(G.i + 1); }
      if (a === 'analisis') return irA('analisis');
      if (a === 'txoff') { await api.tx_detener(); txEstado(); delete G.est.txon; return toast('Transmisión detenida'); }
      if (a === 'refad') { await api.limpiar('fading'); G.fadIdx = 0; delete G.est.fad; return ir(G.i); }
    });
    $('#page-guia').addEventListener('change', e => {
      const el = e.target.closest('[data-g]'); if (!el || ocupado) return;
      const k = el.dataset.g;
      if (k === 'olvido') G.olvido = el.checked;
      else if (k === 'ip_tx' || k === 'ip_rx') { P[k] = el.value.trim(); delete G.est[actual().k]; guardar(); pintarControles(); }
      else if (k === 'rx_dist_sim') { if (+el.value > 0) P[k] = +el.value; guardar(); pintarControles(); }
      else if (k === 'dists') G.dists = el.value;
      else if (+el.value > 0) G[k] = +el.value;
      salvar();
      // se repinta después del clic que pudo provocar este cambio (si no, el botón desaparece bajo el cursor)
      setTimeout(() => { if (!ocupado) pintar(); }, 200);
    });
    $('#gmRepetir').onclick = () => resolver(false);
    $('#gmSeguro').onclick = () => resolver(true);
    $('#btnGuiaNueva').onclick = async () => {
      if (ocupado || !confirm('¿Empezar una práctica nueva? Los resultados actuales se guardan en una copia dentro de mediciones/.')) return;
      const r = await api.guia_nueva_practica();
      if (!r.ok) return toast(r.error, true);
      G = NUEVO(); ultimo = null; salvar(); pintar();
      toast(r.copia ? 'Copia guardada: ' + r.copia : 'Práctica nueva');
    };
  }

  return { iniciar, pintar };
})();
