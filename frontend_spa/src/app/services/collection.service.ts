import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Collection } from '../core/models/collection.model';
import { ApiEndpoints } from '../core/constants/api-endpoints';

@Injectable({
    providedIn: 'root'
})
export class CollectionService {
    private http = inject(HttpClient);

    getCollections(): Observable<Collection[]> {
        return this.http.get<Collection[]>(ApiEndpoints.COLLECTIONS);
    }

    createCollection(collection: Partial<Collection>): Observable<Collection> {
        return this.http.post<Collection>(ApiEndpoints.COLLECTIONS, collection);
    }

    updateCollection(id: string, collection: Partial<Collection>): Observable<Collection> {
        return this.http.put<Collection>(ApiEndpoints.COLLECTION_DETAIL(id), collection);
    }

    deleteCollection(id: string): Observable<void> {
        return this.http.delete<void>(ApiEndpoints.COLLECTION_DETAIL(id));
    }
}
