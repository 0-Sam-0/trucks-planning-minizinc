#!/usr/bin/env python3
"""
Script per unire i risultati dei diversi solver in un unico CSV.
Formato output: wide format con formato numerico italiano (virgola decimale, ; separatore).
Compatibile con Google Sheets Italia.
"""

import pandas as pd
import os

# Configurazione
SOLVER_FILES = ['chuffed.csv', 'gecode.csv', 'HiGHs.csv', 'ortools.csv']
OUTPUT_FILE = 'solver_comparison.csv'

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Lista per contenere i dataframe
    dfs = []

    # Leggi ogni file CSV del solver
    for solver_file in SOLVER_FILES:
        filepath = os.path.join(script_dir, solver_file)

        if not os.path.exists(filepath):
            print(f"Warning: {solver_file} non trovato, salto questo solver")
            continue

        # Leggi il CSV
        df = pd.read_csv(filepath)

        # Estrai il nome del solver dal filename (rimuovi .csv)
        solver_name = solver_file.replace('.csv', '')

        # Rinomina le colonne aggiungendo il prefisso del solver (tranne Instance)
        df = df.rename(columns={
            col: f"{solver_name}_{col}" if col != 'Instance' else col
            for col in df.columns
        })

        dfs.append(df)

    if not dfs:
        print("Errore: nessun file CSV trovato!")
        return

    # Merge di tutti i dataframe sulla colonna Instance
    result = dfs[0]
    for df in dfs[1:]:
        result = result.merge(df, on='Instance', how='outer')

    # Ordina per Instance
    result = result.sort_values('Instance')

    # Converti numeri float in formato italiano (virgola decimale)
    # Identifica colonne numeriche
    numeric_cols = result.select_dtypes(include=['float64', 'float32']).columns

    for col in numeric_cols:
        # Converti i float in stringhe con virgola
        result[col] = result[col].apply(lambda x: str(x).replace('.', ',') if pd.notna(x) else '')

    # Salva il CSV con separatore punto e virgola (formato italiano)
    output_path = os.path.join(script_dir, OUTPUT_FILE)
    result.to_csv(output_path, sep=';', index=False)

    print(f"File creato con successo: {OUTPUT_FILE}")
    print(f"Istanze totali: {len(result)}")
    print(f"Solver inclusi: {', '.join([f.replace('.csv', '') for f in SOLVER_FILES if os.path.exists(os.path.join(script_dir, f))])}")

if __name__ == '__main__':
    main()
