import socket
import struct
import fcntl
import argparse
import time
import multiprocessing as mp
import sys
import ntplib


# ADU_header_t 구조체 정의
ADU_HEADER_FORMAT = 'IIHHiici'
ADU_HEADER_SIZE = struct.calcsize(ADU_HEADER_FORMAT)




# for time sync (ntp)
def get_ntp_offset(server_ip: str = "10.45.0.1", timeout: float = 2.0, num_samples: int = 3) -> float:
    client = ntplib.NTPClient()
    offsets = []

    for i in range(num_samples):
        try:
            response = client.request(server_ip, version=3, timeout=timeout)
            offset = response.offset
            offsets.append(offset)
            #print(f"[{i+1}/{num_samples}] offset: {offset:.6f} sec | delay: {response.delay:.6f} sec")
            time.sleep(0.2)
        except Exception as e:
            print(f"[{i+1}/{num_samples}] NTP request failed: {e}")

    if not offsets:
        print("[ERROR] All NTP requests failed.")
        return 0.0

    average_offset = sum(offsets) / len(offsets)
    print(f"[RESULT] Average offset: {average_offset:.6f} sec (from {len(offsets)} samples)")
    return average_offset

def get_time():
    return time.time() + offset

def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
    try:
        ip_address = socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15].encode('utf-8'))
        )[20:24])
        return ip_address
    except OSError as e:
        print(f"Error getting IP address for interface {ifname}: {e}")
        return None


def client_socket(): # open 4 port
    global client_sockets
    
    #client_ip = get_ip_address('oaitun_ue1')
    #client_port = 5000

def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
    try:
        ip_address = socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15].encode('utf-8'))
        )[20:24])
        return ip_address
    except OSError as e:
        print(f"Error getting IP address for interface {ifname}: {e}")
        return None


def receive_image_with_header(n,traffic_type):
    try:
        global offset
        offset = get_ntp_offset("10.45.0.1")
        print(f"ntp offset setting {offset}")
        client_ip = get_ip_address('rmnet1')
        print(f"{client_ip}")
        if(traffic_type == 1): client_port = 9000
        else: client_port = 5000

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
            
            # turn client socket in any possible port
            while True:
                try:
                    client_socket.bind((client_ip, client_port))
                    break
                except OSError:
                    client_port += 1

            client_socket.listen(5)
            print(f"{n}-th client is listening on {client_ip}:{client_port}", flush=True)



            while True:
                # accept()를 통해 클라이언트 연결 수락
                conn, addr = client_socket.accept()
                print(f"{n}-th client connected to server at {addr[0]}:{addr[1]}", flush=True)

                try:
                    while True: ###SERAE
                        packed_header = b''
                        while len(packed_header) < ADU_HEADER_SIZE:
                            packed_header += conn.recv(ADU_HEADER_SIZE - len(packed_header))

                        try:
                            header = struct.unpack(ADU_HEADER_FORMAT, packed_header)
                        except:
                            time.sleep(0.01)
                            continue

                        header = struct.unpack(ADU_HEADER_FORMAT, packed_header)
                        source_ip = socket.inet_ntoa(struct.pack("I", header[0]))
                        dest_ip = socket.inet_ntoa(struct.pack("I", header[1]))
                        adu_latency = header[5]
                        req_idx = header[7]

                    
                        print(f"Received header from {source_ip}: {header}")

                        adu_size = header[4] #
                        
                        total_data_size = 0
                        while total_data_size <= adu_size:
                            data = conn.recv(adu_size - total_data_size)
                            if not data:
                                break
                            total_data_size += len(data)
                            print(f"Received {total_data_size}/{adu_size}")

                        print(f"Total data received: {total_data_size}")
                        end_time = get_time()
                        print(f"[[AppRAN]],ue_ip,{client_ip},port,{client_port},drb,{client_port % 4 + 2},lcid,{client_port % 4 + 5},req_idx,{req_idx},end_time,{end_time},ADU_size,{adu_size},latency_req,{adu_latency}")
                    
                finally:
                    conn.close()
                    print(f"{n}-th client: Connection closed.")
    except Exception as e:
        print(f"Error: {e}", flush=True)



if __name__ == '__main__':
    interface='oaitun_ue1'
    

    parser = argparse.ArgumentParser()
    
    #parser.add_argument('--ip','-P',type=int, default=0, help='last_index of IP') 
    parser.add_argument('--number','-N',type=int, default=0, help='N of client')
    parser.add_argument('--traffic_type','-T',type=int, default=0, help='Traffic type (0:back, 1:gua)')
    args = parser.parse_args()
    print(f"N: {args.number}, Gua(1)/Back(0): {args.traffic_type}")
    
    # 4개의 프로세스 생성
    processes = []
    for i in range(args.number):
        p = mp.Process(target=receive_image_with_header, args=(i,args.traffic_type))
        p.start()
        processes.append(p)

    # 프로세스 종료 대기
    for p in processes:
        p.join()
