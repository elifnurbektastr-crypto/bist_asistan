/*
 * BIST grafik bileşeni (Streamlit özel bileşeni, derleme gerektirmez).
 * Python mum grafiğini ve indikatörleri Plotly JSON olarak gönderir; bu dosya çizer,
 * çizim araçlarını yönetir ve kullanıcının çizimlerini TARAYICIDA (localStorage) hisse bazında saklar.
 * Çizimler sunucuya gönderilmez: her kullanıcı sadece kendi çizimlerini görür.
 */
"use strict";

// ---------------------------------------------------------------------------
// Saf fonksiyonlar (Node ile test edilir: tests/js/grafik.test.mjs)
// ---------------------------------------------------------------------------

const IZINLI_TURLER = ["line", "rect", "path"];
const IZINLI_ALANLAR = ["type", "x0", "x1", "y0", "y1", "xref", "yref", "path", "line",
                        "fillcolor", "opacity", "editable", "layer"];
const MAKS_CIZIM = 2000;   // pratikte sınırsız; tarayıcı depolamasını korumak için üst sınır

function depoAnahtari(kod) {
  return "bist_asistan_cizim_" + String(kod).toUpperCase();
}

/** Dışarıdan gelen (yüklenen ya da depodan okunan) çizimleri temizler: sadece izinli şekil alanları. */
function temizle(cizimler) {
  if (!Array.isArray(cizimler)) return [];
  const sonuc = [];
  for (const c of cizimler.slice(0, MAKS_CIZIM)) {
    if (!c || typeof c !== "object" || !IZINLI_TURLER.includes(c.type)) continue;
    const temiz = {};
    for (const alan of IZINLI_ALANLAR) {
      if (c[alan] === undefined) continue;
      const deger = c[alan];
      if (alan === "line") {
        if (deger && typeof deger === "object") {
          temiz.line = {};
          if (typeof deger.color === "string" && deger.color.length < 40) temiz.line.color = deger.color;
          if (typeof deger.width === "number") temiz.line.width = Math.min(Math.max(deger.width, 0.5), 8);
          if (typeof deger.dash === "string" && deger.dash.length < 20) temiz.line.dash = deger.dash;
        }
      } else if (["x0", "x1", "y0", "y1"].includes(alan)) {
        if (typeof deger === "number" || typeof deger === "string") temiz[alan] = deger;
      } else if (typeof deger === "string" && deger.length < 20000) {
        temiz[alan] = deger;
      } else if (typeof deger === "number" || typeof deger === "boolean") {
        temiz[alan] = deger;
      }
    }
    if (temiz.type === "path" && typeof temiz.path !== "string") continue;
    temiz.editable = true;
    sonuc.push(temiz);
  }
  return sonuc;
}

/** Grafikte var olan y eksenleri ('y', 'y2', ...). */
function gecerliEksenler(layout) {
  const eksenler = new Set(["paper"]);
  for (const anahtar of Object.keys(layout || {})) {
    const m = anahtar.match(/^yaxis(\d*)$/);
    if (m) eksenler.add("y" + m[1]);
  }
  return eksenler;
}

/** Bu grafikte gösterilemeyecek çizimleri ayırır (ör. RSI paneli kapalıyken RSI'a yapılan çizim). */
function eksenSuz(cizimler, layout) {
  const eksenler = gecerliEksenler(layout);
  const goster = [], sakla = [];
  for (const c of cizimler) {
    const y = String(c.yref || "y").replace(" domain", "");
    (eksenler.has(y) ? goster : sakla).push(c);
  }
  return { goster, sakla };
}

/** Yatay destek/direnç çizgisi: fiyat ekseninde, tüm genişlikte. */
function yatayCizgi(y) {
  return { type: "line", xref: "paper", x0: 0, x1: 1, yref: "y", y0: y, y1: y, editable: true,
           line: { color: "#6250d6", width: 2, dash: "dash" } };
}

if (typeof module !== "undefined") {
  module.exports = { temizle, gecerliEksenler, eksenSuz, yatayCizgi, depoAnahtari, MAKS_CIZIM };
}

// ---------------------------------------------------------------------------
// Tarayıcı tarafı
// ---------------------------------------------------------------------------

if (typeof window !== "undefined" && typeof document !== "undefined") {
  const div = document.getElementById("grafik");
  const durumYazi = document.getElementById("durum");
  const ipucu = document.getElementById("ipucu");
  let kod = null, mod = "pan", dinleyicilerHazir = false, ciziliyor = false, gizliCizimler = [];

  const IPUCLARI = {
    pan: "Grafiği sürükleyerek kaydırın, fare tekerleğiyle yakınlaştırın. Bir çizime tıklayarak seçebilir ve sürükleyebilirsiniz.",
    drawline: "Başlangıç noktasından bitiş noktasına sürükleyin.",
    yatay: "Fiyat grafiğinde istediğiniz seviyeye tıklayın.",
    drawrect: "Bölgenin bir köşesinden karşı köşesine sürükleyin.",
    drawopenpath: "Basılı tutup serbestçe çizin.",
  };
  // Türkçe tarih ve sayı biçimi (plotly.min.js içinde Türkçe yerel ayar paketi yok)
  Plotly.register({
    moduleType: "locale", name: "tr",
    dictionary: { "Autoscale": "Otomatik ölçek", "Zoom in": "Yakınlaştır", "Zoom out": "Uzaklaştır",
                  "Reset axes": "Eksenleri sıfırla", "Pan": "Kaydır", "Zoom": "Yakınlaştır",
                  "Erase active shape": "Seçili çizimi sil" },
    format: {
      days: ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"],
      shortDays: ["Paz", "Pzt", "Sal", "Çar", "Per", "Cum", "Cmt"],
      months: ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"],
      shortMonths: ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"],
      date: "%d.%m.%Y", decimal: ",", thousands: ".",
    },
  });
  const CONFIG = { displaylogo: false, responsive: true, scrollZoom: true, locale: "tr",
                   modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d", "toImage"],
                   modeBarButtonsToAdd: ["eraseshape"] };

  const gonder = (type, veri = {}) => window.parent.postMessage({ isStreamlitMessage: true, type, ...veri }, "*");
  const yukseklikBildir = () => {
    const grafikY = (div.layout && div.layout.height) || div.offsetHeight;
    gonder("streamlit:setFrameHeight", { height: div.offsetTop + grafikY + 12 });
  };
  const durum = (metin) => { durumYazi.textContent = metin; };

  function oku(k) {
    try { return temizle(JSON.parse(localStorage.getItem(depoAnahtari(k)) || "[]")); }
    catch (e) { return []; }
  }
  function yaz(k, cizimler) {
    try {
      localStorage.setItem(depoAnahtari(k), JSON.stringify(cizimler));
      durum(cizimler.length ? `${cizimler.length} çizim kaydedildi (bu tarayıcıda)` : "Çizim yok");
    } catch (e) {
      durum("Kaydedilemedi: tarayıcı depolaması kapalı ya da dolu.");
    }
  }
  function kaydet() {
    if (kod === null || ciziliyor) return;
    yaz(kod, temizle((div.layout && div.layout.shapes) || []).concat(gizliCizimler));
  }

  function modSec(yeni) {
    mod = yeni;
    document.querySelectorAll("button[data-mod]").forEach((b) => {
      b.classList.toggle("aktif", b.dataset.mod === yeni);
      b.setAttribute("aria-pressed", b.dataset.mod === yeni);
    });
    ipucu.textContent = IPUCLARI[yeni] || "";
    if (div.layout) Plotly.relayout(div, { dragmode: yeni === "yatay" ? "pan" : yeni });
  }

  function tiklandi(olay) {
    if (mod !== "yatay" || !olay.event) return;
    const tam = div._fullLayout, ya = tam.yaxis, kutu = div.getBoundingClientRect();
    const piksel = olay.event.clientY - kutu.top - ya._offset;
    if (piksel < 0 || piksel > ya._length) return;   // sadece fiyat panelinde
    const y = ya.p2d(piksel);
    Plotly.relayout(div, { shapes: ((div.layout.shapes) || []).concat([yatayCizgi(Number(y.toFixed(4)))]) });
  }

  function relayoutOldu(olay) {
    if (Object.keys(olay || {}).some((a) => a.startsWith("shapes"))) kaydet();
  }

  function ciz(args) {
    const yeniKod = String(args.kod || "").toUpperCase();
    const sekil = args.sekil || { data: [], layout: {} };
    const layout = Object.assign({}, sekil.layout);
    const ayrim = eksenSuz(oku(yeniKod), layout);
    gizliCizimler = ayrim.sakla;
    layout.shapes = ayrim.goster;
    layout.dragmode = mod === "yatay" ? "pan" : mod;
    layout.autosize = true;
    div.style.height = (layout.height || 600) + "px";
    kod = yeniKod;
    ciziliyor = true;
    Plotly.react(div, sekil.data, layout, CONFIG).then(() => {
      ciziliyor = false;
      if (!dinleyicilerHazir) {
        div.on("plotly_relayout", relayoutOldu);
        div.on("plotly_click", tiklandi);
        dinleyicilerHazir = true;
      }
      const n = ayrim.goster.length + ayrim.sakla.length;
      durum(n ? `${n} kayıtlı çizim yüklendi` : "");
      yukseklikBildir();
    });
  }

  // Araç çubuğu
  document.querySelectorAll("button[data-mod]").forEach((b) => b.addEventListener("click", () => modSec(b.dataset.mod)));
  document.getElementById("sil").addEventListener("click", () => {
    const i = div._fullLayout ? div._fullLayout._activeShapeIndex : undefined;
    if (i === undefined || i === null || i < 0) { durum("Önce silmek istediğiniz çizime tıklayın."); return; }
    const sekiller = (div.layout.shapes || []).slice();
    sekiller.splice(i, 1);
    Plotly.relayout(div, { shapes: sekiller });
  });
  document.getElementById("temizle").addEventListener("click", () => {
    if (!window.confirm(`${kod} için tüm çizimler silinsin mi?`)) return;
    gizliCizimler = [];
    Plotly.relayout(div, { shapes: [] });
    yaz(kod, []);
  });
  document.getElementById("indir").addEventListener("click", () => {
    const icerik = { kod, surum: 1, olusturma: new Date().toISOString(), cizimler: oku(kod) };
    const url = URL.createObjectURL(new Blob([JSON.stringify(icerik, null, 2)], { type: "application/json" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: `cizimler_${kod}.json` });
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  });
  document.getElementById("yukle").addEventListener("change", (olay) => {
    const dosya = olay.target.files[0];
    if (!dosya) return;
    if (dosya.size > 2_000_000) { durum("Dosya çok büyük (en fazla 2 MB)."); return; }
    dosya.text().then((metin) => {
      const veri = JSON.parse(metin);
      const hedef = String(veri.kod || kod).toUpperCase();
      const cizimler = temizle(veri.cizimler);
      yaz(hedef, cizimler);
      if (hedef === kod) {
        const ayrim = eksenSuz(cizimler, div.layout);
        gizliCizimler = ayrim.sakla;
        Plotly.relayout(div, { shapes: ayrim.goster });
      }
      durum(`${hedef}: ${cizimler.length} çizim yüklendi`);
    }).catch(() => durum("Dosya okunamadı: geçerli bir çizim JSON'u değil.")).finally(() => { olay.target.value = ""; });
  });

  // Streamlit iletişimi
  window.addEventListener("message", (olay) => {
    if (olay.data && olay.data.type === "streamlit:render") ciz(olay.data.args || {});
  });
  window.addEventListener("resize", yukseklikBildir);
  ipucu.textContent = IPUCLARI.pan;
  gonder("streamlit:componentReady", { apiVersion: 1 });
}
