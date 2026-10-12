# Viet Nam — LawCodex (Pháp luật Việt Nam)

The legislation of the Socialist Republic of Viet Nam in force, as plain Markdown, in
Vietnamese (the official language). Part of [LawCodex](https://github.com/LawCodex): one
repository per jurisdiction.

Texts are reproduced verbatim from official publications (Công báo — the Official Gazette — and
the Government portal). Nothing is translated or summarised. Where the National Assembly Office
(Văn phòng Quốc hội) or a ministry has published a **văn bản hợp nhất** (official consolidated
text) that covers the document, the consolidated text is used.

- Retrieved: **2026-10-12**
- In-force status: as recorded by the national legal database **vbpl.vn** on the retrieval date.

## Coverage

| Directory | Category | Files | of which consolidated (VBHN) |
| --- | --- | ---: | ---: |
| `hien-phap/` | Hiến pháp 2013 (Constitution, as amended by Nghị quyết 203/2025/QH15) | 1 | 1 |
| `bo-luat/` | Bộ luật (codes: Dân sự, Hình sự, Tố tụng dân sự, Tố tụng hình sự, Lao động, Hàng hải) | 6 | 4 |
| `luat/<year>/` | Luật (laws of the National Assembly, incl. amending laws) | 333 | 157 |
| `phap-lenh/` | Pháp lệnh (ordinances of the NA Standing Committee) | 32 | 4 |
| `nghi-quyet/<year>/` | Nghị quyết of the Quốc hội and of the Ủy ban Thường vụ Quốc hội | 259 | 16 |
| `nghi-dinh/<year>/` | Nghị định (Government decrees) | 1,856 | 175 |
| **Total** | | **2,487** | **357** |

Scope = every document of these types that vbpl.vn marks *Còn hiệu lực* (`InForce`) or
*Hết hiệu lực một phần* (`PartiallyInForce`) and for which an official text could be obtained:
987 constitution/code/law/ordinance/NA-resolution records and 2,543 decree records were in scope.

### Not covered / gaps

- **In-force documents without an obtainable text** (1,043): the official text is not published
  in Công báo online or on vanban.chinhphu.vn, or only as a scanned image / legacy-font
  (VNI/TCVN3) PDF that cannot be converted faithfully (no OCR is used):
  - Luật 11, Pháp lệnh 19 — mostly pre-1990 "không số" (unnumbered) acts still marked in force in
    vbpl.vn, plus a few scanned-only gazette issues (e.g. Luật Đấu giá tài sản 01/2016/QH14,
    Luật Tín ngưỡng, tôn giáo 02/2016/QH14, Luật 92/2025/QH15).
  - Nghị quyết 326 — 133 unnumbered (mostly historical, often non-normative, e.g. confirmation of
    deputies), 108 from before 2010, 85 from 2010 onwards (mostly not published in Công báo).
  - Nghị định 687 — 554 from before 2010, 95 unnumbered, 38 from 2010 onwards.
- **Repealed documents** (`NotInForce`) are not included.
- Resolutions of other bodies (Chính phủ, Hội đồng Thẩm phán…), decisions (Quyết định), circulars
  (Thông tư), joint circulars, local (provincial) documents and treaties are not included.
- **Images, signatures and scanned annexes** are not reproduced. Tables are kept as Markdown tables.
- Consolidated texts are only used when they can be verified to consolidate the document (the
  base document number must appear in the opening of the VBHN). Otherwise the original text as
  promulgated is given (`consolidated: false`); in that case later amendments are **not** applied —
  check the amending laws in the same repository.
- The vbpl.vn in-force flag is taken as-is; a few old documents it marks in force are probably
  obsolete in practice.

## Sources

| Source | Used for |
| --- | --- |
| **Cơ sở dữ liệu quốc gia về pháp luật** — https://vbpl.vn (Ministry of Justice) | List of central-government documents (sitemaps) and per-document metadata: type, number, date, issuing body and **legal force** (schema.org `Legislation` JSON-LD served on each document page). |
| **Công báo nước CHXHCN Việt Nam** — https://congbao.chinhphu.vn (Government Office) | Full texts: DOCX/DOC/PDF files of each document published in the Official Gazette, incl. văn bản hợp nhất (consolidated texts). |
| **Hệ thống văn bản, Cổng TTĐT Chính phủ** — https://vanban.chinhphu.vn | Fallback full texts (attached PDF/DOC) for documents not found in Công báo. |

Why not the full text from vbpl.vn: since its 2025 redesign vbpl.vn loads full texts in the
browser from an API host (`vbpl-bientap-gateway.moj.gov.vn`); `/api/` is disallowed by the
site's `robots.txt` and the gateway was not reachable from outside Viet Nam during retrieval.
The Quốc hội website (quochoi.vn) answers automated clients with a JavaScript cookie challenge,
which LawCodex does not circumvent, so it was not used. thuvienphapluat.vn and other commercial
mirrors were not used.

Every file's front matter records the exact Công báo / vanban.chinhphu.vn page (`source`), the
gazette issue (`gazette`), the format the text was converted from (`source_format`), and the
vbpl.vn record (`vbpl_url`).

## File format

```markdown
---
title: Luật Đầu tư số 143/2025/QH15
identifier: 143/2025/QH15
type: law                      # constitution | code | law | ordinance | resolution | decree
document_type: Luật            # Vietnamese document type
jurisdiction: vn
language: vi
issuer: Quốc hội
date: '2025-12-11'             # date of adoption / signature
effective: '2026-03-01'        # entry into force (from Công báo), when known
last_amended: '2026-09-23'     # date of the consolidated text, when one is used
consolidated: true
consolidated_text: 142/2026/VBHN-LQ-VPQH
status: in_force
legal_force: InForce           # vbpl.vn: InForce | PartiallyInForce
source: https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-142-2026-vbhn-lq-vpqh-470555.htm
source_format: docx
gazette: Công báo số 527-VBHN ngày 2026-09-25
vbpl_url: https://vbpl.vn/van-ban/chi-tiet/luat-dau-tu-so-143-2025-qh15--187601
retrieved: '2026-10-12'
---
```

Structure: *Phần* / *Chương* / *Mục* / *Tiểu mục* become Markdown headings (only the levels a
document actually uses), each *Điều* (article) is a heading at the next level. Footnotes of
consolidated texts (which state which amending act changed each provision) are kept as Markdown
footnotes (`[^fn12]`). Paragraph numbers such as `1.` are escaped (`1\.`) so Markdown does not
renumber them.

File names: `<type>-<number>-<title>.md`, lowercase ASCII, e.g.
`bo-luat/luat-45-2019-qh14-bo-luat-lao-dong.md`, `luat/2024/luat-31-2024-qh15-luat-dat-dai.md`,
`nghi-dinh/2020/nghi-dinh-15-2020-nd-cp-...md`. The year directory is the year of adoption.

## Licence

Legal normative documents are not protected by copyright in Viet Nam (Luật Sở hữu trí tuệ,
Article 15: "văn bản quy phạm pháp luật, văn bản hành chính, văn bản khác thuộc lĩnh vực tư
pháp và bản dịch chính thức của văn bản đó" are not objects of copyright protection). Công báo and
the Government portal ask that the source be cited when re-publishing ("Ghi rõ nguồn
'congbao.chinhphu.vn' / 'www.chinhphu.vn' khi phát hành lại thông tin từ các nguồn này"); every
file cites its source URL. The scripts in `scripts/` are released into the public domain.

## How to regenerate

Requires Python 3 with `requests lxml beautifulsoup4 pyyaml certifi` (`scripts/requirements.txt`),
`pdftotext` (poppler) and macOS `textutil` (used to read legacy `.doc` files). Raw downloads are
cached in `../_raw/vn/` (override with `LAWCODEX_RAW`); all requests identify as
`LawCodex/1.0 (+https://github.com/LawCodex)` and are rate-limited (`LAWCODEX_DELAY`, default 1 s).

```sh
cd scripts
python vn_vbpl_meta.py                     # vbpl.vn sitemaps + metadata/legal force (~10,700 pages)
python vn_cb_list.py quoc-hoi-c31 uy-ban-thuong-vu-quoc-hoi-c28 van-phong-quoc-hoi-c47 \
    luat-l13 phap-lenh-l14 van-ban-hop-nhat-l7 nghi-dinh-l1 nghi-quyet-l6 chinh-phu-c1
python vn_cp_list.py orggroupid=1 typegroupid=3 typegroupid=4   # vanban.chinhphu.vn listings
python vn_build.py laws                    # constitution, codes, laws, ordinances, NA resolutions
python vn_build.py decrees                 # government decrees
```

`scripts/extra-intermediates.pem` is the public "GlobalSign RSA OV SSL CA 2018" intermediate
certificate, which the Công báo CDN (`g7.cdnchinhphu.vn`) does not send; it is appended to the
certifi bundle so TLS verification stays on.
