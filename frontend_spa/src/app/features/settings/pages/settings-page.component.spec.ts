import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { ToastrService } from 'ngx-toastr';
import { describe, it, expect, vi, afterEach } from 'vitest';

import { SettingsPage } from './settings-page.component';

const toastrStub = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() };

describe('SettingsPage (smoke)', () => {
  let fixture: ComponentFixture<SettingsPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SettingsPage],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: ToastrService, useValue: toastrStub },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(SettingsPage);
  });

  afterEach(() => {
    fixture.destroy();
  });

  it('renders without throwing and defaults to the models tab', () => {
    expect(() => fixture.detectChanges()).not.toThrow();
    expect(fixture.componentInstance.activeTab()).toBe('models');
  });

  it('switching tabs updates the active tab signal', () => {
    fixture.detectChanges();
    fixture.componentInstance.activeTab.set('chat');
    expect(fixture.componentInstance.activeTab()).toBe('chat');
  });
});
