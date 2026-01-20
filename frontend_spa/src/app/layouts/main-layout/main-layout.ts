import { Component, signal, effect, inject, OnInit } from '@angular/core';
import { AppRoutes } from '@core/constants/app-routes';
import { RouterOutlet, RouterLink, Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ModalService } from '../../services/modal.service';
import { DocumentsService } from '../../services/documents.service';
import { ConversationsService } from '../../services/conversations.service';
import { ChatService } from '../../services/chat.service';
import { FullscreenModalComponent } from '../../components/loaders/fullscreen-modal/fullscreen-modal.component';
import { SettingsService } from '../../services/settings.service';
import { ToastrService } from 'ngx-toastr';
import { PdfViewerComponent } from '../../components/modals/pdf-viewer/pdf-viewer.component';
import { YoutubeViewer } from '../../components/modals/youtube-viewer/youtube-viewer';
import { VideoPlayerComponent } from '../../components/modals/video-player/video-player.component';
import { Document } from '@core/models';

@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, CommonModule, FormsModule, FullscreenModalComponent, PdfViewerComponent, YoutubeViewer, VideoPlayerComponent],
  templateUrl: './main-layout.html',
  styleUrl: './main-layout.css'
})
export class MainLayout implements OnInit {
  router = inject(Router);
  modalService = inject(ModalService);
  documentsService = inject(DocumentsService);
  conversationsService = inject(ConversationsService);
  chatService = inject(ChatService);
  settingsService = inject(SettingsService);
  public toastr = inject(ToastrService);
  protected readonly AppRoutes = AppRoutes;

  // State Signals
  theme = signal<'dark' | 'light'>('dark');
  isSidebarOpen = signal<boolean>(false);
  activeTab = signal<'chats' | 'documents'>('chats');
  isInitialLoading = signal<boolean>(true);

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

  async ngOnInit() {
    this.toastr.info('Channeling incoming data...');
    this.isInitialLoading.set(true);

    try {
      // Load all initial data
      await Promise.all([
        this.conversationsService.loadConversations(),
        this.documentsService.fetchDocuments(),
        this.settingsService.loadModels(),
        this.settingsService.loadCurrentModel(),
        this.settingsService.loadChatPreferences(),
        this.settingsService.loadConnections()
      ]);
      this.toastr.success('Initial data loaded successfully');
    } catch (error) {
      console.error('Failed to load initial data', error);
      this.toastr.error('Failed to load initial data. Please reload.');
    } finally {
      this.isInitialLoading.set(false);
    }
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

      // Navigate to chat if not already there
      this.router.navigate(['/']);
    } catch (error) {
      console.error('Failed to load conversation', error);
    }
  }

  handleNewChat() {
    this.chatService.clearMessages();
    this.chatService.setConversationId(null);
    this.documentsService.clearSelection();
    this.router.navigate(['/']);
  }

  async handleDeleteConversation(id: string, event: Event) {
    event.stopPropagation();
    if (!confirm('Are you sure you want to delete this conversation?')) return;

    await this.conversationsService.deleteConversation(id);

    if (this.chatService.currentConversationId() === id) {
      this.handleNewChat();
    }
  }

  async handleDeleteDocument(id: string, event: Event) {
    event.stopPropagation();
    if (!confirm('Are you sure you want to delete this document?')) return;

    await this.documentsService.removeDocument(id);
  }

  openPdf(doc: Document, event: Event) {
    event.stopPropagation();
    this.modalService.openPdfViewer(doc);
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
