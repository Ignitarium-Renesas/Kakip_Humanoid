import socket
from motion_manager import *

def start_server(host='127.0.0.1', port=9091):
    motion_manager = MotionManager()
    motion_manager.run_action('stand')
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.listen()
        print(f'Server listening on {host}:{port}')
        conn, addr = s.accept()
        with conn:
            print(f'Connected by {addr}')
            previous_data = None
            while True:
                data = conn.recv(10)
                if not data:
                    break
                if data.decode() != previous_data:
                    print(f'Received: {data.decode()}')
                    if data.decode() == 'one':
                        print("1")
                        motion_manager.run_action('greet')
                    elif data.decode() == 'two':
                        print("2")
                        motion_manager.run_action('twist')
                    elif data.decode() == 'three':
                        print("3")
                        motion_manager.run_action('forward')
                    elif data.decode() == 'four':
                        print("4")
                        motion_manager.run_action('wave')
                    elif data.decode() == 'five':
                        print("5")
                        motion_manager.run_action('left_shot')
                    previous_data = data.decode()
                #conn.sendall(b'Hello, Client!')

if __name__ == "__main__":
    start_server()
