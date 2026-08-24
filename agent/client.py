import asyncio

from mcp.client import ClientSession
from mcp.client.stdio import (
    stdio_client,
    StdioServerParameters,
)

from memory.short_term import ShortTermMemory
from memory.scratchpad import Scratchpad
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from memory.router import PromoteOrDropRouter

from rag.hybrid_search import HybridSearch
from rag.self_rag import SelfRAGVerifier


class CopperleafAgent:

    def __init__(
        self,
        session,
        rag,
        verifier,
        short_term,
        scratchpad,
        episodic,
        semantic,
        router,
    ):
        self.session = session

        self.rag = rag
        self.verifier = verifier

        self.short_term = short_term
        self.scratchpad = scratchpad

        self.episodic = episodic
        self.semantic = semantic

        self.router = router

    # =====================================================
    # MEMORY
    # =====================================================

    def recall_memory(self, query):

        episodic = self.episodic.search(query)
        semantic = self.semantic.search(query)

        return {
            "episodic": episodic,
            "semantic": semantic,
        }

    # =====================================================
    # MCP
    # =====================================================

    async def call_mcp_tool(
        self,
        tool_name,
        arguments,
    ):

        result = await self.session.call_tool(
            tool_name,
            arguments,
        )

        texts = []

        for item in result.content:

            if hasattr(item, "text"):
                texts.append(item.text)

        return "\n".join(texts)

    # =====================================================
    # RAG
    # =====================================================

    def retrieve_knowledge(self, query):

        documents = self.rag.retrieve(query)

        return documents

    # =====================================================
    # SELF-RAG VERIFICATION
    # =====================================================

    def verify_retrieval(
        self,
        query,
        documents,
    ):

        if not documents:

            return {
                "relevant": False,
                "supported": False,
                "reason": "No documents retrieved.",
            }

        return self.verifier.verify(
            query=query,
            documents=documents,
        )

    # =====================================================
    # MEMORY ROUTING
    # =====================================================

    def route_memory(self, item):

        decision = self.router.decide(item)

        print("\n[Memory Router]")
        print(f"Decision: {decision['decision']}")
        print(f"Reason: {decision['reason']}")

        return decision

    # =====================================================
    # HANDLE USER QUERY
    # =====================================================

    async def answer(self, query):

        print("\n===================================")
        print("Processing query...")
        print("===================================")

        # -------------------------------------------------
        # 1. Short-term memory
        # -------------------------------------------------

        self.short_term.add_message(
            role="user",
            content=query,
        )

        # -------------------------------------------------
        # 2. Recall long-term memory
        # -------------------------------------------------

        memory = self.recall_memory(query)

        print(
            f"[Memory] Episodic: "
            f"{len(memory['episodic'])}"
        )

        print(
            f"[Memory] Semantic: "
            f"{len(memory['semantic'])}"
        )

        # -------------------------------------------------
        # 3. Update scratchpad
        # -------------------------------------------------

        self.scratchpad.update(
            current_goal=query,
            current_subgoal="Determine required evidence",
            working_state={
                "episodic_hits": len(
                    memory["episodic"]
                ),
                "semantic_hits": len(
                    memory["semantic"]
                ),
            },
        )

        # -------------------------------------------------
        # 4. Retrieve external knowledge
        # -------------------------------------------------

        documents = self.retrieve_knowledge(query)

        print(
            f"[RAG] Retrieved: "
            f"{len(documents)} documents"
        )

        # -------------------------------------------------
        # 5. Self-RAG verification
        # -------------------------------------------------

        verification = self.verify_retrieval(
            query=query,
            documents=documents,
        )

        print(
            f"[Self-RAG] Relevant: "
            f"{verification['relevant']}"
        )

        print(
            f"[Self-RAG] Supported: "
            f"{verification['supported']}"
        )

        # -------------------------------------------------
        # 6. If retrieval failed, do not hallucinate
        # -------------------------------------------------

        if not verification["relevant"]:

            answer = (
                "I could not find sufficiently "
                "relevant information in the "
                "knowledge base."
            )

        elif not verification["supported"]:

            answer = (
                "The retrieved information does "
                "not sufficiently support an answer."
            )

        else:

            context = "\n\n".join(
                doc.page_content
                for doc in documents
            )

            answer = self.generate_answer(
                query=query,
                context=context,
                memory=memory,
            )

        # -------------------------------------------------
        # 7. Add assistant answer to short-term memory
        # -------------------------------------------------

        self.short_term.add_message(
            role="assistant",
            content=answer,
        )

        # -------------------------------------------------
        # 8. Create candidate memory
        # -------------------------------------------------

        memory_item = {
            "query": query,
            "answer": answer,
            "source": "agent_session",
        }

        # -------------------------------------------------
        # 9. Promote-or-drop
        # -------------------------------------------------

        self.route_memory(
            memory_item
        )

        return answer

    # =====================================================
    # GENERATION
    # =====================================================

    def generate_answer(
        self,
        query,
        context,
        memory,
    ):

        # Replace this with your actual LLM.
        #
        # The important requirement is:
        # answer ONLY from verified context.

        return (
            f"Grounded answer for: {query}\n\n"
            f"Evidence:\n{context[:2000]}"
        )


# =========================================================
# BUILD AGENT
# =========================================================

def build_agent(session):

    short_term = ShortTermMemory(
        max_turns=10
    )

    scratchpad = Scratchpad()

    episodic = EpisodicMemory()

    semantic = SemanticMemory()

    router = PromoteOrDropRouter(
        episodic_store=episodic
    )

    rag = HybridSearch(
        # your existing vector store
        # and document collection
    )

    verifier = SelfRAGVerifier()

    return CopperleafAgent(
        session=session,
        rag=rag,
        verifier=verifier,
        short_term=short_term,
        scratchpad=scratchpad,
        episodic=episodic,
        semantic=semantic,
        router=router,
    )


# =========================================================
# MCP CONNECTION
# =========================================================

async def main():

    server = StdioServerParameters(
        command="python",
        args=["-m", "mcp_server.server"],
    )

    async with stdio_client(server) as (
        read_stream,
        write_stream,
    ):

        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:

            print("Initializing MCP...")

            await session.initialize()

            print("Connected to Copperleaf MCP Server!")

            # ---------------------------------------------
            # Build the actual agent
            # ---------------------------------------------

            agent = build_agent(
                session
            )

            # ---------------------------------------------
            # Agent loop
            # ---------------------------------------------

            while True:

                print("\n===================================")
                print("       Copperleaf Agent")
                print("===================================")

                print("1. Ask Agent")
                print("2. List MCP Tools")
                print("3. List MCP Resources")
                print("4. Read MCP Resource")
                print("5. Exit")

                choice = input(
                    "\nChoice: "
                ).strip()

                # =========================================
                # ASK AGENT
                # =========================================

                if choice == "1":

                    query = input(
                        "\nYou: "
                    ).strip()

                    if not query:
                        continue

                    answer = await agent.answer(
                        query
                    )

                    print("\n-----------------------------------")
                    print("Agent:")
                    print("-----------------------------------")
                    print(answer)

                # =========================================
                # LIST TOOLS
                # =========================================

                elif choice == "2":

                    tools = await session.list_tools()

                    print("\nAvailable MCP Tools:\n")

                    for tool in tools.tools:

                        print(
                            f"• {tool.name}"
                        )

                # =========================================
                # LIST RESOURCES
                # =========================================

                elif choice == "3":

                    resources = (
                        await session.list_resources()
                    )

                    print(
                        "\nAvailable MCP Resources:\n"
                    )

                    for resource in resources.resources:

                        print(
                            f"• {resource.name}"
                        )

                        print(
                            f"  URI: {resource.uri}"
                        )

                # =========================================
                # READ RESOURCE
                # =========================================

                elif choice == "4":

                    uri = input(
                        "\nResource URI: "
                    ).strip()

                    result = (
                        await session.read_resource(
                            uri
                        )
                    )

                    print("\nResource:\n")

                    for item in result.contents:

                        print(
                            item.text
                        )

                # =========================================
                # EXIT
                # =========================================

                elif choice == "5":

                    print(
                        "\nGoodbye!"
                    )

                    break

                else:

                    print(
                        "\nInvalid choice."
                    )


if __name__ == "__main__":

    asyncio.run(main())
