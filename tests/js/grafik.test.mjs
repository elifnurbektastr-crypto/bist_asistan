// Grafik bileşeninin saf fonksiyonları: node --test tests/js/grafik.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const g = require("../../app/bilesenler/grafik/grafik.js");

test("temizle: izinsiz tür ve alanları atar", () => {
  const girdi = [
    { type: "line", x0: "2024-01-02", x1: "2024-02-01", y0: 10, y1: 12, yref: "y",
      line: { color: "#6250d6", width: 99, dash: "dash", bilinmeyen: 1 }, label: { text: "<img src=x onerror=alert(1)>" } },
    { type: "circle", x0: 1 },
    { type: "path" },                                   // path alanı yok
    null, "metin",
    { type: "rect", x0: { kotu: 1 }, y0: 5, fillcolor: "rgba(0,0,0,0.1)" },
  ];
  const sonuc = g.temizle(girdi);
  assert.equal(sonuc.length, 2);
  assert.equal(sonuc[0].label, undefined);              // etiket metni (olası HTML) atılır
  assert.deepEqual(sonuc[0].line, { color: "#6250d6", width: 8, dash: "dash" });
  assert.equal(sonuc[1].x0, undefined);                 // nesne olan koordinat atılır
  assert.ok(sonuc.every((c) => c.editable === true));
});

test("temizle: dizi olmayan girdi ve üst sınır", () => {
  assert.deepEqual(g.temizle({ type: "line" }), []);
  assert.deepEqual(g.temizle(undefined), []);
  const cok = Array.from({ length: g.MAKS_CIZIM + 50 }, () => ({ type: "line", x0: 1, y0: 1 }));
  assert.equal(g.temizle(cok).length, g.MAKS_CIZIM);
});

test("eksenSuz: kapalı paneldeki çizimler saklanır ama gösterilmez", () => {
  const layout = { yaxis: {}, yaxis2: {} };            // fiyat + hacim, RSI paneli kapalı
  const cizimler = [{ yref: "y" }, { yref: "y3" }, { yref: "y2 domain" }, {}, { yref: "paper" }];
  const { goster, sakla } = g.eksenSuz(cizimler, layout);
  assert.equal(goster.length, 4);
  assert.deepEqual(sakla, [{ yref: "y3" }]);
});

test("yatayCizgi ve depo anahtarı", () => {
  const c = g.yatayCizgi(245.5);
  assert.equal(c.y0, 245.5); assert.equal(c.y1, 245.5);
  assert.equal(c.xref, "paper"); assert.equal(c.yref, "y");
  assert.equal(g.depoAnahtari("thyao"), "bist_asistan_cizim_THYAO");
});
