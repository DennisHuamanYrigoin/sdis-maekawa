# Distributed Mutual Exclusion Simulator (Ricart–Agrawala & Maekawa)

Simulador en Python de algoritmos de exclusión mutua distribuida, ejecutado con **multiprocessing**. Incluye:
- **Ricart–Agrawala** (consenso unánime).
- **Maekawa** (voting/quórums) en modos *Light Demand* y *Heavy Demand* (con optimización `INQUIRE/RELINQUISH`).

## Requisitos

- **Python 3.10.12**
- Dependencias (pip):
  - `tabulate==0.9.0`

> Nota: En esta versión del código, la ejecución principal usa `multiprocessing`.

### Instalación

Se recomienda usar un entorno virtual:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install tabulate==0.9.0
```

## Estructura del proyecto

- `main.py`: interfaz por consola y orquestación de escenarios; recolecta eventos y calcula métricas.
- `config.py`: constantes de tipos de mensajes, `NETWORK_DELAY` y generación de quórums para Maekawa.
- `ricart_agrawala.py`: implementación del algoritmo Ricart–Agrawala.
- `maekawa.py`: implementación del algoritmo de Maekawa (Light/Heavy).

## Cómo ejecutar

Ejecuta el simulador:

```bash
python main.py
```

El programa pedirá por consola:

1. **Total Nodos (N)**: número total de procesos/nodos.
2. **Solicitantes (k)**: cuántos procesos (de los N) intentarán entrar a la sección crítica.
3. **Tiempo CS (s)**: duración (en segundos) de la sección crítica por invocación.

Estos inputs se leen con `input()` dentro de `main.py`.

### Ejemplo de ejecución

```text
Total Nodos (N): 9
Solicitantes (k): 3
Tiempo CS (s): 0.5
```

Luego el programa ejecuta automáticamente 3 escenarios:
- `Ricart-Agrawala`
- `Maekawa Light Demand`
- `Maekawa Heavy Demand`

## Métricas reportadas

El simulador recolecta eventos en una `stats_queue` (por ejemplo: `CS_ENTRY`, `CS_EXIT`, `RESPONSE_TIME`, `MSG_COUNT`, `DONE`) y luego imprime métricas agregadas.

Entre otras, se muestra:

- **Total de mensajes del sistema** (suma de `MSG_COUNT` reportado por los procesos).
- **Promedio de mensajes por entrada a CS** (aprox. `total_msgs / k`).
- **Response time promedio** (tiempo desde solicitud hasta entrada a CS).
- **Synchronization delay** aproximado a partir de tiempos de entrada/salida.
- **Throughput** estimado.
- Comparación contra valores teóricos:
  - Ricart–Agrawala: \(2N - 1\) mensajes por entrada.[1]
  - Maekawa Light: aproximación basada en el tamaño promedio del quórum generado.
  - Maekawa Heavy: aproximación basada en el tamaño promedio del quórum generado.

## Explicación breve de los algoritmos

### Ricart–Agrawala
Cada nodo que quiere entrar a la sección crítica envía un `REQUEST` a los demás nodos y espera `REPLY`. Si un nodo recibe un `REQUEST` mientras está solicitando y tiene prioridad (por timestamp/ID), difiere su respuesta; si no, responde inmediatamente. Al salir de la CS, responde a los diferidos.

### Maekawa (quórums)
En lugar de pedir permiso a todos los nodos, cada nodo \(i\) solicita permiso solo a los nodos de su conjunto de votación \(S_i\) (quórum). Cada miembro del quórum concede voto (bloqueo) a un solicitante a la vez (`LOCKED`) y encola solicitudes conflictivas; al salir se libera con `RELEASE`.

- **Light Demand**: intenta operar con baja contención; se usa principalmente `REQUEST`, `LOCKED` y `RELEASE`.
- **Heavy Demand**: cuando hay contención, puede enviar `INQUIRE` y recibir `RELINQUISH` para romper esperas circulares y evitar deadlocks.

### Quórums usados en este código (grid)
Los quórums para Maekawa se generan en `config.py` usando una construcción tipo **fila/columna** basada en \(k=\lceil\sqrt{N}\rceil\): para el nodo \(i\), \(S_i\) contiene nodos de su fila y su columna (más el propio nodo), recortado si \(N\) no llena la grilla.

## Notas sobre timeouts y deadlocks

- La simulación aplica un **timeout** aproximado en función de `k` y el tiempo de CS (`E`). Si se alcanza el timeout, se imprime un mensaje (por ejemplo, indicando bloqueo bajo Light en Maekawa) y se finalizan procesos.
- `NETWORK_DELAY` se usa para simular latencia de red antes de enviar mensajes.

## Recomendaciones de uso

- Para pruebas rápidas:
  - `N = 4` o `N = 9`
  - `k = 1..3`
  - `Tiempo CS = 0.1..0.5`
- Para observar contención real en Maekawa Heavy, prueba valores con más solicitantes (p. ej. `k` cercano a `N`).