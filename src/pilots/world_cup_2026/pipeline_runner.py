import os
import sys

# Ensure the root of the project is in python path for absolute imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.analyzer import run_analysis
from src.collector import run_collection
from src.scraper import run_comment_scraper

if __name__ == "__main__":
    pilot_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(pilot_dir, 'config.yaml')
    
    print("🚀 INICIANDO PIPELINE PILOTO COPA DO MUNDO 2026...")
    print(f"📄 Carregando configuração de: {config_path}\n")
    
    # 1. Rodar a Ingestão / Coletor
    print("\n--- PASSO 1: YouTube API Data Ingestion ---")
    run_collection(config_path)
    
    # 2. Rodar o Scraper de comentários
    print("\n--- PASSO 2: Comments Threads Extraction ---")
    run_comment_scraper()
    
    # 3. Rodar a Análise Qualitativa por IA (Gemini)
    print("\n--- PASSO 3: AI Video and Semantics Synthesis ---")
    run_analysis(config_path)
    
    print("\n✅ PIPELINE PILOTO CONCLUÍDO COM SUCESSO!")
    print("Os dados estão persistidos no Supabase e prontos para exportação pelo despachante do n8n.")
