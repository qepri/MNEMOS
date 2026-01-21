import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ApiEndpoints } from '@core/constants/api-endpoints';

export interface TraversalResult {
    result: string; // The narrative text
    // Future: graph_data for visualization
}

@Injectable({
    providedIn: 'root'
})
export class ReasoningService {
    private http = inject(HttpClient);

    /**
     * Traverse the hypergraph to find a path between two concepts.
     */
    traverse(startConcept: string, goalConcept: string): Observable<TraversalResult> {
        return this.http.post<TraversalResult>(ApiEndpoints.REASONING_TRAVERSE, {
            start: startConcept,
            goal: goalConcept
        });
    }

    /**
     * Trigger reprocessing of all documents to build the hypergraph.
     */
    reprocessAll(): Observable<{ status: string, message: string }> {
        return this.http.post<{ status: string, message: string }>(ApiEndpoints.REASONING_REPROCESS, {});
    }
}
