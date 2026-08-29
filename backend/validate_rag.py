from rag_pipeline import evaluate_compliance

test_queries = [
    "What are the structural definitions and slope rules for exterior walls?",
    "What common angles are specified for bay windows?",
    "What does Equation 170.2-G calculate for Battery Energy Storage Systems?"
]

def run_enterprise_validation():
    print("=" * 70)
    print("RUNNING ENTERPRISE RAG VALIDATION SUITE")
    print("=" * 70)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n[Test Case {i} of {len(test_queries)}]")
        print(f"Query: {query}")
        print("-" * 70)
        report = evaluate_compliance(query)
        print(report)
        print("=" * 70)

if __name__ == "__main__":
    run_enterprise_validation()