# Third-Party Notices

The self-contained Archify HTML viewers in this directory include software generated from Archify. Archify is not a runtime dependency of the Whole Home Agent Python package.

## Archify

MIT License

- Copyright (c) 2026 tt-a1i (Archify)
- Copyright (c) 2025 Cocoon AI (original "architecture-diagram-generator")

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Optional video-development dependencies

These packages are installed only through the `video` optional extra and are not vendored in this repository. Exact artifacts and hashes are recorded in `uv.lock`.

- [PyAV](https://pypi.org/project/av/) 18.1.0 — BSD-3-Clause; published wheels bundle FFmpeg libraries whose applicable notices remain with that distribution.
- [NumPy](https://numpy.org/) — BSD-3-Clause.
- [Pillow](https://python-pillow.github.io/) — HPND.

The project-generated replay under `examples/media/generated` is separately marked `CC0-1.0` in its manifest and directory README.

## Optional model-candidate dependency

- [RF-DETR](https://pypi.org/project/rfdetr/1.9.4/) 1.9.4 — Apache-2.0 for the reviewed Nano through Large core package and weights. This project permits only the reviewed Nano and Small variants at its closed adapter boundary and does not include Plus, XL, 2XL, or model weights. One ignored local Small checkpoint was used for the bounded M12 development screen; it is not distributed.

RF-DETR is resolved only through the `rf-detr` optional extra. No third-party model weights are committed or distributed by this repository.

## Optional public indoor evaluation data

- [EPIC-KITCHENS VISOR](https://epic-kitchens.github.io/VISOR/site) — CC BY-NC 4.0,
  used only as a separately downloaded, local, non-commercial D0 method screen. The
  repository contains source URLs, hashes, conversion code, and derived bounded
  findings; it contains no VISOR images, annotations, or archives.

The upstream dataset requires attribution, a license link, and change indication, and
prohibits commercial use under that license. This repository does not grant broader
rights or redistribute the dataset.

- [VOST](https://www.vostdataset.org/data.html) — CC BY-NC-SA 4.0, used only as a
  separately downloaded, local, non-commercial consecutive-frame motion screen. The
  source sequences are credited upstream to Ego4D and EPIC-KITCHENS; VOST requests that
  publications cite VOST, Ego4D, and EPIC-KITCHENS. The repository includes an exact
  range-acquisition manifest, adapter, and derived bounded metrics, but no VOST image,
  mask, video, split, README, or license bytes.

VOST attribution, non-commercial, ShareAlike, license-link, and change-indication terms
continue to apply to the dataset and distributed adapted material. The repository's MIT
license applies only to original project code and documentation and grants no broader
rights over VOST content.

## Optional paired detector baseline

- [torchvision](https://github.com/pytorch/vision/tree/v0.26.0) 0.26.0 — BSD-3-Clause.
  The local screen uses official SSDLite320 MobileNetV3 Large COCO V1 and RetinaNet
  ResNet50 FPN v2 COCO V1 weights from `download.pytorch.org`.

Neither PyTorch, torchvision, nor model weights are installed by the default package or
committed to this repository. Their exact source URLs, sizes, and hashes are recorded in
the frozen baseline config. Upstream model/data terms continue to apply.

## Optional demo dependency

- [Streamlit](https://pypi.org/project/streamlit/1.62.0/) 1.62.0 — Apache-2.0; used only by the local presentation app in the `demo` extra.

Transitive demo artifacts and hashes are recorded in `uv.lock`; they are not vendored in this repository.
