"""
Offline AI Evaluation: Sentiment Classification Benchmark.
Measures Accuracy, Precision, Recall, and Macro-F1 on synthetic ground-truth golden datasets.
"""

import json
from pathlib import Path

from src.fetcher import map_sentiment


def load_sentiment_goldens():
    fixture_path = Path(__file__).parent / "fixtures" / "sentiment_goldens.json"
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


def calculate_classification_metrics(y_true, y_pred, labels):
    """
    Computes per-class Precision, Recall, F1 and overall Accuracy and Macro-F1.
    """
    total = len(y_true)
    correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
    accuracy = correct / total if total > 0 else 0.0

    metrics_per_class = {}
    f1_scores = []

    for label in labels:
        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == label and yp == label)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt != label and yp == label)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == label and yp != label)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        metrics_per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(1 for yt in y_true if yt == label),
        }
        f1_scores.append(f1)

    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0

    return {
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_class": metrics_per_class,
    }


def test_sentiment_classification_accuracy_and_macro_f1():
    """
    Evaluate sentiment mapping accuracy and Macro-F1 against synthetic ground-truth goldens.
    Asserts both Accuracy and Macro-F1 exceed target quality thresholds.
    """
    goldens = load_sentiment_goldens()
    labels = ["Positivo", "Negativo", "Neutro"]

    y_true = []
    y_pred = []

    for item in goldens:
        expected = item["expected_sentiment"]
        raw_output = item["model_sentiment_output"]
        predicted = map_sentiment(raw_output)

        y_true.append(expected)
        y_pred.append(predicted)

    eval_report = calculate_classification_metrics(y_true, y_pred, labels)

    print("\n--- AI EVALUATION REPORT: SENTIMENT CLASSIFICATION ---")
    print(f"Total Golden Samples: {len(goldens)}")
    print(f"Overall Accuracy:     {eval_report['accuracy']:.4f}")
    print(f"Macro-F1 Score:       {eval_report['macro_f1']:.4f}")
    for lbl, m in eval_report["per_class"].items():
        print(f"  Class '{lbl}': Precision={m['precision']:.3f}, Recall={m['recall']:.3f}, F1={m['f1']:.3f}")

    # Benchmark Acceptance Thresholds
    assert eval_report["accuracy"] >= 0.80, f"Accuracy {eval_report['accuracy']} below threshold 0.80"
    assert eval_report["macro_f1"] >= 0.80, f"Macro-F1 {eval_report['macro_f1']} below threshold 0.80"
