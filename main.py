import multiprocessing
import time
import math
import queue
from config import generate_maekawa_voting_sets, NETWORK_DELAY
from ricart_agrawala import run_ricart_agrawala
from maekawa import run_maekawa

def print_detailed_metrics(algo_name, collected_stats, N, k_active, E):
    total_msgs = 0
    entries = []
    exits = []
    response_times = []
    
    sorted_events = sorted(collected_stats, key=lambda x: x[1] if isinstance(x[1], float) else 0)
    
    for item in sorted_events:
        tag = item[0]
        val = item[1]
        if tag == 'MSG_COUNT': total_msgs += val
        elif tag == 'CS_ENTRY': entries.append(val)
        elif tag == 'CS_EXIT': exits.append(val)
        elif tag == 'RESPONSE_TIME': response_times.append(val)

    avg_msgs = total_msgs / k_active if k_active > 0 else 0
    avg_resp = sum(response_times) / len(response_times) if response_times else 0
    
    sync_delays = []
    if len(exits) > 0 and len(entries) > 0:
        entries.sort()
        exits.sort()
        for i in range(len(entries) - 1):
            if i < len(exits):
                delay = entries[i+1] - exits[i]
                if delay > 0: sync_delays.append(delay)
    avg_sd = sum(sync_delays) / len(sync_delays) if sync_delays else 0
    throughput = 1 / (avg_sd + E) if (avg_sd + E) > 0 else 0
    
    theory_avg = 0
    
    if "Ricart" in algo_name:
        theory_avg = 2 * (N - 1)
    else:
        # Calcular K real basado en la topología de Grid generada
        voting_sets = generate_maekawa_voting_sets(N)
        k_sizes_remote = [len(v_set) - 1 for v_set in voting_sets.values()]
        K_remote_avg = sum(k_sizes_remote) / len(k_sizes_remote)
        
        if "Light" in algo_name:
            # Flujo: Request(K) + Locked(K) + Release(K)
            theory_avg = 3 * K_remote_avg
        else: # Heavy Demand
            # Flujo base + Inquire/Relinquish/Failed
            theory_avg = 5 * K_remote_avg

    theory_total = theory_avg * k_active

    print("\n" + "="*70)
    print(f" RESULTADOS MÉTRICAS: {algo_name}")
    print("="*70)
    print(f"Configuración: N={N}, k={k_active}, E={E}s, S(i) = {2*math.sqrt(N)-1:.2f}")
    print("-" * 70)
    print(f"[1] COMPLEJIDAD DE MENSAJES")
    print(f"    Total Sistema    : {total_msgs} (Teórico: ~{theory_total:.1f})")
    print(f"    Promedio por CS  : {avg_msgs:.1f} (Teórico: ~{theory_avg:.1f})")
    
    print("-" * 70)
    print(f"[2] SYNCHRONIZATION DELAY (SD) : {avg_sd:.4f} s")
    print(f"[3] RESPONSE TIME PROMEDIO     : {avg_resp:.4f} s")
    print(f"[4] SYSTEM THROUGHPUT          : {throughput:.4f}")
    print("="*70 + "\n")

def run_simulation(algo_type, N, k_active, E):
    print(f"\n>>> En Ejecución: {algo_type} <<<")
    manager = multiprocessing.Manager()
    queues = [manager.Queue() for _ in range(N)]
    stats_queue = manager.Queue()
    collected_stats = []
    active_ids = list(range(k_active))
    processes = []
    
    if "Ricart" in algo_type:
        for i in range(N):
            is_active = i in active_ids
            p = multiprocessing.Process(target=run_ricart_agrawala, args=(i, N, queues, stats_queue, E, 0, is_active))
            processes.append(p)
            
    elif "Maekawa" in algo_type:
        voting_sets = generate_maekawa_voting_sets(N)
        for i in range(N):
            is_active = i in active_ids
            start_delay = 0
            use_opt = False
            
            if is_active:
                if "Light" in algo_type:
                    start_delay = 0 
                    use_opt = False
                else:
                    start_delay = 0
                    use_opt = True

            p = multiprocessing.Process(target=run_maekawa, args=(i, voting_sets[i], queues, stats_queue, E, start_delay, is_active, use_opt))
            processes.append(p)

    for p in processes: p.start()
    
    TIMEOUT_LIMIT = (k_active * (E + (15 * NETWORK_DELAY))) + 45 # Timeout
    print(f"Esperando finalización (Timeout: {TIMEOUT_LIMIT:.1f}s)...")

    start_t = time.time()
    done_count = 0
    deadlock_detected = False
    
    while done_count < k_active:
        if time.time() - start_t > TIMEOUT_LIMIT:
            print("\n" + "!"*60)
            if "Light" in algo_type:
                print(" TIMEOUT ALCANZADO (DEADLOCK)")
                print(" Maekawa Under Light se bloqueó por espera circular.")
            else:
                print(" ERROR: TIMEOUT ALCANZADO")
            print("!"*60 + "\n")
            deadlock_detected = True
            break
        try:
            while True:
                item = stats_queue.get_nowait()
                collected_stats.append(item)
                if item[0] == 'DONE': done_count += 1
        except queue.Empty: time.sleep(0.1)
        
    for q in queues: q.put("STOP")
    time.sleep(1)
    try:
        while not stats_queue.empty(): collected_stats.append(stats_queue.get_nowait())
    except: pass
    
    for p in processes: 
        if p.is_alive(): p.terminate()
        
    if not deadlock_detected:
        print_detailed_metrics(algo_type, collected_stats, N, k_active, E)

def main():
    try:
        N = int(input("Total Nodos (N): "))
        k = int(input(f"Solicitantes (k): "))
        E = float(input("Tiempo CS (s): "))
    except: return

    scenarios = ["Ricart-Agrawala", "Maekawa (Light Demand)", "Maekawa (Heavy Demand)"] 
    
    for sc in scenarios:
        run_simulation(sc, N, k, E)
        time.sleep(2)

if __name__ == "__main__":
    main()