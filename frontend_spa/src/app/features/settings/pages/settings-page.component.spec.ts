import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter, Router } from '@angular/router';
import { ToastrService } from 'ngx-toastr';
import { BehaviorSubject } from 'rxjs';
import { describe, it, expect, vi, afterEach } from 'vitest';

import { SettingsPage } from './settings-page.component';

const toastrStub = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() };

/** Minimal ActivatedRoute stub whose queryParamMap can be pushed to mid-test -
 * exercising the same "navigation within /settings" path the real Router
 * would (T035 fixed a bug where a snapshot-only read missed exactly this). */
function activatedRouteStub(initialParams: Record<string, string> = {}) {
  const subject = new BehaviorSubject(convertToParamMap(initialParams));
  return {
    subject,
    provider: {
      provide: ActivatedRoute,
      useValue: { snapshot: { queryParamMap: subject.value }, queryParamMap: subject },
    },
  };
}

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

describe('SettingsPage query-param routing (FR-010/FR-015)', () => {
  let fixture: ComponentFixture<SettingsPage>;
  let route: ReturnType<typeof activatedRouteStub>;

  async function build(initialParams: Record<string, string> = {}) {
    route = activatedRouteStub(initialParams);
    await TestBed.configureTestingModule({
      imports: [SettingsPage],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: ToastrService, useValue: toastrStub },
        route.provider,
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(SettingsPage);
  }

  afterEach(() => {
    fixture.destroy();
  });

  it('?tab=chat opens on Chat Settings instead of the default Installed Models tab', async () => {
    await build({ tab: 'chat' });
    fixture.detectChanges();
    expect(fixture.componentInstance.activeTab()).toBe('chat');
  });

  it('?create=custom-connection sets openCreateConnection', async () => {
    await build({ tab: 'chat', create: 'custom-connection' });
    fixture.detectChanges();
    expect(fixture.componentInstance.openCreateConnection()).toBe(true);
  });

  it('ignores an unknown tab value rather than throwing', async () => {
    await build({ tab: 'not-a-real-tab' });
    expect(() => fixture.detectChanges()).not.toThrow();
    expect(fixture.componentInstance.activeTab()).toBe('models');
  });

  it('reacts to a query-param change after the component already exists', async () => {
    // The bug T035 fixed: Angular reuses this component instance for
    // same-route navigations (e.g. a button inside Settings linking
    // chat -> discover), so reading queryParamMap once in ngOnInit would
    // miss this entirely. Asserts the live subscription actually re-fires.
    await build({ tab: 'chat' });
    fixture.detectChanges();
    expect(fixture.componentInstance.activeTab()).toBe('chat');

    route.subject.next(convertToParamMap({ tab: 'discover' }));
    fixture.detectChanges();

    expect(fixture.componentInstance.activeTab()).toBe('discover');
  });

  it('switchTab pushes the tab into the URL via merge, not a full replace', async () => {
    await build({});
    fixture.detectChanges();
    const router = TestBed.inject(Router);
    const navigateSpy = vi.spyOn(router, 'navigate');

    fixture.componentInstance.switchTab('voice');

    expect(navigateSpy).toHaveBeenCalledWith([], expect.objectContaining({
      queryParams: { tab: 'voice' },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    }));
  });
});
