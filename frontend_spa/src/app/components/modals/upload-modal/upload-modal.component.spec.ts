import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ToastrService } from 'ngx-toastr';
import { describe, it, expect, vi } from 'vitest';

import { UploadModalComponent } from './upload-modal.component';

const toastrStub = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() };

describe('UploadModalComponent (smoke)', () => {
  let fixture: ComponentFixture<UploadModalComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UploadModalComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ToastrService, useValue: toastrStub },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(UploadModalComponent);
    fixture.detectChanges();
  });

  it('renders without throwing', () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('defaults to the file upload tab with no files selected', () => {
    expect(fixture.componentInstance.uploadTab()).toBe('file');
    expect(fixture.componentInstance.selectedFiles()).toEqual([]);
  });

  it('selecting a file adds it to selectedFiles', () => {
    const file = new File(['content'], 'report.pdf', { type: 'application/pdf' });
    const input = document.createElement('input');
    input.type = 'file';
    Object.defineProperty(input, 'files', { value: [file] });

    fixture.componentInstance.onFileSelected({ target: input } as unknown as Event);

    expect(fixture.componentInstance.selectedFiles().map((f) => f.name)).toEqual(['report.pdf']);
  });

  it('switching to the youtube tab updates state', () => {
    fixture.componentInstance.switchUploadTab('youtube');
    expect(fixture.componentInstance.uploadTab()).toBe('youtube');
  });
});
