import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { Router, provideRouter } from '@angular/router';
import { ToastrService } from 'ngx-toastr';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';

import { LlmSelectorComponent } from './llm-selector.component';

const toastrStub = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() };

describe('LlmSelectorComponent installLocalModel (FR-015)', () => {
  let fixture: ComponentFixture<LlmSelectorComponent>;
  let httpMock: HttpTestingController;
  let confirmSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LlmSelectorComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: ToastrService, useValue: toastrStub },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(LlmSelectorComponent);
    fixture.detectChanges();

    // The constructor kicks off loadConnections()/loadLlamacppModels(); flush
    // whatever landed so it doesn't leak into the next test as a pending request.
    httpMock = TestBed.inject(HttpTestingController);
    httpMock.match(() => true).forEach(req => req.flush([]));
  });

  afterEach(() => {
    confirmSpy?.mockRestore();
    fixture.destroy();
  });

  it('navigates to Discover Models when the user confirms', () => {
    confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const router = TestBed.inject(Router);
    const navigateSpy = vi.spyOn(router, 'navigate').mockResolvedValue(true);

    fixture.componentInstance.installLocalModel();

    expect(confirmSpy).toHaveBeenCalledOnce();
    expect(navigateSpy).toHaveBeenCalledWith(['/settings'], { queryParams: { tab: 'discover' } });
  });

  it('does not navigate when the user cancels the confirmation', () => {
    confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const router = TestBed.inject(Router);
    const navigateSpy = vi.spyOn(router, 'navigate');

    fixture.componentInstance.installLocalModel();

    expect(confirmSpy).toHaveBeenCalledOnce();
    expect(navigateSpy).not.toHaveBeenCalled();
  });
});
