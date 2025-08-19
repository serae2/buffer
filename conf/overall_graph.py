import glob
import re
import pandas as pd
import matplotlib.pyplot as plt
import argparse
import numpy as np
import os

parser = argparse.ArgumentParser()
parser.add_argument("--type", type=str, required=True, help="Log file identifier ")
parser.add_argument("--ue", type=int, required=True, help="numberofUE ")
args = parser.parse_args()
type = args.type
ue = args.ue

log_dir = "./"

# 패턴 정의
pattern = re.compile(
    r"\[\[AppRAN\]\],ue_ip,([\d\.]+),port,(\d+),drb,(\d+),lcid,(\d+),req_idx,(\d+),"
    r"(start_time|end_time),(\d+\.\d+),ADU_size,(\d+),latency_req,(\d+)"
)

# 로그 파서 함수
def parse_log(file_path):
    rows = []
    with open(file_path, 'r') as f: #, encoding='utf-8') as f:
        for line in f:
            m = pattern.search(line)
            if m:
                ue_ip, port, drb, lcid, req_idx, time_type, timestamp, adu_size, latency = m.groups()
                key = (ue_ip, int(port), int(drb), int(lcid))
                rows.append({
                    "key": key,
                    "req_idx": int(req_idx),
                    "time_type": time_type,
                    "timestamp": float(timestamp),
                    "ADU_size": adu_size,
                    "deadline": latency
                })
    return pd.DataFrame(rows)

# 경로 정의
log1_path = f"{log_dir}UE{ue}/{type}/mec.txt"  # C log (1st)
log2_path = f"{log_dir}UE{ue}/{type}/desc.txt"    # Python start_time (2nd)
client_log_paths = sorted(glob.glob(os.path.join(log_dir, f"UE{ue}/{type}/client_*.txt")))


# client는 여러 개
#client_log_paths = sorted(glob.glob(os.path.join(log_dir, f"UE{ue}/client_{type}_*.txt")))


# 로그 읽기
df1 = parse_log(log1_path)
df2 = parse_log(log2_path)
#df3 = parse_log(log3_path)
# client 여러 파일 읽어서 concat
df3_list = [parse_log(f) for f in client_log_paths]
df3 = pd.concat(df3_list, ignore_index=True)

# 각각 분리 및 이름 바꾸기
df1 = df1[df1.time_type == "start_time"].rename(columns={"timestamp": "start_time_c"})
df2 = df2[df2.time_type == "start_time"].rename(columns={"timestamp": "start_time_py"})
df3 = df3[df3.time_type == "end_time"].rename(columns={"timestamp": "end_time"})

# 각 df에서 time_type 제거
df1 = df1.drop(columns=["time_type"])
df2 = df2.drop(columns=["time_type"])
df3 = df3.drop(columns=["time_type"])

# 조인: key + req_idx 기준
merged = df1.merge(df2, on=["key", "req_idx"], how='inner')
merged = merged.merge(df3, on=["key", "req_idx"], how='inner')

merged.to_csv(f"{log_dir}{type}_{ue}.csv")

print(f"{type}_{ue} at {log_dir}: lengh of files {len(df1)} - {len(df2)} - {len(df3)} to {len(merged)}")
