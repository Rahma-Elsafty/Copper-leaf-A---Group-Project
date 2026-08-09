## Architecture Comparison

| Architecture | Answer Accuracy (12 test questions) | Retrieval Accuracy | Avg. tokens/query | Avg. latency/query |
|---|---:|---:|---:|---:|
| Naive RAG | 11/12 | 12/12 | 47 | 8.71s |
| Hybrid Search (Vector + BM25) | 11/12 | 12/12 | 39 | 8.14s |
| Agentic RAG (Multi-hop) | 11/12 | 12/12 | 43 | 15.18s |

### Findings

All three architectures retrieved the required evidence for all 12 test questions, achieving **100% retrieval accuracy**. However, they achieved **11/12 (91.7%) answer accuracy**, so retrieval success did not always guarantee a fully correct final answer.

**Naive RAG** achieved the same answer and retrieval accuracy as the other architectures, but used the highest average number of output tokens and was slightly slower than Hybrid Search.

**Hybrid Search**, combining vector similarity with BM25 keyword retrieval, achieved the same accuracy while producing the shortest answers and the lowest average latency. This is particularly useful for exact identifiers, menu items, section names, and other keyword-sensitive queries where lexical matching can complement semantic retrieval.

**Agentic RAG** also achieved 11/12 answer accuracy and 100% retrieval accuracy, but its average latency was almost twice that of Hybrid Search. Its additional reasoning and retrieval steps therefore did not provide a measurable accuracy improvement on this test set.

### Final Architecture Choice

Based on the evaluation and the expected query workload, **Hybrid Search is selected as the default retrieval architecture**.

The knowledge base is expected to receive many direct questions about menu items, prices, allergens, policies, reservations, and takeaway information. These queries benefit from both semantic similarity and exact keyword matching, while users also benefit from lower response latency.

Agentic RAG can still be used selectively for more complex, multi-part questions that require information from several parts of the knowledge base. This avoids paying the additional latency and token cost of agentic retrieval for every query.

Therefore, the final routing strategy is:

```text
                         User Query
                             |
                             v
                    Query Complexity Check
                       /               \
                      /                 \
             Simple / Direct       Multi-part /
             / Keyword-heavy      Decomposition
                  |                     |
                  v                     v
            Hybrid Search          Agentic RAG
                  |                     |
                  v                     v
             Final Answer          Final Answer
