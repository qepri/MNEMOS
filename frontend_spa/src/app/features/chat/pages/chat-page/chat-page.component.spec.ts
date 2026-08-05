import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { ToastrService } from 'ngx-toastr';
import { describe, it, expect, vi } from 'vitest';

import { ChatPage } from './chat-page.component';
import { LlmAvailabilityService } from '@services/llm-availability.service';

const toastrStub = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() };

describe('ChatPage (smoke)', () => {
  let fixture: ComponentFixture<ChatPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ChatPage],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        // The dormant state links to Settings, so the page now needs routing.
        provideRouter([]),
        { provide: ToastrService, useValue: toastrStub },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatPage);
  });

  it('renders without throwing', () => {
    expect(() => fixture.detectChanges()).not.toThrow();
  });

  it('shows the dormant state when no LLM is available', () => {
    // Availability starts 'unknown' and the probe never resolves under
    // HttpClientTesting - the same position a slim install with no model
    // server is in. Chat must explain itself rather than offering an input
    // that can only fail on submit.
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('app-llm-dormant')).toBeTruthy();
    expect(fixture.nativeElement.querySelector('app-chat-empty-state')).toBeFalsy();
    expect(fixture.nativeElement.querySelector('app-chat-input')).toBeFalsy();
  });

  it('shows the empty state and input once an LLM is available', () => {
    const availability = TestBed.inject(LlmAvailabilityService);
    availability.availability.set({
      state: 'available',
      provider: 'lm_studio',
      endpoint: 'http://host.docker.internal:11434/v1',
      detail: null,
    });

    fixture.detectChanges();

    expect(fixture.componentInstance.chatService.messages().length).toBe(0);
    expect(fixture.nativeElement.querySelector('app-chat-empty-state')).toBeTruthy();
    expect(fixture.nativeElement.querySelector('app-llm-dormant')).toBeFalsy();
  });
});
