from app.extensions import db
from app.models.knowledge_graph import Concept, HyperEdge, HyperEdgeMember
from app.services.llm_client import get_llm_client
from collections import defaultdict, deque
from sqlalchemy.orm import joinedload
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

class ReasoningEngine:
    
    def __init__(self):
        # Force reload to ensure we pick up latest settings (Provider changes)
        from app.services.llm_client import reset_client, get_llm_client
        reset_client()
        self.llm = get_llm_client()

    def _find_concept(self, name: str):
        """Find concept by exact match or fuzzy vector search."""
        from app.services.embedder import EmbedderService
        
        # 1. Exact Match
        concept = db.session.query(Concept).filter_by(name=name).first()
        if concept:
            return concept
            
        # 2. Fuzzy Match
        try:
            embedder = EmbedderService()
            query_vec = embedder.embed([name])[0]
            
            # Find closest within reasonable distance (e.g. 0.3)
            # 0.3 cosine distance ~ 0.7 similarity
            closest = db.session.query(Concept).order_by(
                Concept.embedding.cosine_distance(query_vec)
            ).limit(1).first()
            
            if closest:
                # Check distance
                dist = db.session.query(
                    Concept.embedding.cosine_distance(query_vec)
                ).filter(Concept.id == closest.id).scalar()
                
                # If distance is too far, maybe don't return? 
                # For "Reasoning", user usually wants the BEST guess.
                # Let's be lenient but log it.
                if dist < 0.4:
                    logger.info(f"Reasoning Fuzzy Match: '{name}' -> '{closest.name}' (dist: {dist:.3f})")
                    return closest
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            
        return None

    def traverse(self, start_concept_name: str, goal_concept_name: str, max_depth=3, k_paths=3, intersection_size=1):
        """
        Traverse the Hypergraph from start_concept to goal_concept using BFS on HyperEdges.
        Returns a narrative explanation of the connections found.
        """
        start_concept_name = start_concept_name.lower().strip()
        goal_concept_name = goal_concept_name.lower().strip()
        
        # 1. Resolve Concepts (Exact -> Fuzzy)
        start_node = self._find_concept(start_concept_name)
        goal_node = self._find_concept(goal_concept_name)
        
        if not start_node:
            return f"Starting concept '{start_concept_name}' not found (and no close matches)."
        if not goal_node:
            return f"Goal concept '{goal_concept_name}' not found (and no close matches)."
            
        logger.info(f"Starting traversal from {start_node.name} to {goal_node.name}")

        # 2. Build Local Inverted Index (Optimization: Load only relevant neighborhood if possible, 
        # but for now we load members for simplicity or we do iterative SQL queries.
        # Iterative SQL is better for scale than loading whole graph in RAM.
        
        # We will do a hybrid: iterative expansion.
        
        # BFS State
        # Queue: (current_hyper_edge_id, path_of_edges)
        queue = deque()
        
        # Initial Set: All HyperEdges containing start_node
        start_edges = [m.hyper_edge for m in start_node.hyper_edge_members]
        for edge in start_edges:
            queue.append((edge, [edge]))
            
        visited_edges = set([e.id for e in start_edges])
        found_paths = []
        
        while queue:
            current_edge, path = queue.popleft()
            
            if len(path) > max_depth:
                continue
                
            # Check if current edge contains goal node
            # We can check DB or check loaded object
            member_ids = [m.concept_id for m in current_edge.members]
            if goal_node.id in member_ids:
                found_paths.append(path)
                if len(found_paths) >= k_paths:
                    break
                continue
            
            # Expand: Find all edges that intersect with current_edge >= intersection_size
            # intersection = concepts in current_edge
            current_concept_ids = [m.concept_id for m in current_edge.members]
            
            # Find candidate next edges: Edges that contain ANY of these concepts
            # (In a stricter version, we enforce >= intersection_size logic in python)
            
            # Query: Find all members where concept_id IN current_concept_ids
            # Then get their hyper_edge_ids
            candidates = db.session.query(HyperEdgeMember)\
                .filter(HyperEdgeMember.concept_id.in_(current_concept_ids))\
                .options(joinedload(HyperEdgeMember.hyper_edge).joinedload(HyperEdge.members))\
                .all()
                
            candidate_edges = {} # edge_id -> HyperEdge Obj
            
            for c_member in candidates:
                e_id = c_member.hyper_edge_id
                if e_id not in visited_edges:
                    candidate_edges[e_id] = c_member.hyper_edge
            
            # Filter by Intersection Size
            for cand_id, cand_edge in candidate_edges.items():
                cand_concept_ids = [m.concept_id for m in cand_edge.members]
                
                # Intersection count
                common = set(current_concept_ids) & set(cand_concept_ids)
                if len(common) >= intersection_size:
                    visited_edges.add(cand_id)
                    new_path = list(path)
                    new_path.append(cand_edge)
                    queue.append((cand_edge, new_path))
        
        # 3. Path Reconstruction & Synthesis
        if not found_paths:
            return f"No connection found between {start_concept_name} and {goal_concept_name} within depth {max_depth}."
            
        return self._synthesize_paths(start_node, goal_node, found_paths)

    def _synthesize_paths(self, start_node, goal_node, paths):
        """
        Turn raw paths into a human-readable explanation using LLM,
        AND return structured graph data for Cytoscape.
        """
        # 1. Build Graph Data (Cytoscape JSON)
        elements = {
            "nodes": [],
            "edges": []
        }
        
        seen_nodes = set()
        seen_edges = set()
        
        for path in paths:
            for hyper_edge in path:
                # Add HyperEdge Node (The Context)
                if hyper_edge.id not in seen_nodes:
                    # Shorten description for label if needed
                    label = (hyper_edge.description[:30] + '..') if len(hyper_edge.description) > 30 else hyper_edge.description
                    elements["nodes"].append({
                        "data": {
                            "id": str(hyper_edge.id),
                            "label": label,
                            "full_desc": hyper_edge.description,
                            "type": "hyperedge",
                            "color": "#888888" # Grey for context
                        }
                    })
                    seen_nodes.add(hyper_edge.id)
                
                # Add Concept Nodes & Links
                for member in hyper_edge.members:
                    concept = member.concept
                    
                    # Add Concept Node
                    if concept.id not in seen_nodes:
                        elements["nodes"].append({
                            "data": {
                                "id": str(concept.id),
                                "label": concept.name,
                                "type": "concept",
                                "color": "#007BFF" # Blue for concepts
                            }
                        })
                        seen_nodes.add(concept.id)
                    
                    # Add Link (Concept <-> HyperEdge)
                    # Unique ID for edge: edgeID_conceptID
                    link_id = f"{hyper_edge.id}_{concept.id}"
                    if link_id not in seen_edges:
                        # Directionality? Hypergraphs are often undirected sets, 
                        # but if we have roles, we can use arrows.
                        # For now, undirected containment is safest to visualize.
                        elements["edges"].append({
                            "data": {
                                "id": link_id,
                                "source": str(concept.id), 
                                "target": str(hyper_edge.id),
                                "label": member.role or ""
                            }
                        })
                        seen_edges.add(link_id)

        # 2. Generate Narrative
        paths_text = ""
        for i, path in enumerate(paths):
            paths_text += f"Path {i+1}:\n"
            for edge in path:
                concepts = [m.concept.name for m in edge.members]
                paths_text += f"  - Context: {edge.description} (Concepts: {', '.join(concepts)})\n"
            paths_text += "\n"
            
        prompt = f"""
        I have found the following logical paths connecting "{start_node.name}" to "{goal_node.name}" in a scientific knowledge graph.
        
        Paths:
        {paths_text}
        
        Synthesize a coherent explanation (hypothesis) of how these concepts are related. 
        Explain the "mechanistic bridge" - how one context leads to another via shared concepts.
        """
        
        response = self.llm.chat(
            system="You are an expert scientific reasoner.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return {
            "narrative": response,
            "graph_data": elements
        }
