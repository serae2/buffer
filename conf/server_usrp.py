import multiprocessing as mp
import socket
import struct
import time
import pickle
import os
import sys
import argparse
import threading
import fcntl
import array
#import psutil
import random
import queue
import csv
import numpy as np
import math

random.seed(42)

# ADU_header_t struct
ADU_HEADER_FORMAT = 'IIHHiici'
ADU_HEADER_SIZE = struct.calcsize(ADU_HEADER_FORMAT)

SERVER_PORT = 8080
INT_INF = 1e8

num_client = 0
client_sockets = []
client_processes = []
server_sockets = []

task_queues = []

LAT_LIST = []


UE_info = {}

send_lock = threading.Lock()

def get_interval(baseline, req_type = 'P', REQ_P = 4):
    
    now = time.time() * 1000  # 현재 시간 (ms 단위)
    interval = 0

    if req_type == "P":
        # periodic
        return baseline + 1/REQ_P*1000
    if req_type == "E":
        # exponential = poisson
        return baseline + random.expovariate(REQ_P) * 1000
    if req_type == "L":
        # lognormal: burst traffic
        return baseline + min(random.lognormvariate(math.log(1/REQ_P), 1.5), 0.25) * 1000
    print("Error: Invalid req_type. Please select traffic pattern among 'P', 'E', or 'L'.")
    sys.exit(1)
    

def generate_random_data(size):
    return bytes(random.choices(b'ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=int(size)))

def read_csv(file_path_idx=1, field_index = 1):
    sizes = []
    if file_path_idx == 1:
        file_path = "/home/rana/serae/AppRAN/ADU_data/VR_rec_room.csv"
    
    with open(file_path, 'r') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # 첫 번째 라인(헤더) 건너뜀
        for row in reader:
            try:
                sizes.append(int(row[field_index]))
            except (ValueError, IndexError):
                continue
    return sizes


def server_socket(req_type = "P", interval = 4, scaling = 1):
    global num_client
    global server_sockets
    global UE_info
    global task_queues  # Shared queue for all clients
    n_ue = 0
    
    while(True):
        # make server socket to connect
        server_ip = '10.45.0.1'
        server_port = SERVER_PORT
        
        print(f"{len(server_sockets)}-th server is bind in {server_ip}:{server_port}", flush=True)
        
        while(True):
          try:
            _UE_ip = int(input("Enter client ip, form of 10.45.0.x: "))
            break
          except:
            continue
        
        if _UE_ip < 0:
            break
        task_queue_ue = mp.Queue()
        
        n_ue += 1
        task_queues.append(task_queue_ue)
        
        while True:
            
            while True:
              try:
                UE_port = int(input("Enter UE port: ")) + 9000
                break
              except:
                continue
                
            if UE_port - 9000 < 0: break
            UE_ip = f"10.45.0.{_UE_ip}"
            
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
            # turn server socket in any available port
            while True:
                try:
                    server_socket.bind((server_ip, server_port))
                    break
                except OSError:
                    server_port += 1
                    
            server_sockets.append(server_socket)
        
            server_socket.settimeout(2)
            error = server_socket.connect_ex((UE_ip, UE_port))
            if error:
                print(f"error occurs {error}")
                continue
            else:
                print(f"connect estabilishes to {UE_ip}:{UE_port} from {server_ip}:{server_port}")
                server_socket.settimeout(None)
         
            # task_queues[num_client] = queue.Queue()  

            p = mp.Process(
                target=server_thread,
                args=(server_socket, server_ip, server_port, num_client, req_type, interval, scaling, task_queue_ue)
            )
            client_processes.append(p)

            UE_info[num_client] = {"ip": UE_ip, "port": UE_port}
            
            num_client += 1
    
    size_list = read_csv(file_path_idx=1, field_index=1)[:4000]  # Read the task sizes
    print(f"max: {np.max(size_list)}\navg: {np.mean(size_list)}")

    input()

    base_time = time.time() * 1000 + 1000 # Global reference time
    for task_queue in task_queues:
        start_idx = random.randint(0, len(size_list))
        next_time = base_time  # Initialize the first task time
        for idx in range(100):# range(1000):
            size = size_list[(idx + start_idx) % len(size_list)] # / scaling # No scaling twice
            next_time = get_interval(next_time, req_type, interval)
            task_queue.put((size, next_time, idx))
        #task_queue.put((size, next_time, idx))

    print("connection is end, connected UE is")
    print(UE_info)

    for p in client_processes:
        p.start()

# def send_adu_descriptor(ue_ip_str: str, port, adu_size: int, latency: int, req_idx: int):
#     SOCKET_PATH = "/tmp/descriptor.sock"
#     try:
#         sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
#         msg_type = 4
#         ue_ip_int = struct.unpack("!I", socket.inet_aton(ue_ip_str))[0]
#         packed = struct.pack("!BIHIII", msg_type, ue_ip_int, port, adu_size, latency, req_idx)
#         sock.sendto(packed, SOCKET_PATH)
#         sock.close()
#     except Exception as e:
#         print(f"[WARN] Failed to send ADU to descriptor: {e}")

# server-clinet thread
def server_thread(server_socket,  server_ip, server_port, rnti, req_type, interval, scaling, task_queue):
    global LAT_LIST
    # server thread with mp.queue
    
    # size_list = read_csv(file_path_idx=1, field_index = 1)
    #task_queue = queue.Queue()

    
    # base_time = time.time() * 1000  # 기준 시간
    # next_time = base_time  # 다음 전송 시간 초기화


    # for idx, size in enumerate(size_list): 
    #     count += 1
    #     next_time = get_interval(next_time, req_type, interval)
    #     task_queue.put((size, next_time, count))
    while True:
        if not task_queue.empty():
            size, target_time, req_idx = task_queue.get()
            req_idx = req_idx + 1
            size = size * scaling
            print(f"{rnti}: Scheduled task {req_idx}: size={size}, target_time={target_time}")
        else:
            break
        
        # Wait until the scheduled target time
        now_time = time.time() * 1000  # Current time in milliseconds
        sleep_time = (target_time - now_time) / 1000.0

        if sleep_time > 0:
            print(f"Sleeping for {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)  # Sleep until target time
        #while target_time > now_time:
        #    time.sleep(0.001)
        #    now_time = time.time() * 1000

        # 큐의 작업을 순차적으로 처리
        data = generate_random_data(size)
        #ADU_size = sys.getsizeof(data)
        ADU_size = len(data) 
        #ADU_latency = int(random.choice([100,200,300]))
        #ADU_latency = 200 #int(random.choice([100, 200]))
        ADU_latency = int(random.choice(LAT_LIST))
        
        #print(f"ADU size and latency is {ADU_size} and {ADU_latency}")
        
        client_ip, client_port = server_socket.getpeername()
        
        start_time = time.time() * 1000

        #send_adu_descriptor(client_ip, client_port, ADU_size, int(max(min(ADU_latency + 2 * (target_time - start_time), INT_INF), 1)), req_idx)
        #print(f"send ADU info to descriptor with UE_IP {client_ip}, PORT {client_port}:: ADU size {ADU_size} latency {ADU_latency} idx {req_idx}")
        
        # make ADU header
        
        header = {
            'source_ip': struct.unpack("I", socket.inet_aton(server_ip))[0],
            'dest_ip': struct.unpack("I", socket.inet_aton(client_ip))[0],
            'source_port': server_port,
            'dest_port': client_port,
            'ADU_size': ADU_size,
            'ADU_latency': int(max(min(ADU_latency + 2 * (target_time - start_time), INT_INF), 1)),
            'qfi': b'\x01',
            'req_idx': req_idx
        }
        
        
        packed_header = struct.pack(
            ADU_HEADER_FORMAT,
            header['source_ip'],
            header['dest_ip'],
            header['source_port'],
            header['dest_port'],
            header['ADU_size'],
            header['ADU_latency'],
            header['qfi'],
            header['req_idx']
        )

        start_time = time.monotonic_ns() 
        sec = start_time // 1_000_000_000
        nsec = start_time % 1_000_000_000

        
        CHUNK_SIZE = 4096
        packed = socket.inet_aton(client_ip)
        client_ip_as_int = struct.unpack("<I", packed)[0]

        print(f"[FEEDER],server_ADU_first_packet,ue_ip,{client_ip_as_int},port,{client_port},req_idx,{req_idx},start_time,{sec}.{nsec:09d},ADU_size,{ADU_size},latency_req,{ADU_latency}")
        
        server_socket.sendall(packed_header)
        
        # Send data in chunks
        server_socket.sendall(data)
            
        # check buffer is empty
        outq = array.array('i', [0])
        fcntl.ioctl(server_socket, 0x5411, outq)
        
        buf_start = time.time() * 1000
        while outq[0] > 0:
            #if (time.time() * 1000 - buf_start) >= 800:
            #    break
            fcntl.ioctl(server_socket, 0x5411, outq)
            time.sleep(0.001)
        
        empty_time = time.monotonic_ns()
        sec = empty_time // 1_000_000_000
        nsec = empty_time % 1_000_000_000

        print(f"[FEEDER],server_ADU_last_packet,ue_ip,{client_ip_as_int},port,{client_port},req_idx,{req_idx},start_time,{sec}.{nsec:09d},ADU_size,{ADU_size},latency_req,{ADU_latency}")
            
        #print(f"latency,{time.time()*1000 - start},ADU_size,{ADU_size},time,{target_time},lat_req,{ADU_latency}")
        #cpu_utils = psutil.cpu_percent(percpu = True)
        #mem = psutil.virtual_memory().percent
        #print(f"len,{len(cpu_utils)},cpu,{np.mean(cpu_utils)},mem,{mem}")

        
    
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    #parser.add_argument('--traffic','-T',type=str, default="P", help='traffic pattern, P/E/L')
    #parser.add_argument('--interval','-I',type=int, default=4, help='average interval, x per sec')
    #parser.add_argument('--g','-S',type=float, default=4, help='scaled_size, size*S')
    args = parser.parse_args()
    
    Ttraffic = "L"
    Iinterval = 20
    Sscaling = 1
    
    LAT_LIST = [200] 

    print(f"T: {Ttraffic}, I: {Iinterval}, S: {Sscaling}")

    server_socket(Ttraffic, Iinterval, Sscaling)


    try:
        while 1:
            pass
    except KeyboardInterrupt:
        pass
    finally:
        print("Terminating processes...")
        
        for _server_sock in server_sockets:
            _server_sock.close()
        
        for _p in client_processes:
            _p.join()
            _p.terminate()
    
