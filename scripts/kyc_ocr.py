import json
import re
import sys
from pathlib import Path

import numpy as np
import pytesseract
from PIL import Image, ImageOps

docs = Path(sys.argv[1])
out = Path(sys.argv[2])


def clean(path):
    img = Image.open(path).convert("RGB")
    a = np.asarray(img).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    pink = (r - g > 25) & (r - b > 15)
    gray = np.asarray(ImageOps.grayscale(img)).astype(int)
    gray[pink] = 255
    bw = np.where(gray < 150, 0, 255).astype(np.uint8)
    im = Image.fromarray(bw)
    if im.width < 1600:
        im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
    return im, img.size


results = {}
for p in sorted(docs.glob("K*.png")):
    im, size = clean(p)
    raw = pytesseract.image_to_string(Image.open(p), config="--psm 4")
    txt = pytesseract.image_to_string(im, config="--psm 4")
    data = pytesseract.image_to_data(im, config="--psm 4", output_type=pytesseract.Output.DICT)
    confs = [int(c) for c, w in zip(data["conf"], data["text"]) if w.strip() and int(c) >= 0]
    results[p.name] = {"size": size, "text": txt, "raw_text": raw, "mean_conf": round(float(np.mean(confs)), 1) if confs else None,
                       "low_conf_words": sum(c < 60 for c in confs), "words": len(confs)}
    print(f"== {p.name} {size} conf={results[p.name]['mean_conf']} low={results[p.name]['low_conf_words']}/{len(confs)}")
    print(txt.strip())
out.write_text(json.dumps(results, indent=1))
