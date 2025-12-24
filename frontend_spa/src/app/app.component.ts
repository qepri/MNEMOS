import { Component, signal, effect, inject, OnInit } from '@angular/core';
import { RouterOutlet, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ModalService } from './services/modal.service';
import { DocumentsService } from './services/documents.service';
import { ConversationsService } from './services/conversations.service';
import { ChatService } from './services/chat.service';

@Component({
    selector: 'app-root',
    standalone: true,
    imports: [RouterOutlet, RouterLink, CommonModule, FormsModule],
    templateUrl: './app.component.html',
    styleUrl: './app.component.css'
})
export class AppComponent implements OnInit {
    title = 'MNEMOS';
    modalService = inject(ModalService);
    documentsService = inject(DocumentsService);
    conversationsService = inject(ConversationsService);
    chatService = inject(ChatService);

    // State Signals
    theme = signal<'dark' | 'light'>('dark');
    isSidebarOpen = signal<boolean>(false);
    activeTab = signal<'chats' | 'documents'>('chats');

    // Upload Modal State
    uploadTab = signal<'file' | 'youtube'>('file');
    uploadProgress = signal<number>(0);
    isUploading = signal<boolean>(false);
    selectedFile = signal<File | null>(null);
    youtubeUrl = signal<string>('');

    constructor() {
        // Load saved theme
        const savedTheme = localStorage.getItem('theme') as 'dark' | 'light';
        if (savedTheme) {
            this.theme.set(savedTheme);
        }

        // Apply theme effect
        effect(() => {
            const themeName = this.theme() === 'dark' ? 'mnemos-dark' : 'mnemos-light';
            document.documentElement.setAttribute('data-theme', themeName);
            localStorage.setItem('theme', this.theme());
        });
    }

    ngOnInit() {
        this.conversationsService.loadConversations();
    }

    toggleTheme() {
        this.theme.update(t => t === 'dark' ? 'light' : 'dark');
    }

    toggleSidebar() {
        this.isSidebarOpen.update(v => !v);
    }

    switchTab(tab: 'chats' | 'documents') {
        this.activeTab.set(tab);
    }

    // Conversation Methods
    async handleSelectConversation(id: string) {
        try {
            const detail = await this.conversationsService.loadConversationDetail(id);
            this.chatService.loadMessages(detail.messages);
            this.chatService.setConversationId(id);

            // Update documents selection based on conversation history
            this.documentsService.clearSelection();
            detail.related_document_ids.forEach(docId => {
                this.documentsService.toggleDocument(docId);
            });
        } catch (error) {
            console.error('Failed to load conversation', error);
        }
    }

    handleNewChat() {
        this.chatService.clearMessages();
        this.chatService.setConversationId(null);
        this.documentsService.clearSelection();
    }

    // Upload Modal Methods
    switchUploadTab(tab: 'file' | 'youtube') {
        this.uploadTab.set(tab);
    }

    onFileSelected(event: Event) {
        const input = event.target as HTMLInputElement;
        if (input.files?.length) {
            this.selectedFile.set(input.files[0]);
        }
    }

    onDragOver(event: DragEvent) {
        event.preventDefault();
        event.stopPropagation();
        // Add visual feedback class if needed
    }

    onDrop(event: DragEvent) {
        event.preventDefault();
        event.stopPropagation();
        if (event.dataTransfer?.files.length) {
            this.selectedFile.set(event.dataTransfer.files[0]);
        }
    }

    async startUpload() {
        if (!this.selectedFile() && this.uploadTab() === 'file') return;
        if (!this.youtubeUrl() && this.uploadTab() === 'youtube') return;

        this.isUploading.set(true);
        this.uploadProgress.set(10); // Start progress

        try {
            let success = false;

            if (this.uploadTab() === 'youtube') {
                success = await this.documentsService.uploadYouTubeUrl(this.youtubeUrl());
            } else if (this.selectedFile()) {
                success = await this.documentsService.uploadDocument(this.selectedFile()!);
            }

            if (success) {
                this.uploadProgress.set(100);
                setTimeout(() => {
                    this.isUploading.set(false);
                    this.modalService.closeUpload();
                    this.uploadProgress.set(0);
                    this.selectedFile.set(null);
                    this.youtubeUrl.set(''); // Reset URL
                }, 500);
            } else {
                this.isUploading.set(false);
                this.uploadProgress.set(0);
                // Handle error state
            }
        } catch (error) {
            console.error(error);
            this.isUploading.set(false);
        }
    }
}
