"""
Offline AI Evaluation: Retrieval and RAG Ranking Benchmark.
Measures Recall@K (K=1, K=3, K=5) and MRR (Mean Reciprocal Rank) on synthetic semantic queries.
"""

import math


def cosine_similarity(v1, v2):
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_v1 = math.sqrt(sum(a * a for a in v1))
    norm_v2 = math.sqrt(sum(b * b for b in v2))
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return dot / (norm_v1 * norm_v2)


def rank_documents(query_embedding, documents):
    """
    Ranks documents by cosine similarity to query embedding.
    """
    scored = []
    for doc in documents:
        sim = cosine_similarity(query_embedding, doc["embedding"])
        scored.append((doc["id"], sim))
    # Sort descending by similarity score
    scored.sort(key=lambda x: x[1], reverse=True)
    return [doc_id for doc_id, _ in scored]


def calculate_retrieval_metrics(queries, corpus, k_values=(1, 3, 5)):
    """
    Computes Recall@K and MRR across a suite of query test cases.
    """
    recall_at_k = {k: 0.0 for k in k_values}
    mrr_total = 0.0
    num_queries = len(queries)

    for q in queries:
        ranked_doc_ids = rank_documents(q["query_embedding"], corpus)
        target_id = q["relevant_doc_id"]

        # Reciprocal Rank calculation
        if target_id in ranked_doc_ids:
            rank = ranked_doc_ids.index(target_id) + 1
            mrr_total += 1.0 / rank
        else:
            rank = float("inf")

        # Recall@K calculation
        for k in k_values:
            top_k_ids = set(ranked_doc_ids[:k])
            if target_id in top_k_ids:
                recall_at_k[k] += 1.0

    mean_recall = {k: (hits / num_queries) for k, hits in recall_at_k.items()}
    mrr = mrr_total / num_queries if num_queries > 0 else 0.0

    return {
        "mrr": mrr,
        "recall_at_k": mean_recall,
        "num_queries": num_queries,
    }


def test_rag_retrieval_recall_and_mrr():
    """
    Evaluate vector retrieval ranking across synthetic queries with known relevant documents.
    Validates Recall@1, Recall@3, Recall@5 and Mean Reciprocal Rank (MRR).
    """
    # Synthetic corpus with distinct directional unit vectors
    corpus = [
        {"id": "doc_tactics", "title": "Tática 4-3-3 e Meio Campo", "embedding": [0.95, 0.10, 0.05, 0.00]},
        {"id": "doc_tickets", "title": "Preço de Ingressos e Custo", "embedding": [0.05, 0.95, 0.10, 0.00]},
        {"id": "doc_stadiums", "title": "Logística e Sedes dos Estádios", "embedding": [0.05, 0.10, 0.95, 0.00]},
        {"id": "doc_influencers", "title": "Criadores e Reacts do YouTube", "embedding": [0.00, 0.05, 0.10, 0.95]},
        {"id": "doc_drama", "title": "Polêmica de Convocação e Lesões", "embedding": [0.70, 0.60, 0.00, 0.10]},
    ]

    # Queries aligned closely to corpus vectors with small synthetic noise
    queries = [
        {
            "query": "Como o time joga no esquema 4-3-3?",
            "relevant_doc_id": "doc_tactics",
            "query_embedding": [0.92, 0.12, 0.02, 0.00],
        },
        {
            "query": "Quanto custa o ingresso para a final?",
            "relevant_doc_id": "doc_tickets",
            "query_embedding": [0.02, 0.94, 0.08, 0.01],
        },
        {
            "query": "Quais estádios vão receber os jogos de abertura?",
            "relevant_doc_id": "doc_stadiums",
            "query_embedding": [0.08, 0.05, 0.91, 0.02],
        },
        {
            "query": "Quem são os influencers com mais engajamento?",
            "relevant_doc_id": "doc_influencers",
            "query_embedding": [0.01, 0.02, 0.12, 0.92],
        },
    ]

    metrics = calculate_retrieval_metrics(queries, corpus, k_values=(1, 3, 5))

    print("\n--- AI EVALUATION REPORT: RAG RETRIEVAL & RANKING ---")
    print(f"Evaluated Queries: {metrics['num_queries']}")
    print(f"Mean Reciprocal Rank (MRR): {metrics['mrr']:.4f}")
    for k, rec in metrics["recall_at_k"].items():
        print(f"Recall@{k}: {rec * 100:.1f}%")

    # Benchmark Acceptance Criteria
    assert metrics["recall_at_k"][1] >= 0.75, "Recall@1 should be at least 75%"
    assert metrics["recall_at_k"][3] == 1.0, "Recall@3 should be 100% on benchmark"
    assert metrics["mrr"] >= 0.85, "MRR should be at least 0.85"
