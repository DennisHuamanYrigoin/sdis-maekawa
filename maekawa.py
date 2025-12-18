# maekawa.py
import time
import heapq
from config import REQUEST, LOCKED, RELEASE, FAILED, INQUIRE, RELINQUISH, NETWORK_DELAY

def run_maekawa(node_id, voting_set, queues, stats_queue, log_queue, cs_duration, start_delay, active_participant, use_inquire_optimization):
    my_queue = queues[node_id]
    clock = 0
    msgs_sent_count = 0
    
    # Arbitro
    voted_for = None
    voted_for_ts = float('inf')
    request_queue = []
    sent_inquire_to = None
    
    # Solicitante
    received_votes = set()
    needed_votes = len(voting_set)
    has_requested = False
    is_in_cs = False
    my_ts = 0
    req_start_time = 0

    time.sleep(start_delay)

    if active_participant:
        clock += 1
        my_ts = clock
        has_requested = True
        req_start_time = time.perf_counter()
        
        # REQUEST (Multicast al Voting Set)
        time.sleep(NETWORK_DELAY) 
        for member in voting_set:
            queues[member].put((REQUEST, my_ts, node_id))
            if member != node_id:
                msgs_sent_count += 1
                # LOG
                log_queue.put(f"[MK] Node {node_id} -> Node {member}: REQUEST (TS={my_ts})")

    while True:
        if active_participant and not has_requested and not is_in_cs and len(received_votes) == 0:
             stats_queue.put(('DONE', node_id))
             active_participant = False

        try: msg = my_queue.get(timeout=0.1)
        except: continue
        if msg == "STOP": break

        msg_type, src_ts, src_id = msg
        clock = max(clock, src_ts) + 1

        # Lógica del Arbitro
        if msg_type == REQUEST:
            if voted_for is None:
                # Voto
                voted_for = src_id
                voted_for_ts = src_ts
                time.sleep(NETWORK_DELAY)
                queues[src_id].put((LOCKED, clock, node_id))
                if src_id != node_id:
                    msgs_sent_count += 1
                    log_queue.put(f"[MK] Node {node_id} -> Node {src_id}: LOCKED")
            else:
                heapq.heappush(request_queue, (src_ts, src_id))
                
                if use_inquire_optimization: # HEAVY DEMAND
                    curr = (voted_for_ts, voted_for)
                    new = (src_ts, src_id)
                    # Si el nuevo tiene prioridad, recuperar el voto
                    if new < curr and sent_inquire_to != voted_for:
                        time.sleep(NETWORK_DELAY)
                        queues[voted_for].put((INQUIRE, clock, node_id))
                        if voted_for != node_id:
                            msgs_sent_count += 1
                            log_queue.put(f"[MK] Node {node_id} -> Node {voted_for}: INQUIRE")
                        sent_inquire_to = voted_for
                    else:
                        # En Heavy sí enviamos FAILED
                        queues[src_id].put((FAILED, clock, node_id)) 
                        if src_id != node_id:
                            msgs_sent_count += 1
                            log_queue.put(f"[MK] Node {node_id} -> Node {src_id}: FAILED")
                else: # LIGHT DEMAND
                    pass

        elif msg_type == RELEASE:
            if src_id == voted_for:
                voted_for = None
                voted_for_ts = float('inf')
                sent_inquire_to = None
                if request_queue:
                    next_ts, next_node = heapq.heappop(request_queue)
                    voted_for = next_node
                    voted_for_ts = next_ts
                    time.sleep(NETWORK_DELAY)
                    queues[next_node].put((LOCKED, clock, node_id))
                    if next_node != node_id:
                        msgs_sent_count += 1
                        log_queue.put(f"[MK] Node {node_id} -> Node {next_node}: LOCKED (Handoff)")

        elif msg_type == RELINQUISH:
            if src_id == voted_for:
                heapq.heappush(request_queue, (voted_for_ts, voted_for))
                voted_for = None
                voted_for_ts = float('inf')
                sent_inquire_to = None
                if request_queue:
                    next_ts, next_node = heapq.heappop(request_queue)
                    voted_for = next_node
                    voted_for_ts = next_ts
                    time.sleep(NETWORK_DELAY)
                    queues[next_node].put((LOCKED, clock, node_id))
                    if next_node != node_id:
                        msgs_sent_count += 1
                        log_queue.put(f"[MK] Node {node_id} -> Node {next_node}: LOCKED (Post-Relinquish)")

        # Lógica del Solicitante
        if has_requested:
            if msg_type == LOCKED:
                received_votes.add(src_id)
                if len(received_votes) == needed_votes:
                    is_in_cs = True
                    has_requested = False
                    entry_time = time.perf_counter()
                    stats_queue.put(('CS_ENTRY', entry_time))
                    stats_queue.put(('RESPONSE_TIME', entry_time - req_start_time))
                    log_queue.put(f"[MK] Node {node_id} *** ENTERING CS ***")
                    
                    time.sleep(cs_duration)
                    
                    exit_time = time.perf_counter()
                    stats_queue.put(('CS_EXIT', exit_time))
                    log_queue.put(f"[MK] Node {node_id} *** EXITING CS ***")
                    
                    is_in_cs = False
                    received_votes.clear()
                    
                    # RELEASE (Multicast al Voting Set)
                    time.sleep(NETWORK_DELAY)
                    for member in voting_set:
                        queues[member].put((RELEASE, clock, node_id))
                        if member != node_id:
                            msgs_sent_count += 1
                            log_queue.put(f"[MK] Node {node_id} -> Node {member}: RELEASE")
            
            elif msg_type == INQUIRE and use_inquire_optimization:
                if not is_in_cs and src_id in received_votes:
                    received_votes.remove(src_id)
                    time.sleep(NETWORK_DELAY)
                    queues[src_id].put((RELINQUISH, clock, node_id))
                    if src_id != node_id:
                        msgs_sent_count += 1
                        log_queue.put(f"[MK] Node {node_id} -> Node {src_id}: RELINQUISH")
            
            elif msg_type == FAILED:
                pass

    stats_queue.put(('MSG_COUNT', msgs_sent_count))