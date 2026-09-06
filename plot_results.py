#!/usr/bin/env python3
"""
Script per generare grafici di analisi dei risultati benchmark per il progetto "16 Trucks Problem".

Genera confronti tra solver e strategie per le versioni SAT (base_problem) e ottimizzazione (minimization).

Usage:
    python plot_results.py                          # Genera tutti i grafici
    python plot_results.py --problem base           # Solo base_problem
    python plot_results.py --plot-type solver       # Solo confronti solver
    python plot_results.py --strategies 1 5 10      # Solo strategie specifiche
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from pathlib import Path
import argparse
import warnings
from typing import Tuple, List, Optional, Dict

warnings.filterwarnings('ignore')

# ================================
# Configurazione Grafica
# ================================

class PlotConfig:
    """Configurazione centralizzata per tutti i parametri grafici."""

    # Dimensioni figure
    FIGURE_SIZE_SOLVER = (16, 8)
    FIGURE_SIZE_STRATEGY = (18, 10)
    DPI = 300

    # Colori solver
    SOLVER_COLORS = {
        'chuffed': '#1f77b4',   # Blu
        'gecode': '#ff7f0e',    # Arancione
        'HiGHs': '#2ca02c',     # Verde
        'ortools': '#d62728'    # Rosso
    }

    # Colori stati minimization
    STATUS_COLORS = {
        'OPTIMAL': '#2ca02c',          # Verde
        'SAT_MIN': '#ff7f0e',          # Arancione
        'TIMEOUT_OPTIMAL': '#17becf',  # Ciano
        'ERROR_MIN': '#d62728',        # Rosso
        'TIMEOUT': '#7f7f7f'           # Grigio (per base_problem)
    }

    # Marker
    MARKER_SUCCESS = 'o'
    MARKER_TIMEOUT = 'x'
    MARKER_SIZE_SUCCESS = 30
    MARKER_SIZE_TIMEOUT = 100

    # Timeout
    TIMEOUT_VALUE = 300.0  # secondi
    TIMEOUT_Y_POSITION = 400.0  # Posizione Y per marker timeout nei grafici

    # Font
    FONT_TITLE = 16
    FONT_LABEL = 14
    FONT_LEGEND = 11
    FONT_TICK = 10

    # Grid
    GRID_ALPHA = 0.3
    GRID_LINESTYLE = '--'

    # Scala Y logaritmica
    Y_MIN = 0.05
    Y_MAX = 500.0


# ================================
# Funzioni di Caricamento Dati
# ================================

def load_solver_data(base_path: Path, solver_name: str, problem_type: str) -> Optional[pd.DataFrame]:
    """
    Carica dati di un solver dai file processed.

    Args:
        base_path: Path alla directory base (base_problem/ o minimization/)
        solver_name: Nome del solver (chuffed, gecode, HiGHs, ortools)
        problem_type: 'base' o 'minimization'

    Returns:
        DataFrame con colonne standardizzate o None se file non trovato
    """
    csv_path = base_path / 'results' / 'processed' / f'{solver_name}.csv'

    try:
        df = pd.read_csv(csv_path)

        # Converti Time_Seconds a numerico
        df['Time_Seconds'] = pd.to_numeric(df['Time_Seconds'], errors='coerce')

        # Aggiungi colonna indice numerico
        df['Instance_Num'] = df['Instance'].str.extract(r'i(\d+)').astype(int)

        # RIORDINAMENTO: ordina per Instance_Num (i file potrebbero non essere ordinati)
        df = df.sort_values('Instance_Num').reset_index(drop=True)

        # Standardizza colonna Success
        if problem_type == 'base':
            df['Success'] = df['SAT'] == 'SAT'
        else:
            # Per minimization: successo se OPTIMAL o SAT_MIN
            df['Success'] = df['SAT'].isin(['OPTIMAL', 'SAT_MIN'])

        return df

    except FileNotFoundError:
        print(f"[WARN] File non trovato: {csv_path}")
        return None
    except Exception as e:
        print(f"[WARN] Errore caricamento {csv_path}: {e}")
        return None


def load_strategy_data(base_path: Path, strategy_id: int, problem_type: str) -> Optional[pd.DataFrame]:
    """
    Carica dati di una strategia dai file processed.

    IMPORTANTE: I file strategie NON sono ordinati e contengono solo un sottoset di istanze.
    Questa funzione riordina per Instance_Num.

    Args:
        base_path: Path alla directory base
        strategy_id: ID della strategia (0-12 per base, 0-10 per minimization)
        problem_type: 'base' o 'minimization'

    Returns:
        DataFrame ordinato con colonne standardizzate o None se file non trovato
    """
    csv_path = base_path / 'results' / 'processed' / f'{strategy_id}.csv'

    try:
        df = pd.read_csv(csv_path)

        # RIORDINAMENTO: estrai numero da "i42" -> 42
        df['Instance_Num'] = df['Instance'].str.extract(r'i(\d+)').astype(int)
        df = df.sort_values('Instance_Num').reset_index(drop=True)

        # Converti Time_Seconds a numerico
        df['Time_Seconds'] = pd.to_numeric(df['Time_Seconds'], errors='coerce')

        # Standardizza colonna Success
        if problem_type == 'base':
            df['Success'] = df['SAT'] == 'SAT'
        else:
            df['Success'] = df['SAT'].isin(['OPTIMAL', 'SAT_MIN'])

        return df

    except FileNotFoundError:
        print(f"[WARN] File non trovato: {csv_path}")
        return None
    except Exception as e:
        print(f"[WARN] Errore caricamento {csv_path}: {e}")
        return None


# ================================
# Funzioni di Preprocessing
# ================================

def detect_timeout_types(strategy_df: pd.DataFrame, default_df: pd.DataFrame) -> pd.DataFrame:
    """
    Classifica i timeout per base_problem in due categorie.

    - TIMEOUT_SOLVABLE: strategia ha timeout ma default ha risolto (problema risolvibile)
    - TIMEOUT_HARD: sia strategia che default hanno timeout (problema difficile)

    Args:
        strategy_df: DataFrame della strategia da analizzare
        default_df: DataFrame della strategia 0_default (riferimento)

    Returns:
        DataFrame modificato con colonna Status
    """
    df = strategy_df.copy()

    # Merge con default per confrontare Success
    merged = df.merge(
        default_df[['Instance', 'Success']],
        on='Instance',
        suffixes=('', '_default'),
        how='left'
    )

    # Aggiungi colonna Status
    df['Status'] = 'SAT'  # default

    # SAT rimane SAT
    df.loc[df['Success'], 'Status'] = 'SAT'

    # TIMEOUT: distingui tra solvable e hard
    timeout_mask = ~df['Success']

    # TIMEOUT_SOLVABLE: strategia timeout, default ha risolto
    timeout_solvable_mask = timeout_mask & merged['Success_default']
    df.loc[timeout_solvable_mask, 'Status'] = 'TIMEOUT_SOLVABLE'

    # TIMEOUT_HARD: sia strategia che default hanno timeout
    timeout_hard_mask = timeout_mask & (~merged['Success_default'])
    df.loc[timeout_hard_mask, 'Status'] = 'TIMEOUT_HARD'

    num_solvable = timeout_solvable_mask.sum()
    num_hard = timeout_hard_mask.sum()
    if num_solvable > 0 or num_hard > 0:
        print(f"   -> Timeout: {num_solvable} risolvibili, {num_hard} difficili")

    return df


def detect_timeout_optimal(strategy_df: pd.DataFrame, default_df: pd.DataFrame) -> pd.DataFrame:
    """
    Rileva timeout "ottimali" per minimization: SAT_MIN con Min_Cost uguale a 0_default.

    Questi timeout hanno raggiunto l'ottimo ma sono stati interrotti prima della prova formale.
    Vengono marcati come TIMEOUT_OPTIMAL per distinguerli visivamente.

    Args:
        strategy_df: DataFrame della strategia da analizzare
        default_df: DataFrame della strategia 0_default (riferimento)

    Returns:
        DataFrame modificato con stato TIMEOUT_OPTIMAL dove applicabile
    """
    # Crea copia per evitare modifiche al DataFrame originale
    df = strategy_df.copy()

    # Merge con default per confrontare Min_Cost
    merged = df.merge(
        default_df[['Instance', 'Min_Cost']],
        on='Instance',
        suffixes=('', '_default'),
        how='left'
    )

    # Identifica timeout ottimali: SAT_MIN con costo uguale a default
    timeout_optimal_mask = (
        (merged['SAT'] == 'SAT_MIN') &
        (merged['Min_Cost'] == merged['Min_Cost_default'])
    )

    # Aggiungi colonna Status se non esiste
    if 'Status' not in df.columns:
        df['Status'] = df['SAT']

    # Marca come TIMEOUT_OPTIMAL
    df.loc[timeout_optimal_mask, 'Status'] = 'TIMEOUT_OPTIMAL'

    num_timeout_optimal = timeout_optimal_mask.sum()
    if num_timeout_optimal > 0:
        print(f"   -> Rilevati {num_timeout_optimal} timeout ottimali")

    return df


# ================================
# Funzioni di Plotting
# ================================

def plot_solver_comparison(base_path: Path, problem_type: str, solvers: List[str], output_dir: Path):
    """
    Genera grafici di confronto tra solver.

    Crea due versioni:
    - FULL: include timeout con marker 'x' a Y=400s
    - SUCCESS: solo istanze risolte con successo

    Args:
        base_path: Path alla directory base
        problem_type: 'base' o 'minimization'
        solvers: Lista nomi solver da confrontare
        output_dir: Directory output per salvare grafici
    """
    print(f"\nGenerazione confronto solver per {problem_type}...")

    # Carica dati di tutti i solver
    solver_data = {}
    for solver in solvers:
        df = load_solver_data(base_path, solver, problem_type)
        if df is not None:
            solver_data[solver] = df
            print(f"   [OK] {solver}: {len(df)} istanze")

    if not solver_data:
        print("   [WARN] Nessun dato solver caricato, skip.")
        return

    # ===== VERSIONE FULL (con timeout) =====
    fig, ax = plt.subplots(figsize=PlotConfig.FIGURE_SIZE_SOLVER, dpi=PlotConfig.DPI)

    for solver, df in solver_data.items():
        color = PlotConfig.SOLVER_COLORS.get(solver, '#000000')

        # Prepara array Y: Time_Seconds per successi, TIMEOUT_Y_POSITION per timeout
        y_values = df['Time_Seconds'].copy()
        y_values[~df['Success']] = PlotConfig.TIMEOUT_Y_POSITION

        # Plot linea continua che collega tutti i punti
        ax.plot(
            df['Instance_Num'],
            y_values,
            c=color,
            marker=PlotConfig.MARKER_SUCCESS,
            markersize=4,
            linewidth=1.5,
            label=solver,
            alpha=0.8
        )

        # Evidenzia timeout con marker X
        timeout_df = df[~df['Success']].copy()
        if not timeout_df.empty:
            ax.scatter(
                timeout_df['Instance_Num'],
                [PlotConfig.TIMEOUT_Y_POSITION] * len(timeout_df),
                c=color,
                marker=PlotConfig.MARKER_TIMEOUT,
                s=PlotConfig.MARKER_SIZE_TIMEOUT,
                alpha=0.6,
                edgecolors='black',
                linewidths=0.5
            )

    # Linea timeout
    ax.axhline(y=PlotConfig.TIMEOUT_VALUE, color='red', linestyle='--', linewidth=1.5,
               label=f'Timeout ({PlotConfig.TIMEOUT_VALUE}s)', alpha=0.7)

    # Annotazioni min_cost per minimization
    if problem_type == 'minimization':
        # Usa solo il primo solver per le annotazioni per evitare sovrapposizioni
        first_solver = list(solver_data.keys())[0]
        df = solver_data[first_solver]

        for idx, row in df.iterrows():
            if 'Min_Cost' in row and pd.notna(row['Min_Cost']):
                # Determina il testo dell'annotazione
                if row['SAT'] == 'ERROR_MIN':
                    cost_text = 'N/A'
                else:
                    cost_text = f"{int(row['Min_Cost'])}"

                # Posizione Y: usa TIMEOUT_Y_POSITION per timeout, altrimenti Time_Seconds
                y_pos = PlotConfig.TIMEOUT_Y_POSITION if not row['Success'] else row['Time_Seconds']

                ax.annotate(
                    cost_text,
                    xy=(row['Instance_Num'], y_pos),
                    xytext=(0, 8),  # Offset verticale di 8 punti
                    textcoords='offset points',
                    fontsize=7,
                    alpha=0.7,
                    ha='center',
                    va='bottom'
                )

    ax.set_xlabel('Instance Index', fontsize=PlotConfig.FONT_LABEL)
    ax.set_ylabel('Time (seconds)', fontsize=PlotConfig.FONT_LABEL)
    ax.set_title(f'Solver Comparison - {problem_type.capitalize()} (with timeout)',
                 fontsize=PlotConfig.FONT_TITLE, fontweight='bold')
    ax.set_yscale('log')
    ax.set_ylim(PlotConfig.Y_MIN, PlotConfig.Y_MAX)
    ax.grid(True, alpha=PlotConfig.GRID_ALPHA, linestyle=PlotConfig.GRID_LINESTYLE)
    ax.legend(fontsize=PlotConfig.FONT_LEGEND, loc='upper left')
    ax.tick_params(labelsize=PlotConfig.FONT_TICK)

    plt.tight_layout()
    output_file = output_dir / f'solver_comparison_{problem_type}_full.png'
    plt.savefig(output_file, dpi=PlotConfig.DPI, bbox_inches='tight')
    plt.close()
    print(f"   [OK] Salvato: {output_file.name}")

    # ===== VERSIONE SUCCESS (solo successi) =====
    fig, ax = plt.subplots(figsize=PlotConfig.FIGURE_SIZE_SOLVER, dpi=PlotConfig.DPI)

    for solver, df in solver_data.items():
        color = PlotConfig.SOLVER_COLORS.get(solver, '#000000')

        # Prepara array Y: Time_Seconds per successi, NaN per timeout
        # Così la linea si interrompe dove ci sono timeout
        y_values = df['Time_Seconds'].copy()
        y_values[~df['Success']] = np.nan

        # Plot linea con interruzioni dove ci sono timeout
        ax.plot(
            df['Instance_Num'],
            y_values,
            c=color,
            marker=PlotConfig.MARKER_SUCCESS,
            markersize=4,
            linewidth=1.5,
            label=solver,
            alpha=0.8
        )

    # Annotazioni min_cost per minimization (solo successi)
    if problem_type == 'minimization':
        # Usa solo il primo solver per le annotazioni per evitare sovrapposizioni
        first_solver = list(solver_data.keys())[0]
        df = solver_data[first_solver]

        # Solo per istanze risolte con successo
        success_df = df[df['Success']].copy()
        for idx, row in success_df.iterrows():
            if 'Min_Cost' in row and pd.notna(row['Min_Cost']):
                cost_text = f"{int(row['Min_Cost'])}"

                ax.annotate(
                    cost_text,
                    xy=(row['Instance_Num'], row['Time_Seconds']),
                    xytext=(0, 8),  # Offset verticale di 8 punti
                    textcoords='offset points',
                    fontsize=7,
                    alpha=0.7,
                    ha='center',
                    va='bottom'
                )

    ax.set_xlabel('Instance Index', fontsize=PlotConfig.FONT_LABEL)
    ax.set_ylabel('Time (seconds)', fontsize=PlotConfig.FONT_LABEL)
    ax.set_title(f'Solver Comparison - {problem_type.capitalize()} (successful only)',
                 fontsize=PlotConfig.FONT_TITLE, fontweight='bold')
    ax.set_yscale('log')
    ax.set_ylim(PlotConfig.Y_MIN, PlotConfig.TIMEOUT_VALUE * 1.2)
    ax.grid(True, alpha=PlotConfig.GRID_ALPHA, linestyle=PlotConfig.GRID_LINESTYLE)
    ax.legend(fontsize=PlotConfig.FONT_LEGEND, loc='upper left')
    ax.tick_params(labelsize=PlotConfig.FONT_TICK)

    plt.tight_layout()
    output_file = output_dir / f'solver_comparison_{problem_type}_success.png'
    plt.savefig(output_file, dpi=PlotConfig.DPI, bbox_inches='tight')
    plt.close()
    print(f"   [OK] Salvato: {output_file.name}")


def plot_strategy_combined(base_path: Path, problem_type: str, strategy_ids: List[int], output_dir: Path):
    """
    Genera grafico combinato con 0_default vs tutte le altre strategie.

    0_default è evidenziato con linea nera spessa, le altre sono trasparenti.

    Args:
        base_path: Path alla directory base
        problem_type: 'base' o 'minimization'
        strategy_ids: Lista ID strategie da plottare (escluso 0)
        output_dir: Directory output
    """
    print(f"\nGenerazione confronto strategie combinato per {problem_type}...")

    # Carica 0_default
    default_df = load_strategy_data(base_path, 0, problem_type)
    if default_df is None:
        print("   [WARN] Impossibile caricare 0_default, skip.")
        return

    print(f"   [OK] 0_default: {len(default_df)} istanze")

    # Carica altre strategie
    strategy_data = {}
    for sid in strategy_ids:
        if sid == 0:
            continue
        df = load_strategy_data(base_path, sid, problem_type)
        if df is not None:
            strategy_data[sid] = df
            print(f"   [OK] Strategia {sid}: {len(df)} istanze")

    if not strategy_data:
        print("   [WARN] Nessuna strategia caricata, skip.")
        return

    # Colormap per strategie (escluso nero per default)
    colors = plt.cm.tab20(np.linspace(0, 1, 20))

    # ===== VERSIONE FULL =====
    fig, ax = plt.subplots(figsize=PlotConfig.FIGURE_SIZE_STRATEGY, dpi=PlotConfig.DPI)

    # Plot altre strategie (background, trasparente)
    for i, (sid, df) in enumerate(strategy_data.items()):
        success_df = df[df['Success']].copy()
        if not success_df.empty:
            ax.plot(
                success_df['Instance'],
                success_df['Time_Seconds'],
                c=colors[i % 20],
                marker=PlotConfig.MARKER_SUCCESS,
                markersize=4,
                linewidth=1,
                label=f'Strategy {sid}',
                alpha=0.5
            )

    # Plot 0_default (foreground, evidenziato)
    default_success = default_df[default_df['Success']].copy()
    ax.plot(
        default_success['Instance'],
        default_success['Time_Seconds'],
        c='black',
        marker=PlotConfig.MARKER_SUCCESS,
        markersize=6,
        linewidth=2.5,
        label='0_default',
        alpha=1.0,
        zorder=10
    )

    # Timeout di default
    default_timeout = default_df[~default_df['Success']].copy()
    if not default_timeout.empty:
        ax.scatter(
            default_timeout['Instance'],
            [PlotConfig.TIMEOUT_Y_POSITION] * len(default_timeout),
            c='black',
            marker=PlotConfig.MARKER_TIMEOUT,
            s=PlotConfig.MARKER_SIZE_TIMEOUT,
            alpha=0.6,
            zorder=10
        )

    # Linea timeout
    ax.axhline(y=PlotConfig.TIMEOUT_VALUE, color='red', linestyle='--', linewidth=1.5,
               label=f'Timeout ({PlotConfig.TIMEOUT_VALUE}s)', alpha=0.7)

    ax.set_xlabel('Instance', fontsize=PlotConfig.FONT_LABEL)
    ax.set_ylabel('Time (seconds)', fontsize=PlotConfig.FONT_LABEL)
    ax.set_title(f'Strategy Comparison - {problem_type.capitalize()} (combined)',
                 fontsize=PlotConfig.FONT_TITLE, fontweight='bold')
    ax.set_yscale('log')
    ax.set_ylim(PlotConfig.Y_MIN, PlotConfig.Y_MAX)
    ax.grid(True, alpha=PlotConfig.GRID_ALPHA, linestyle=PlotConfig.GRID_LINESTYLE)

    # Legenda: 0_default in alto, altre strategie sotto
    handles, labels = ax.get_legend_handles_labels()
    # Riordina: default first
    if '0_default' in labels:
        idx = labels.index('0_default')
        handles = [handles[idx]] + handles[:idx] + handles[idx+1:]
        labels = [labels[idx]] + labels[:idx] + labels[idx+1:]

    ax.legend(handles, labels, fontsize=PlotConfig.FONT_LEGEND - 1, loc='upper left', ncol=2)
    ax.tick_params(labelsize=PlotConfig.FONT_TICK)
    plt.xticks(rotation=45, ha='right')

    plt.tight_layout()
    output_file = output_dir / f'strategy_combined_{problem_type}_full.png'
    plt.savefig(output_file, dpi=PlotConfig.DPI, bbox_inches='tight')
    plt.close()
    print(f"   [OK] Salvato: {output_file.name}")

    # ===== VERSIONE SUCCESS =====
    fig, ax = plt.subplots(figsize=PlotConfig.FIGURE_SIZE_STRATEGY, dpi=PlotConfig.DPI)

    for i, (sid, df) in enumerate(strategy_data.items()):
        success_df = df[df['Success']].copy()
        if not success_df.empty:
            ax.plot(
                success_df['Instance'],
                success_df['Time_Seconds'],
                c=colors[i % 20],
                marker=PlotConfig.MARKER_SUCCESS,
                markersize=4,
                linewidth=1,
                label=f'Strategy {sid}',
                alpha=0.5
            )

    ax.plot(
        default_success['Instance'],
        default_success['Time_Seconds'],
        c='black',
        marker=PlotConfig.MARKER_SUCCESS,
        markersize=6,
        linewidth=2.5,
        label='0_default',
        alpha=1.0,
        zorder=10
    )

    ax.set_xlabel('Instance', fontsize=PlotConfig.FONT_LABEL)
    ax.set_ylabel('Time (seconds)', fontsize=PlotConfig.FONT_LABEL)
    ax.set_title(f'Strategy Comparison - {problem_type.capitalize()} (successful only)',
                 fontsize=PlotConfig.FONT_TITLE, fontweight='bold')
    ax.set_yscale('log')
    ax.set_ylim(PlotConfig.Y_MIN, PlotConfig.TIMEOUT_VALUE * 1.2)
    ax.grid(True, alpha=PlotConfig.GRID_ALPHA, linestyle=PlotConfig.GRID_LINESTYLE)

    handles, labels = ax.get_legend_handles_labels()
    if '0_default' in labels:
        idx = labels.index('0_default')
        handles = [handles[idx]] + handles[:idx] + handles[idx+1:]
        labels = [labels[idx]] + labels[:idx] + labels[idx+1:]

    ax.legend(handles, labels, fontsize=PlotConfig.FONT_LEGEND - 1, loc='upper left', ncol=2)
    ax.tick_params(labelsize=PlotConfig.FONT_TICK)
    plt.xticks(rotation=45, ha='right')

    plt.tight_layout()
    output_file = output_dir / f'strategy_combined_{problem_type}_success.png'
    plt.savefig(output_file, dpi=PlotConfig.DPI, bbox_inches='tight')
    plt.close()
    print(f"   [OK] Salvato: {output_file.name}")


def plot_strategy_vs_default(base_path: Path, problem_type: str, strategy_id: int,
                             default_df: pd.DataFrame, output_dir: Path):
    """
    Genera grafico individuale: strategia N vs 0_default.

    Per minimization, usa colori diversi per stati (OPTIMAL, SAT_MIN, TIMEOUT_OPTIMAL, ERROR_MIN).

    Args:
        base_path: Path alla directory base
        problem_type: 'base' o 'minimization'
        strategy_id: ID strategia da confrontare
        default_df: DataFrame di 0_default (già caricato)
        output_dir: Directory output
    """
    # Carica strategia
    strategy_df = load_strategy_data(base_path, strategy_id, problem_type)
    if strategy_df is None:
        return

    # Per minimization, rileva timeout ottimali
    if problem_type == 'minimization':
        strategy_df = detect_timeout_optimal(strategy_df, default_df)
        if 'Status' not in strategy_df.columns:
            strategy_df['Status'] = strategy_df['SAT']

    # Plot
    fig, ax = plt.subplots(figsize=PlotConfig.FIGURE_SIZE_STRATEGY, dpi=PlotConfig.DPI)

    # Plot 0_default (background)
    default_success = default_df[default_df['Success']].copy()
    ax.plot(
        default_success['Instance'],
        default_success['Time_Seconds'],
        c='black',
        marker=PlotConfig.MARKER_SUCCESS,
        markersize=5,
        linewidth=2,
        label='0_default',
        alpha=0.8,
        zorder=5
    )

    # Timeout default
    default_timeout = default_df[~default_df['Success']].copy()
    if not default_timeout.empty:
        ax.scatter(
            default_timeout['Instance'],
            [PlotConfig.TIMEOUT_Y_POSITION] * len(default_timeout),
            c='black',
            marker=PlotConfig.MARKER_TIMEOUT,
            s=PlotConfig.MARKER_SIZE_TIMEOUT,
            alpha=0.4,
            zorder=5
        )

    # Plot strategia
    if problem_type == 'base':
        # Base: linea base + colori per stato (come minimization)

        # Rileva tipi di timeout
        strategy_df = detect_timeout_types(strategy_df, default_df)

        # 1. Plot linea di base per la strategia (blu, come minimization)
        y_base = strategy_df['Time_Seconds'].copy()
        y_base[~strategy_df['Success']] = PlotConfig.TIMEOUT_Y_POSITION

        ax.plot(
            strategy_df['Instance'],
            y_base,
            c='#1f77b4',  # Blu
            linewidth=1.5,
            alpha=0.7,
            zorder=1,
            label=f'Strategy {strategy_id}'
        )

        # 2. Scatter sopra con colori per stato
        status_colors_base = {
            'SAT': '#2ca02c',  # Verde
            'TIMEOUT_SOLVABLE': '#ff7f0e',  # Arancione
            'TIMEOUT_HARD': '#d62728'  # Rosso
        }

        for status, color in status_colors_base.items():
            status_df = strategy_df[strategy_df['Status'] == status].copy()

            if status_df.empty:
                continue

            if status == 'SAT':
                y_values = status_df['Time_Seconds'].values
                marker = PlotConfig.MARKER_SUCCESS
                size = PlotConfig.MARKER_SIZE_SUCCESS
                label = 'SAT'
            else:
                # TIMEOUT
                y_values = [PlotConfig.TIMEOUT_Y_POSITION] * len(status_df)
                marker = PlotConfig.MARKER_TIMEOUT
                size = PlotConfig.MARKER_SIZE_TIMEOUT
                if status == 'TIMEOUT_SOLVABLE':
                    label = 'Timeout (solvable)'
                else:
                    label = 'Timeout (hard)'

            ax.scatter(
                status_df['Instance'],
                y_values,
                c=color,
                marker=marker,
                s=size,
                label=label,
                alpha=0.8,
                zorder=3,
                edgecolors='white',
                linewidths=0.5
            )

    else:
        # Minimization: linea base + colori per stato

        # 1. Plot linea di base per la strategia (blu, come base_problem)
        y_base = strategy_df['Time_Seconds'].copy()
        y_base[strategy_df.get('Status', strategy_df['SAT']).isin(['SAT_MIN', 'ERROR_MIN'])] = PlotConfig.TIMEOUT_Y_POSITION

        ax.plot(
            strategy_df['Instance'],
            y_base,
            c='#1f77b4',  # Blu
            linewidth=1.5,
            alpha=0.7,
            zorder=1,
            label=f'Strategy {strategy_id}'
        )

        # 2. Scatter sopra con colori per stato
        for status, color in PlotConfig.STATUS_COLORS.items():
            status_df = strategy_df[strategy_df.get('Status', strategy_df['SAT']) == status].copy()

            if status_df.empty:
                continue

            # Timeout vanno a Y fisso
            if status in ['SAT_MIN', 'ERROR_MIN']:
                y_values = [PlotConfig.TIMEOUT_Y_POSITION] * len(status_df)
                marker = PlotConfig.MARKER_TIMEOUT
                size = PlotConfig.MARKER_SIZE_TIMEOUT
            elif status == 'TIMEOUT_OPTIMAL':
                # Timeout ottimale: usa tempo reale ma marker timeout
                y_values = status_df['Time_Seconds'].values
                marker = PlotConfig.MARKER_TIMEOUT
                size = PlotConfig.MARKER_SIZE_TIMEOUT
            else:
                # OPTIMAL
                y_values = status_df['Time_Seconds'].values
                marker = PlotConfig.MARKER_SUCCESS
                size = PlotConfig.MARKER_SIZE_SUCCESS

            ax.scatter(
                status_df['Instance'],
                y_values,
                c=color,
                marker=marker,
                s=size,
                label=status,
                alpha=0.8,
                zorder=3,
                edgecolors='white',
                linewidths=0.5
            )

        # Annotazioni min_cost per minimization

        # 1. Annotazioni per DEFAULT (tutti i punti) - offset a sinistra
        for i, (idx, row) in enumerate(default_df.iterrows()):
            if 'Min_Cost' in row and pd.notna(row['Min_Cost']):
                cost_text = f"{int(row['Min_Cost'])}"

                # Posizione Y: usa TIMEOUT_Y_POSITION se non ha successo, altrimenti Time_Seconds
                y_pos = PlotConfig.TIMEOUT_Y_POSITION if not row['Success'] else row['Time_Seconds']

                ax.annotate(
                    cost_text,
                    xy=(i, y_pos),
                    xytext=(-8, 8),  # Offset: sinistra e alto
                    textcoords='offset points',
                    fontsize=7,
                    alpha=0.8,
                    ha='right',
                    va='bottom',
                    color='black',
                    fontweight='bold'
                )

        # 2. Annotazioni per STRATEGIA (solo SAT_MIN e ERROR_MIN) - offset a destra
        for i, (idx, row) in enumerate(strategy_df.iterrows()):
            status = row.get('Status', row['SAT'])

            # Annota solo se non è ottimale (SAT_MIN o ERROR_MIN)
            if status in ['SAT_MIN', 'ERROR_MIN']:
                if 'Min_Cost' in row and pd.notna(row['Min_Cost']):
                    # Determina il testo dell'annotazione
                    if status == 'ERROR_MIN':
                        cost_text = 'N/A'
                    else:
                        cost_text = f"{int(row['Min_Cost'])}"

                    # Posizione Y
                    y_pos = PlotConfig.TIMEOUT_Y_POSITION

                    ax.annotate(
                        cost_text,
                        xy=(i, y_pos),
                        xytext=(8, 8),  # Offset: destra e alto
                        textcoords='offset points',
                        fontsize=7,
                        alpha=0.8,
                        ha='left',
                        va='bottom',
                        color='#d62728'  # Rosso per distinguere
                    )

    # Linea timeout
    ax.axhline(y=PlotConfig.TIMEOUT_VALUE, color='red', linestyle='--', linewidth=1.5,
               label=f'Timeout ({PlotConfig.TIMEOUT_VALUE}s)', alpha=0.7)

    ax.set_xlabel('Instance', fontsize=PlotConfig.FONT_LABEL)
    ax.set_ylabel('Time (seconds)', fontsize=PlotConfig.FONT_LABEL)
    ax.set_title(f'Strategy {strategy_id} vs 0_default - {problem_type.capitalize()}',
                 fontsize=PlotConfig.FONT_TITLE, fontweight='bold')
    ax.set_yscale('log')
    ax.set_ylim(PlotConfig.Y_MIN, PlotConfig.Y_MAX)
    ax.grid(True, alpha=PlotConfig.GRID_ALPHA, linestyle=PlotConfig.GRID_LINESTYLE)
    ax.legend(fontsize=PlotConfig.FONT_LEGEND, loc='upper left')
    ax.tick_params(labelsize=PlotConfig.FONT_TICK)
    plt.xticks(rotation=45, ha='right')

    plt.tight_layout()
    output_file = output_dir / f'strategy_{strategy_id}_vs_default_{problem_type}.png'
    plt.savefig(output_file, dpi=PlotConfig.DPI, bbox_inches='tight')
    plt.close()
    print(f"   [OK] Salvato: strategy_{strategy_id}_vs_default_{problem_type}.png")


# ================================
# Main e CLI
# ================================

def main():
    parser = argparse.ArgumentParser(
        description='Genera grafici di analisi benchmark per il progetto 16 Trucks Problem',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  python plot_results.py                          # Genera tutti i grafici
  python plot_results.py --problem base           # Solo base_problem
  python plot_results.py --plot-type solver       # Solo confronti solver
  python plot_results.py --strategies 1 5 10      # Solo strategie specifiche
        """
    )

    parser.add_argument(
        '--problem',
        choices=['base', 'minimization', 'both'],
        default='both',
        help='Tipo di problema da analizzare (default: both)'
    )

    parser.add_argument(
        '--plot-type',
        choices=['solver', 'strategy', 'both'],
        default='both',
        help='Tipo di grafico da generare (default: both)'
    )

    parser.add_argument(
        '--strategies',
        type=int,
        nargs='+',
        help='Lista ID strategie da plottare (es: 1 5 10). Se omesso, plotta tutte.'
    )

    args = parser.parse_args()

    # Determina problemi da processare
    problems = ['base', 'minimization'] if args.problem == 'both' else [args.problem]

    # Configurazione solver e strategie per problema
    config = {
        'base': {
            'path': Path('base_problem'),
            'solvers': ['chuffed', 'gecode', 'HiGHs', 'ortools'],
            'strategies': list(range(13))  # 0-12
        },
        'minimization': {
            'path': Path('minimization'),
            'solvers': ['chuffed', 'gecode', 'HiGHs', 'ortools'],
            'strategies': list(range(11))  # 0-10
        }
    }

    print("=" * 80)
    print("GENERAZIONE GRAFICI ANALISI BENCHMARK")
    print("=" * 80)

    for problem_type in problems:
        cfg = config[problem_type]
        base_path = cfg['path']
        output_dir = base_path / 'results' / 'figures'
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\nProcessing: {problem_type}")
        print(f"   Output: {output_dir}")

        # Confronto solver
        if args.plot_type in ['solver', 'both']:
            plot_solver_comparison(base_path, problem_type, cfg['solvers'], output_dir)

        # Confronto strategie
        if args.plot_type in ['strategy', 'both']:
            # Determina strategie da plottare
            if args.strategies:
                strategy_ids = [s for s in args.strategies if s in cfg['strategies']]
            else:
                strategy_ids = cfg['strategies']

            # Combinato
            plot_strategy_combined(base_path, problem_type, strategy_ids, output_dir)

            # Individuali (escluso 0)
            default_df = load_strategy_data(base_path, 0, problem_type)
            if default_df is not None:
                print(f"\nGenerazione confronti individuali per {problem_type}...")
                for sid in strategy_ids:
                    if sid == 0:
                        continue
                    plot_strategy_vs_default(base_path, problem_type, sid, default_df, output_dir)

    print("\n" + "=" * 80)
    print("COMPLETATO!")
    print("=" * 80)


if __name__ == '__main__':
    main()
