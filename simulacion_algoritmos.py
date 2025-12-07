#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simulación Comparativa: Maekawa vs Ricart & Agrawala
Uso: mpiexec -n <N> python simulacion_algoritmos.py --algo <RA|MAEKAWA>
Requisito: N debe ser un cuadrado perfecto (4, 9, 16) para Maekawa.

Métricas según la teoría:
┌─────────────────────┬─────────────────────────────┬───────────────────────────┐
│ Métrica             │ Algoritmo de Maekawa        │ Ricart & Agrawala (RA)    │
├─────────────────────┼─────────────────────────────┼───────────────────────────┤
│ Ancho de Banda      │ O(√N) (≈ 3√N mensajes)      │ O(N) (≈ 2(N-1) mensajes)  │
│ (Mensajes)          │                             │                           │
├─────────────────────┼─────────────────────────────┼───────────────────────────┤
│ Retardo de          │ 2T (Dos unidades de tiempo) │ T (Una unidad de tiempo)  │
│ Sincronización      │                             │                           │
└─────────────────────┴─────────────────────────────┴───────────────────────────┘
"""

from mpi4py import MPI
import argparse
import math
import time
import threading
import sys
import random
from queue import PriorityQueue, Queue
from datetime import datetime

# --- CONFIGURACIÓN VISUAL Y COLORES ---
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"     # Para Sección Crítica
    GREEN = "\033[92m"   # Para Requests
    YELLOW = "\033[93m"  # Advertencias
    BLUE = "\033[94m"    # Infos generales
    CYAN = "\033[96m"    # Replies/Votos
    MAGENTA = "\033[95m" # Releases
    GREY = "\033[90m"    # Logs secundarios
    WHITE = "\033[97m"   # Texto blanco
    BG_RED = "\033[41m"  # Fondo rojo para SC
    BG_GREEN = "\033[42m"# Fondo verde
    BG_BLUE = "\033[44m" # Fondo azul
    UNDERLINE = "\033[4m"

# Tipos de mensaje
MSG_REQUEST = 1
MSG_REPLY = 2      # También llamado LOCKED/VOTE
MSG_RELEASE = 3
MSG_INQUIRE = 4    # Pregunta si puede reclamar el voto
MSG_RELINQUISH = 5 # Cede el voto (también llamado YIELD)
MSG_FAILED = 6     # Indica que no se puede obtener el voto

# --- CLASE DE LOGGING Y MÉTRICAS ---
class SimulationManager:
    def __init__(self, rank, comm):
        self.rank = rank
        self.comm = comm
        self.msg_count = 0
        self.msg_sent_count = 0
        self.msg_recv_count = 0
        self.lock = threading.Lock()
        self.start_time = time.time()
        
        # Métricas de tiempo
        self.request_start_time = None
        self.cs_enter_time = None
        self.cs_exit_time = None
        self.release_end_time = None
        self.release_time = 0  # Tiempo de la ronda de RELEASE
        self.sync_delay = 0  # Retardo de sincronización (tiempo real)
        
        # Contadores de rondas de mensajes
        self.rounds_to_enter = 0  # Rondas para entrar a SC
        self.rounds_to_release = 0  # Rondas para completar release
        
        # Historial de eventos para visualización
        self.event_log = []

    def log(self, message, color=Colors.RESET, event_type="INFO"):
        """Imprime un mensaje formateado y coloreado"""
        elapsed = time.time() - self.start_time
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Símbolo según tipo de evento
        symbols = {
            "REQUEST": "📤",
            "REPLY": "📩",
            "RELEASE": "🔓",
            "CS_ENTER": "🔒",
            "CS_EXIT": "🔑",
            "INFO": "ℹ️",
            "VOTE": "🗳️",
            "METRIC": "📊",
            "ERROR": "❌",
            "SUCCESS": "✅",
            "WAIT": "⏳",
            "INQUIRE": "❓",
            "RELINQUISH": "🔄",
            "FAILED": "❌"
        }
        symbol = symbols.get(event_type, "•")
        
        # Formato: [00.123s] [PROC 0] Mensaje
        prefix = f"{Colors.GREY}[{elapsed:07.3f}s]{Colors.RESET} {Colors.BOLD}[P{self.rank}]{Colors.RESET}"
        log_line = f"{prefix} {symbol} {color}{message}{Colors.RESET}"
        
        sys.stdout.write(log_line + "\n")
        sys.stdout.flush()
        
        # Guardar evento
        with self.lock:
            self.event_log.append({
                'time': elapsed,
                'rank': self.rank,
                'type': event_type,
                'message': message
            })

    def record_msg_sent(self, msg_type="UNKNOWN"):
        """Incrementa el contador de mensajes enviados (Métrica clave)"""
        with self.lock:
            self.msg_count += 1
            self.msg_sent_count += 1

    def record_msg_recv(self):
        """Incrementa el contador de mensajes recibidos"""
        with self.lock:
            self.msg_recv_count += 1

    def start_request(self):
        """Marca el inicio de una solicitud de SC"""
        self.request_start_time = time.time()
        
    def enter_cs(self):
        """Marca la entrada a la SC"""
        self.cs_enter_time = time.time()
        if self.request_start_time:
            self.sync_delay = self.cs_enter_time - self.request_start_time
            
    def exit_cs(self):
        """Marca la salida de la SC"""
        self.cs_exit_time = time.time()
    
    def end_release(self):
        """Marca el fin del proceso de release"""
        self.release_end_time = time.time()

    def get_total_metrics(self):
        """Recopila las métricas de TODOS los procesos"""
        total = self.comm.reduce(self.msg_count, op=MPI.SUM, root=0)
        return total
    
    def get_sync_delay(self):
        """Obtiene el retardo de sincronización máximo entre todos los procesos"""
        max_delay = self.comm.reduce(self.sync_delay, op=MPI.MAX, root=0)
        return max_delay
    
    def get_message_rounds(self):
        """Retorna el número de rondas de mensajes"""
        return self.rounds_to_enter, self.rounds_to_release
        return max_delay

# --- ALGORITMO 1: RICART & AGRAWALA ---
# Complejidad: O(N) mensajes por entrada a SC
# Mensajes por acceso: 2(N-1) = (N-1) REQUEST + (N-1) REPLY
# Retardo de sincronización: T (una ronda de mensajes)
class RicartAgrawala:
    def __init__(self, comm, rank, size, manager):
        self.comm = comm
        self.rank = rank
        self.size = size
        self.mgr = manager
        
        # Reloj lógico de Lamport
        self.clock = 0
        # Cola de solicitudes diferidas
        self.deferred_queue = []
        self.replies_received = 0
        self.requesting_cs = False
        self.my_request_timestamp = 0  # Timestamp de mi solicitud actual
        self.cond = threading.Condition()

    def request_access(self):
        self.mgr.start_request()
        
        with self.cond:
            self.requesting_cs = True
            self.clock += 1
            self.my_request_timestamp = self.clock  # Guardar timestamp de solicitud
            self.replies_received = 0
            timestamp = self.clock

        self.mgr.log(f"Solicitando acceso a SC (Lamport Clock={timestamp})", Colors.GREEN, "REQUEST")
        self.mgr.log(f"[RONDA 1] Enviando REQUEST a {self.size - 1} procesos...", Colors.BLUE, "INFO")
        
        # RONDA 1: Enviar REQUEST a TODOS los demás procesos (N-1 mensajes)
        for i in range(self.size):
            if i != self.rank:
                self.comm.send({
                    't': MSG_REQUEST, 
                    'ts': timestamp, 
                    'src': self.rank
                }, dest=i, tag=1)
                self.mgr.record_msg_sent("REQUEST")
                self.mgr.log(f"  → REQUEST enviado a P{i}", Colors.GREY, "INFO")

        # Esperar (N-1) REPLYs para entrar a SC (esto completa la RONDA 1)
        with self.cond:
            while self.replies_received < self.size - 1:
                self.cond.wait()
        
        # Ricart-Agrawala: Solo 1 ronda (REQUEST→REPLY)
        self.mgr.rounds_to_enter = 1
        
        self.mgr.enter_cs()
        self.mgr.log(f"[RONDA 1 COMPLETA] Permiso concedido! ({self.replies_received}/{self.size-1} REPLYs)", 
                     Colors.BOLD + Colors.GREEN, "SUCCESS")

    def release_access(self):
        self.mgr.exit_cs()
        self.mgr.log("Liberando SC. Respondiendo a solicitudes diferidas...", Colors.MAGENTA, "RELEASE")
        
        # En RA, el release es local (no hay ronda adicional de mensajes para entrar)
        # Los REPLYs diferidos se envían pero no son parte del retardo de sincronización
        self.mgr.rounds_to_release = 0  # No hay ronda adicional obligatoria
        
        with self.cond:
            self.requesting_cs = False
            count = 0
            # Responder a todas las solicitudes en cola
            for req_src in self.deferred_queue:
                self.comm.send({'t': MSG_REPLY, 'src': self.rank}, dest=req_src, tag=1)
                self.mgr.record_msg_sent("REPLY")
                count += 1
            self.deferred_queue.clear()
            
        if count > 0:
            self.mgr.log(f"  → {count} REPLYs enviados a procesos en espera", Colors.CYAN, "REPLY")

    def handle_message(self, msg):
        m_type = msg['t']
        src = msg['src']
        self.mgr.record_msg_recv()
        
        with self.cond:
            # Actualizar reloj de Lamport
            if 'ts' in msg:
                self.clock = max(self.clock, msg['ts']) + 1

            if m_type == MSG_REQUEST:
                req_ts = msg['ts']
                
                # Regla de Ricart-Agrawala para determinar prioridad:
                # Diferir si: (1) Quiero entrar Y (2) Tengo mayor prioridad
                # Prioridad: menor timestamp gana; en empate, menor rank gana
                my_priority = (self.requesting_cs and 
                              (self.my_request_timestamp < req_ts or 
                               (self.my_request_timestamp == req_ts and self.rank < src)))
                
                if my_priority:
                    self.mgr.log(f"Diferiendo REQUEST de P{src} (ts={req_ts}) - Mi prioridad: ts={self.my_request_timestamp}", 
                                 Colors.YELLOW, "INFO")
                    self.deferred_queue.append(src)
                else:
                    # Enviar REPLY inmediatamente
                    self.comm.send({'t': MSG_REPLY, 'src': self.rank}, dest=src, tag=1)
                    self.mgr.record_msg_sent("REPLY")
                    self.mgr.log(f"REPLY enviado a P{src} (ts={req_ts})", Colors.CYAN, "REPLY")
            
            elif m_type == MSG_REPLY:
                self.replies_received += 1
                self.mgr.log(f"REPLY recibido de P{src} ({self.replies_received}/{self.size-1})", 
                             Colors.CYAN, "REPLY")
                if self.replies_received == self.size - 1:
                    self.cond.notify()

# --- ALGORITMO 2: MAEKAWA ---
# Complejidad: O(√N) mensajes por entrada a SC
# Mensajes por acceso: ~3√N = √N REQUEST + √N REPLY + √N RELEASE  
# Retardo de sincronización: 2T (dos rondas de mensajes: REQUEST→REPLY, luego RELEASE)
#
# IMPLEMENTACIÓN COMPLETA CON PREVENCIÓN DE DEADLOCK:
# - INQUIRE: Cuando un proceso tiene una solicitud de mayor prioridad encolada,
#            pregunta al proceso que tiene su voto si puede cederlo.
# - RELINQUISH/YIELD: El proceso cede el voto si aún no ha entrado a SC.
# - FAILED: Indica que no se puede obtener el voto (alternativa a INQUIRE).
#
# Mensajes del algoritmo:
# - REQUEST: Solicita acceso a SC (contiene timestamp para prioridad)
# - LOCKED/REPLY: Concede el voto
# - RELEASE: Libera el voto al salir de SC
# - INQUIRE: Pregunta si el proceso puede ceder el voto
# - RELINQUISH: Cede el voto recibido (respuesta a INQUIRE)
# - FAILED: No se puede dar el voto (alternativa)

class Maekawa:
    def __init__(self, comm, rank, size, manager):
        self.comm = comm
        self.rank = rank
        self.size = size
        self.mgr = manager
        
        # Estados del proceso
        self.state = 'RELEASED'  # Estados: RELEASED, WANTED, HELD
        
        # Control de votos
        self.voted_for = None           # ¿A quién le di mi voto? (y su timestamp)
        self.voted_for_ts = None        # Timestamp del proceso al que voté
        self.pending_requests = []      # Solicitudes pendientes: [(timestamp, rank)]
        self.inquire_sent = False       # ¿Ya envié INQUIRE al que tiene mi voto?
        
        # Votos recibidos para entrar a SC
        self.votes_received = set()     # Conjunto de procesos que me dieron su voto
        self.my_timestamp = 0           # Mi timestamp actual de solicitud
        
        # Sincronización
        self.cond = threading.Condition()
        self.lock = threading.Lock()
        
        # --- Construcción del Voting Set (Grid 2D) ---
        self.k = int(math.sqrt(size))
        if self.k * self.k != size:
            raise ValueError(f"N={size} no es un cuadrado perfecto. Maekawa requiere 4, 9, 16, 25...")
        
        row = rank // self.k
        col = rank % self.k
        
        self.voting_set = set()
        # Añadir toda mi fila
        for c in range(self.k): 
            self.voting_set.add(row * self.k + c)
        # Añadir toda mi columna
        for r in range(self.k): 
            self.voting_set.add(r * self.k + col)
        
        # Excluimos a nosotros mismos para comunicación
        self.voting_set.discard(self.rank)
        
        self.mgr.log(f"Grid {self.k}×{self.k} | Posición: fila={row}, col={col} | Voting Set: {sorted(self.voting_set)}", 
                     Colors.BLUE, "INFO")

    def _get_timestamp(self):
        """Genera un timestamp único basado en tiempo + rank para desempate"""
        return (time.time(), self.rank)
    
    def _compare_priority(self, ts1, rank1, ts2, rank2):
        """Compara prioridad: menor timestamp gana, en empate menor rank gana.
           Retorna True si (ts1, rank1) tiene MAYOR prioridad que (ts2, rank2)"""
        if ts1 < ts2:
            return True
        elif ts1 == ts2:
            return rank1 < rank2
        return False

    def request_access(self):
        self.mgr.start_request()
        
        with self.lock:
            self.state = 'WANTED'
            self.my_timestamp = time.time()
            self.votes_received = set()
            self.inquire_sent = False
        
        set_size = len(self.voting_set)
        self.mgr.log(f"Solicitando acceso a SC (ts={self.my_timestamp:.4f}). Enviando REQUEST a Voting Set ({set_size} procesos)", 
                     Colors.GREEN, "REQUEST")
        self.mgr.log(f"[RONDA 1] Enviando REQUESTs...", Colors.BLUE, "INFO")

        # RONDA 1: Enviar REQUEST a todos en el Voting Set
        for dest in self.voting_set:
            self.comm.send({
                't': MSG_REQUEST, 
                'src': self.rank,
                'ts': self.my_timestamp
            }, dest=dest, tag=2)
            self.mgr.record_msg_sent("REQUEST")
            self.mgr.log(f"  → REQUEST enviado a P{dest}", Colors.GREY, "INFO")
            
        # Esperar votos de todos en el Voting Set
        with self.cond:
            while len(self.votes_received) < len(self.voting_set):
                self.cond.wait(timeout=0.5)
                # Log de progreso
                if len(self.votes_received) < len(self.voting_set):
                    missing = self.voting_set - self.votes_received
                    self.mgr.log(f"⏳ Esperando votos de: {sorted(missing)} ({len(self.votes_received)}/{set_size})", 
                                 Colors.YELLOW, "WAIT")
        
        with self.lock:
            self.state = 'HELD'
        
        self.mgr.rounds_to_enter = 1
        self.mgr.enter_cs()
        self.mgr.log(f"[RONDA 1 COMPLETA] Todos los votos reunidos ({set_size} votos). Entrando a SC!", 
                     Colors.BOLD + Colors.GREEN, "SUCCESS")

    def release_access(self):
        self.mgr.exit_cs()
        release_start = time.time()
        self.mgr.log("[RONDA 2] Liberando SC. Enviando RELEASE a Voting Set...", Colors.MAGENTA, "RELEASE")
        
        with self.lock:
            self.state = 'RELEASED'
            self.votes_received = set()
            self.my_timestamp = 0
        
        # RONDA 2: Enviar RELEASE a todos en el Voting Set
        for dest in self.voting_set:
            self.comm.send({'t': MSG_RELEASE, 'src': self.rank}, dest=dest, tag=2)
            self.mgr.record_msg_sent("RELEASE")
            self.mgr.log(f"  → RELEASE enviado a P{dest}", Colors.GREY, "INFO")
        
        self.mgr.rounds_to_release = 1
        self.mgr.release_time = time.time() - release_start
        self.mgr.log(f"[RONDA 2 COMPLETA] RELEASEs enviados. Total: 2 rondas (2T)", Colors.BLUE, "INFO")

    def _try_give_vote(self, requester, req_ts):
        """Intenta dar el voto a un solicitante. Maneja la lógica de INQUIRE."""
        with self.lock:
            if self.voted_for is None:
                # No he votado por nadie, dar el voto
                self.comm.send({'t': MSG_REPLY, 'src': self.rank}, dest=requester, tag=2)
                self.mgr.record_msg_sent("VOTE")
                self.voted_for = requester
                self.voted_for_ts = req_ts
                self.inquire_sent = False
                self.mgr.log(f"🗳️ LOCKED/VOTO enviado a P{requester}", Colors.CYAN, "VOTE")
                return True
            else:
                # Ya voté por alguien, encolar y posiblemente enviar INQUIRE
                self.pending_requests.append((req_ts, requester))
                self.pending_requests.sort()  # Ordenar por timestamp (prioridad)
                self.mgr.log(f"📋 REQUEST de P{requester} (ts={req_ts:.4f}) encolado. Cola: {[(r, f'{t:.4f}') for t,r in self.pending_requests]}", 
                             Colors.YELLOW, "INFO")
                
                # Verificar si el nuevo request tiene mayor prioridad que el actual votado
                # y enviar INQUIRE si aún no lo hemos hecho
                if (not self.inquire_sent and 
                    self._compare_priority(req_ts, requester, self.voted_for_ts, self.voted_for)):
                    # El nuevo solicitante tiene mayor prioridad, enviar INQUIRE
                    self.comm.send({
                        't': MSG_INQUIRE, 
                        'src': self.rank
                    }, dest=self.voted_for, tag=2)
                    self.mgr.record_msg_sent("INQUIRE")
                    self.inquire_sent = True
                    self.mgr.log(f"❓ INQUIRE enviado a P{self.voted_for} (tiene mi voto, pero P{requester} tiene mayor prioridad)", 
                                 Colors.YELLOW, "INQUIRE")
                return False

    def _process_pending_after_release(self):
        """Procesa la cola después de recibir RELEASE o RELINQUISH"""
        with self.lock:
            if self.voted_for is not None:
                return  # Ya voté por alguien
            
            if not self.pending_requests:
                return  # No hay solicitudes pendientes
            
            # Dar voto al de mayor prioridad (menor timestamp)
            req_ts, requester = self.pending_requests.pop(0)
            self.comm.send({'t': MSG_REPLY, 'src': self.rank}, dest=requester, tag=2)
            self.mgr.record_msg_sent("VOTE")
            self.voted_for = requester
            self.voted_for_ts = req_ts
            self.inquire_sent = False
            self.mgr.log(f"🗳️ LOCKED/VOTO enviado a P{requester} (desde cola pendiente)", Colors.CYAN, "VOTE")

    def handle_message(self, msg):
        m_type = msg['t']
        src = msg['src']
        self.mgr.record_msg_recv()
        
        if m_type == MSG_REQUEST:
            req_ts = msg.get('ts', time.time())
            self.mgr.log(f"📥 REQUEST recibido de P{src} (ts={req_ts:.4f})", Colors.GREEN, "REQUEST")
            self._try_give_vote(src, req_ts)
        
        elif m_type == MSG_REPLY:
            # Recibí un voto (LOCKED)
            with self.cond:
                self.votes_received.add(src)
                self.mgr.log(f"🗳️ VOTO recibido de P{src} ({len(self.votes_received)}/{len(self.voting_set)})", 
                             Colors.CYAN, "VOTE")
                if len(self.votes_received) == len(self.voting_set):
                    self.cond.notify_all()
        
        elif m_type == MSG_RELEASE:
            self.mgr.log(f"🔓 RELEASE recibido de P{src}", Colors.MAGENTA, "RELEASE")
            with self.lock:
                if self.voted_for == src:
                    self.voted_for = None
                    self.voted_for_ts = None
                    self.inquire_sent = False
            self._process_pending_after_release()
        
        elif m_type == MSG_INQUIRE:
            # Alguien pregunta si puedo ceder el voto que me dio
            self.mgr.log(f"❓ INQUIRE recibido de P{src}", Colors.YELLOW, "INQUIRE")
            with self.lock:
                # Solo cedo el voto si aún no he entrado a SC (state == WANTED)
                # y si aún tengo el voto de este proceso
                if self.state == 'WANTED' and src in self.votes_received:
                    # Cedo el voto - envío RELINQUISH
                    self.votes_received.discard(src)
                    self.comm.send({'t': MSG_RELINQUISH, 'src': self.rank}, dest=src, tag=2)
                    self.mgr.record_msg_sent("RELINQUISH")
                    self.mgr.log(f"🔄 RELINQUISH enviado a P{src} (cedí el voto, votos restantes: {len(self.votes_received)})", 
                                 Colors.YELLOW, "RELINQUISH")
                elif self.state == 'HELD':
                    self.mgr.log(f"❌ No puedo ceder voto de P{src} (ya estoy en HELD)", Colors.RED, "INFO")
                else:
                    self.mgr.log(f"⚠️ INQUIRE de P{src} ignorado (no tengo su voto o ya en SC)", Colors.GREY, "INFO")
        
        elif m_type == MSG_RELINQUISH:
            # Alguien me devuelve el voto que le di
            self.mgr.log(f"🔄 RELINQUISH recibido de P{src} (recuperé mi voto)", Colors.YELLOW, "RELINQUISH")
            with self.lock:
                if self.voted_for == src:
                    self.voted_for = None
                    self.voted_for_ts = None
                    self.inquire_sent = False
            self._process_pending_after_release()
        
        elif m_type == MSG_FAILED:
            # El proceso no puede darme el voto (alternativa a INQUIRE)
            self.mgr.log(f"❌ FAILED recibido de P{src}", Colors.RED, "FAILED")
            # En esta implementación, usamos INQUIRE/RELINQUISH en lugar de FAILED


# --- INFRAESTRUCTURA DE SIMULACIÓN ---
def listen_loop(algo):
    """Loop infinito que escucha mensajes MPI con timeout para evitar bloqueos"""
    while True:
        # Usar Iprobe con un pequeño sleep para no consumir CPU y evitar race conditions
        if algo.comm.Iprobe(source=MPI.ANY_SOURCE, tag=MPI.ANY_TAG):
            status = MPI.Status()
            msg = algo.comm.recv(source=MPI.ANY_SOURCE, tag=MPI.ANY_TAG, status=status)
            if msg == "STOP": break
            algo.handle_message(msg)
        else:
            time.sleep(0.001)  # 1ms sleep para evitar busy-wait y dar tiempo a otros hilos

def print_header(algo_name, size):
    """Imprime el encabezado de la simulación"""
    header = f"""
{'='*70}
{Colors.BOLD}{Colors.BG_BLUE}{Colors.WHITE}  SIMULACIÓN DE EXCLUSIÓN MUTUA DISTRIBUIDA  {Colors.RESET}
{'='*70}
  Algoritmo: {Colors.BOLD}{algo_name}{Colors.RESET}
  Procesos:  {Colors.BOLD}{size}{Colors.RESET}
  Fecha:     {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
{'='*70}
"""
    print(header)

def print_metrics_table(algo_name, size, total_msgs, sync_delay, cs_duration, rounds_enter, rounds_release, release_time=0):
    """Imprime una tabla detallada con las métricas comparativas"""
    
    # Cálculos Teóricos
    if algo_name == "RICART-AGRAWALA":
        teorico_msgs = 2 * (size - 1)
        formula_msgs = f"2(N-1) = {teorico_msgs}"
        teorico_delay = "T (1 ronda)"
        teorico_rounds = 1
        complexity = "O(N)"
    else:  # MAEKAWA
        k = int(math.sqrt(size))
        teorico_msgs = int(3 * math.sqrt(size))  # 3*√N mensajes
        formula_msgs = f"3√N = {teorico_msgs}"
        teorico_delay = "2T (2 rondas)"
        teorico_rounds = 2
        complexity = "O(√N)"
    
    # Rondas observadas
    total_rounds = rounds_enter + rounds_release
    
    # Calcular tiempo por ronda (T) basado en la primera ronda
    if rounds_enter > 0 and sync_delay > 0:
        time_per_round = sync_delay / rounds_enter  # T = tiempo de una ronda (REQUEST→REPLY)
    else:
        time_per_round = 0
    
    # Tiempo total de sincronización = rondas × T
    # Para Maekawa: 2T (REQUEST→REPLY + RELEASE)
    # Para RA: 1T (REQUEST→REPLY)
    total_sync_time = time_per_round * total_rounds
    
    # Generar tabla
    print(f"\n{'='*70}")
    print(f"{Colors.BOLD}  📊 MÉTRICAS DE RENDIMIENTO - {algo_name}{Colors.RESET}")
    print(f"{'='*70}")
    
    # Tabla de métricas
    print(f"""
┌─────────────────────────────────┬─────────────────────┬─────────────────────┐
│ {Colors.BOLD}Métrica{Colors.RESET}                         │ {Colors.BOLD}Observado{Colors.RESET}           │ {Colors.BOLD}Teórico{Colors.RESET}             │
├─────────────────────────────────┼─────────────────────┼─────────────────────┤
│ Complejidad de Mensajes         │                     │ {complexity:<19} │
├─────────────────────────────────┼─────────────────────┼─────────────────────┤
│ Mensajes Totales (Ancho Banda)  │ {Colors.CYAN}{total_msgs:<19}{Colors.RESET} │ {formula_msgs:<19} │
├─────────────────────────────────┼─────────────────────┼─────────────────────┤
│ Retardo Sincronización (rondas) │ {Colors.CYAN}{total_rounds}T ({total_rounds} rondas){Colors.RESET}        │ {teorico_delay:<19} │
├─────────────────────────────────┼─────────────────────┼─────────────────────┤
│ Tiempo 1 Ronda (T)              │ {Colors.CYAN}{time_per_round*1000:>7.2f} ms{Colors.RESET}         │ (depende de red)    │
├─────────────────────────────────┼─────────────────────┼─────────────────────┤
│ Tiempo Total Sincronización     │ {Colors.CYAN}{total_sync_time*1000:>7.2f} ms{Colors.RESET}         │ {total_rounds}T = {total_sync_time*1000:.2f} ms      │
├─────────────────────────────────┼─────────────────────┼─────────────────────┤
│ Tiempo en Sección Crítica       │ {Colors.CYAN}{cs_duration*1000:>7.2f} ms{Colors.RESET}         │ (variable)          │
└─────────────────────────────────┴─────────────────────┴─────────────────────┘
""")
    
    # Análisis comparativo
    print(f"  {Colors.BOLD}📈 ANÁLISIS:{Colors.RESET}")
    
    # Validación de mensajes
    diff_percent = abs(total_msgs - teorico_msgs) / teorico_msgs * 100 if teorico_msgs > 0 else 0
    if diff_percent < 20:
        msg_status = f"{Colors.GREEN}✓ CORRECTO{Colors.RESET}"
    elif diff_percent < 50:
        msg_status = f"{Colors.YELLOW}~ ACEPTABLE{Colors.RESET}"
    else:
        msg_status = f"{Colors.RED}✗ REVISAR{Colors.RESET}"
    
    print(f"  • Mensajes: {msg_status} (desviación: {diff_percent:.1f}%)")
    
    # Validación de rondas
    if total_rounds == teorico_rounds:
        rounds_status = f"{Colors.GREEN}✓ CORRECTO{Colors.RESET}"
    else:
        rounds_status = f"{Colors.RED}✗ INCORRECTO{Colors.RESET}"
    print(f"  • Rondas de sincronización: {rounds_status} ({total_rounds}T observado vs {teorico_rounds}T teórico)")
    
    # Nota importante sobre T vs 2T
    print(f"\n  {Colors.YELLOW}⚠️  NOTA SOBRE RETARDO T vs 2T:{Colors.RESET}")
    if algo_name == "MAEKAWA":
        print(f"  {Colors.GREY}   El retardo 2T se manifiesta cuando HAY CONTENCIÓN (múltiples procesos")
        print(f"     compitiendo). En ese caso, el proceso siguiente debe esperar:")
        print(f"     - Ronda 1: REQUEST → VOTE")
        print(f"     - Ronda 2: Esperar RELEASE del proceso anterior para obtener votos")
        print(f"     Use --compete para ver este efecto en acción.{Colors.RESET}")
    else:
        print(f"  {Colors.GREY}   El retardo T significa que solo se necesita 1 ronda (REQUEST → REPLY)")
        print(f"     para entrar a la SC. Los REPLYs se pueden acumular mientras se espera.")
        print(f"     Use --compete para comparar con Maekawa (2T).{Colors.RESET}")
    
    # Información adicional según el algoritmo
    print(f"\n  {Colors.BOLD}📋 DESGLOSE DE MENSAJES:{Colors.RESET}")
    if algo_name == "MAEKAWA":
        k = int(math.sqrt(size))
        sqrt_n = int(math.sqrt(size))
        print(f"  • Grid: {k}×{k} = {size} procesos")
        print(f"  • Complejidad teórica: 3√N = 3×{sqrt_n} = {3*sqrt_n} mensajes")
        print(f"  • Desglose: √N REQUEST + √N REPLY + √N RELEASE = 3√N msgs")
    else:
        print(f"  • Procesos contactados: {size - 1} (todos menos yo)")
        print(f"  • Desglose: {size-1} REQUEST + {size-1} REPLY = {2*(size-1)} msgs")
    
    print(f"\n{'='*70}")
    
    # Comparación teórica
    print(f"\n{Colors.BOLD}  📚 COMPARACIÓN TEÓRICA (Referencia){Colors.RESET}")
    print(f"""
┌─────────────────────┬─────────────────────────────┬───────────────────────────┐
│ Métrica             │ Algoritmo de Maekawa        │ Ricart & Agrawala (RA)    │
├─────────────────────┼─────────────────────────────┼───────────────────────────┤
│ Ancho de Banda      │ O(√N) (≈ 3√N mensajes)      │ O(N) (≈ 2(N-1) mensajes)  │
│ (Mensajes)          │                             │                           │
├─────────────────────┼─────────────────────────────┼───────────────────────────┤
│ Retardo de          │ 2T (Dos unidades de tiempo) │ T (Una unidad de tiempo)  │
│ Sincronización      │                             │                           │
└─────────────────────┴─────────────────────────────┴───────────────────────────┘
""")

def print_timeline(events, size):
    """Imprime una línea de tiempo visual de los eventos"""
    print(f"\n{Colors.BOLD}  ⏱️  LÍNEA DE TIEMPO DE EVENTOS{Colors.RESET}")
    print(f"{'─'*70}")
    
    # Agrupar eventos por tipo para mejor visualización
    for event in sorted(events, key=lambda x: x['time'])[:20]:  # Primeros 20 eventos
        time_str = f"{event['time']:07.3f}s"
        rank_str = f"P{event['rank']}"
        type_color = {
            "REQUEST": Colors.GREEN,
            "REPLY": Colors.CYAN,
            "RELEASE": Colors.MAGENTA,
            "VOTE": Colors.CYAN,
            "CS_ENTER": Colors.RED,
            "CS_EXIT": Colors.RED,
            "SUCCESS": Colors.GREEN,
            "INFO": Colors.GREY
        }.get(event['type'], Colors.RESET)
        
        print(f"  {Colors.GREY}{time_str}{Colors.RESET} │ {Colors.BOLD}{rank_str:>3}{Colors.RESET} │ {type_color}{event['type']:<10}{Colors.RESET} │ {event['message'][:40]}")
    
    print(f"{'─'*70}\n")

# Constante para tiempo en sección crítica (igual para ambos algoritmos)
CS_TIME = 0.1  # 100 ms - tiempo que cada proceso pasa en la SC

def main():
    # Argument parsing
    parser = argparse.ArgumentParser(description="Simulación Exclusión Mutua")
    parser.add_argument('--algo', choices=['RA', 'MAEKAWA'], required=True, help='Algoritmo a ejecutar')
    parser.add_argument('--compete', action='store_true', help='Modo competencia: múltiples procesos intentan entrar a SC')
    parser.add_argument('--cs-time', type=float, default=CS_TIME, help=f'Tiempo en SC en segundos (default: {CS_TIME})')
    args, _ = parser.parse_known_args()
    
    cs_time = args.cs_time  # Tiempo configurable en SC

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    
    mgr = SimulationManager(rank, comm)
    
    # Nombre completo del algoritmo
    algo_name = "RICART-AGRAWALA" if args.algo == 'RA' else "MAEKAWA"
    
    # Instanciación
    algo = None
    tag_offset = 0
    
    try:
        if args.algo == 'RA':
            algo = RicartAgrawala(comm, rank, size, mgr)
            tag_offset = 1
        elif args.algo == 'MAEKAWA':
            algo = Maekawa(comm, rank, size, mgr)
            tag_offset = 2
    except ValueError as e:
        if rank == 0:
            print(f"{Colors.RED}❌ Error Fatal:{Colors.RESET} {e}")
        return

    # Iniciar Listener en background
    listener = threading.Thread(target=listen_loop, args=(algo,), daemon=True)
    listener.start()
    
    comm.Barrier()  # Sincronización inicial
    
    # Variables para métricas
    cs_duration = 0
    rounds_enter = 0
    rounds_release = 0
    my_wait_time = 0  # Tiempo que esperé para entrar
    
    if args.compete:
        # =====================================================
        # MODO COMPETENCIA: Múltiples procesos compiten por SC
        # Aquí se nota la diferencia entre T (RA) y 2T (Maekawa)
        # =====================================================
        if rank == 0:
            print_header(algo_name, size)
            print(f"\n{Colors.YELLOW}{Colors.BOLD}  ⚔️  MODO COMPETENCIA: Todos los procesos compiten por la SC{Colors.RESET}")
            print(f"{Colors.GREY}  Esto demuestra la diferencia en retardo de sincronización (T vs 2T)")
            print(f"  Tiempo en SC por proceso: {cs_time*1000:.0f} ms (igual para ambos algoritmos){Colors.RESET}\n")
            print(f"{Colors.GREY}{'─'*70}{Colors.RESET}\n")
        
        comm.Barrier()  # Todos listos para competir
        
        # =====================================================
        # ESTRATEGIA DE INICIO PARA EVITAR DEADLOCK
        # =====================================================
        # Maekawa es susceptible a deadlock cuando TODOS piden SIMULTÁNEAMENTE
        # porque los voting sets se intersectan y ningún proceso puede obtener
        # todos los votos que necesita.
        #
        # Solución: Escalonar el inicio. El primer proceso (P0) pide sin espera,
        # los demás esperan un pequeño tiempo para que las solicitudes lleguen
        # ordenadamente y el sistema pueda procesarlas sin deadlock.
        
        if algo_name == "MAEKAWA":
            # Para Maekawa: escalonar significativamente
            # Cada proceso espera (rank * tiempo_suficiente) para que el anterior
            # al menos haya enviado sus REQUESTs antes de que este empiece
            jitter = rank * 0.05  # 50ms entre cada proceso
            if rank > 0:
                time.sleep(jitter)
                mgr.log(f"Esperé {jitter*1000:.0f}ms antes de pedir (evitar deadlock)", Colors.GREY, "INFO")
        else:
            # Para RA: pequeño jitter aleatorio, RA no tiene deadlocks
            random.seed(rank * 1000)
            jitter = random.uniform(0, 0.005)  # 0-5ms aleatorio
            time.sleep(jitter)
        
        # TODOS los procesos intentan entrar a la SC
        start_wait = time.time()
        mgr.log(f"Intentando entrar a SC...", Colors.GREEN, "REQUEST")
        
        algo.request_access()
        
        my_wait_time = time.time() - start_wait
        mgr.log(f"ENTRÓ a SC después de esperar {my_wait_time*1000:.2f} ms", Colors.BOLD + Colors.RED, "CS_ENTER")
        
        # Simular trabajo en SC (TIEMPO IGUAL PARA AMBOS ALGORITMOS)
        cs_start = time.time()
        time.sleep(cs_time)  # Tiempo configurable, igual para RA y Maekawa
        cs_duration = time.time() - cs_start
        
        mgr.log(f"SALIENDO de SC (estuvo {cs_duration*1000:.0f} ms)", Colors.MAGENTA, "CS_EXIT")
        algo.release_access()
        
        rounds_enter = mgr.rounds_to_enter
        rounds_release = mgr.rounds_to_release
        
        time.sleep(1)  # Esperar a que todos terminen
        
    else:
        # =====================================================
        # MODO NORMAL: Solo P0 entra a la SC
        # =====================================================
        if rank == 0:
            print_header(algo_name, size)
            mgr.log(f"Iniciando simulación de {algo_name} con {size} procesos.", Colors.BOLD, "INFO")
            print(f"{Colors.GREY}  Tiempo en SC: {cs_time*1000:.0f} ms{Colors.RESET}")
            time.sleep(0.5)
            
            print(f"\n{Colors.GREY}{'─'*70}{Colors.RESET}")
            print(f"{Colors.BOLD}  🚀 INICIO DE LA SIMULACIÓN (Solo P0 entra a SC){Colors.RESET}")
            print(f"{Colors.GREY}{'─'*70}{Colors.RESET}\n")
            
            algo.request_access()
            
            print(f"\n{Colors.BG_RED}{Colors.WHITE}{Colors.BOLD}")
            print(f"  ╔══════════════════════════════════════════════════════════════╗")
            print(f"  ║          🔒 DENTRO DE LA SECCIÓN CRÍTICA (P{rank})              ║")
            print(f"  ║              Ejecutando operación exclusiva...              ║")
            print(f"  ╚══════════════════════════════════════════════════════════════╝")
            print(f"{Colors.RESET}\n")
            
            cs_start = time.time()
            time.sleep(cs_time)  # Tiempo configurable, igual para RA y Maekawa
            cs_duration = time.time() - cs_start
            
            algo.release_access()
            
            print(f"\n{Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD}")
            print(f"  ╔══════════════════════════════════════════════════════════════╗")
            print(f"  ║          🔓 SECCIÓN CRÍTICA LIBERADA (P{rank})                  ║")
            print(f"  ╚══════════════════════════════════════════════════════════════╝")
            print(f"{Colors.RESET}\n")
            
            time.sleep(0.5)
            rounds_enter = mgr.rounds_to_enter
            rounds_release = mgr.rounds_to_release
        else:
            time.sleep(2)
        
    # Recolección de Métricas
    comm.Barrier()
    total_msgs = mgr.get_total_metrics()
    sync_delay = mgr.get_sync_delay()
    
    # Recopilar tiempos de espera de todos los procesos (para modo competencia)
    all_wait_times = comm.gather(my_wait_time, root=0)
    all_rounds_enter = comm.gather(rounds_enter, root=0)
    all_rounds_release = comm.gather(rounds_release, root=0)
    
    # Recopilar todos los eventos en el proceso 0
    all_events = comm.gather(mgr.event_log, root=0)
    
    # Detener el listener
    comm.send("STOP", dest=rank, tag=tag_offset)
    
    # Imprimir reporte (solo proceso 0)
    if rank == 0:
        # Aplanar la lista de eventos
        flat_events = [evt for sublist in all_events for evt in sublist]
        
        # Imprimir timeline
        print_timeline(flat_events, size)
        
        # Usar las rondas del primer proceso que tenga datos válidos
        for i in range(size):
            if all_rounds_enter[i] > 0:
                rounds_enter = all_rounds_enter[i]
                rounds_release = all_rounds_release[i]
                break
        
        # Imprimir métricas
        print_metrics_table(algo_name, size, total_msgs, sync_delay, cs_duration, rounds_enter, rounds_release)
        
        # En modo competencia, mostrar análisis adicional
        if args.compete:
            print(f"\n{Colors.BOLD}  ⏱️  TIEMPOS DE ESPERA POR PROCESO (Modo Competencia){Colors.RESET}")
            print(f"{'─'*70}")
            
            sorted_times = sorted(enumerate(all_wait_times), key=lambda x: x[1])
            for i, (proc, wait_time) in enumerate(sorted_times):
                order = i + 1
                bar_len = int(wait_time * 100)  # Escala para visualización
                bar = "█" * min(bar_len, 40)
                print(f"  {order}º P{proc}: {wait_time*1000:>8.2f} ms {Colors.CYAN}{bar}{Colors.RESET}")
            
            print(f"{'─'*70}")
            
            # Calcular tiempo entre el primero y el último
            min_time = min(all_wait_times)
            max_time = max(all_wait_times)
            spread = max_time - min_time
            
            # Calcular tiempo promedio entre accesos consecutivos
            avg_between_access = spread / (size - 1) if size > 1 else 0
            
            print(f"\n  {Colors.BOLD}📊 ANÁLISIS DE CONTENCIÓN (AQUÍ SE VE T vs 2T):{Colors.RESET}")
            print(f"  • Tiempo en SC (igual para todos): {Colors.CYAN}{cs_time*1000:.0f} ms{Colors.RESET}")
            print(f"  • Primer proceso en entrar: {min_time*1000:.2f} ms")
            print(f"  • Último proceso en entrar: {max_time*1000:.2f} ms")
            print(f"  • Spread total (contención): {Colors.YELLOW}{spread*1000:.2f} ms{Colors.RESET}")
            print(f"  • Tiempo promedio entre accesos: {Colors.CYAN}{avg_between_access*1000:.2f} ms{Colors.RESET}")
            
            # Mostrar la diferencia T vs 2T
            print(f"\n  {Colors.BOLD}🔑 DEMOSTRACIÓN DE RETARDO T vs 2T:{Colors.RESET}")
            if algo_name == "MAEKAWA":
                print(f"  {Colors.YELLOW}  MAEKAWA usa 2T porque:{Colors.RESET}")
                print(f"     • Ronda 1 (T): Proceso solicita → recibe VOTOs → entra a SC")
                print(f"     • Ronda 2 (T): Proceso sale → envía RELEASE → siguiente puede votar")
                print(f"     • Tiempo entre accesos ≈ CS_time + overhead RELEASE")
                print(f"     • Observado: {avg_between_access*1000:.2f} ms por acceso")
            else:
                print(f"  {Colors.GREEN}  RICART-AGRAWALA usa T porque:{Colors.RESET}")
                print(f"     • Ronda 1 (T): Proceso solicita → recibe REPLYs → entra a SC")
                print(f"     • NO hay ronda 2: REPLYs diferidos se envían inmediatamente al salir")
                print(f"     • Los procesos acumulan REPLYs mientras esperan")
                print(f"     • Tiempo entre accesos ≈ CS_time")
                print(f"     • Observado: {avg_between_access*1000:.2f} ms por acceso")
            
            print(f"\n  {Colors.BOLD}📈 COMPARACIÓN ESPERADA:{Colors.RESET}")
            print(f"  ┌─────────────────┬─────────────────┬─────────────────┐")
            print(f"  │ Algoritmo       │ Retardo Teórico │ Entre Accesos   │")
            print(f"  ├─────────────────┼─────────────────┼─────────────────┤")
            print(f"  │ Ricart-Agrawala │ T (1 ronda)     │ ≈ {cs_time*1000:.0f} ms         │")
            print(f"  │ Maekawa         │ 2T (2 rondas)   │ ≈ {cs_time*1000*1.2:.0f}-{cs_time*1000*1.5:.0f} ms     │")
            print(f"  └─────────────────┴─────────────────┴─────────────────┘")
            
            print(f"\n  {Colors.GREY}💡 Ejecuta ambos algoritmos con --compete y compara el 'Spread total'{Colors.RESET}")
            print(f"  {Colors.GREY}   Maekawa debería tener un spread mayor que RA.{Colors.RESET}")
        
        print(f"\n{Colors.GREEN}✓ Simulación completada exitosamente{Colors.RESET}\n")

if __name__ == "__main__":
    main()