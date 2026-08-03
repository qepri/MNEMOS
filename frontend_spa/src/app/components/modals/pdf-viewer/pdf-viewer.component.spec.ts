import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { PdfViewerComponent } from './pdf-viewer.component';
import { ModalService } from '@services/modal.service';

describe('PdfViewerComponent search highlighting', () => {
  let fixture: ComponentFixture<PdfViewerComponent>;
  let component: PdfViewerComponent;
  let modalService: ModalService;
  let findSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [PdfViewerComponent] });

    fixture = TestBed.createComponent(PdfViewerComponent);
    component = fixture.componentInstance;
    modalService = TestBed.inject(ModalService);

    // Spy on the instance the component actually resolved. A TestBed
    // `providers` override does not take effect here - NgxExtendedPdfViewerService
    // is providedIn:'root' and the component still receives the real one.
    findSpy = vi.spyOn(component.pdfService, 'find').mockImplementation(() => undefined as any);
  });

  it('highlights as soon as the text layer is ready, with no artificial delay', () => {
    modalService.pdfSearchTerm.set('mitochondria');

    component.onTextLayerRendered();

    // Synchronous: nothing to wait out. If someone reintroduces a setTimeout
    // before the search, this assertion fails.
    expect(findSpy).toHaveBeenCalledWith('mitochondria', expect.objectContaining({ highlightAll: false }));
  });

  it('searches only once even though textLayerRendered fires per page', () => {
    modalService.pdfSearchTerm.set('mitochondria');

    component.onTextLayerRendered();
    component.onTextLayerRendered();
    component.onTextLayerRendered();

    expect(findSpy).toHaveBeenCalledTimes(1);
  });

  it('does not search when no term was supplied', () => {
    modalService.pdfSearchTerm.set(null);

    component.onTextLayerRendered();

    expect(findSpy).not.toHaveBeenCalled();
  });

  it('searches a short snippet, not the entire chunk', () => {
    // Callers pass source.text, which for the main RAG path is the whole
    // chunk (~932 chars average in practice). pdf.js will not match a
    // string that long against extracted PDF text, and scanning for it is
    // slow - so the component reduces it to a distinctive opening snippet.
    const wholeChunk =
      'Psilocybin was administered in a single supervised session. ' +
      'Participants were monitored for six hours afterwards. '.repeat(20);

    modalService.pdfSearchTerm.set(wholeChunk);
    component.onTextLayerRendered();

    const [termUsed] = findSpy.mock.calls[0] as [string, unknown];
    expect(termUsed.length).toBeLessThanOrEqual(100);
    expect(wholeChunk).toContain(termUsed);
  });

  it('strips the trailing ellipsis that truncated sources carry', () => {
    // Graph/wiki sources arrive as content[:200] + '...' - the literal dots
    // are not in the PDF, so leaving them guarantees a failed match.
    modalService.pdfSearchTerm.set('Psilocybin was administered in a single session...');
    component.onTextLayerRendered();

    const [termUsed] = findSpy.mock.calls[0] as [string, unknown];
    expect(termUsed.endsWith('...')).toBe(false);
    expect(termUsed).toContain('Psilocybin was administered');
  });

  it('keeps the viewer mounted after close so pdf.js is not rebuilt per open', () => {
    // The regression this guards: closing used to unmount the viewer, so
    // every reopen paid a full pdf.js bootstrap (the spinner).
    modalService.openPdfViewer({ id: 'doc-1' } as any, 'a term', 3);
    fixture.detectChanges();
    expect(component.hasOpened()).toBe(true);
    const srcWhileOpen = component.src();

    modalService.closePdfViewer();
    fixture.detectChanges();

    expect(component.hasOpened()).toBe(true);
    expect(component.src()).toBe(srcWhileOpen);
  });

  it('loads the new file when a different document is opened', () => {
    modalService.openPdfViewer({ id: 'doc-1' } as any, 'a term');
    fixture.detectChanges();
    const firstSrc = component.src();

    modalService.openPdfViewer({ id: 'doc-2' } as any, 'another term');
    fixture.detectChanges();

    expect(component.src()).not.toBe(firstSrc);
    expect(component.src()).toContain('doc-2');
  });

  it('highlights a new term when the SAME document is reopened', () => {
    // The viewer is now kept alive between opens, so reopening the same
    // document renders nothing new and textLayerRendered never fires again.
    // Opening must therefore search immediately, or the second citation
    // opens with the first citation's highlight still showing.
    modalService.pdfSearchTerm.set('first term');
    component.onTextLayerRendered();
    expect(findSpy).toHaveBeenCalledTimes(1);

    modalService.pdfSearchTerm.set('second term');
    component.onOpened();

    expect(findSpy).toHaveBeenCalledTimes(2);
    expect(findSpy).toHaveBeenLastCalledWith('second term', expect.objectContaining({ highlightAll: false }));
  });

  it('does not search on open until the text layer has rendered', () => {
    // First ever open: nothing is rendered yet, so opening must not fire a
    // search that would silently match nothing.
    modalService.pdfSearchTerm.set('a term');

    component.onOpened();

    expect(findSpy).not.toHaveBeenCalled();
  });
});
