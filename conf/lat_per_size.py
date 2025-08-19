import glob
import re
import pandas as pd
import matplotlib.pyplot as plt
import argparse
import numpy as np
import os

file_home = "./"
file_list = ["AppRAN_5", "PF_5", "PDU_5", "GBR_5", "NVS_5"]
bin_n = 20

fig_cdf, ax_cdf = plt.subplots()
fig_t, ax_t = plt.subplots()

for typ in file_list:
    file_path = f"{file_home}{typ}.csv"
    f = pd.read_csv(file_path)

    fig, ax = plt.subplots()
    fig.suptitle(file_path)

    min_s = np.min(f["ADU_size"])
    max_s = np.max(f["ADU_size"])

    f["bin_size"] = f["ADU_size"] - min_s
    step = (max_s - min_s) / bin_n

    for s in range(bin_n):
        f_bin = f[(f["bin_size"] <= (s + 1) * step) & (f["bin_size"] > s * step)]
        print(f"f_bin length{len(f_bin)}")
        ax.boxplot(f_bin["end_time"] - f_bin["start_time_c"],
                   positions=[s], showfliers=False, whis=[0.01, 0.99])
    ax.axhline(y=0.1,xmin=0,xmax=3,c="blue",linewidth=0.5,zorder=0)
    
    # --- CDF ---
    latency = f["end_time"] - f["start_time_c"]
    ax_t.plot(latency)
    latency = latency.sort_values()
    y = np.linspace(0, 1, len(latency), endpoint=False)
    ax_cdf.plot(latency, y, label=typ)

    ax.set_ylim(0, 0.4)

# --- Legend and label for CDF plot ---
ax_cdf.set_xlabel("Latency")
ax_cdf.set_ylabel("CDF")
ax_cdf.set_ylim(0, 1)
ax_cdf.legend(title="Schemes")
fig_cdf.suptitle("Latency CDF")

plt.show()

