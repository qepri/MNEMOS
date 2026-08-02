import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ToastrService } from 'ngx-toastr';
import { describe, it, expect, vi } from 'vitest';

import { ChatPage } from './chat-page.component';

const toastrStub = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() };

describe('ChatPage (smoke)', () => {
  let fixture: ComponentFixture<ChatPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ChatPage],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ToastrService, useValue: toastrStub },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatPage);
  });

  it('renders without throwing', () => {
    expect(() => fixture.detectChanges()).not.toThrow();
  });

  it('shows the empty state when there are no messages yet', () => {
    fixture.detectChanges();
    expect(fixture.componentInstance.chatService.messages().length).toBe(0);
    expect(fixture.nativeElement.querySelector('app-chat-empty-state')).toBeTruthy();
  });
});
