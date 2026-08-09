# Retrieval Architecture Evaluation

## Overview

This evaluation compares three Retrieval-Augmented Generation (RAG) architectures using the same fixed set of 12 questions and the same knowledge base.

The evaluated architectures are:

1. **Naive RAG**
2. **Hybrid Search**
3. **Agentic RAG**

The goal is to compare their answer quality, retrieval quality, token usage, and latency.

---

## Evaluation Setup

All architectures use the same:

- Knowledge base
- Test questions
- Embedding model
- LLM
- Evaluation procedure

This makes the comparison focused on the differences between the retrieval architectures rather than differences in the underlying data or model.

### Test Set

The evaluation contains **12 questions** covering simple information-retrieval tasks related to the Copperleaf Restaurant knowledge base.

The questions include topics such as:

- Menu items
- Prices
- Allergens
- Dietary information
- Reservations
- Takeaway orders
- Customer service

---

## Architectures

### 1. Naive RAG

The Naive RAG architecture retrieves relevant documents from the vector store and passes them to the language model to generate the final answer.

**Flow:**

```text
User Query
    ↓
Vector Retrieval
    ↓
Retrieved Documents
    ↓
LLM
    ↓
Final Answer
