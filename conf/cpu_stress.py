# cpu_stress.py
import threading
import time

def cpu_burn():
    while True:
        pass  # 무한 루프로 CPU 점유

threads = []
num_threads = 8  # CPU 코어 수 또는 원하는 개수로 조절

for _ in range(num_threads):
    t = threading.Thread(target=cpu_burn)
    t.start()
    threads.append(t)

time.sleep(60)  # 60초 동안 유지 (필요 시 조절)

# # mem_stress.py
# import time

# memory_hog = []

# try:
#     for _ in range(1000):
#         memory_hog.append('X' * 10**6)  # 약 1MB 문자열 할당
#         time.sleep(0.1)  # 천천히 증가 (0.1초마다 1MB)
# except KeyboardInterrupt:
#     print("Stopped by user.")