# ricart_agrawala.py
import time
from config import REQUEST, REPLY, NETWORK_DELAY

def run_ricart_agrawala(node_id, total_nodes, queues, stats_queue, cs_duration, start_delay, active_participant):
    my_queue = queues[node_id]
    clock = 0
    msgs_sent_count = 0
    
    time.sleep(start_delay)

    if active_participant:
        # 1. SOLICITUD
        clock += 1
        my_ts = clock
        replies_needed = total_nodes - 1
        replies_received = 0
        deferred_nodes = []
        
        req_start_time = time.perf_counter()
        
        # --- (BROADCAST) ---
        time.sleep(NETWORK_DELAY) 
        for i in range(total_nodes):
            if i != node_id:
                queues[i].put((REQUEST, my_ts, node_id))
                msgs_sent_count += 1

        requesting = True
        
        # 2. ESPERA
        while replies_received < replies_needed:
            msg = my_queue.get()
            if msg == "STOP": return
            msg_type, src_ts, src_id = msg
            clock = max(clock, src_ts) + 1
            
            if msg_type == REQUEST:
                my_priority = (my_ts, node_id)
                other_priority = (src_ts, src_id)
                
                if requesting and (my_priority < other_priority):
                    deferred_nodes.append(src_id)
                else:
                    time.sleep(NETWORK_DELAY)
                    queues[src_id].put((REPLY, clock, node_id))
                    msgs_sent_count += 1
            
            elif msg_type == REPLY:
                replies_received += 1

        # 3. SECCIÓN CRÍTICA
        entry_time = time.perf_counter()
        stats_queue.put(('CS_ENTRY', entry_time))
        stats_queue.put(('RESPONSE_TIME', entry_time - req_start_time))
        
        time.sleep(cs_duration)
        
        exit_time = time.perf_counter()
        stats_queue.put(('CS_EXIT', exit_time))
        
        requesting = False
        
        # 4. SALIDA (REPLY A DIFERIDOS)
        if deferred_nodes:
            time.sleep(NETWORK_DELAY)
            for target_id in deferred_nodes:
                queues[target_id].put((REPLY, clock, node_id))
                msgs_sent_count += 1
            
        stats_queue.put(('DONE', node_id))

    while True:
        try:
            msg = my_queue.get(timeout=0.5)
            if msg == "STOP": break
            msg_type, src_ts, src_id = msg
            clock = max(clock, src_ts) + 1
            if msg_type == REQUEST:
                time.sleep(NETWORK_DELAY)
                queues[src_id].put((REPLY, clock, node_id))
                msgs_sent_count += 1
        except: pass

    stats_queue.put(('MSG_COUNT', msgs_sent_count))