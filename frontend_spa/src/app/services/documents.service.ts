import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, firstValueFrom, interval } from 'rxjs';
import { ApiEndpoints } from '@core/constants/api-endpoints';
import { Document } from '@core/models';

@Injectable({
    providedIn: 'root'
})
export class DocumentsService {
    private http = inject(HttpClient);
    private pollingIntervals = new Map<string, any>();

    // State
    documents = signal<Document[]>([]);

    selectedCount = computed(() => this.documents().filter((d: Document) => d.selected).length);
    totalCount = computed(() => this.documents().length);

    processingDocuments = computed(() => this.documents().filter((d: Document) => d.status === 'pending' || d.status === 'processing'));

    constructor() {
    }

    getDocuments(collectionId?: string | null): Observable<Document[]> {
        let url = ApiEndpoints.DOCUMENTS;
        if (collectionId !== undefined) {
            url += `?collection_id=${collectionId}`;
        } else if (collectionId === null) {
            url += `?collection_id=null`;
        }
        return this.http.get<Document[]>(url);
    }

    async fetchDocuments(collectionId?: string | null) {
        try {
            const docs = await firstValueFrom(this.getDocuments(collectionId));
            // Map backend fields to UI fields if necessary, or just use them
            this.documents.set(docs.map((d: Document) => ({ ...d, selected: false })));

            // Resume polling for any documents still processing
            docs.forEach((doc: Document) => {
                if (doc.status === 'pending' || doc.status === 'processing') {
                    this.startPolling(doc.id);
                }
            });
        } catch (error) {
            console.error('Failed to fetch documents', error);
        }
    }

    async updateDocument(id: string, updates: Partial<Document>) {
        try {
            const updatedDoc = await firstValueFrom(this.http.put<Document>(`${ApiEndpoints.DOCUMENTS}/${id}`, updates));
            this.documents.update((docs: Document[]) =>
                docs.map((d: Document) => d.id === id ? { ...updatedDoc, selected: d.selected } : d)
            );
            return updatedDoc;
        } catch (error) {
            console.error('Failed to update document', error);
            throw error;
        }
    }

    toggleDocument(id: string) {
        this.documents.update((docs: Document[]) =>
            docs.map((d: Document) => d.id === id ? { ...d, selected: !d.selected } : d)
        );
    }

    clearSelection() {
        this.documents.update((docs: Document[]) => docs.map((d: Document) => ({ ...d, selected: false })));
    }

    async uploadDocument(file: File) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const newDoc: Document = await firstValueFrom(this.http.post<Document>(ApiEndpoints.DOCUMENTS_UPLOAD, formData));
            this.documents.update((docs: Document[]) => [{ ...newDoc, selected: false }, ...docs]);

            // Start polling for status if document is pending/processing
            if (newDoc.status === 'pending' || newDoc.status === 'processing') {
                this.startPolling(newDoc.id);
            }

            return true;
        } catch (error) {
            console.error('Upload failed', error);
            return false;
        }
    }

    async uploadYouTubeUrl(url: string) {
        const formData = new FormData();
        formData.append('youtube_url', url);

        try {
            const newDoc: Document = await firstValueFrom(this.http.post<Document>(ApiEndpoints.DOCUMENTS_UPLOAD, formData));
            this.documents.update((docs: Document[]) => [{ ...newDoc, selected: false }, ...docs]);

            // Start polling for status
            if (newDoc.status === 'pending' || newDoc.status === 'processing') {
                this.startPolling(newDoc.id);
            }

            return true;
        } catch (error) {
            console.error('YouTube upload failed', error);
            return false;
        }
    }

    startPolling(docId: string) {
        // Don't start if already polling
        if (this.pollingIntervals.has(docId)) {
            return;
        }

        // Poll every 2 seconds
        const subscription = interval(2000).subscribe(async () => {
            try {
                const statusUpdate: { status: string, progress?: number, error?: string } = await firstValueFrom(
                    this.http.get<{ status: string, progress?: number, error?: string }>(ApiEndpoints.DOCUMENT_STATUS(docId))
                );

                // Update document in list
                this.documents.update((docs: Document[]) =>
                    docs.map((d: Document) => d.id === docId ? { ...d, status: statusUpdate.status as Document['status'], progress: statusUpdate.progress, error_message: statusUpdate.error } : d)
                );

                // Stop polling if completed or failed
                if (statusUpdate.status === 'completed' || statusUpdate.status === 'failed') {
                    this.stopPolling(docId);
                }
            } catch (error) {
                console.error(`Polling failed for document ${docId}`, error);
                this.stopPolling(docId);
            }
        });

        this.pollingIntervals.set(docId, subscription);
    }

    stopPolling(docId: string) {
        const subscription = this.pollingIntervals.get(docId);
        if (subscription) {
            subscription.unsubscribe();
            this.pollingIntervals.delete(docId);
        }
    }

    async removeDocument(id: string) {
        try {
            // Stop polling if active
            this.stopPolling(id);

            await firstValueFrom(this.http.delete(ApiEndpoints.DOCUMENT_DELETE(id)));
            this.documents.update((docs: Document[]) => docs.filter((d: Document) => d.id !== id));
        } catch (error) {
            console.error('Delete failed', error);
        }
    }

    getSelectedIds(): string[] {
        return this.documents().filter(d => d.selected).map(d => d.id);
    }

    /**
     * LLM-free passage search. Returns ranked chunks, no generated answer —
     * works even when no language model is configured.
     */
    searchChunks(query: string, documentIds?: string[], topK = 10): Observable<SearchResponse> {
        return this.http.post<SearchResponse>(ApiEndpoints.DOCUMENTS_SEARCH, {
            query,
            document_ids: documentIds && documentIds.length ? documentIds : undefined,
            top_k: topK,
        });
    }
}

export interface SearchResult {
    id: string;
    content: string;
    chunk_index: number | null;
    page_number: number | null;
    start_time: number | null;
    end_time: number | null;
    document_id: string;
    document_title: string | null;
}

export interface SearchResponse {
    query: string;
    count: number;
    results: SearchResult[];
}
