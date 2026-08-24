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

  # Copperleaf Kitchen — Stateful Agent Platform

## Final Project

Copperleaf Kitchen is a stateful multi-agent restaurant operations platform built around durable state graphs, MCP tools, human-in-the-loop control, failure recovery, checkpointing, RAG, and an administrative web platform.

The system is designed for operational tasks that cannot be represented as a single request/response interaction. Instead, each workflow maintains persistent state, can pause for human decisions or external events, can fail and recover, and can continue from its latest durable checkpoint.

---

## 1. Project Overview

The final system combines the existing Copperleaf Kitchen agent infrastructure with a new stateful workflow layer and an administrative/user platform.

The system contains three main stateful workflows:

1. **Supplier Onboarding**
2. **Food Safety Incident Management**
3. **Purchase Order Fulfillment**

Each workflow is implemented as an explicit state graph.

The graphs support:

* branching
* waiting
* human approval
* external events
* failures
* durable checkpoints
* recovery
* LLM-based reasoning techniques
* MCP/database operations

The project also provides a web platform for interacting with agents and administering:

* agents
* MCP tools
* RAG documents
* HITL tasks
* failure tickets
* state-graph runs

---

# 2. Architecture

```text
                         ┌─────────────────────────┐
                         │       Web Platform       │
                         │                         │
                         │  User UI    Admin UI     │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │      Platform API       │
                         │                         │
                         │ runs / HITL / tickets   │
                         │ agents / tools / RAG     │
                         └────────────┬────────────┘
                                      │
                ┌─────────────────────┼─────────────────────┐
                │                     │                     │
                ▼                     ▼                     ▼
        ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
        │   Supplier    │     │ Food Safety   │     │ Purchase      │
        │   Onboarding  │     │ Incident      │     │ Order         │
        │   Graph       │     │ Graph         │     │ Graph         │
        └───────┬───────┘     └───────┬───────┘     └───────┬───────┘
                │                     │                     │
                └─────────────────────┼─────────────────────┘
                                      ▼
                         ┌─────────────────────────┐
                         │   State Graph Engine    │
                         │                         │
                         │ checkpoints             │
                         │ waits                   │
                         │ HITL pauses             │
                         │ failures                │
                         │ recovery                │
                         └────────────┬────────────┘
                                      │
                         ┌────────────┴────────────┐
                         ▼                         ▼
                ┌─────────────────┐       ┌─────────────────┐
                │   MCP Server    │       │ Durable Store   │
                │                 │       │                 │
                │ database tools  │       │ SQLite          │
                │ tool permissions│       │ checkpoints     │
                └────────┬────────┘       │ HITL tasks      │
                         │                │ failure tickets │
                         ▼                └─────────────────┘
                ┌─────────────────┐
                │ Copperleaf DB   │
                │                 │
                │ suppliers       │
                │ inventory       │
                │ purchases       │
                │ incidents       │
                │ policies        │
                └─────────────────┘
```

---

# 3. Why These Problems Are Stateful

## 3.1 Supplier Onboarding

Supplier onboarding cannot be completed in one interaction because the workflow depends on multiple sequential conditions.

Typical flow:

```text
START
  │
  ▼
Collect supplier information
  │
  ▼
Compliance / policy check
  │
  ▼
Manager approval
  │
  ├──────── Reject ───────► FAILED
  │
  ▼
Wait for signed agreement
  │
  ├──────── Timeout/failure ─────► FAILURE TICKET
  │
  ▼
Verify supplier
  │
  ▼
DONE
```

The graph needs persistent state because the manager decision and signed agreement may occur much later than the initial request.

### Techniques

* RAG
* constrained ReAct

RAG provides grounded access to relevant restaurant policies and supplier information.

Constrained ReAct allows the agent to reason about the next operational action while restricting execution to permitted tools/actions.

---

# 4. Food Safety Incident Management

Food-safety incidents require investigation, evidence gathering, policy consultation, and human confirmation.

Example flow:

```text
START
  │
  ▼
Record incident
  │
  ▼
Retrieve relevant safety policies
  │
  ▼
Investigate possible causes
  │
  ▼
Determine corrective action
  │
  ▼
Human safety review
  │
  ├──────── Reject ───────► INVESTIGATE AGAIN
  │
  ▼
Close incident
  │
  ▼
DONE
```

The workflow is stateful because investigation and approval can occur at different times and because a rejected decision can send the workflow back to an earlier state.

### Techniques

* RAG
* Tree of Thoughts

RAG grounds decisions in the restaurant's stored safety policies.

Tree of Thoughts evaluates multiple possible investigation/corrective-action paths before selecting the preferred path.

---

# 5. Purchase Order Fulfillment

Purchase-order fulfillment involves checking inventory, suppliers, budgets, approvals, and execution.

Example flow:

```text
START
  │
  ▼
Determine required purchase
  │
  ▼
Decompose purchasing task
  │
  ▼
Check suppliers / inventory
  │
  ▼
Select supplier
  │
  ▼
Create purchase order
  │
  ▼
Approval required?
  │
  ├── YES ──► HITL APPROVAL
  │              │
  │              ├── REJECT ──► REVISE
  │              │
  │              └── APPROVE
  │
  ▼
Fulfill order
  │
  ▼
DONE
```

### Techniques

* Task decomposition
* constrained ReAct

Task decomposition converts the purchasing objective into smaller operational steps.

Constrained ReAct performs the required database/MCP actions while respecting the available tool constraints.

---

# 6. Durable Checkpointing

The state graph engine persists workflow state after important transitions.

A checkpoint contains the information required to reconstruct the current workflow state.

Conceptually:

```text
Graph State
    │
    ▼
Execute node
    │
    ├── success ──► persist checkpoint
    │
    ├── wait ─────► persist checkpoint + WAIT
    │
    ├── HITL ─────► persist checkpoint + HITL task
    │
    └── failure ──► persist checkpoint + failure ticket
```

The important property is that workflow progress does not exist only in process memory.

If the process terminates, the persisted checkpoint remains available.

---

# 7. Crash Recovery

The project includes a crash-recovery demonstration.

The recovery sequence is:

```text
Process A
   │
   ▼
Run workflow
   │
   ▼
Persist checkpoint
   │
   ▼
Process killed
   X

Process B
   │
   ▼
Load same run ID
   │
   ▼
Load persisted checkpoint
   │
   ▼
Resume workflow
   │
   ▼
Continue normally
```

This demonstrates that the workflow is durable across process restarts.

Run the demonstration with:

```bash
python -m state_graph.demo_crash_recovery
```

---

# 8. Human-in-the-Loop

Some decisions should not be performed automatically.

When a graph reaches a HITL node:

```text
Graph
  │
  ▼
HITL condition
  │
  ▼
Persist current state
  │
  ▼
Create HITL task
  │
  ▼
Admin reviews task
  │
  ├── APPROVE
  │
  └── REJECT
        │
        ▼
Resume graph
```

The graph therefore does not lose its state while waiting for the administrator.

---

# 9. Failure Tickets

Operational failures are represented as persistent failure tickets.

The intended lifecycle is:

```text
OPEN
  │
  ▼
INVESTIGATING
  │
  ▼
RESOLVED
  │
  ▼
RETRY / RESUME
```

A failure ticket is associated with the workflow state/checkpoint that produced it.

Resolving the ticket can therefore resume the workflow from the persisted state rather than restarting the entire workflow.

---

# 10. MCP Integration

Copperleaf operations are exposed through MCP tools.

Examples include operations for:

* suppliers
* inventory
* recipes
* purchase orders
* supplier verification
* inventory counts

The state graphs use these tools for real operational actions rather than directly bypassing the existing application layer.

---

# 11. Runtime MCP Tool Permissions

Tool permissions are controlled from the administrative platform.

The important behavior is runtime enforcement.

When a tool is enabled:

```text
Admin
  │
  ▼
Enable tool
  │
  ▼
Permission store
  │
  ▼
MCP runtime
  │
  ▼
Tool appears and can be called
```

When a tool is disabled:

```text
Admin
  │
  ▼
Disable tool
  │
  ▼
Permission store
  │
  ▼
MCP runtime
  │
  ├── tool no longer exposed
  │
  └── direct call is rejected
```

The permission check must therefore occur at the actual MCP boundary, not only in the UI.

---

# 12. RAG Administration

The platform provides an administrative RAG document interface.

Administrators can add/remove documents used by the agents.

The intended behavior is:

```text
Admin adds document
       │
       ▼
RAG storage/index
       │
       ▼
Agent retrieval
       │
       ▼
Response grounded in document
```

Removing a document removes it from the available retrieval knowledge.

This allows the administrator to modify the agent's knowledge without changing the workflow implementation.

---

# 13. Platform

The web platform provides two main surfaces.

## User Surface

Users can:

* interact with agents
* switch between agents
* start/use stateful workflows
* observe workflow state
* receive workflow results

## Admin Surface

Administrators can manage:

* HITL tasks
* failure tickets
* agents
* MCP tools
* RAG documents
* state-graph runs

---

# 14. Project Structure

```text
Copper-leaf-A---Group-Project/
│
├── mcp_server/
│   ├── server.py
│   ├── database.py
│   ├── validation.py
│   └── ...
│
├── state_graph/
│   ├── engine.py
│   ├── store.py
│   ├── techniques.py
│   ├── demo_crash_recovery.py
│   │
│   └── graphs/
│       ├── supplier_onboarding.py
│       ├── food_safety_incident.py
│       └── purchase_order_fulfillment.py
│
├── platform/
│   ├── backend.py
│   ├── requirements.txt
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── ...
│
├── tests_state_graph/
│   ├── test_supplier_onboarding_graph.py
│   ├── test_food_safety_graph.py
│   ├── test_purchase_order_graph.py
│   └── ...
│
├── requirements.txt
├── PLATFORM_AND_STATE_GRAPH.md
├── DEMO_EVIDENCE.md
└── README.md
```

---

# 15. Installation

## Windows

```powershell
git clone <repository-url>
cd Copper-leaf-A---Group-Project

python -m venv .venv
.venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r platform\requirements.txt
```

## Linux / macOS

```bash
git clone <repository-url>
cd Copper-leaf-A---Group-Project

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r platform/requirements.txt
```

---

# 16. Environment Variables

Create a `.env` file when an LLM provider is required.

Do not commit the `.env` file.

Example:

```env
COPPERLEAF_LLM_MODEL=your-model
COPPERLEAF_LLM_BASE_URL=your-compatible-base-url
OPENROUTER_API_KEY=your-key
```

Use the variables expected by the specific agent/LLM configuration in the repository.

Never commit API keys, passwords, or credentials.

---

# 17. Run the Final Platform

From the project root:

```bash
python platform/backend.py
```

Then open:

```text
http://localhost:5000
```

The Flask backend serves the platform frontend.

---

# 18. Run the State Graph Tests

```bash
pytest tests_state_graph -v
```

All three graph test suites should be executed before the final demonstration.

---

# 19. Crash Recovery Test

Run:

```bash
python -m state_graph.demo_crash_recovery
```

The demonstration intentionally terminates one process and starts another process using the same persisted workflow state.

The expected result is that the second process resumes from the saved checkpoint.

---

# 20. Recommended Final Demonstration

## Demo 1 — HITL

1. Start a stateful workflow.
2. Let it reach a HITL node.
3. Open the admin platform.
4. Show the pending HITL task.
5. Approve/reject the task.
6. Show that the same workflow resumes.
7. Show the resulting state.

## Demo 2 — Failure Recovery

1. Start a workflow.
2. Trigger a controlled failure.
3. Show the generated failure ticket.
4. Show its persisted workflow/checkpoint.
5. Move the ticket through investigation.
6. Resolve it.
7. Retry/resume the workflow.
8. Show that execution continues from the checkpoint.

## Demo 3 — Crash Recovery

1. Start the crash-recovery demonstration.
2. Show the workflow checkpoint.
3. Kill the running process.
4. Start the recovery process.
5. Show the same run ID being restored.
6. Show that the workflow continues from the checkpoint.

---

# 21. Runtime MCP Permission Demonstration

For the final presentation:

1. Open the admin tool-management page.
2. Enable an MCP tool.
3. Show that the tool is available to the agent/MCP runtime.
4. Disable the same tool.
5. Show that it disappears from the available tool set or is rejected at call time.
6. Re-enable the tool.
7. Show that it becomes available again.

This verifies that the administrative setting affects the actual runtime rather than only changing the UI.

---

# 22. Testing Checklist

Before submission:

* [ ] All Python dependencies install successfully.
* [ ] Platform starts successfully.
* [ ] Frontend loads.
* [ ] Agent switching works.
* [ ] State-graph runs can be created.
* [ ] Supplier onboarding works.
* [ ] Food safety workflow works.
* [ ] Purchase-order workflow works.
* [ ] HITL task is persisted.
* [ ] HITL approval resumes the graph.
* [ ] Failure creates a persistent ticket.
* [ ] Ticket can be investigated/resolved.
* [ ] Resolved failure resumes from checkpoint.
* [ ] Crash recovery works after process termination.
* [ ] MCP tools execute correctly.
* [ ] Disabled MCP tools cannot be called.
* [ ] RAG document addition affects retrieval.
* [ ] RAG document removal affects retrieval.
* [ ] `.env` and credentials are not committed.
* [ ] README matches the implementation.
* [ ] Demo evidence is recorded.

---

# 23. Final Project Validation

The final system should be evaluated as one integrated platform rather than as isolated scripts.

The key validation questions are:

### Stateful workflows

Can each workflow pause, persist, resume, branch, and recover?

### Checkpointing

Does the workflow survive process termination?

### HITL

Can a human decision pause and later resume a workflow?

### Failure recovery

Can an operational failure become a ticket and resume from persisted state?

### MCP

Do the workflows use the actual MCP operational tools?

### Runtime permissions

Does disabling a tool actually prevent the runtime from using it?

### RAG

Do administrative document changes affect agent retrieval?

### Platform

Can a user operate agents and can an administrator control the system?

---

# 24. Final Submission Checklist

Before submitting the repository:

```text
[ ] README updated
[ ] Three state graphs implemented
[ ] Two LLM techniques per graph
[ ] Durable checkpointing verified
[ ] HITL verified
[ ] Failure ticket recovery verified
[ ] Crash recovery verified
[ ] MCP runtime permissions verified
[ ] RAG administration verified
[ ] User agent switching verified
[ ] Admin platform verified
[ ] Automated tests pass
[ ] Demo evidence recorded
[ ] GitHub issues created
[ ] Issues linked to implementation PRs
[ ] No secrets committed
```

---

## Conclusion

Copperleaf Kitchen demonstrates a stateful multi-agent architecture in which operational workflows are represented as durable state graphs rather than one-shot LLM calls.

The combination of MCP tools, RAG, multiple reasoning/decomposition techniques, human approval, persistent failure tickets, durable checkpoints, crash recovery, and administrative controls provides the foundation for reliable restaurant operations automation.

