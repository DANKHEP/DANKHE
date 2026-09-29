/* SM · Search Mining — DANKHE PROJETOS */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const dash = (v) => (v === null || v === undefined || v === "" ? "—" : esc(v));
  const fmtArea = (v) => (v == null ? "—" : `${Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ha`);
  const digits = (v) => (v || "").replace(/\D/g, "");

  const form = $("#searchForm"), input = $("#q"), hint = $("#hint"), results = $("#results"), btn = $("#searchBtn");
  let mode = "processo", lastList = null, map = null;

  /* ---------------- tema ---------------- */
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* sem storage */ } },
  };
  const savedTheme = store.get("sm-theme");
  if (savedTheme) document.documentElement.dataset.theme = savedTheme;
  $("#themeToggle").addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = dark ? "light" : "dark";
    store.set("sm-theme", document.documentElement.dataset.theme);
  });

  /* ---------------- modos / máscaras ---------------- */
  const MODES = {
    processo: {
      placeholder: "000.000/0000", inputmode: "numeric",
      hint: 'Ex.: <button type="button" class="chip" data-example="830.123/2010">830.123/2010</button> — formato 000.000/AAAA',
      mask(v) {
        const d = digits(v).slice(0, 10);
        if (d.length <= 3) return d;
        if (d.length <= 6) return `${d.slice(0, 3)}.${d.slice(3)}`;
        return `${d.slice(0, 3)}.${d.slice(3, 6)}/${d.slice(6)}`;
      },
      validate: (v) => (/^\d{3}\.\d{3}\/\d{4}$/.test(v) ? null : "Informe o processo no formato 000.000/AAAA."),
    },
    documento: {
      placeholder: "CPF ou CNPJ do interessado", inputmode: "numeric",
      hint: 'Ex.: <button type="button" class="chip" data-example="11.222.333/0001-81">11.222.333/0001-81</button> — lista todos os processos do titular/requerente',
      mask(v) {
        const d = digits(v).slice(0, 14);
        if (d.length <= 11) {
          return d.replace(/^(\d{3})(\d)/, "$1.$2").replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3").replace(/\.(\d{3})(\d{1,2})$/, ".$1-$2");
        }
        return d.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{0,2}).*/, "$1.$2.$3/$4-$5");
      },
      validate: (v) => (validCpf(digits(v)) || validCnpj(digits(v)) ? null : "CPF ou CNPJ inválido. Confira os dígitos."),
    },
    titular: {
      placeholder: "Nome ou razão social do titular", inputmode: "text",
      hint: "Busca por parte do nome no SIGMINE (processos ativos). Ex.: <button type=\"button\" class=\"chip\" data-example=\"MINERAÇÃO\">MINERAÇÃO</button>",
      mask: (v) => v,
      validate: (v) => (v.trim().length >= 3 ? null : "Digite ao menos 3 caracteres do nome."),
    },
  };

  function validCpf(d) {
    if (d.length !== 11 || /^(\d)\1+$/.test(d)) return false;
    for (const n of [9, 10]) {
      let s = 0;
      for (let i = 0; i < n; i++) s += +d[i] * (n + 1 - i);
      if (((s * 10) % 11) % 10 !== +d[n]) return false;
    }
    return true;
  }
  function validCnpj(d) {
    if (d.length !== 14 || /^(\d)\1+$/.test(d)) return false;
    const w = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    for (const n of [12, 13]) {
      const p = n === 12 ? w : [6, ...w];
      let s = 0;
      for (let i = 0; i < n; i++) s += +d[i] * p[i];
      const r = s % 11;
      if ((r < 2 ? 0 : 11 - r) !== +d[n]) return false;
    }
    return true;
  }

  function setMode(m, keepValue = false) {
    mode = m;
    const idx = Object.keys(MODES).indexOf(m);
    $$(".seg-btn").forEach((b, i) => { b.classList.toggle("active", i === idx); b.setAttribute("aria-selected", i === idx); });
    $(".seg-glider").style.transform = `translateX(${idx * 100}%)`;
    input.placeholder = MODES[m].placeholder;
    input.inputMode = MODES[m].inputmode;
    hint.innerHTML = MODES[m].hint;
    if (!keepValue) input.value = "";
    input.focus();
  }
  $$(".seg-btn").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
  input.addEventListener("input", () => {
    const pos = input.value.length === input.selectionStart;
    input.value = MODES[mode].mask(input.value);
    if (pos) input.setSelectionRange(input.value.length, input.value.length);
  });
  hint.addEventListener("click", (e) => {
    const c = e.target.closest("[data-example]");
    if (c) { input.value = c.dataset.example; form.requestSubmit(); }
  });

  /* ---------------- util ---------------- */
  let toastTimer;
  function toast(msg, err = false) {
    const t = $("#toast");
    t.textContent = msg;
    t.className = `toast show${err ? " err" : ""}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (t.className = "toast"), 4200);
  }
  function busy(on) {
    btn.disabled = on;
    btn.innerHTML = on ? '<span class="spin"></span><span>Consultando…</span>' : '<span>Consultar</span><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z"/></svg>';
  }
  async function api(url, opts) {
    const r = await fetch(url, opts);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.erro || `Erro ${r.status} ao consultar a ANM.`);
    return data;
  }
  function badgeClass(fase) {
    const f = (fase || "").toLowerCase();
    if (f.includes("lavra") || f.includes("garimp")) return "lavra";
    if (f.includes("licenc")) return "lic";
    if (f.includes("requerimento")) return "req";
    if (f.includes("disponib")) return "disp";
    return "";
  }
  const statusHtml = (s) => `<span class="status ${/ativo/i.test(s || "") && !/inativo/i.test(s) ? "on" : "off"}">${dash(s)}</span>`;
  function skeleton(n = 3) {
    results.innerHTML = `<div class="grid" style="margin-top:28px">${'<div class="skeleton"></div>'.repeat(n)}</div>`;
  }
  function empty(title, text, icon = "⛏") {
    results.innerHTML = `<div class="empty"><div class="ico">${icon}</div><h3>${esc(title)}</h3><p>${esc(text)}</p></div>`;
  }
  async function download(url, filename, opts) {
    const r = await fetch(url, opts);
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.erro || "Falha no download."); }
    const blob = await r.blob();
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: filename });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
  const fileBase = (proc) => `SM_processo_${proc.replace(/\./g, "").replace("/", "-")}`;

  /* ---------------- busca ---------------- */
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const v = input.value.trim();
    const err = MODES[mode].validate(v);
    if (err) return toast(err, true);
    const next = `#${mode}=${encodeURIComponent(v)}`;
    if (location.hash === next) { lastList = null; route(); } else location.hash = next;
  });

  async function run(m, v) {
    busy(true);
    skeleton(m === "processo" ? 1 : 3);
    try {
      if (m === "processo") {
        renderDetail(await api(`/api/processo?numero=${encodeURIComponent(v)}`), null);
      } else {
        const url = m === "documento" ? `/api/documento?doc=${encodeURIComponent(digits(v))}` : `/api/titular?nome=${encodeURIComponent(v)}`;
        lastList = { mode: m, query: v, items: await api(url) };
        renderList(lastList);
      }
    } catch (ex) {
      empty("Não foi possível concluir a consulta", ex.message, "!");
      toast(ex.message, true);
    } finally {
      busy(false);
    }
  }

  function renderList({ mode: m, query, items }) {
    if (!items.length) return empty("Nenhum processo encontrado", m === "documento" ? "Não há processos vinculados a este CPF/CNPJ no Cadastro Mineiro." : "Nenhum processo ativo com esse nome no SIGMINE.");
    results.innerHTML = `
      <div class="results-head">
        <div><h2>${items.length} processo${items.length > 1 ? "s" : ""} encontrado${items.length > 1 ? "s" : ""}</h2>
        <p>${m === "documento" ? "CPF/CNPJ" : "Titular"}: <b>${esc(query)}</b></p></div>
        <div class="actions" style="margin:0">
          <label class="check"><input type="checkbox" id="selAll"> Selecionar todos</label>
          <button class="btn btn-teal" id="pdfSel" disabled>PDF dos selecionados</button>
        </div>
      </div>
      <div class="grid">${items.map((p, i) => `
        <article class="card" style="animation-delay:${Math.min(i, 12) * 40}ms">
          <div class="row"><span class="badge ${badgeClass(p.fase)}">${dash(p.fase)}</span>${statusHtml(p.status)}</div>
          <h3 style="margin-top:10px">${esc(p.processo)}</h3>
          <p class="sub" title="${esc(p.titular)}">${dash(p.titular)}</p>
          <dl>
            <div><dt>Substância</dt><dd>${dash(p.substancia)}</dd></div>
            <div><dt>Área</dt><dd>${fmtArea(p.area_ha)}</dd></div>
            <div><dt>UF</dt><dd>${dash(p.uf)}</dd></div>
            <div><dt>Último evento</dt><dd>${dash(p.ultimo_evento?.data)}</dd></div>
          </dl>
          <div class="row">
            <label class="check"><input type="checkbox" class="sel" value="${esc(p.processo)}"> Incluir no PDF</label>
            <button class="btn btn-ghost" data-open="${esc(p.processo)}" style="min-height:40px;padding:0 14px">Ver detalhes →</button>
          </div>
        </article>`).join("")}
      </div>`;
    const sels = $$(".sel"), pdfBtn = $("#pdfSel");
    const refresh = () => {
      const n = sels.filter((s) => s.checked).length;
      pdfBtn.disabled = !n;
      pdfBtn.textContent = n ? `PDF dos selecionados (${n})` : "PDF dos selecionados";
    };
    sels.forEach((s) => s.addEventListener("change", refresh));
    $("#selAll").addEventListener("change", (e) => { sels.slice(0, 25).forEach((s) => (s.checked = e.target.checked)); refresh(); });
    pdfBtn.addEventListener("click", async () => {
      const processos = sels.filter((s) => s.checked).map((s) => s.value);
      if (processos.length > 25) toast("Máximo de 25 processos por PDF; os primeiros 25 serão incluídos.");
      pdfBtn.disabled = true; pdfBtn.innerHTML = '<span class="spin"></span> Gerando PDF…';
      try {
        await download("/api/pdf", "SM_relatorio_processos.pdf", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ processos }) });
        toast("PDF gerado com sucesso.");
      } catch (ex) { toast(ex.message, true); } finally { refresh(); }
    });
    $$("[data-open]").forEach((b) => b.addEventListener("click", () => { location.hash = `processo=${encodeURIComponent(b.dataset.open)}&from=list`; }));
  }

  function renderDetail(p, back) {
    const ev = p.ultimo_evento || {};
    const evTxt = [ev.codigo, ev.descricao].filter(Boolean).join(" - ");
    const verts = p.poligonos.flat();
    results.innerHTML = `
      <div class="detail">
        <section class="panel">
          ${back ? '<button class="back" id="back">← Voltar à lista</button>' : ""}
          <div class="detail-top">
            <div>
              <span class="badge ${badgeClass(p.fase)}">${dash(p.fase)}</span>
              <h2>${esc(p.processo)}</h2>
              <p class="titular">${dash(p.titular)}</p>
              ${p.cpf_cnpj ? `<span class="doc">CPF/CNPJ: ${esc(p.cpf_cnpj)}</span>` : ""}
            </div>
            ${statusHtml(p.status)}
          </div>
          <div class="kpis">
            <div class="kpi"><span>Status</span><b>${dash(p.status)}</b></div>
            <div class="kpi"><span>Área</span><b>${fmtArea(p.area_ha)}</b></div>
            <div class="kpi"><span>Vencimento</span><b>${dash(p.data_vencimento)}</b></div>
            <div class="kpi"><span>UF</span><b>${dash(p.uf)}</b></div>
          </div>
          <dl class="info">
            <div><dt>Número do processo</dt><dd>${esc(p.processo)}</dd></div>
            <div><dt>Nome do titular</dt><dd>${dash(p.titular)}</dd></div>
            <div><dt>Fase do processo</dt><dd>${dash(p.fase)}</dd></div>
            <div><dt>Substância mineral</dt><dd>${dash(p.substancia)}</dd></div>
            <div><dt>Área</dt><dd>${fmtArea(p.area_ha)}</dd></div>
            <div><dt>Uso</dt><dd>${dash(p.uso)}</dd></div>
            <div><dt>Município</dt><dd>${dash(p.municipio)}</dd></div>
            <div><dt>Estado</dt><dd>${dash(p.uf)}</dd></div>
            <div><dt>Data de vencimento</dt><dd>${dash(p.data_vencimento)}</dd></div>
            <div><dt>Data do último evento</dt><dd>${dash(ev.data)}</dd></div>
          </dl>
          <div class="last-event">
            <small>Último evento</small>
            <p>${dash(evTxt)}</p>
            <time>${dash(ev.data)}</time>
          </div>
          ${p.eventos?.length > 1 ? `<details class="more"><summary>Histórico de eventos (${p.eventos.length})</summary>
            <ol class="timeline">${p.eventos.map((e) => `<li><time>${dash(e.data)}</time>${esc([e.codigo, e.descricao].filter(Boolean).join(" - "))}</li>`).join("")}</ol></details>` : ""}
          ${(p.avisos || []).map((a) => `<div class="notice">${esc(a)}</div>`).join("")}
          <div class="actions">
            <button class="btn btn-primary" id="dlPdf">⬇ Salvar em PDF</button>
            <button class="btn btn-teal" id="dlKml" ${verts.length ? "" : "disabled"}>⬇ Baixar KML</button>
            <button class="btn btn-ghost" id="share">Copiar link</button>
          </div>
          <p class="sources">Fontes: ${esc((p.fontes || []).join(" · "))}</p>
        </section>
        <section class="panel map-panel">
          <div class="row" style="display:flex;justify-content:space-between;align-items:center">
            <h3 style="margin:0">Polígono de localização</h3>
            <span class="pill pill-warn">${verts.length ? `${verts.length} vértices · WGS84` : "Sem geometria"}</span>
          </div>
          ${verts.length ? '<div id="map" role="img" aria-label="Mapa do polígono do processo"></div>' : '<div class="map-empty">Polígono não disponível no SIGMINE para este processo<br>(processos inativos não possuem geometria na base pública).</div>'}
          ${p.centroide ? `<div class="coords"><span>Centroide: ${p.centroide[1].toFixed(6)}, ${p.centroide[0].toFixed(6)}</span><a href="https://www.google.com/maps?q=${p.centroide[1]},${p.centroide[0]}" target="_blank" rel="noopener">Abrir no Google Maps ↗</a></div>` : ""}
        </section>
      </div>`;

    if (back) $("#back").addEventListener("click", () => history.back());
    $("#dlPdf").addEventListener("click", (e) => withBusy(e.currentTarget, () => download(`/api/pdf?numero=${encodeURIComponent(p.processo)}`, `${fileBase(p.processo)}.pdf`)));
    $("#dlKml").addEventListener("click", (e) => withBusy(e.currentTarget, () => download(`/api/kml?numero=${encodeURIComponent(p.processo)}`, `${fileBase(p.processo)}.kml`)));
    $("#share").addEventListener("click", async () => {
      const url = `${location.origin}${location.pathname}#processo=${encodeURIComponent(p.processo)}`;
      try { await navigator.clipboard.writeText(url); toast("Link copiado!"); } catch { toast(url); }
    });
    if (verts.length) drawMap(p);
  }

  async function withBusy(b, fn) {
    const html = b.innerHTML;
    b.disabled = true; b.innerHTML = '<span class="spin"></span> Gerando…';
    try { await fn(); toast("Download iniciado."); } catch (ex) { toast(ex.message, true); } finally { b.disabled = false; b.innerHTML = html; }
  }

  function drawMap(p) {
    if (typeof L === "undefined") { $("#map").outerHTML = '<div class="map-empty">Não foi possível carregar o mapa.</div>'; return; }
    if (map) { map.remove(); map = null; }
    map = L.map("map", { scrollWheelZoom: false });
    const sat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19, attribution: "Imagens © Esri" });
    const osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" });
    sat.addTo(map);
    L.control.layers({ "Satélite": sat, "Mapa": osm }, null, { position: "topright" }).addTo(map);
    const poly = L.polygon(p.poligonos.map((r) => r.map(([x, y]) => [y, x])), { color: "#F9B122", weight: 3, fillColor: "#5FB8B3", fillOpacity: 0.35 }).addTo(map);
    poly.bindPopup(`<b>${esc(p.processo)}</b><br>${esc(p.titular)}<br>${esc(p.fase)} · ${esc(p.substancia)}<br>${fmtArea(p.area_ha)}`);
    map.fitBounds(poly.getBounds(), { padding: [24, 24] });
    L.control.scale({ imperial: false }).addTo(map);
  }

  /* ---------------- roteamento por hash (links compartilháveis) ---------------- */
  function route() {
    const h = new URLSearchParams(location.hash.slice(1));
    for (const m of Object.keys(MODES)) {
      if (h.has(m)) {
        const v = h.get(m);
        if (mode !== m) setMode(m, true);
        input.value = v;
        if (m === "processo" && h.get("from") === "list" && lastList) {
          busy(true); skeleton(1);
          api(`/api/processo?numero=${encodeURIComponent(v)}`)
            .then((p) => { renderDetail(p, true); results.scrollIntoView({ behavior: "smooth", block: "start" }); })
            .catch((ex) => { empty("Não foi possível concluir a consulta", ex.message, "!"); toast(ex.message, true); })
            .finally(() => busy(false));
          return;
        }
        if (m !== "processo" && lastList && lastList.mode === m && lastList.query === v) return renderList(lastList);
        return run(m, v);
      }
    }
    results.innerHTML = "";
  }
  window.addEventListener("hashchange", route);
  route();
})();
