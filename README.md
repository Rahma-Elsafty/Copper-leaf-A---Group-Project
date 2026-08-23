# Memory & RAG Lab — Giving the Copperleaf Agent Memory and Grounded Knowledge

> **This README covers the Memory & RAG agent only.** For the separate
> Decomposition & Planning agent (a different agent, reusing the same
> `mcp_server/` and `db/`, never touching this one's code path), see
> [`README_PLANNING_AGENT.md`](README_PLANNING_AGENT.md).

## Overview

This project extends the existing **Copperleaf MCP system** with two capabilities that were missing from the original agent:

1. **Long-term memory** — so useful information from previous interactions can survive beyond the current session.
2. **Grounded retrieval (RAG)** — so the agent can answer questions using internal knowledge documents that are not exposed as MCP tools.

The extension reuses the existing:

- `mcp_server/`
- `db/`
- MCP tools
- MCP resources
- existing agent/client structure

The goal is not to replace the existing MCP system, but to extend it with memory, context management, retrieval, and verification.

---

## 1. The Problem

The original Copperleaf agent could interact with structured operational data through MCP tools, but two important limitations remained.

### Problem 1 — Session-level forgetting

Information discussed during one interaction was not reliably available in later interactions.

For example, a staff member may provide an important operational preference or recurring piece of information during a previous interaction. Once the session ends, the agent has no mechanism for deciding whether that information should be forgotten or retained for future use.

This makes repeated interactions inefficient and can cause the agent to ask for the same information again.

### Problem 2 — Knowledge outside the database

Not every useful piece of knowledge belongs in the operational database or deserves its own MCP tool.

Copperleaf also has internal knowledge such as:

- food and menu information
- allergen information
- customer-service policies
- reservation guidance
- takeaway policies
- general operational policies

These documents are better handled through a retrieval layer than by creating a separate MCP tool for every individual fact.

Therefore, the system needs a RAG layer that can retrieve relevant document chunks and ground the generated answer in those documents.

---

## 2. System Architecture

The extended system contains four major layers:

```text
                         ┌─────────────────────┐
                         │       User          │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Copperleaf Agent  │
                         └──────────┬──────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                │                   │                   │
                ▼                   ▼                   ▼
        ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
        │    Memory    │    │     RAG      │    │     MCP      │
        │    System    │    │    System    │    │    Server    │
        └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
               │                   │                   │
               ▼                   ▼                   ▼
        ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
        │ Episodic /   │    │ Vector DB +  │    │ Existing DB  │
        │ Semantic     │    │ Hybrid RAG   │    │              │
        └──────────────┘    └──────────────┘    └──────────────┘
```

The agent can therefore combine:

- current conversation context
- scratchpad state
- previous memories
- retrieved document knowledge
- live information from the existing MCP server

before producing a response.

---

## 3. Memory Architecture

The memory system is divided into separate components so that temporary conversation context is not confused with long-term knowledge.

### 3.1 Short-Term Memory

Short-term memory maintains a rolling buffer of recent conversation messages.

Its purpose is to preserve the most recent conversational context while preventing the context window from growing indefinitely.

Example:

```text
Turn 1
Turn 2
Turn 3
...
Turn 10
```

When the buffer reaches its limit, older information becomes eligible for routing.

### 3.2 Scratchpad

The scratchpad is separate from the conversation transcript.

It stores the agent's current:

- goal
- sub-goal
- working state
- intermediate information

Example:

```text
Current goal:
Answer the user's inventory question.

Current sub-goal:
Find ingredients below the reorder threshold.

Working state:
location_id = 2
retrieval completed = true
MCP result available = true
```

This distinction is important because pruning the conversation should not destroy the agent's current working state.

---

## 4. Promote-or-Drop Routing

When short-term memory overflows, an aging item is passed to a routing decision.

The router has only two possible outcomes:

```text
              Aging memory item
                      │
                      ▼
              Promote-or-Drop
                 /        \
                /          \
             DROP        EPISODIC
              │              │
              ▼              ▼
           Forget       Store episode
```

The router does not write directly to semantic memory.

Instead, it records the decision and the reasoning behind it.

Example:

```text
Decision: PROMOTE

Reason:
The information is likely to be useful across future
sessions and represents a recurring operational fact.
```

or:

```text
Decision: DROP

Reason:
The information is temporary and only relevant to
the current interaction.
```

This makes the routing decision visible and auditable.

---

## 5. Episodic Memory

Promoted memories are stored as episodes.

An episode represents a concrete event or interaction rather than an immediately generalized fact.

Example:

```text
Episode:
A staff member requested that a particular operational
preference be remembered for future interactions.

Timestamp:
2026-08-XX

Source:
agent_session
```

The episodic store acts as the historical source from which semantic knowledge can later be consolidated.

---

## 6. Semantic Memory and Consolidation

Semantic memory is not written directly by the promote-or-drop router.

Instead, a separate consolidation process periodically reads the episodic store and produces stable semantic facts.

```text
Episodic Memory
      │
      │ periodic consolidation
      ▼
Semantic Memory
```

The consolidation layer is responsible for:

- updating changed facts
- preserving previous versions
- expiring stale facts
- resolving contradictions

### Versioning

When a fact changes, the previous version is not silently deleted.

Instead, the system keeps the history:

```text
Fact v1
Status: superseded

Fact v2
Status: current
```

This preserves the history of how the knowledge changed.

### Expiration

Facts that are expected to become stale can contain expiration information.

- `created_at`
- `updated_at`
- `expires_at`
- `status`

This prevents old information from being treated as permanently valid.

### Conflict Resolution

When two episodes imply contradictory facts, consolidation explicitly resolves the conflict.

The system compares the available evidence and keeps the selected current fact while preserving the older version.

```text
Episode A
    ↓
Fact: X

Episode B
    ↓
Fact: Y

       ↓
 Consolidation
       ↓
Conflict resolution
       ↓
Current semantic fact: Y
Previous fact: X
Status: superseded
```

The old fact remains available for traceability rather than being silently overwritten.

---

## 7. Context Window Management

The project implements all four required context-window strategies:

- Sliding Window
- Observation / Tool-Output Masking
- Recursive Summarization
- Zone-Based Pruning

All strategies are evaluated against the same long-context workload.

The workload contains multi-turn, tool-heavy conversations where important information can become buried underneath large tool outputs.

The evaluation measures:

- task accuracy
- average input tokens
- average output tokens
- latency

---

## 8. Context Management Evaluation

The following results were produced directly by the context evaluation system (`context_eval/evaluate.py`).

### Results

| Strategy | Accuracy | Accuracy Rate | Avg. Input Tokens | Avg. Output Tokens | Avg. Latency (s) |
|---|---|---|---|---|---|
| Sliding Window (last 10 turns) | 8/10 | 0.80 | 9,978 | 118 | 4.504 |
| Observation Masking (last 3 tool outputs) | 10/10 | 1.00 | 7,930 | 271 | 6.519 |
| Recursive Summarization (last 6 turns) | 10/10 | 1.00 | 303 | 496 | 14.991 |
| Zone-Based Pruning (early=3, recent=5) | 10/10 | 1.00 | 219 | 617 | 14.434 |

---

## 9. Context Strategy Analysis

### Sliding Window

Sliding Window keeps only the most recent turns.

It achieved:

- 8/10 accuracy
- lowest latency: 4.504 seconds
- relatively high input-token usage

Its main weakness is that important information from early turns can disappear when only the latest turns are retained.

**Result:** Fastest strategy, but not reliable enough for the long-context workload.

### Observation / Tool-Output Masking

Observation Masking removes or limits large historical tool outputs while preserving useful conversational information.

It achieved:

- 10/10 accuracy
- 7,930 average input tokens
- 6.519 seconds average latency

This strategy is particularly appropriate for a tool-heavy agent because large tool results are a major source of context growth.

**Result:** Strong balance between accuracy, context reduction, and latency.

### Recursive Summarization

Recursive Summarization achieved:

- 10/10 accuracy
- only 303 average input tokens

However, it required 14.991 seconds on average.

The additional summarization processing introduces substantial latency.

**Result:** Excellent compression, but too expensive in latency for the current workload.

### Zone-Based Pruning

Zone-Based Pruning achieved:

- 10/10 accuracy
- lowest input-token usage: 219 tokens

However, it also had high latency: 14.434 seconds.

It also generated the highest average output-token count.

**Result:** Excellent context compression, but the latency and output cost reduce its practical advantage.

---

## 10. Context Production Decision

Based on the measured results, the system selects:

### **Observation / Tool-Output Masking**

The decision is based on the evaluation rather than theoretical preference.

Observation Masking provides:

- 100% accuracy
- significant input-token reduction
- substantially lower latency than summarization-based approaches
- a natural fit for the tool-heavy Copperleaf workload

The alternatives remain implemented and evaluated, but Observation Masking is the selected production strategy.

---

## 11. Vector Database Architecture

The RAG system uses a real vector database rather than storing vectors in a Python list or dictionary.

The vector store uses:

- Chroma
- ANN similarity search
- document text storage
- metadata payloads
- embeddings
- persistent storage

Document metadata is preserved with the stored chunks.

The vector database therefore supports the basic retrieval pipeline:

```text
Documents
    ↓
Chunking
    ↓
Embedding
    ↓
Vector Database
    ↓
Similarity Search
    ↓
Retrieved Chunks
```

The metadata associated with chunks allows the retrieval layer to retain document-level information such as source and other available metadata.

---

## 12. RAG Pipeline

The retrieval pipeline follows the standard RAG flow:

```text
Documents
    ↓
Document Loader
    ↓
Chunking
    ↓
Embedding
    ↓
Vector Store
    ↓
Retriever
    ↓
LLM
    ↓
Grounded Answer
```

The system implements three required retrieval architectures:

- Naive RAG
- Hybrid Search
- Agentic RAG

---

## 13. Naive RAG

Naive RAG provides the baseline retrieval architecture.

```text
Query
 ↓
Vector Similarity Search
 ↓
Top-k Documents
 ↓
LLM
 ↓
Answer
```

It is simple and provides a baseline against which more advanced retrieval strategies can be compared.

---

## 14. Hybrid Search

Hybrid Search combines:

- vector similarity
- keyword/BM25 retrieval

This is useful when a query contains exact identifiers or terminology that may not be represented distinctly in embedding space.

```text
                    Query
                      │
              ┌───────┴────────┐
              ▼                ▼
       Vector Search       BM25 Search
              │                │
              └───────┬────────┘
                      ▼
                 Combined Rank
                      │
                      ▼
                   LLM
```

This allows the system to benefit from both semantic similarity and exact lexical matching.

---

## 15. Agentic RAG

Agentic RAG introduces a reasoning loop.

Instead of retrieving once and immediately generating an answer, the agent can:

1. Analyze the question
2. Retrieve relevant information
3. Inspect the retrieved evidence
4. Determine whether more retrieval is necessary
5. Retrieve again when needed
6. Generate the final answer

Conceptually:

```text
Question
   ↓
Reason
   ↓
Retrieve
   ↓
Observe
   ↓
Enough evidence?
   ├── No → Retrieve again
   │
   └── Yes
        ↓
      Answer
```

This is particularly useful for multi-part questions that require several pieces of evidence.

---

## 16. Retrieval Architecture Evaluation

All three architectures were evaluated against the same 12-question domain-specific test set.

The evaluation measures:

- answer accuracy
- retrieval accuracy
- average tokens per query
- average latency per query

### Architecture Comparison

| Architecture | Answer Accuracy (12 test questions) | Retrieval Accuracy | Avg. tokens/query | Avg. latency/query |
|---|---|---|---|---|
| Naive RAG | 11/12 | 12/12 | 47 | 8.71s |
| Hybrid Search (Vector + BM25) | 11/12 | 12/12 | 39 | 8.14s |
| Agentic RAG (Multi-hop) | 11/12 | 12/12 | 43 | 15.18s |

---

## 17. Retrieval Results Analysis

All three architectures achieved:

- Retrieval Accuracy = 12/12
- Answer Accuracy = 11/12

Therefore, the retrieval comparison does not show an accuracy advantage for Agentic RAG on this particular fixed test set.

The main measured differences are efficiency and latency.

**Naive RAG**
- 11/12 answer accuracy
- 12/12 retrieval accuracy
- 47 average tokens/query
- 8.71 seconds average latency

Naive RAG provides a strong baseline and is the simplest architecture.

**Hybrid Search**
- 11/12 answer accuracy
- 12/12 retrieval accuracy
- 39 average tokens/query
- 8.14 seconds average latency

Hybrid Search uses both vector similarity and keyword matching and achieved the lowest measured token usage and latency among the three architectures.

**Agentic RAG**
- 11/12 answer accuracy
- 12/12 retrieval accuracy
- 43 average tokens/query
- 15.18 seconds average latency

Agentic RAG provides a multi-hop retrieval mechanism, but the additional reasoning/retrieval loop introduces a significant latency cost in this workload.

---

## 18. Retrieval Production Decision

Based on the measured evaluation, the default retrieval architecture is:

### **Hybrid Search**

The choice is based on the actual measurements:

| Criterion | Result |
|---|---|
| Answer Accuracy | All three: 11/12 |
| Retrieval Accuracy | All three: 12/12 |
| Lowest Token Usage | Hybrid Search |
| Lowest Latency | Hybrid Search |
| Multi-hop capability | Agentic RAG |
| Baseline simplicity | Naive RAG |

Hybrid Search therefore provides the best measured efficiency while maintaining the same accuracy on the fixed evaluation set.

Agentic RAG remains available for queries that require decomposition or multiple retrieval rounds.

---

## 19. Self-RAG-Style Verification

Retrieval alone is not enough.

A retrieved document can be:

- irrelevant
- only partially relevant
- insufficient to support the generated answer

Therefore, the system includes a Self-RAG-style verification layer before an answer reaches the user.

The verification process checks:

- Retrieval relevance
- Answer support

```text
Query
 ↓
Retrieve documents
 ↓
Relevance check
 ↓
Are documents relevant?
 ├── No → Do not answer from them
 │
 └── Yes
      ↓
Generate grounded answer
      ↓
Support check
      ↓
Is answer supported?
 ├── No → Reject / request more evidence
 │
 └── Yes
      ↓
Return answer
```

The same verification principle is applied to information recalled from memory.

This prevents the agent from treating an unsupported retrieved passage or memory as automatically correct.

---

## 20. Agent and MCP Integration

The existing MCP server and database remain the operational source of truth for structured data.

The extended agent connects to the existing MCP server through the MCP client.

```text
Agent
  │
  ├── Memory
  │
  ├── RAG
  │
  └── MCP Client
          │
          ▼
     MCP Server
          │
          ▼
       Existing DB
```

The existing MCP tools continue to provide live structured information such as:

- suppliers
- low-stock items
- recipe allergens
- purchase orders
- inventory counts
- supplier verification

The agent therefore does not duplicate the database or MCP server.

Instead, it decides which source is appropriate:

| Information Type | Source |
|---|---|
| Live operational data | MCP / Database |
| External/internal document knowledge | RAG |
| Previous interaction knowledge | Memory |
| Current reasoning state | Scratchpad |

---

## 21. End-to-End Agent Flow

The integrated agent follows this general flow:

```text
User Query
    │
    ▼
Short-Term Memory
    │
    ▼
Scratchpad / Working State
    │
    ├───────────────┐
    │               │
    ▼               ▼
Memory Recall      RAG Retrieval
    │               │
    │               ▼
    │          Self-RAG Check
    │               │
    └───────┬───────┘
            │
            ▼
      MCP when live
      structured data
      is required
            │
            ▼
       Grounded Answer
            │
            ▼
      Memory Routing
            │
       ┌────┴────┐
       ▼         ▼
     Drop     Episodic
                 │
                 ▼
          Periodic Consolidation
                 │
                 ▼
             Semantic Memory
```

This demonstrates that memory, RAG, and MCP are components of the same agent workflow rather than isolated implementations.

---

## 22. Repository Structure

This repo now hosts **two separate agents** that both extend the same
`mcp_server/` and `db/`: the Memory/RAG agent documented in this file, and
the Decomposition & Planning agent documented in
[`README_PLANNING_AGENT.md`](README_PLANNING_AGENT.md). Neither agent's
code path touches the other's.

```text
project/
│
├── agent/
│   ├── client.py                  # Memory/RAG agent (CopperleafAgent)
│   └── planning_agent/
│       └── main.py                # Planning agent entry point — separate agent, separate path
│
├── mcp_server/                    # shared by both agents
│   ├── server.py
│   ├── database.py
│   ├── validation.py
│   ├── auth.py
│   ├── notifications.py
│   ├── tools_read.py
│   ├── tools_write.py
│   ├── resources.py
│   └── prompts.py
│
├── db/                            # shared by both agents
│   ├── schema.sql
│   ├── seed.sql
│   ├── init_db.py
│   └── erd.mmd
│
├── memory/                        # Memory/RAG agent only
│   ├── short_term_memory.py
│   ├── scratchpad_manager.py
│   ├── episodic_memory.py
│   ├── semantic_memory.py
│   ├── routing.py
│   └── consolidation.py
│
├── context_eval/                  # Memory/RAG agent only
│   ├── evaluate.py
│   └── ...
│
├── rag/                           # Memory/RAG agent only
│   ├── loader.py
│   ├── chunker.py
│   ├── embedder.py
│   ├── vector_store.py
│   ├── Naive_Rag.py
│   ├── hybrid_search.py
│   ├── Agentic_Rag.py
│   ├── Graph_Rag.py
│   └── Self_Rag.py
│
├── retrieval_eval/                # Memory/RAG agent only
│   ├── questions.json
│   ├── evaluate.py
│   └── retrieval_summary.json
│
├── planning/                      # Planning agent only — forked/extended
│   ├── dag.py                     #   from github.com/AmrSheta22/task_decomposition_and_planning
│   ├── decomposition.py
│   ├── dynamic_decomposition.py
│   ├── plan_and_solve.py
│   ├── tree_of_thoughts.py
│   ├── lats.py
│   ├── router.py
│   ├── self_refine.py
│   ├── reflexion.py
│   └── environment.py             # grounded EnvironmentFeedback (real MCP calls, not random)
│
├── planning_eval/                 # Planning agent only
│   ├── test_cases.py
│   ├── run_evaluation.py
│   └── results/                   # JSON traces per run, written by run_evaluation.py
│
├── vector_db/                     # generated, git-ignored
├── .env                           # generated, git-ignored — never commit this
├── .gitignore
├── requirements.txt
├── README.md                      # this file — Memory/RAG agent
└── README_PLANNING_AGENT.md       # Decomposition & Planning agent
```

---

## 23. Evaluation Reproducibility

### Context Evaluation

From the project root:

```bash
python -m context_eval.evaluate
```

The evaluation runs all four context-management strategies against the same fixed test suite.

### Retrieval Evaluation

From the project root:

```bash
python -m retrieval_eval.run_retrieval_evaluation
```

The retrieval evaluation runs:

- Naive RAG
- Hybrid Search
- Agentic RAG

against the same fixed question set.

Results are saved to:

- `retrieval_eval/retrieval_results.csv`
- `retrieval_eval/retrieval_summary.json`
- `retrieval_eval/README.md`

---

## 24. Environment Setup

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```text
OPENROUTER_API_KEY=your_api_key_here
```

API keys and credentials must never be committed to Git.

The `.gitignore` should contain:

```text
.env
.venv/
__pycache__/
vector_db/
*.pyc
```

---


## 25. Design Decisions

The main production decisions are driven by measured results.

### Context Management

**Selected: Observation / Tool-Output Masking**

Reason:

- 100% accuracy
- substantially lower latency than summarization-based strategies
- significant reduction in input context
- appropriate for the tool-heavy workload

### Retrieval

**Selected: Hybrid Search**

Reason:

- 11/12 answer accuracy
- 12/12 retrieval accuracy
- lowest measured token usage
- lowest measured latency
- combines semantic and exact lexical retrieval

Agentic RAG remains useful for queries that genuinely require multi-hop reasoning.

---

## 26. Comparison Summary

### Context Management

| Strategy | Accuracy | Input Tokens | Output Tokens | Latency |
|---|---|---|---|---|
| Sliding Window | 8/10 | 9,978 | 118 | 4.504s |
| Observation Masking | 10/10 | 7,930 | 271 | 6.519s |
| Recursive Summarization | 10/10 | 303 | 496 | 14.991s |
| Zone-Based Pruning | 10/10 | 219 | 617 | 14.434s |

**Selected:** Observation Masking

### Retrieval Architecture

| Architecture | Answer Accuracy | Retrieval Accuracy | Avg. Tokens | Avg. Latency |
|---|---|---|---|---|
| Naive RAG | 11/12 | 12/12 | 47 | 8.71s |
| Hybrid Search | 11/12 | 12/12 | 39 | 8.14s |
| Agentic RAG | 11/12 | 12/12 | 43 | 15.18s |

**Selected:** Hybrid Search

---

## 27. Why These Components Exist

Each component addresses a specific system problem rather than being added only because it is part of the assignment.

| Component | Problem Addressed |
|---|---|
| Short-Term Memory | Preserve recent conversation context |
| Scratchpad | Preserve active reasoning state during pruning |
| Sliding Window | Simple baseline context management |
| Observation Masking | Reduce large historical tool outputs |
| Recursive Summarization | Compress long conversations |
| Zone-Based Pruning | Preserve important context zones |
| Promote-or-Drop Router | Decide what should survive short-term memory |
| Episodic Memory | Preserve concrete historical events |
| Consolidation | Build stable semantic knowledge |
| Versioning | Preserve changed facts |
| Expiration | Prevent stale facts from remaining permanently valid |
| Conflict Resolution | Handle contradictory memories |
| Vector Database | Efficient ANN retrieval |
| Naive RAG | Retrieval baseline |
| Hybrid Search | Handle semantic and exact lexical queries |
| Agentic RAG | Handle multi-step retrieval |
| Self-RAG Verification | Prevent unsupported answers |
| MCP Integration | Access live structured operational data |

---

## 28. Safety and Grounding

The system follows several grounding principles.

**No unsupported RAG answers**

If retrieved documents do not provide sufficient evidence, the agent should not invent an answer.

**No direct router-to-semantic writes**

The promote-or-drop router only decides:

- FORGET
- or EPISODIC

Semantic memory is populated only through consolidation.

**Preserve old facts**

When semantic knowledge changes, previous versions are preserved rather than silently deleted.

**Do not commit secrets**

API keys, database credentials, and embedding credentials must remain outside Git.

---

## 29. Final Outcome

The Copperleaf system has been extended from an MCP-only agent into a system that combines:

```text
                    Copperleaf Agent
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
     Memory               RAG                MCP
        │                  │                  │
        ▼                  ▼                  ▼
 Episodic +          Vector + BM25        Existing DB
 Semantic            Retrieval
        │                  │
        └──────────┬───────┘
                   ▼
            Self-RAG Verification
                   │
                   ▼
             Grounded Answer
```

The final production configuration is:

- Observation Masking for context management
- Hybrid Search as the default RAG architecture
- Agentic RAG available for multi-hop queries
- Episodic + Semantic Memory for long-term knowledge
- Scratchpad for active working state
- Self-RAG-style verification for retrieved knowledge and memory recall
- Existing MCP server and database for live structured operational information

The system is therefore designed around the actual distinction between:

- **What is happening now?** → MCP / database
- **What happened before?** → Memory
- **What do our documents say?** → RAG
- **What is the agent currently trying to do?** → Scratchpad
- **Can the evidence actually support this answer?** → Self-RAG verification
