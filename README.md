# Simulación de Exclusión Mutua Distribuida

Simulación comparativa de los algoritmos **Maekawa** y **Ricart-Agrawala** para exclusión mutua distribuida usando MPI.

## Descripción

Este proyecto implementa y compara dos algoritmos clásicos de exclusión mutua distribuida:

| Algoritmo | Mensajes | Retardo |
|-----------|----------|---------|
| **Ricart-Agrawala** | O(N) ≈ 2(N-1) | T (1 ronda) |
| **Maekawa** | O(√N) ≈ 3√N | 2T (2 rondas) |

## Requisitos

- Python 3.x
- mpi4py
- OpenMPI o MPICH

### Instalación de dependencias

```bash
pip install mpi4py
```

## Uso

### Comandos básicos

```bash
# Ricart-Agrawala con 4 procesos
mpiexec -n 4 python simulacion_algoritmos.py --algo RA

# Maekawa con 9 procesos (debe ser cuadrado perfecto)
mpiexec -n 9 python simulacion_algoritmos.py --algo MAEKAWA
```

## Restricciones

- **Maekawa**: N debe ser un cuadrado perfecto (4, 9, 16, 25...)
- **Ricart-Agrawala**: Cualquier N ≥ 2

## Ejemplo de salida

```
======================================================================
  SIMULACIÓN DE EXCLUSIÓN MUTUA DISTRIBUIDA  
======================================================================
  Algoritmo: MAEKAWA
  Procesos:  9
======================================================================

[000.123s] [P0] 📤 Solicitando acceso a SC...
[000.234s] [P0] 🗳️ VOTO recibido de P1 (1/4)
...
[000.456s] [P0] ✅ Entrando a SC!
```

## Métricas

La simulación muestra:

- **Mensajes totales**: Cantidad de mensajes enviados
- **Retardo de sincronización**: Rondas necesarias para entrar a SC
- **Tiempo en sección crítica**: Duración dentro de la SC
