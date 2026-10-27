# A3-Scanner unter Linux

Harte Voraussetzung aus Plan 2.1: Der Scanner muss unter Linux (SANE) laufen. Geprüft am 27.10.2026 direkt in den
Gerätebeschreibungen des SANE-Projekts (`doc/descriptions/*.desc`) und in Hersteller-/Forenquellen.

| Modell | A3 | Linux-Status | Quelle | Bewertung |
| --- | --- | --- | --- | --- |
| **Epson Expression 12000XL** | ja | SANE `epson2`: **complete** | SANE epson2.desc | ✅ empfohlen, aber nicht mehr im Handel → gebraucht |
| **Epson Expression 11000XL** | ja | SANE `epson2`: **good** | SANE epson2.desc | ✅ gebraucht |
| **Epson Expression 13000XL Pro** | ja | Epson nennt SANE (Linux) als Treiber; nicht in der SANE-Liste | Epson EU, Bechtle | 🟡 neu, ca. 4.300 € netto; vor Kauf testen |
| Epson WorkForce DS-60000 | ja (+ADF) | SANE `epsonds`: good | SANE epsonds.desc | 🟡 Dokumentenscanner, eingestellt |
| Epson WorkForce DS-50000 | ja | SANE `epsonds`: untested | SANE epsonds.desc | ⚠️ ungetestet, eingestellt |
| Avision FB6080E | ja | SANE `avision`: complete | SANE avision.desc | 🟡 alt, schwer erhältlich |
| Avision FB6280E | ja | SANE `avision`: **basic** | SANE avision.desc | ⚠️ nur Grundfunktionen |
| **Plustek OpticSlim 1180** | ja | **nicht in SANE**; Plustek nennt nur Windows/macOS, Linux nur für Systemintegratoren | Fedora-Forum | ❌ nicht kaufen (entgegen Plan) |
| Plustek OpticSlim 1680 | ja | nicht verifiziert | – | ❌ ohne Test nicht kaufen |
| Epson Perfection V600 | nein (A4) | – | – | ❌ zu klein für Alben |

## Hinweise

- Ein Flachbett braucht pro Comic (zwei Seiten inkl. Umlegen) ca. 45–60 s (Schätzung). Für große Mengen ist eine
  Kamera-Station 3–4× schneller, siehe `future-improvements/001-skalierung-1-million-comics.md`.
- Franko-belgische Alben (ca. 22,5 × 29,7 cm) sind breiter als A4; ein A4-Scanner reicht deshalb nicht.
- Test nach dem Anschließen: `scanimage -L`, dann `comics-probe-scan` (Rolle `scanner`).

## Quellen

- SANE-Gerätelisten: [epson2.desc](https://gitlab.com/sane-project/backends/-/raw/master/doc/descriptions/epson2.desc),
  [epsonds.desc](https://gitlab.com/sane-project/backends/-/raw/master/doc/descriptions/epsonds.desc),
  [avision.desc](https://gitlab.com/sane-project/backends/-/raw/master/doc/descriptions/avision.desc),
  [sane-plustek](https://man.archlinux.org/man/extra/sane/sane-plustek.5.en)
- [Fedora-Forum: Plustek OpticSlim 1180 unter Linux](https://discussion.fedoraproject.org/t/connot-use-plustek-scanner-also-detected-by-sane-find-scanner/78395)
- [Epson Expression 13000XL Pro bei Bechtle](https://bechtle.com/fr-en/shop/epson-expression-13000xl-pro-scanner--4775017--p),
  [Epson Expression 12000XL Pro (EU)](https://www.epson.eu/en_EU/products/scanners/document-scanner/epson-expression-12000xl-pro/p/20977)
