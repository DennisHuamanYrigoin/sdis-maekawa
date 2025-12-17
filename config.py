import math

# Tipos de Mensajes
REQUEST = 'REQUEST'
REPLY = 'REPLY'
RELEASE = 'RELEASE'
LOCKED = 'LOCKED'
FAILED = 'FAILED'
INQUIRE = 'INQUIRE'
RELINQUISH = 'RELINQUISH'

NETWORK_DELAY = 1

def generate_maekawa_voting_sets(N):
    if N == 0: return {}
    k = int(math.ceil(math.sqrt(N)))
    voting_sets = {}
    for i in range(N):
        row = i // k
        col = i % k
        s_i = set()
        for c in range(k): # Fila
            member = row * k + c
            if member < N: s_i.add(member)
        for r in range(k): # Columna
            member = r * k + col
            if member < N: s_i.add(member)
        s_i.add(i) # Self
        voting_sets[i] = list(s_i)
    return voting_sets