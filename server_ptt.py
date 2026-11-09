import tkinter as tk
from tkinter import ttk, scrolledtext
import socket
import threading
import queue
import datetime

# --- Configuración del Servidor ---
HOST = '0.0.0.0'  # Escucha en todas las interfaces de red
PORT = 5001       # Puerto de escucha (debe coincidir con el cliente)

class PTTServer:
    def __init__(self, root):
        self.root = root
        self.root.title("Servidor PTT - Windows")
        self.root.geometry("450x400")
        self.root.resizable(False, False)

        self.server_socket = None
        self.client_socket = None
        self.is_running = False
        self.msg_queue = queue.Queue() # Cola para comunicación segura entre hilos

        self.setup_ui()
        self.process_queue() # Inicia el bucle que revisa la cola

    def setup_ui(self):
        # Indicador de estado del PTT
        self.indicator_frame = tk.Frame(self.root, bg='gray', height=100)
        self.indicator_frame.pack(fill=tk.X, padx=20, pady=20)
        self.indicator_label = tk.Label(
            self.indicator_frame, 
            text="ESPERANDO SEÑAL PTT", 
            font=('Arial', 14, 'bold'), 
            bg='gray', fg='white'
        )
        self.indicator_label.pack(expand=True)

        # Información de conexión
        self.info_label = tk.Label(self.root, text=f"Servidor escuchando en el puerto: {PORT}", font=('Arial', 10))
        self.info_label.pack(pady=5)
        self.ip_label = tk.Label(self.root, text="IP local: Buscando...", font=('Arial', 10, 'italic'))
        self.ip_label.pack(pady=5)
        self.update_ip_label()

        # Registro de eventos (Log)
        self.log_area = scrolledtext.ScrolledText(self.root, height=10, state='disabled', font=('Consolas', 9))
        self.log_area.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)

    def update_ip_label(self):
        # Obtiene la IP local de forma sencilla
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            self.ip_label.config(text=f"IP local: {ip} (Ingresa esta IP en la App Android)")
        except:
            self.ip_label.config(text="IP local: No detectada")

    def log_message(self, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.msg_queue.put(f"[{timestamp}] {message}\n")

    def process_queue(self):
        # Procesa mensajes de la cola en el hilo principal de Tkinter
        while not self.msg_queue.empty():
            msg = self.msg_queue.get()
            self.log_area.config(state='normal')
            self.log_area.insert(tk.END, msg)
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')
        self.root.after(100, self.process_queue)

    def start_server(self):
        self.is_running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((HOST, PORT))
            self.server_socket.listen(1)
            self.log_message(f"Servidor iniciado en {HOST}:{PORT}. Esperando conexiones...")
            # Hilo para aceptar conexiones
            threading.Thread(target=self.accept_connections, daemon=True).start()
        except Exception as e:
            self.log_message(f"Error al iniciar servidor: {e}")

    def accept_connections(self):
        while self.is_running:
            try:
                self.server_socket.settimeout(1.0) # Timeout para poder cerrar el servidor
                client, addr = self.server_socket.accept()
                self.client_socket = client
                self.log_message(f"Cliente conectado desde: {addr[0]}:{addr[1]}")
                # Hilo para recibir datos del cliente
                threading.Thread(target=self.receive_data, args=(client,), daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                break # El socket se cerró

    def receive_data(self, client):
        while self.is_running:
            try:
                data = client.recv(1024)
                if not data:
                    break
                message = data.decode('utf-8')
                if message == "PTT_START":
                    self.msg_queue.put(("indicator_on", None))
                    self.log_message("Señal PTT recibida: INICIO de transmisión.")
                    client.sendall(b"ACK")
                elif message == "PTT_STOP":
                    self.msg_queue.put(("indicator_off", None))
                    self.log_message("Señal PTT recibida: FIN de transmisión.")
                    client.sendall(b"ACK")
            except ConnectionResetError:
                break
            except Exception as e:
                self.log_message(f"Error de recepción: {e}")
                break
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None
            self.msg_queue.put(("indicator_off", None))
            self.log_message("Cliente desconectado.")

    def on_closing(self):
        self.is_running = False
        if self.client_socket:
            self.client_socket.close()
        if self.server_socket:
            self.server_socket.close()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = PTTServer(root)
    # Sobrescribe el método put de la cola para manejar acciones de UI directamente
    original_put = app.msg_queue.put
    def ui_queue_put(item, block=True, timeout=None):
        if isinstance(item, tuple) and item[0] == "indicator_on":
            app.indicator_frame.config(bg='red')
            app.indicator_label.config(text="🔴 TRANSMITIENDO (PTT ACTIVO)", bg='red')
        elif isinstance(item, tuple) and item[0] == "indicator_off":
            app.indicator_frame.config(bg='gray')
            app.indicator_label.config(text="ESPERANDO SEÑAL PTT", bg='gray')
        else:
            original_put(item, block, timeout)
    app.msg_queue.put = ui_queue_put

    app.start_server()
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
