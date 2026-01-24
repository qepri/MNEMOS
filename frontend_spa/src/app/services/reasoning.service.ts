import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ApiEndpoints } from '@core/constants/api-endpoints';

export interface TraversalResult {
    result: string; // The narrative text due to legacy
    narrative?: string; // The specific narrative field
    graph_data?: any; // The graph data for visualization
    conversation_id?: string; // The ID of the created conversation
}

@Injectable({
    providedIn: 'root'
})
export class ReasoningService {
    private http = inject(HttpClient);

    /**
     * Traverse the hypergraph to find a path between two concepts.
     */
    traverse(startConcept: string, goalConcept: string, collectionIds: string[] = [], saveToChat: boolean = false, useSemanticLeap: boolean = false, maxDepth: number = 3): Observable<TraversalResult> {
        return this.http.post<TraversalResult>(ApiEndpoints.REASONING_TRAVERSE, {
            start: startConcept,
            goal: goalConcept,
            collection_ids: collectionIds,
            save_to_chat: saveToChat,
            use_semantic_leap: useSemanticLeap,
            max_depth: maxDepth
        });
    }

    /**
     * Trigger reprocessing of all documents to build the hypergraph.
     */
    reprocessAll(): Observable<{ status: string, message: string; }> {
        return this.http.post<{ status: string, message: string; }>(ApiEndpoints.REASONING_REPROCESS, {});
    }

    getReprocessStatus(): Observable<{ status: string }> {
        return this.http.get<{ status: string }>(`${ApiEndpoints.REASONING_REPROCESS}/status`);
    }
}
