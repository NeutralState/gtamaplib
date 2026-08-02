import json
import os
import sys

import numpy as np

RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"


dirname = "ambrosia"
panorama_hfov_range = np.arange(44.5, 51.51, 0.5)
postcard_hfov_delta_range = np.arange(-2.0, 2.1, 0.5)
if len(sys.argv) > 1 and sys.argv[1] == "--highres":
    panorama_hfov_range = np.arange(50.5, 51.01, 0.1)
    postcard_hfov_delta_range = np.arange(0.9, 1.41, 0.1)

loss, p, pc = [], [], []
for hfov in panorama_hfov_range:
    p.append(hfov)
    for postcard_hfov_delta in postcard_hfov_delta_range:
        postcard_hfov = hfov + postcard_hfov_delta
        pc.append(postcard_hfov_delta)
        losses = []
        for json_filename in [
            f"{dirname}/panorama {hfov=:.3f}.json",
            f"{dirname}/bikers {hfov=:.3f}.json",
            f"{dirname}/postcard {hfov=:.3f},{postcard_hfov:.3f}.json",
            f"{dirname}/fires {hfov=:.3f},{postcard_hfov:.3f}.json"
        ]:
            if os.path.exists(json_filename):
                with open(json_filename) as f:
                    l = json.load(f)["loss"]
                losses.append(l)
        loss.append(sum(losses)/len(losses) if len(losses) == 4 else 0)

sorted_loss = sorted(enumerate(loss), key=lambda x: x[1])
COLOR = {
    i: CYAN if v < 3 else GREEN if v < 4 else YELLOW if v < 8 else RED if v < 16 else MAGENTA if v < 32 else BLUE if v < 64 else CYAN
    for x, (i, v) in enumerate(sorted_loss)
}

rows, cols = len(panorama_hfov_range), len(postcard_hfov_delta_range)
print()
print(f"   mean" + "".join([f"  pc {pc[c]:+3.1f}" for c in range(cols)]))
for r in range(rows):
    print(f" p {p[r]:4.1f}", end="")
    for c in range(cols):
        i = r * cols + c
        v = f"{loss[i]:7.3f}" if loss[i] > 0 else 7 * " "
        print(f"  {COLOR[i]}{v}{RESET}", end="")
    print()

print()