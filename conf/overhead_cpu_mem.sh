#!/bin/bash

logfile="/home/rana/serae/AppRAN/eval_0724/micro/mem_cpu/overhead.txt"
echo "Timestamp,Total_CPU(%),Total_MEM(%),Total_RSS(KB),Total_VSZ(KB)" > "$logfile"

echo "Logging sum of CPU and memory usage for cset shield processes..."
echo "Writing to $logfile"
echo "Press Ctrl+C to stop."

while true; do
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    total_cpu="0"
    total_mem="0"
    total_rss=0
    total_vsz=0

    # Get PIDs from cpuset
    pids=$(cat /sys/fs/cgroup/cpuset/user/tasks)

    for pid in $pids; do
        if [ -d "/proc/$pid" ]; then
            stats=$(ps -p $pid -o %cpu,%mem,rss,vsz --no-headers 2>/dev/null | awk '{print $1, $2, $3, $4}')
            read cpu mem rss vsz <<< "$stats"

            # 기본값 설정 (빈 값 방지)
            cpu=${cpu:-0}
            mem=${mem:-0}
            rss=${rss:-0}
            vsz=${vsz:-0}

            # 숫자인지 확인 (정수/소수 모두 허용)
            if [[ $cpu =~ ^[0-9.]+$ ]]; then
                total_cpu=$(echo "$total_cpu + $cpu" | bc)
            fi
            if [[ $mem =~ ^[0-9.]+$ ]]; then
                total_mem=$(echo "$total_mem + $mem" | bc)
            fi
            if [[ $rss =~ ^[0-9]+$ ]]; then
                total_rss=$((total_rss + rss))
            fi
            if [[ $vsz =~ ^[0-9]+$ ]]; then
                total_vsz=$((total_vsz + vsz))
            fi
        fi
    done

    echo "$timestamp,$total_cpu,$total_mem,$total_rss,$total_vsz" >> "$logfile"
    sleep 1
done
