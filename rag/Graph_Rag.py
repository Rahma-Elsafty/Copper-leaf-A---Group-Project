from neo4j import GraphDatabase

class GraphRAG:
    def __init__(self, uri, auth):
        self.driver = GraphDatabase.driver(uri, auth=auth)

    def retrieve_triplets(self, entity_name):
        query = """
        MATCH (e {name: $name})-[r]->(target)
        RETURN e.name AS source, type(r) AS rel, target.name AS target
        """
        with self.driver.session() as session:
            result = session.run(query, name=entity_name)
            return [f"{record['source']} {record['rel']} {record['target']}" for record in result]

    def generate_with_graph(self, query, entity, llm_client):
        triplets = self.retrieve_triplets(entity)
        context = "\n".join(triplets)
        prompt = f"Using this knowledge graph structure:\n{context}\n\nAnswer: {query}"
        return llm_client.generate(prompt)
